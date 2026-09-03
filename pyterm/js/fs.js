/* ==========================================================================
   fs.js — systeme de fichiers virtuel persistant (localStorage)
   Un seul niveau de dossiers logiques : les noms peuvent contenir des "/".
   ========================================================================== */
(function (global) {
  'use strict';

  var KEY = 'pyterm.fs.v1';
  var SETTINGS_KEY = 'pyterm.settings.v1';

  var SEED = {
    'main.py': [
      '"""Bienvenue dans PyTerm.',
      '',
      'Ctrl+Entree  (ou le bouton Executer)  lance ce fichier.',
      'Ctrl+`       ouvre / ferme le terminal.',
      'Ctrl+Maj+P   ouvre la palette de commandes.',
      '',
      'Le terminal en bas est un vrai REPL : tapez-y une expression.',
      '"""',
      '',
      'import sys',
      'import platform',
      '',
      '',
      'def salut(nom: str) -> str:',
      '    return f"Bonjour {nom} !"',
      '',
      '',
      'if __name__ == "__main__":',
      '    print(salut("developpeur"))',
      '    print("Python", sys.version.split()[0], "sur", platform.machine())',
      '',
      '    total = sum(n * n for n in range(1, 11))',
      '    print("Somme des carres de 1 a 10 :", total)',
      ''
    ].join('\n'),
    'exemples/donnees.py': [
      '"""Manipulation de donnees avec la bibliotheque standard."""',
      'import json',
      'from collections import Counter',
      'from dataclasses import dataclass, asdict',
      '',
      '',
      '@dataclass',
      'class Vente:',
      '    ville: str',
      '    produit: str',
      '    montant: float',
      '',
      '',
      'ventes = [',
      '    Vente("Abidjan", "cafe", 1200.0),',
      '    Vente("Bouake", "cacao", 3400.5),',
      '    Vente("Abidjan", "cacao", 2750.0),',
      '    Vente("Yamoussoukro", "cafe", 980.25),',
      ']',
      '',
      'par_ville = Counter()',
      'for v in ventes:',
      '    par_ville[v.ville] += v.montant',
      '',
      'for ville, montant in par_ville.most_common():',
      '    print(f"{ville:<16} {montant:>10,.2f}")',
      '',
      'print()',
      'print(json.dumps([asdict(v) for v in ventes], indent=2, ensure_ascii=False))',
      ''
    ].join('\n'),
    'exemples/interactif.py': [
      '"""Lecture au clavier — fonctionne avec input()."""',
      '',
      'nom = input("Votre prenom ? ")',
      'age = input("Votre age ? ")',
      '',
      'try:',
      '    annees = int(age)',
      'except ValueError:',
      '    print("Age illisible, on prend 0.")',
      '    annees = 0',
      '',
      'print(f"Salut {nom}, dans 10 ans tu auras {annees + 10} ans.")',
      ''
    ].join('\n'),
    'README.md': [
      '# Mon espace PyTerm',
      '',
      'Tous les fichiers de ce panneau vivent dans le stockage local du',
      'navigateur : ils survivent a la fermeture de l\'onglet et fonctionnent',
      'hors connexion.',
      '',
      '- **Exporter** : bouton fleche-bas de l\'explorateur (fichier actif)',
      '  ou *Exporter tout* dans les reglages.',
      '- **Importer** : bouton fleche-haut, ou glisser-deposer sur l\'editeur.',
      '',
      'Pour lever toutes les limites du navigateur (sockets, `pip` complet,',
      'acces au vrai disque), lancez `server/kernel.py` sur la machine et',
      'passez le moteur sur *Local — vrai CPython* dans les reglages.',
      ''
    ].join('\n')
  };

  function nowIso() { return new Date().toISOString(); }

  function safeParse(raw, fallback) {
    if (!raw) return fallback;
    try {
      var v = JSON.parse(raw);
      return (v && typeof v === 'object') ? v : fallback;
    } catch (e) { return fallback; }
  }

  function FS() {
    this._files = null;
    this._listeners = [];
    this.available = true;
    try {
      global.localStorage.setItem('pyterm.probe', '1');
      global.localStorage.removeItem('pyterm.probe');
    } catch (e) {
      this.available = false;
    }
    this._load();
  }

  FS.prototype._load = function () {
    var raw = null;
    if (this.available) {
      try { raw = global.localStorage.getItem(KEY); } catch (e) { raw = null; }
    }
    var data = safeParse(raw, null);
    if (!data || !data.files || !Object.keys(data.files).length) {
      this._files = {};
      var self = this;
      Object.keys(SEED).forEach(function (p) {
        self._files[p] = { content: SEED[p], mtime: nowIso() };
      });
      this._persist();
    } else {
      this._files = data.files;
    }
  };

  FS.prototype._persist = function () {
    if (!this.available) return;
    try {
      global.localStorage.setItem(KEY, JSON.stringify({ v: 1, files: this._files }));
    } catch (e) {
      // Quota depasse : on avertit sans perdre la session en cours.
      this._emit({ type: 'error', error: e });
    }
  };

  FS.prototype._emit = function (evt) {
    this._listeners.forEach(function (fn) {
      try { fn(evt); } catch (e) { /* un abonne ne doit pas casser les autres */ }
    });
  };

  FS.prototype.onChange = function (fn) { this._listeners.push(fn); };

  /** Normalise un chemin : pas de "/" initial, pas de doublons, pas de "..". */
  FS.prototype.normalize = function (path) {
    var parts = String(path || '').split('/')
      .map(function (s) { return s.trim(); })
      .filter(function (s) { return s && s !== '.' && s !== '..'; });
    return parts.join('/');
  };

  FS.prototype.list = function () {
    return Object.keys(this._files).sort(function (a, b) {
      var da = a.indexOf('/') >= 0, db = b.indexOf('/') >= 0;
      if (da !== db) return da ? 1 : -1;      // racine d'abord
      return a.localeCompare(b, 'fr');
    });
  };

  FS.prototype.exists = function (path) {
    return Object.prototype.hasOwnProperty.call(this._files, this.normalize(path));
  };

  FS.prototype.read = function (path) {
    var f = this._files[this.normalize(path)];
    return f ? f.content : null;
  };

  FS.prototype.stat = function (path) {
    var f = this._files[this.normalize(path)];
    return f ? { path: this.normalize(path), mtime: f.mtime, size: f.content.length } : null;
  };

  FS.prototype.write = function (path, content) {
    var p = this.normalize(path);
    if (!p) return null;
    var isNew = !this.exists(p);
    this._files[p] = { content: String(content == null ? '' : content), mtime: nowIso() };
    this._persist();
    this._emit({ type: isNew ? 'create' : 'write', path: p });
    return p;
  };

  FS.prototype.remove = function (path) {
    var p = this.normalize(path);
    if (!this.exists(p)) return false;
    delete this._files[p];
    this._persist();
    this._emit({ type: 'remove', path: p });
    return true;
  };

  FS.prototype.rename = function (from, to) {
    var a = this.normalize(from), b = this.normalize(to);
    if (!this.exists(a) || !b || a === b) return false;
    if (this.exists(b)) return false;
    this._files[b] = this._files[a];
    this._files[b].mtime = nowIso();
    delete this._files[a];
    this._persist();
    this._emit({ type: 'rename', path: b, from: a });
    return true;
  };

  /** Nom libre derive d'une base, ex. "sans-titre.py" -> "sans-titre-2.py". */
  FS.prototype.uniqueName = function (base) {
    var p = this.normalize(base) || 'sans-titre.py';
    if (!this.exists(p)) return p;
    var dot = p.lastIndexOf('.');
    var stem = dot > 0 ? p.slice(0, dot) : p;
    var ext = dot > 0 ? p.slice(dot) : '';
    for (var i = 2; i < 1000; i++) {
      var cand = stem + '-' + i + ext;
      if (!this.exists(cand)) return cand;
    }
    return stem + '-' + Date.now() + ext;
  };

  FS.prototype.toJSON = function () {
    return { v: 1, exported: nowIso(), files: this._files };
  };

  /** Fusionne un export ; renvoie le nombre de fichiers ecrits. */
  FS.prototype.importJSON = function (data, overwrite) {
    if (!data || !data.files) return 0;
    var n = 0, self = this;
    Object.keys(data.files).forEach(function (p) {
      var entry = data.files[p];
      var content = (entry && typeof entry === 'object') ? entry.content : entry;
      if (typeof content !== 'string') return;
      var target = self.normalize(p);
      if (!target) return;
      if (!overwrite && self.exists(target)) target = self.uniqueName(target);
      self._files[target] = { content: content, mtime: nowIso() };
      n++;
    });
    this._persist();
    this._emit({ type: 'bulk' });
    return n;
  };

  FS.prototype.resetAll = function () {
    this._files = {};
    if (this.available) {
      try { global.localStorage.removeItem(KEY); } catch (e) { /* ignore */ }
    }
    this._load();
    this._emit({ type: 'bulk' });
  };

  /* ---------------- Reglages ---------------- */

  /* Quand l'interface est servie par kernel.py, le noyau est sur la meme
     origine ; depuis un fichier local, on vise le port par defaut.        */
  function defaultKernelUrl() {
    try {
      if (/^https?:$/.test(global.location.protocol)) return global.location.origin;
    } catch (e) { /* environnement sans location */ }
    return 'http://127.0.0.1:8777';
  }

  var DEFAULTS = {
    theme: 'dark',
    backend: 'pyodide',
    kernelUrl: defaultKernelUrl(),
    fontSize: 14,
    tabSize: 4,
    wrap: false,
    saveBeforeRun: true,
    keybar: null,          // null = auto (actif sur ecran tactile)
    sidebarWidth: 250,
    panelHeight: 240,
    openTabs: null,
    activeFile: 'main.py'
  };

  var Settings = {
    _v: null,
    all: function () {
      if (!this._v) {
        var raw = null;
        try { raw = global.localStorage.getItem(SETTINGS_KEY); } catch (e) { raw = null; }
        var stored = safeParse(raw, {});
        this._v = {};
        Object.keys(DEFAULTS).forEach(function (k) {
          this._v[k] = Object.prototype.hasOwnProperty.call(stored, k) ? stored[k] : DEFAULTS[k];
        }, this);
      }
      return this._v;
    },
    get: function (k) { return this.all()[k]; },
    set: function (k, v) {
      this.all()[k] = v;
      try { global.localStorage.setItem(SETTINGS_KEY, JSON.stringify(this._v)); } catch (e) { /* ignore */ }
      return v;
    },
    defaults: DEFAULTS
  };

  global.PyFS = new FS();
  global.PySettings = Settings;
})(window);
