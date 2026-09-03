/* ==========================================================================
   main.js — assemblage de l'application
   ========================================================================== */
(function (global) {
  'use strict';

  var FS = global.PyFS;
  var S = global.PySettings;
  var RT = global.PyRuntime;

  var $ = function (id) { return document.getElementById(id); };
  var app = $('app');

  var editor = null;
  var term = null;
  var state = {
    tabs: [],
    active: null,
    running: false,
    stdinMode: null,        // 'live' | 'prefill'
    stdinResolve: null,
    saveTimer: null,
    dirty: {}
  };

  /* ------------------------------------------------------------ helpers */

  function toast(msg, ms) {
    var el = $('toast');
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { el.hidden = true; }, ms || 2200);
  }

  function status(msg) {
    $('st-msg').textContent = msg || '';
  }

  function isPython(path) { return /\.py$/i.test(path || ''); }

  function download(name, text, mime) {
    var blob = new Blob([text], { type: mime || 'text/plain;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = name.split('/').pop();
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1500);
  }

  function fmtDuration(ms) {
    if (ms < 1000) return ms + ' ms';
    return (ms / 1000).toFixed(2) + ' s';
  }

  /* -------------------------------------------------------------- theme */

  function applyTheme(name) {
    document.documentElement.setAttribute('data-theme', name);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', name === 'light' ? '#ffffff' : '#1b1f27');
    S.set('theme', name);
    if (editor) editor.refresh();
  }

  /* ------------------------------------------------------ onglets / fichiers */

  function renderFiles() {
    var ul = $('file-list');
    ul.textContent = '';
    var files = FS.list();
    files.forEach(function (path) {
      var li = document.createElement('li');
      li.dataset.path = path;
      if (path === state.active) li.className = 'is-active';

      var icon = document.createElement('span');
      icon.className = 'ficon';
      icon.textContent = isPython(path) ? 'PY' : (path.split('.').pop() || '?').slice(0, 3).toUpperCase();

      var name = document.createElement('span');
      name.className = 'fname';
      name.textContent = path;

      var rm = document.createElement('button');
      rm.className = 'icon-btn sm frm';
      rm.title = 'Supprimer';
      rm.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>';
      rm.addEventListener('click', function (e) {
        e.stopPropagation();
        if (!global.confirm('Supprimer ' + path + ' ?')) return;
        FS.remove(path);
        closeTab(path);
        renderFiles();
      });

      li.appendChild(icon);
      li.appendChild(name);
      li.appendChild(rm);
      li.addEventListener('click', function () { openFile(path); });
      ul.appendChild(li);
    });
    $('st-files').textContent = files.length + ' fichier' + (files.length > 1 ? 's' : '');
  }

  function renderTabs() {
    var bar = $('tabs');
    bar.textContent = '';
    state.tabs.forEach(function (path) {
      var t = document.createElement('div');
      t.className = 'tab' + (path === state.active ? ' is-active' : '');
      t.setAttribute('role', 'tab');

      var label = document.createElement('span');
      label.textContent = path.split('/').pop();
      t.appendChild(label);

      if (state.dirty[path]) {
        var dot = document.createElement('span');
        dot.className = 'tdirty';
        t.appendChild(dot);
      }

      var x = document.createElement('span');
      x.className = 'tclose';
      x.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>';
      x.addEventListener('click', function (e) { e.stopPropagation(); closeTab(path); });
      t.appendChild(x);

      t.addEventListener('click', function () { openFile(path); });
      bar.appendChild(t);
    });

    $('crumb-name').textContent = state.active || '—';
    $('crumb-dirty').hidden = !state.dirty[state.active];
  }

  function openFile(path) {
    if (!FS.exists(path)) return;
    if (state.tabs.indexOf(path) < 0) state.tabs.push(path);
    state.active = path;
    editor.open(path, FS.read(path));
    S.set('activeFile', path);
    S.set('openTabs', state.tabs);
    renderTabs();
    renderFiles();
    if (global.innerWidth <= 780) app.setAttribute('data-sidebar', 'closed');
    editor.focus();
  }

  function closeTab(path) {
    var i = state.tabs.indexOf(path);
    if (i >= 0) state.tabs.splice(i, 1);
    editor.close(path);
    delete state.dirty[path];
    if (state.active === path) {
      var next = state.tabs[Math.max(0, i - 1)] || FS.list()[0] || null;
      state.active = null;
      if (next) openFile(next); else { editor.setValue(''); renderTabs(); }
    } else {
      renderTabs();
    }
    S.set('openTabs', state.tabs);
  }

  function newFile() {
    var name = global.prompt('Nom du nouveau fichier', FS.uniqueName('sans-titre.py'));
    if (!name) return;
    var path = FS.normalize(name);
    if (!path) return;
    if (FS.exists(path)) { openFile(path); return; }
    FS.write(path, isPython(path) ? '' : '');
    renderFiles();
    openFile(path);
  }

  function saveActive(silent) {
    if (!state.active) return;
    FS.write(state.active, editor.value());
    delete state.dirty[state.active];
    renderTabs();
    if (!silent) status('enregistre — ' + state.active);
  }

  function scheduleSave() {
    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(function () { saveActive(true); }, 700);
  }

  /* ------------------------------------------------------------ execution */

  function collectFiles() {
    var out = {};
    FS.list().forEach(function (p) { out[p] = FS.read(p); });
    if (state.active) out[state.active] = editor.value();
    return out;
  }

  var INPUT_RE = /(?:^|[^\w.])input\s*\(/;

  function needsPrefill(code) {
    return INPUT_RE.test(code) && !(RT.info && RT.info.blockingStdin);
  }

  function askPrefill(code) {
    if (!needsPrefill(code)) return Promise.resolve([]);
    return openStdinModal(
      'prefill',
      'Ce programme lit des entrees avec input().\n' +
      'Ce navigateur ne permet pas la saisie pendant l\'execution :\n' +
      'indiquez les reponses a l\'avance, une par ligne.'
    ).then(function (text) {
      if (text === null) return null;
      return text.split('\n');
    });
  }

  function setRunning(on) {
    state.running = on;
    $('btn-run').disabled = on || !RT.ready;
    $('btn-stop').disabled = !on;
    var badge = $('runtime-badge');
    if (on) { badge.textContent = 'execution…'; badge.className = 'badge busy'; }
    else if (RT.ready) { badge.textContent = RT.backend.label; badge.className = 'badge ok'; }
  }

  function reportResult(res, ms, label) {
    term.flush();
    if (!res) return;
    if (res.value != null) term.line(res.value, 'repr');
    if (res.ok) {
      status(label + ' — termine en ' + fmtDuration(ms));
      setProblems([]);
    } else {
      status(label + ' — ' + (res.type || 'erreur'));
      if (res.line) {
        editor.markError(res.line);
        setProblems([{ file: state.active, line: res.line, type: res.type, msg: res.msg }]);
      } else {
        setProblems([{ file: state.active, line: 0, type: res.type, msg: res.msg }]);
      }
    }
  }

  function runCurrentFile() {
    if (!RT.ready || state.running || !state.active) return;
    saveActive(true);
    var path = state.active;
    var code = editor.value();

    askPrefill(code).then(function (stdin) {
      if (stdin === null) return;
      var prep = RT.backend.name === 'native'
        ? RT.syncFiles(collectFiles())
        : Promise.resolve(true);

      prep.then(function () {
        setRunning(true);
        editor.clearErrors();
        term.banner('▶ ' + path + '  ·  ' + new Date().toLocaleTimeString());
        openPanel(true);
        var started = Date.now();
        RT.run(code, { echo: false, filename: path, stdin: stdin }).then(function (out) {
          setRunning(false);
          reportResult(out && out.result, (out && out.ms) || (Date.now() - started), path);
        });
      });
    });
  }

  function runSelection() {
    if (!RT.ready || state.running) return;
    var code = editor.cm.somethingSelected() ? editor.cm.getSelection() : editor.cm.getLine(editor.cm.getCursor().line);
    if (!code.trim()) return;
    submitToRepl(code, true);
  }

  function stopRun() {
    if (!state.running) return;
    RT.interrupt().then(function (soft) {
      if (!soft) {
        term.line('■ moteur redemarre (interruption impossible sans isolation du site)', 'warn');
        setRunning(false);
      }
    });
  }

  /* -------------------------------------------------------------- REPL */

  var COMMANDS_HELP = [
    '!help                 cette aide',
    '!ls                   liste des fichiers',
    '!open <fichier>       ouvre un fichier dans l\'editeur',
    '!run [fichier]        execute le fichier (par defaut : le fichier actif)',
    '!cat <fichier>        affiche un fichier',
    '!new <fichier>        cree un fichier',
    '!rm <fichier>         supprime un fichier',
    '!pip install <paquet> installe un paquet',
    '!reset                vide l\'espace de noms Python',
    '!clear                efface la console',
    '!backend [nom]        moteur courant (pyodide | native)'
  ].join('\n');

  function handleMagic(line) {
    var m = line.replace(/^[!%]/, '').trim();
    var parts = m.split(/\s+/);
    var cmd = parts[0];
    var arg = parts.slice(1).join(' ').trim();

    switch (cmd) {
      case 'help':
        term.line(COMMANDS_HELP, 'info');
        return true;
      case 'clear':
        term.clear();
        return true;
      case 'ls':
        term.line(FS.list().join('\n') || '(aucun fichier)', 'info');
        return true;
      case 'open':
        if (FS.exists(arg)) { openFile(arg); term.line('ouvert : ' + arg, 'ok'); }
        else term.line('introuvable : ' + arg, 'err');
        return true;
      case 'cat':
        if (FS.exists(arg)) term.line(FS.read(arg), 'out');
        else term.line('introuvable : ' + arg, 'err');
        return true;
      case 'new':
        if (!arg) { term.line('usage : !new <fichier>', 'err'); return true; }
        FS.write(FS.uniqueName(arg), '');
        renderFiles();
        term.line('cree : ' + arg, 'ok');
        return true;
      case 'rm':
        if (FS.remove(arg)) { closeTab(arg); renderFiles(); term.line('supprime : ' + arg, 'ok'); }
        else term.line('introuvable : ' + arg, 'err');
        return true;
      case 'run':
        if (arg && FS.exists(arg)) openFile(arg);
        runCurrentFile();
        return true;
      case 'reset':
        RT.reset();
        term.line('espace de noms reinitialise', 'ok');
        return true;
      case 'backend':
        if (arg === 'pyodide' || arg === 'native') { switchBackend(arg); }
        else term.line('moteur : ' + (RT.backend ? RT.backend.label : 'aucun'), 'info');
        return true;
      case 'pip':
      case 'pip3':
        if (parts[1] === 'install' && parts[2]) { installPackage(parts.slice(2).join(' ')); return true; }
        term.line('usage : !pip install <paquet>', 'err');
        return true;
      default:
        term.line('commande inconnue : ' + cmd + '  (essayez !help)', 'err');
        return true;
    }
  }

  function submitToRepl(code, fromEditor) {
    if (!RT.ready) { term.line('moteur non pret — voir les reglages', 'warn'); return; }
    if (state.running) { term.line('une execution est deja en cours', 'warn'); return; }
    term.echo(code.split('\n').join('\n... '));

    askPrefill(code).then(function (stdin) {
      if (stdin === null) return;
      setRunning(true);
      var started = Date.now();
      RT.run(code, { echo: true, filename: fromEditor ? (state.active || '<repl>') : '<repl>', stdin: stdin })
        .then(function (out) {
          setRunning(false);
          reportResult(out && out.result, (out && out.ms) || (Date.now() - started), 'repl');
        });
    });
  }

  function onReplSubmit(e) {
    e.preventDefault();
    var input = $('term-in');
    var line = input.value;
    if (!line.trim()) return;
    input.value = '';
    term.remember(line);

    if (/^[!%]/.test(line) || /^(pip|pip3)\s+install\s+/.test(line.trim())) {
      term.echo(line);
      handleMagic(line.replace(/^(?=pip)/, '!'));
      return;
    }
    submitToRepl(line, false);
  }

  /* ------------------------------------------------------------- stdin */

  function openStdinModal(mode, label) {
    var modal = $('stdin-modal');
    var input = $('stdin-input');
    $('stdin-label').textContent = label;
    input.rows = mode === 'prefill' ? 4 : 1;
    input.value = '';
    modal.hidden = false;
    state.stdinMode = mode;
    setTimeout(function () { input.focus(); }, 30);
    return new Promise(function (resolve) { state.stdinResolve = resolve; });
  }

  function closeStdinModal(value) {
    $('stdin-modal').hidden = true;
    var resolve = state.stdinResolve;
    state.stdinResolve = null;
    state.stdinMode = null;
    if (resolve) resolve(value);
  }

  /* ---------------------------------------------------------- problemes */

  function setProblems(items) {
    var ul = $('problem-list');
    ul.textContent = '';
    items.forEach(function (p) {
      var li = document.createElement('li');
      var loc = document.createElement('span');
      loc.className = 'ploc';
      loc.textContent = (p.file || '?') + (p.line ? ':' + p.line : '') + '  ';
      var msg = document.createElement('span');
      msg.className = 'pmsg';
      msg.textContent = (p.type ? p.type + ': ' : '') + (p.msg || '');
      li.appendChild(loc);
      li.appendChild(msg);
      if (p.line) li.addEventListener('click', function () { editor.goTo(p.line); });
      ul.appendChild(li);
    });
    var badge = $('problem-count');
    badge.textContent = items.length;
    badge.hidden = items.length === 0;
  }

  /* ----------------------------------------------------------- paquets */

  var SUGGESTED = ['numpy', 'pandas', 'matplotlib', 'sympy', 'requests', 'rich',
                   'beautifulsoup4', 'pillow', 'scikit-learn', 'networkx'];

  function installPackage(name) {
    if (!RT.ready) { term.line('moteur non pret', 'err'); return; }
    term.line('installation de ' + name + '…', 'info');
    openPanel(true);
    RT.install(name).then(function (res) {
      if (res && res.ok) {
        term.line('✓ ' + name + ' installe', 'ok');
        toast(name + ' installe');
        RT.packages();
      } else {
        term.line('✗ echec : ' + ((res && res.error) || 'inconnu'), 'err');
      }
    });
  }

  function renderPackages(names) {
    var ul = $('pkg-list');
    ul.textContent = '';
    (names || []).filter(function (n) { return n && n[0] !== '_'; })
      .slice(0, 400)
      .forEach(function (n) {
        var li = document.createElement('li');
        li.textContent = n;
        ul.appendChild(li);
      });
  }

  function renderSuggested() {
    var ul = $('pkg-quick');
    ul.textContent = '';
    SUGGESTED.forEach(function (n) {
      var li = document.createElement('li');
      li.textContent = n;
      li.addEventListener('click', function () { installPackage(n); });
      ul.appendChild(li);
    });
  }

  /* ---------------------------------------------------------- snippets */

  function renderSnippets() {
    var ul = $('snippet-list');
    ul.textContent = '';
    (global.PySnippets || []).forEach(function (sn) {
      var li = document.createElement('li');
      var t = document.createElement('div');
      t.className = 'stitle';
      t.textContent = sn.title;
      var d = document.createElement('div');
      d.className = 'sdesc';
      d.textContent = sn.desc;
      li.appendChild(t);
      li.appendChild(d);
      li.addEventListener('click', function () {
        var path = FS.uniqueName(sn.file);
        FS.write(path, sn.code);
        renderFiles();
        openFile(path);
        toast('modele ajoute : ' + path);
      });
      ul.appendChild(li);
    });
  }

  /* ----------------------------------------------------------- moteur */

  function switchBackend(name) {
    var url = S.get('kernelUrl');
    S.set('backend', name);
    $('set-backend').value = name;
    $('runtime-badge').textContent = 'demarrage…';
    $('runtime-badge').className = 'badge muted';
    $('btn-run').disabled = true;
    RT.use(name, url).then(function (info) {
      if (info && name === 'native') RT.syncFiles(collectFiles());
      RT.packages();
    });
  }

  function wireRuntime() {
    RT.on('status', function (s) {
      var badge = $('runtime-badge');
      $('st-backend').textContent = RT.backend ? RT.backend.label : '—';
      if (s.state === 'ready') {
        badge.textContent = RT.backend.label;
        badge.className = 'badge ok';
        $('btn-run').disabled = false;
        term.line('● ' + s.message + '  —  ' + RT.backend.label, 'ok');
        if (RT.backend.name === 'pyodide' && !RT.info.blockingStdin) {
          term.line('  input() : saisie demandee avant l\'execution (site non isole). ' +
                    'Lancez server/serve.py pour la saisie en direct.', 'warn');
        }
        updateEnvInfo();
      } else if (s.state === 'loading') {
        badge.textContent = 'chargement…';
        badge.className = 'badge busy';
        status(s.message);
      } else if (s.state === 'error') {
        badge.textContent = 'erreur';
        badge.className = 'badge err';
        term.line('✗ ' + s.message, 'err');
        $('btn-run').disabled = true;
      }
    });

    RT.on('stdout', function (d) { term.stream(d, 'out'); });
    RT.on('stderr', function (d) { term.stream(d, 'err'); });
    RT.on('packages', renderPackages);
    RT.on('stdin', function () {
      openStdinModal('live', 'Le programme attend une entree :').then(function (value) {
        RT.pushStdin(value === null ? null : value.split('\n')[0]);
      });
    });
  }

  function updateEnvInfo() {
    var bits = [];
    bits.push('Moteur : ' + (RT.backend ? RT.backend.label : '—'));
    if (RT.info.version) bits.push('Python ' + RT.info.version);
    bits.push('Isolation du site : ' + (global.crossOriginIsolated ? 'oui (saisie et Ctrl+C en direct)' : 'non'));
    bits.push('Stockage : ' + (FS.available ? 'localStorage actif' : 'indisponible (mode prive ?)'));
    if (RT.info.cwd) bits.push('Dossier : ' + RT.info.cwd);
    $('env-info').textContent = bits.join(' · ');
  }

  /* --------------------------------------------------------- panneaux */

  function openPanel(force) {
    if (force || app.getAttribute('data-panel') === 'closed') {
      app.setAttribute('data-panel', 'open');
      if (editor) editor.refresh();
    }
  }

  function togglePanel() {
    app.setAttribute('data-panel', app.getAttribute('data-panel') === 'open' ? 'closed' : 'open');
    editor.refresh();
  }

  function showView(name) {
    Array.prototype.forEach.call(document.querySelectorAll('#sidebar .view'), function (v) {
      v.hidden = v.dataset.view !== name;
    });
    Array.prototype.forEach.call(document.querySelectorAll('.act'), function (b) {
      b.classList.toggle('is-active', b.dataset.view === name);
    });
    app.setAttribute('data-sidebar', 'open');
  }

  function toggleSidebar() {
    app.setAttribute('data-sidebar',
      app.getAttribute('data-sidebar') === 'open' ? 'closed' : 'open');
    editor.refresh();
  }

  /* ------------------------------------------------- palette de commandes */

  function commandList() {
    var cmds = [
      { name: 'Executer le fichier', key: 'Ctrl+Entree', run: runCurrentFile },
      { name: 'Executer la selection', key: 'Ctrl+Maj+Entree', run: runSelection },
      { name: 'Arreter l\'execution', key: 'Ctrl+C', run: stopRun },
      { name: 'Enregistrer', key: 'Ctrl+S', run: function () { saveActive(); } },
      { name: 'Nouveau fichier', key: '', run: newFile },
      { name: 'Renommer le fichier actif', key: '', run: renameActive },
      { name: 'Telecharger le fichier actif', key: '', run: exportActive },
      { name: 'Importer des fichiers', key: '', run: function () { $('file-input').click(); } },
      { name: 'Exporter tout l\'espace (.json)', key: '', run: exportAll },
      { name: 'Terminal : afficher / masquer', key: 'Ctrl+`', run: togglePanel },
      { name: 'Explorateur : afficher / masquer', key: '', run: toggleSidebar },
      { name: 'Effacer la console', key: '', run: function () { term.clear(); } },
      { name: 'Reinitialiser l\'espace de noms Python', key: '', run: function () { RT.reset(); toast('espace de noms vide'); } },
      { name: 'Redemarrer le moteur', key: '', run: function () { RT.restart(); } },
      { name: 'Theme clair / sombre', key: '', run: function () {
          applyTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark'); } },
      { name: 'Moteur : navigateur (Pyodide)', key: '', run: function () { switchBackend('pyodide'); } },
      { name: 'Moteur : CPython local', key: '', run: function () { switchBackend('native'); } },
      { name: 'Installer un paquet…', key: '', run: function () {
          var n = global.prompt('Nom du paquet'); if (n) installPackage(n.trim()); } },
      { name: 'Installer l\'application', key: '', run: function () {
          if (global.PyPlatform) global.PyPlatform.showInstall(); } },
      { name: 'Reglages', key: '', run: function () { showView('settings'); } }
    ];
    FS.list().forEach(function (p) {
      cmds.push({ name: p, key: 'fichier', sub: true, run: function () { openFile(p); } });
    });
    return cmds;
  }

  var palette = { items: [], filtered: [], index: 0 };

  function openPalette() {
    palette.items = commandList();
    $('palette').hidden = false;
    $('palette-input').value = '';
    filterPalette('');
    setTimeout(function () { $('palette-input').focus(); }, 30);
  }

  function closePalette() { $('palette').hidden = true; }

  function filterPalette(q) {
    var needle = q.toLowerCase().trim();
    palette.filtered = palette.items.filter(function (c) {
      return !needle || c.name.toLowerCase().indexOf(needle) >= 0;
    }).slice(0, 40);
    palette.index = 0;
    renderPalette();
  }

  function renderPalette() {
    var ul = $('palette-list');
    ul.textContent = '';
    palette.filtered.forEach(function (c, i) {
      var li = document.createElement('li');
      if (i === palette.index) li.className = 'is-sel';
      var n = document.createElement('span');
      n.className = c.sub ? 'psub' : '';
      n.textContent = c.name;
      li.appendChild(n);
      if (c.key) {
        var k = document.createElement('span');
        k.className = 'pk';
        k.textContent = c.key;
        li.appendChild(k);
      }
      li.addEventListener('click', function () { closePalette(); c.run(); });
      ul.appendChild(li);
    });
  }

  /* ------------------------------------------------- import / export */

  function exportActive() {
    if (!state.active) return;
    download(state.active, editor.value());
  }

  function exportAll() {
    saveActive(true);
    download('pyterm-espace-' + new Date().toISOString().slice(0, 10) + '.json',
      JSON.stringify(FS.toJSON(), null, 2), 'application/json');
  }

  function importFiles(fileList) {
    var files = Array.prototype.slice.call(fileList || []);
    if (!files.length) return;
    var pending = files.length;
    files.forEach(function (f) {
      var reader = new FileReader();
      reader.onload = function () {
        var text = String(reader.result);
        if (/\.json$/i.test(f.name)) {
          var data = null;
          try { data = JSON.parse(text); } catch (e) { data = null; }
          if (data && data.files) {
            var n = FS.importJSON(data, false);
            toast(n + ' fichier(s) importe(s)');
            if (!--pending) { renderFiles(); }
            return;
          }
        }
        var path = FS.uniqueName(f.name);
        FS.write(path, text);
        if (!--pending) { renderFiles(); openFile(path); }
      };
      reader.onerror = function () { if (!--pending) renderFiles(); };
      reader.readAsText(f);
    });
  }

  function renameActive() {
    if (!state.active) return;
    var to = global.prompt('Nouveau nom', state.active);
    if (!to || to === state.active) return;
    saveActive(true);
    var from = state.active;
    var target = FS.normalize(to);
    if (FS.exists(target)) { toast('ce nom existe deja'); return; }
    if (!FS.rename(from, target)) { toast('renommage impossible'); return; }
    editor.rename(from, target);
    var i = state.tabs.indexOf(from);
    if (i >= 0) state.tabs[i] = target;
    state.active = target;
    renderFiles();
    renderTabs();
    S.set('activeFile', target);
    S.set('openTabs', state.tabs);
  }

  /* -------------------------------------------------------- splitters */

  function wireSplitter(el, axis) {
    var dragging = false;
    function move(e) {
      if (!dragging) return;
      var point = e.touches ? e.touches[0] : e;
      if (axis === 'x') {
        var w = Math.max(160, Math.min(520, point.clientX - $('activitybar').offsetWidth));
        document.documentElement.style.setProperty('--w-sidebar', w + 'px');
        S.set('sidebarWidth', w);
      } else {
        var rect = $('main').getBoundingClientRect();
        var h = Math.max(90, Math.min(rect.height - 90, rect.bottom - point.clientY));
        document.documentElement.style.setProperty('--h-panel', h + 'px');
        S.set('panelHeight', h);
      }
      editor.refresh();
    }
    function stop() {
      dragging = false;
      el.classList.remove('is-drag');
      document.body.style.userSelect = '';
    }
    el.addEventListener('pointerdown', function (e) {
      dragging = true;
      el.classList.add('is-drag');
      document.body.style.userSelect = 'none';
      el.setPointerCapture(e.pointerId);
    });
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerup', stop);
    el.addEventListener('pointercancel', stop);
  }

  /* --------------------------------------------------------- raccourcis */

  function wireKeys() {
    document.addEventListener('keydown', function (e) {
      var meta = e.ctrlKey || e.metaKey;

      if (e.key === 'Escape') {
        if (!$('palette').hidden) { closePalette(); return; }
        if (!$('stdin-modal').hidden) { closeStdinModal(null); return; }
      }
      if (meta && e.shiftKey && (e.key === 'P' || e.key === 'p')) {
        e.preventDefault(); openPalette(); return;
      }
      if (meta && (e.key === 'p' || e.key === 'P') && !e.shiftKey) {
        e.preventDefault(); openPalette(); return;
      }
      if (meta && e.key === '`') { e.preventDefault(); togglePanel(); return; }
      if (meta && e.key === 'b') { e.preventDefault(); toggleSidebar(); return; }
      if (meta && e.key === 's') { e.preventDefault(); saveActive(); return; }
      if (meta && e.shiftKey && e.key === 'Enter') { e.preventDefault(); runSelection(); return; }
      if (meta && e.key === 'Enter') { e.preventDefault(); runCurrentFile(); return; }
      if (meta && e.key === 'c' && state.running && !global.getSelection().toString()) {
        e.preventDefault(); stopRun(); return;
      }
    });

    var pinput = $('palette-input');
    pinput.addEventListener('input', function () { filterPalette(pinput.value); });
    pinput.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        palette.index = Math.min(palette.filtered.length - 1, palette.index + 1);
        renderPalette();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        palette.index = Math.max(0, palette.index - 1);
        renderPalette();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        var c = palette.filtered[palette.index];
        closePalette();
        if (c) c.run();
      }
    });
    $('palette').addEventListener('click', function (e) {
      if (e.target === $('palette')) closePalette();
    });

    var tin = $('term-in');
    tin.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowUp') {
        var prev = term.recall(-1);
        if (prev !== null) { e.preventDefault(); tin.value = prev; }
      } else if (e.key === 'ArrowDown') {
        var next = term.recall(1);
        if (next !== null) { e.preventDefault(); tin.value = next; }
      } else if (e.key === 'l' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault(); term.clear();
      }
    });
  }

  /* ------------------------------------------------------- barre mobile */

  function wireKeybar() {
    var bar = $('keybar');
    bar.addEventListener('pointerdown', function (e) {
      var btn = e.target.closest('button');
      if (!btn) return;
      e.preventDefault();
      var text = btn.dataset.ins;
      var tin = $('term-in');
      if (document.activeElement === tin) {
        var start = tin.selectionStart, end = tin.selectionEnd;
        tin.value = tin.value.slice(0, start) + text + tin.value.slice(end);
        tin.selectionStart = tin.selectionEnd = start + text.length;
        tin.focus();
      } else {
        editor.insert(text);
      }
    });
  }

  function keybarEnabled() {
    var pref = S.get('keybar');
    if (pref === null || pref === undefined) {
      return global.matchMedia('(hover: none)').matches || global.innerWidth <= 780;
    }
    return !!pref;
  }

  function applyKeybar() {
    $('keybar').hidden = !keybarEnabled();
  }

  /* ---------------------------------------------------------- reglages */

  function wireSettings() {
    var s = S.all();

    $('set-backend').value = s.backend;
    $('set-kernel-url').value = s.kernelUrl;
    $('set-fontsize').value = s.fontSize;
    $('set-tabsize').value = String(s.tabSize);
    $('set-wrap').checked = !!s.wrap;
    $('set-autorun').checked = !!s.saveBeforeRun;
    $('set-keybar').checked = keybarEnabled();
    $('field-kernel').style.display = s.backend === 'native' ? '' : 'none';

    $('set-backend').addEventListener('change', function () {
      $('field-kernel').style.display = this.value === 'native' ? '' : 'none';
      switchBackend(this.value);
    });
    $('set-kernel-url').addEventListener('change', function () {
      S.set('kernelUrl', this.value.trim());
      if (S.get('backend') === 'native') switchBackend('native');
    });
    $('set-fontsize').addEventListener('input', function () {
      S.set('fontSize', parseInt(this.value, 10));
      editor.applySettings(S.all());
    });
    $('set-tabsize').addEventListener('change', function () {
      S.set('tabSize', parseInt(this.value, 10));
      editor.applySettings(S.all());
    });
    $('set-wrap').addEventListener('change', function () {
      S.set('wrap', this.checked);
      editor.applySettings(S.all());
    });
    $('set-autorun').addEventListener('change', function () { S.set('saveBeforeRun', this.checked); });
    $('set-keybar').addEventListener('change', function () { S.set('keybar', this.checked); applyKeybar(); });
    $('btn-export-all').addEventListener('click', exportAll);
    $('btn-reset').addEventListener('click', function () {
      if (!global.confirm('Effacer tous les fichiers et revenir aux exemples ?')) return;
      FS.resetAll();
      state.tabs = [];
      state.active = null;
      Object.keys(editor.docs).forEach(function (p) { editor.close(p); });
      renderFiles();
      openFile(FS.list()[0]);
      toast('espace reinitialise');
    });
  }

  /* ------------------------------------------------------------- boot */

  function wireUI() {
    $('btn-run').addEventListener('click', runCurrentFile);
    $('btn-stop').addEventListener('click', stopRun);
    $('btn-menu').addEventListener('click', toggleSidebar);
    $('btn-panel').addEventListener('click', togglePanel);
    $('btn-panel-close').addEventListener('click', togglePanel);
    $('btn-palette').addEventListener('click', openPalette);
    $('btn-theme').addEventListener('click', function () {
      applyTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
    });
    $('btn-new-file').addEventListener('click', newFile);
    $('btn-export').addEventListener('click', exportActive);
    $('btn-import').addEventListener('click', function () { $('file-input').click(); });
    $('file-input').addEventListener('change', function () { importFiles(this.files); this.value = ''; });
    $('btn-clear').addEventListener('click', function () { term.clear(); });

    Array.prototype.forEach.call(document.querySelectorAll('.act'), function (b) {
      b.addEventListener('click', function () {
        if (b.classList.contains('is-active') && app.getAttribute('data-sidebar') === 'open'
            && global.innerWidth > 780) { toggleSidebar(); return; }
        showView(b.dataset.view);
      });
    });

    Array.prototype.forEach.call(document.querySelectorAll('.ptab'), function (b) {
      b.addEventListener('click', function () {
        Array.prototype.forEach.call(document.querySelectorAll('.ptab'), function (o) {
          o.classList.toggle('is-active', o === b);
        });
        Array.prototype.forEach.call(document.querySelectorAll('.panel-body'), function (p) {
          p.hidden = p.dataset.tab !== b.dataset.tab;
        });
      });
    });

    $('term-form').addEventListener('submit', onReplSubmit);
    $('pkg-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var n = $('pkg-name').value.trim();
      if (n) { installPackage(n); $('pkg-name').value = ''; }
    });
    $('stdin-form').addEventListener('submit', function (e) {
      e.preventDefault();
      closeStdinModal($('stdin-input').value);
    });
    $('stdin-input').addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && state.stdinMode === 'live') {
        e.preventDefault();
        closeStdinModal(this.value);
      }
    });

    // Glisser-deposer de fichiers sur l'editeur
    ['dragover', 'drop'].forEach(function (evt) {
      document.addEventListener(evt, function (e) {
        e.preventDefault();
        if (evt === 'drop' && e.dataTransfer) importFiles(e.dataTransfer.files);
      });
    });

    global.addEventListener('beforeunload', function () { saveActive(true); });
    global.addEventListener('resize', function () { editor.refresh(); });

    setInterval(function () {
      $('st-time').textContent = new Date().toLocaleTimeString();
    }, 1000);
  }

  function boot() {
    var s = S.all();
    applyTheme(s.theme);
    document.documentElement.style.setProperty('--w-sidebar', s.sidebarWidth + 'px');
    document.documentElement.style.setProperty('--h-panel', s.panelHeight + 'px');
    document.documentElement.style.setProperty('--editor-fs', s.fontSize + 'px');

    term = new global.PyTerminal($('term-out'), $('term-in'), $('term-prompt'));

    editor = new global.PyEditor($('editor-host'), {
      onChange: function (path) {
        if (!path) return;
        state.dirty[path] = true;
        $('crumb-dirty').hidden = false;
        scheduleSave();
      },
      onCursor: function (line, col) { $('st-pos').textContent = 'L' + line + ' : C' + col; },
      onRun: runCurrentFile,
      onSave: function () { saveActive(); },
      onPalette: openPalette
    });
    editor.applySettings(s);

    global.PyApp = { fs: FS, editor: editor, terminal: term, runtime: RT, settings: S };

    renderFiles();
    renderSnippets();
    renderSuggested();
    showView('files');
    applyKeybar();
    wireUI();
    wireKeys();
    wireKeybar();
    wireSettings();
    wireSplitter($('split-v'), 'x');
    wireSplitter($('split-h'), 'y');
    wireRuntime();

    var tabs = Array.isArray(s.openTabs) ? s.openTabs.filter(function (p) { return FS.exists(p); }) : [];
    state.tabs = tabs.length ? tabs : [FS.list()[0]].filter(Boolean);
    var active = FS.exists(s.activeFile) ? s.activeFile : state.tabs[0];
    if (active) openFile(active);

    term.line('PyTerm — studio Python autonome.  !help pour les commandes.', 'info');
    setRunning(false);
    switchBackend(s.backend);

    if (location.protocol === 'http:' || location.protocol === 'https:') {
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('sw.js').catch(function () { /* hors-ligne indisponible */ });
      }
    }

    if (global.PyPlatform) global.PyPlatform.init();

    FS.onChange(function (evt) {
      if (evt.type === 'error') toast('stockage plein : exportez puis allegez vos fichiers', 4000);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})(window);
