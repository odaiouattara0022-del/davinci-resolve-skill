/* ==========================================================================
   runtime.js — deux moteurs d'execution Python derriere une meme interface
     * PyodideBackend : CPython compile en WebAssembly, dans un Worker.
                        Aucune installation, fonctionne hors-ligne.
     * NativeBackend  : vrai CPython local via server/kernel.py (HTTP + SSE).
                        Aucune limite : sockets, pip complet, vrai disque.

   Evenements emis : status, stdout, stderr, value, done, stdin, packages, log
   ========================================================================== */
(function (global) {
  'use strict';

  var PYODIDE_URL = 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/';

  /* ---------------------------------------------------------------- utils */

  function Emitter() { this._h = {}; }
  Emitter.prototype.on = function (evt, fn) {
    (this._h[evt] = this._h[evt] || []).push(fn);
    return this;
  };
  Emitter.prototype.emit = function (evt, payload) {
    (this._h[evt] || []).forEach(function (fn) {
      try { fn(payload); } catch (e) { if (global.console) console.error(e); }
    });
  };

  function hasSAB() {
    try { return typeof SharedArrayBuffer === 'function' && global.crossOriginIsolated === true; }
    catch (e) { return false; }
  }

  /* ------------------------------------------------- code du Worker Pyodide */
  /* Ecrit en une chaine puis transforme en Blob : cela fonctionne aussi bien
     depuis http(s) que depuis file://, ou un Worker externe serait bloque.  */

  var PY_BOOT = [
    'import ast, sys, json, builtins',
    '',
    '_NS = {"__name__": "__main__", "__doc__": None}',
    '',
    'def _pyterm_reset():',
    '    _NS.clear()',
    '    _NS.update({"__name__": "__main__", "__doc__": None})',
    '    return "ok"',
    '',
    'def _pyterm_lineno(exc, filename):',
    '    tb, line = exc.__traceback__, 0',
    '    while tb is not None:',
    '        if tb.tb_frame.f_code.co_filename == filename:',
    '            line = tb.tb_lineno',
    '        tb = tb.tb_next',
    '    return line',
    '',
    'def _pyterm_exec(source, echo=False, filename="<pyterm>"):',
    '    import traceback',
    '    try:',
    '        tree = ast.parse(source, filename=filename, mode="exec")',
    '    except SyntaxError as e:',
    '        traceback.print_exception(SyntaxError, e, None)',
    '        return json.dumps({"ok": False, "type": "SyntaxError",',
    '                           "msg": e.msg or "erreur de syntaxe", "line": e.lineno or 0})',
    '    body = list(tree.body)',
    '    tail = body.pop() if (echo and body and isinstance(body[-1], ast.Expr)) else None',
    '    try:',
    '        if body:',
    '            exec(compile(ast.Module(body=body, type_ignores=[]), filename, "exec"), _NS)',
    '        value = None',
    '        if tail is not None:',
    '            result = eval(compile(ast.Expression(tail.value), filename, "eval"), _NS)',
    '            if result is not None:',
    '                builtins._ = result',
    '                try:',
    '                    value = repr(result)',
    '                except Exception:',
    '                    value = "<objet dont repr() a echoue>"',
    '        return json.dumps({"ok": True, "value": value})',
    '    except SystemExit as e:',
    '        return json.dumps({"ok": True, "exit": 0 if e.code is None else e.code})',
    '    except KeyboardInterrupt:',
    '        print("^C  execution interrompue", file=sys.stderr)',
    '        return json.dumps({"ok": False, "type": "KeyboardInterrupt", "msg": "interrompu", "line": 0})',
    '    except BaseException as e:',
    '        traceback.print_exc()',
    '        return json.dumps({"ok": False, "type": type(e).__name__,',
    '                           "msg": str(e), "line": _pyterm_lineno(e, filename)})',
    ''
  ].join('\n');

  function workerSource() {
    return [
      '"use strict";',
      'let pyodide = null;',
      'let stdinQueue = [];',
      'let stdinCtl = null, stdinBuf = null;',
      'const PY_BOOT = ' + JSON.stringify(PY_BOOT) + ';',
      '',
      'function post(type, payload) { self.postMessage(Object.assign({ type: type }, payload || {})); }',
      '',
      '/* Lecture bloquante quand SharedArrayBuffer est disponible ;',
      '   sinon on puise dans la file fournie avant execution.        */',
      'function readStdin() {',
      '  if (stdinQueue.length) return stdinQueue.shift();',
      '  if (!stdinCtl) return null;',
      '  Atomics.store(stdinCtl, 0, 1);',
      '  post("stdin");',
      '  while (Atomics.load(stdinCtl, 0) === 1) { Atomics.wait(stdinCtl, 0, 1, 250); }',
      '  const state = Atomics.load(stdinCtl, 0);',
      '  Atomics.store(stdinCtl, 0, 0);',
      '  if (state === 3) return null;',
      '  const len = Atomics.load(stdinCtl, 1);',
      '  return new TextDecoder().decode(stdinBuf.subarray(0, len));',
      '}',
      '',
      'async function boot(msg) {',
      '  if (msg.stdinSab) {',
      '    stdinCtl = new Int32Array(msg.stdinSab, 0, 2);',
      '    stdinBuf = new Uint8Array(msg.stdinSab, 8);',
      '  }',
      '  try {',
      '    importScripts(msg.indexUrl + "pyodide.js");',
      '    pyodide = await loadPyodide({',
      '      indexURL: msg.indexUrl,',
      '      stdout: (s) => post("stdout", { data: s + "\\n" }),',
      '      stderr: (s) => post("stderr", { data: s + "\\n" })',
      '    });',
      '    if (msg.interruptSab) pyodide.setInterruptBuffer(new Uint8Array(msg.interruptSab));',
      '    pyodide.setStdin({ stdin: readStdin, isatty: false });',
      '    pyodide.runPython(PY_BOOT);',
      '    post("ready", {',
      '      version: pyodide.runPython("import sys; sys.version.split()[0]"),',
      '      full: pyodide.runPython("import sys; sys.version"),',
      '      interrupt: !!msg.interruptSab,',
      '      blockingStdin: !!msg.stdinSab',
      '    });',
      '  } catch (err) {',
      '    post("fatal", { error: String(err && err.message || err) });',
      '  }',
      '}',
      '',
      'async function run(msg) {',
      '  stdinQueue = Array.isArray(msg.stdin) ? msg.stdin.slice() : [];',
      '  const started = Date.now();',
      '  try {',
      '    if (msg.autoImport !== false) {',
      '      try { await pyodide.loadPackagesFromImports(msg.code, { messageCallback: () => {} }); }',
      '      catch (e) { post("stderr", { data: "[paquets] " + e + "\\n" }); }',
      '    }',
      '    pyodide.globals.set("_pyterm_src", msg.code);',
      '    pyodide.globals.set("_pyterm_echo", !!msg.echo);',
      '    pyodide.globals.set("_pyterm_file", msg.filename || "<pyterm>");',
      '    const raw = await pyodide.runPythonAsync(',
      '      "_pyterm_exec(_pyterm_src, _pyterm_echo, _pyterm_file)");',
      '    post("done", { id: msg.id, result: JSON.parse(raw), ms: Date.now() - started });',
      '  } catch (err) {',
      '    post("done", {',
      '      id: msg.id,',
      '      result: { ok: false, type: "RuntimeError", msg: String(err && err.message || err), line: 0 },',
      '      ms: Date.now() - started',
      '    });',
      '  }',
      '}',
      '',
      'async function install(msg) {',
      '  try {',
      '    await pyodide.loadPackage("micropip");',
      '    const micropip = pyodide.pyimport("micropip");',
      '    await micropip.install(msg.name);',
      '    post("installed", { name: msg.name });',
      '  } catch (err) {',
      '    post("install-failed", { name: msg.name, error: String(err && err.message || err) });',
      '  }',
      '}',
      '',
      'self.onmessage = async (e) => {',
      '  const msg = e.data || {};',
      '  switch (msg.type) {',
      '    case "boot":    return boot(msg);',
      '    case "run":     return run(msg);',
      '    case "install": return install(msg);',
      '    case "packages":',
      '      try {',
      '        const names = pyodide.runPython(',
      '          "import json,sys; json.dumps(sorted({m.split(\'.\')[0] for m in sys.modules}))");',
      '        post("packages", { names: JSON.parse(names) });',
      '      } catch (err) { post("packages", { names: [] }); }',
      '      return;',
      '    case "reset":',
      '      try { pyodide.runPython("_pyterm_reset()"); post("reset-done", {}); }',
      '      catch (err) { post("reset-done", {}); }',
      '      return;',
      '  }',
      '};',
      ''
    ].join('\n');
  }

  /* ------------------------------------------------------ PyodideBackend */

  function PyodideBackend(bus) {
    this.bus = bus;
    this.name = 'pyodide';
    this.label = 'Pyodide';
    this.worker = null;
    this.ready = false;
    this.busy = false;
    this.info = {};
    this._pending = null;
    this._interruptBuf = null;
    this._stdinCtl = null;
    this._stdinBytes = null;
    this._installs = {};
  }

  PyodideBackend.prototype.init = function () {
    var self = this;
    if (this._initPromise) return this._initPromise;

    this._initPromise = new Promise(function (resolve) {
      var blob = new Blob([workerSource()], { type: 'text/javascript' });
      var url = URL.createObjectURL(blob);
      self.worker = new Worker(url);
      URL.revokeObjectURL(url);

      var boot = { type: 'boot', indexUrl: PYODIDE_URL };
      if (hasSAB()) {
        var ib = new SharedArrayBuffer(1);
        var sb = new SharedArrayBuffer(8 + 65536);
        self._interruptBuf = new Uint8Array(ib);
        self._stdinCtl = new Int32Array(sb, 0, 2);
        self._stdinBytes = new Uint8Array(sb, 8);
        boot.interruptSab = ib;
        boot.stdinSab = sb;
      }

      self.worker.onmessage = function (e) { self._onMessage(e.data || {}, resolve); };
      self.worker.onerror = function (e) {
        self.bus.emit('status', { state: 'error', message: e.message || 'worker en erreur' });
      };
      self.bus.emit('status', { state: 'loading', message: 'telechargement de Pyodide…' });
      self.worker.postMessage(boot);
    });
    return this._initPromise;
  };

  PyodideBackend.prototype._onMessage = function (msg, resolveInit) {
    switch (msg.type) {
      case 'ready':
        this.ready = true;
        this.info = { version: msg.version, full: msg.full,
                      interrupt: msg.interrupt, blockingStdin: msg.blockingStdin };
        this.bus.emit('status', { state: 'ready', message: 'Python ' + msg.version });
        if (resolveInit) resolveInit(this.info);
        break;
      case 'fatal':
        this.bus.emit('status', { state: 'error', message: msg.error });
        if (resolveInit) resolveInit(null);
        break;
      case 'stdout': this.bus.emit('stdout', msg.data); break;
      case 'stderr': this.bus.emit('stderr', msg.data); break;
      case 'stdin':  this.bus.emit('stdin', {}); break;
      case 'done':
        this.busy = false;
        if (this._pending) { this._pending({ result: msg.result, ms: msg.ms }); this._pending = null; }
        this.bus.emit('done', { result: msg.result, ms: msg.ms });
        break;
      case 'installed':
        if (this._installs[msg.name]) { this._installs[msg.name]({ ok: true }); delete this._installs[msg.name]; }
        break;
      case 'install-failed':
        if (this._installs[msg.name]) {
          this._installs[msg.name]({ ok: false, error: msg.error });
          delete this._installs[msg.name];
        }
        break;
      case 'packages': this.bus.emit('packages', msg.names || []); break;
    }
  };

  PyodideBackend.prototype.run = function (code, opts) {
    var self = this;
    opts = opts || {};
    if (!this.ready) return Promise.resolve({ result: { ok: false, msg: 'moteur non pret' }, ms: 0 });
    this.busy = true;
    return new Promise(function (resolve) {
      self._pending = resolve;
      self.worker.postMessage({
        type: 'run', code: code, echo: !!opts.echo,
        filename: opts.filename || '<pyterm>',
        stdin: opts.stdin || [], id: opts.id || 0
      });
    });
  };

  /** Fournit une ligne au programme en attente (mode SharedArrayBuffer). */
  PyodideBackend.prototype.pushStdin = function (line) {
    if (!this._stdinCtl) return false;
    if (line === null) { Atomics.store(this._stdinCtl, 0, 3); }
    else {
      var bytes = new TextEncoder().encode(String(line) + '\n');
      var n = Math.min(bytes.length, this._stdinBytes.length);
      this._stdinBytes.set(bytes.subarray(0, n));
      Atomics.store(this._stdinCtl, 1, n);
      Atomics.store(this._stdinCtl, 0, 2);
    }
    Atomics.notify(this._stdinCtl, 0);
    return true;
  };

  PyodideBackend.prototype.interrupt = function () {
    if (this._interruptBuf) { this._interruptBuf[0] = 2; return Promise.resolve(true); }
    return this.restart().then(function () { return false; });
  };

  PyodideBackend.prototype.restart = function () {
    if (this.worker) this.worker.terminate();
    this.worker = null; this.ready = false; this.busy = false;
    this._initPromise = null;
    if (this._pending) {
      this._pending({ result: { ok: false, type: 'KeyboardInterrupt', msg: 'interrompu', line: 0 }, ms: 0 });
      this._pending = null;
    }
    return this.init();
  };

  PyodideBackend.prototype.reset = function () {
    if (this.worker) this.worker.postMessage({ type: 'reset' });
    return Promise.resolve(true);
  };

  PyodideBackend.prototype.install = function (name) {
    var self = this;
    if (!this.ready) return Promise.resolve({ ok: false, error: 'moteur non pret' });
    return new Promise(function (resolve) {
      self._installs[name] = resolve;
      self.worker.postMessage({ type: 'install', name: name });
    });
  };

  PyodideBackend.prototype.packages = function () {
    if (this.worker) this.worker.postMessage({ type: 'packages' });
  };

  PyodideBackend.prototype.syncFiles = function () { return Promise.resolve(true); };

  /* -------------------------------------------------------- NativeBackend */

  function NativeBackend(bus, url) {
    this.bus = bus;
    this.name = 'native';
    this.label = 'CPython local';
    this.url = String(url || '').replace(/\/+$/, '');
    this.ready = false;
    this.busy = false;
    this.info = {};
    this._es = null;
    this._pending = null;
    this._runId = 0;
  }

  NativeBackend.prototype._fetch = function (path, options) {
    return fetch(this.url + path, Object.assign({ mode: 'cors' }, options || {}));
  };

  NativeBackend.prototype.init = function () {
    var self = this;
    this.bus.emit('status', { state: 'loading', message: 'connexion au noyau local…' });
    return this._fetch('/kernel')
      .then(function (r) {
        if (!r.ok) throw new Error('reponse ' + r.status);
        return r.json();
      })
      .then(function (info) {
        self.info = info;
        self.ready = true;
        self._openStream();
        self.bus.emit('status', { state: 'ready', message: 'Python ' + info.version + ' (local)' });
        return info;
      })
      .catch(function (err) {
        self.ready = false;
        self.bus.emit('status', {
          state: 'error',
          message: 'noyau injoignable sur ' + self.url + ' — ' + (err.message || err)
        });
        return null;
      });
  };

  NativeBackend.prototype._openStream = function () {
    var self = this;
    if (this._es) this._es.close();
    this._es = new EventSource(this.url + '/events');
    this._es.onmessage = function (e) {
      var msg;
      try { msg = JSON.parse(e.data); } catch (err) { return; }
      switch (msg.type) {
        case 'stdout': self.bus.emit('stdout', msg.data); break;
        case 'stderr': self.bus.emit('stderr', msg.data); break;
        case 'stdin':  self.bus.emit('stdin', {}); break;
        case 'done':
          self.busy = false;
          var payload = { result: msg.result, ms: msg.ms };
          if (self._pending) { self._pending(payload); self._pending = null; }
          self.bus.emit('done', payload);
          break;
        case 'packages': self.bus.emit('packages', msg.names || []); break;
      }
    };
    this._es.onerror = function () {
      if (self._es && self._es.readyState === 2) {
        self.ready = false;
        self.bus.emit('status', { state: 'error', message: 'flux du noyau interrompu' });
      }
    };
  };

  NativeBackend.prototype.run = function (code, opts) {
    var self = this;
    opts = opts || {};
    if (!this.ready) return Promise.resolve({ result: { ok: false, msg: 'noyau non connecte' }, ms: 0 });
    this.busy = true;
    this._runId += 1;
    var promise = new Promise(function (resolve) { self._pending = resolve; });
    this._fetch('/exec', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code: code, echo: !!opts.echo,
        filename: opts.filename || '<pyterm>',
        stdin: opts.stdin || [], id: this._runId
      })
    }).catch(function (err) {
      self.busy = false;
      if (self._pending) {
        self._pending({ result: { ok: false, type: 'ConnectionError', msg: String(err), line: 0 }, ms: 0 });
        self._pending = null;
      }
    });
    return promise;
  };

  NativeBackend.prototype.pushStdin = function (line) {
    this._fetch('/stdin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data: line })
    }).catch(function () { /* le programme a peut-etre deja rendu la main */ });
    return true;
  };

  NativeBackend.prototype.interrupt = function () {
    return this._fetch('/interrupt', { method: 'POST' })
      .then(function () { return true; })
      .catch(function () { return false; });
  };

  NativeBackend.prototype.restart = function () {
    var self = this;
    return this._fetch('/reset', { method: 'POST' })
      .then(function () { return self.init(); })
      .catch(function () { return null; });
  };

  NativeBackend.prototype.reset = function () {
    return this._fetch('/reset', { method: 'POST' })
      .then(function () { return true; })
      .catch(function () { return false; });
  };

  NativeBackend.prototype.install = function (name) {
    return this._fetch('/install', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name })
    }).then(function (r) { return r.json(); })
      .catch(function (err) { return { ok: false, error: String(err) }; });
  };

  NativeBackend.prototype.packages = function () {
    var self = this;
    this._fetch('/packages').then(function (r) { return r.json(); })
      .then(function (d) { self.bus.emit('packages', d.names || []); })
      .catch(function () { /* silencieux */ });
  };

  /** Recopie les fichiers de l'editeur dans le dossier de travail du noyau. */
  NativeBackend.prototype.syncFiles = function (files) {
    if (!this.ready || !files) return Promise.resolve(false);
    return this._fetch('/fs/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ files: files })
    }).then(function (r) { return r.ok; }).catch(function () { return false; });
  };

  /* ------------------------------------------------------------- facade */

  function Runtime() {
    Emitter.call(this);
    this.backend = null;
    this.state = 'idle';
    var self = this;
    this.on('status', function (s) { self.state = s.state; });
  }
  Runtime.prototype = Object.create(Emitter.prototype);
  Runtime.prototype.constructor = Runtime;

  Runtime.prototype.use = function (name, kernelUrl) {
    if (this.backend && this.backend.name === name &&
        (name !== 'native' || this.backend.url === String(kernelUrl || '').replace(/\/+$/, ''))) {
      return Promise.resolve(this.backend.info);
    }
    if (this.backend && this.backend.name === 'pyodide' && this.backend.worker) {
      this.backend.worker.terminate();
      this.backend.worker = null;
    }
    if (this.backend && this.backend._es) this.backend._es.close();

    this.backend = (name === 'native')
      ? new NativeBackend(this, kernelUrl)
      : new PyodideBackend(this);
    return this.backend.init();
  };

  ['run', 'interrupt', 'restart', 'reset', 'install', 'packages', 'pushStdin', 'syncFiles']
    .forEach(function (m) {
      Runtime.prototype[m] = function (a, b) {
        if (!this.backend) return Promise.resolve(null);
        return this.backend[m](a, b);
      };
    });

  Object.defineProperty(Runtime.prototype, 'ready', {
    get: function () { return !!(this.backend && this.backend.ready); }
  });
  Object.defineProperty(Runtime.prototype, 'busy', {
    get: function () { return !!(this.backend && this.backend.busy); }
  });
  Object.defineProperty(Runtime.prototype, 'info', {
    get: function () { return (this.backend && this.backend.info) || {}; }
  });

  global.PyRuntime = new Runtime();
  global.PyRuntime.hasSAB = hasSAB;
})(window);
