/* ==========================================================================
   editor.js — enveloppe CodeMirror : un document par fichier ouvert
   ========================================================================== */
(function (global) {
  'use strict';

  var KEYWORDS = ('and as assert async await break class continue def del elif else except ' +
    'finally for from global if import in is lambda nonlocal not or pass raise return try ' +
    'while with yield True False None self print len range enumerate zip sorted sum min max ' +
    'abs round list dict set tuple str int float bool open input isinstance type dir help ' +
    'map filter any all reversed format repr').split(' ');

  function modeFor(path) {
    var p = String(path).toLowerCase();
    if (/\.(md|markdown)$/.test(p)) return 'markdown';
    if (/\.(json|js)$/.test(p)) return { name: 'javascript', json: /\.json$/.test(p) };
    if (/\.(txt|csv|log|cfg|ini)$/.test(p)) return null;
    return 'python';
  }

  function PyEditor(host, hooks) {
    this.hooks = hooks || {};
    this.docs = {};          // chemin -> CodeMirror.Doc
    this.current = null;
    this._errorMarks = [];

    var self = this;
    this.cm = global.CodeMirror(host, {
      value: '',
      mode: 'python',
      lineNumbers: true,
      indentUnit: 4,
      tabSize: 4,
      indentWithTabs: false,
      smartIndent: true,
      lineWrapping: false,
      matchBrackets: true,
      autoCloseBrackets: true,
      styleActiveLine: true,
      scrollbarStyle: 'native',
      inputStyle: 'textarea',
      extraKeys: this._keymap()
    });

    this.cm.on('change', function () {
      self.clearErrors();
      if (self.hooks.onChange) self.hooks.onChange(self.current, self.cm.getValue());
    });
    this.cm.on('cursorActivity', function () {
      var c = self.cm.getCursor();
      if (self.hooks.onCursor) self.hooks.onCursor(c.line + 1, c.ch + 1);
    });
  }

  PyEditor.prototype._keymap = function () {
    var self = this;
    var run = function () { if (self.hooks.onRun) self.hooks.onRun(); };
    var save = function () { if (self.hooks.onSave) self.hooks.onSave(); };
    return {
      'Ctrl-Enter': run,
      'Cmd-Enter': run,
      'Shift-Enter': run,
      'Ctrl-S': save,
      'Cmd-S': save,
      'Ctrl-/': function (cm) { cm.toggleComment({ indent: true }); },
      'Cmd-/': function (cm) { cm.toggleComment({ indent: true }); },
      'Ctrl-D': function (cm) { self.duplicateLine(cm); },
      'Cmd-D': function (cm) { self.duplicateLine(cm); },
      'Alt-Up': function (cm) { self.moveLine(cm, -1); },
      'Alt-Down': function (cm) { self.moveLine(cm, 1); },
      'Ctrl-Space': function (cm) { self.complete(cm); },
      'Tab': function (cm) {
        if (cm.somethingSelected()) { cm.indentSelection('add'); return; }
        cm.replaceSelection(new Array(cm.getOption('indentUnit') + 1).join(' '), 'end');
      },
      'Shift-Tab': function (cm) { cm.indentSelection('subtract'); },
      'Ctrl-P': function () { if (self.hooks.onPalette) self.hooks.onPalette(); },
      'Cmd-P': function () { if (self.hooks.onPalette) self.hooks.onPalette(); }
    };
  };

  PyEditor.prototype.duplicateLine = function (cm) {
    var c = cm.getCursor();
    var text = cm.getLine(c.line);
    cm.replaceRange('\n' + text, { line: c.line, ch: text.length });
    cm.setCursor({ line: c.line + 1, ch: c.ch });
  };

  PyEditor.prototype.moveLine = function (cm, dir) {
    var c = cm.getCursor();
    var target = c.line + dir;
    if (target < 0 || target >= cm.lineCount()) return;
    var a = cm.getLine(c.line), b = cm.getLine(target);
    cm.replaceRange(b, { line: c.line, ch: 0 }, { line: c.line, ch: a.length });
    cm.replaceRange(a, { line: target, ch: 0 }, { line: target, ch: b.length });
    cm.setCursor({ line: target, ch: c.ch });
  };

  /** Completion : mots du document + mots-cles Python. */
  PyEditor.prototype.complete = function (cm) {
    var hint = global.CodeMirror.hint;
    if (!hint || !hint.anyword) return;
    cm.showHint({
      completeSingle: false,
      hint: function (editor, options) {
        var res = hint.anyword(editor, options) || { list: [], from: editor.getCursor(), to: editor.getCursor() };
        var cur = editor.getCursor();
        var token = editor.getTokenAt(cur);
        var word = (token.string || '').trim();
        if (word) {
          KEYWORDS.forEach(function (k) {
            if (k.indexOf(word) === 0 && res.list.indexOf(k) < 0) res.list.push(k);
          });
        }
        res.list.sort();
        return res;
      }
    });
  };

  PyEditor.prototype.open = function (path, content) {
    if (!this.docs[path]) {
      this.docs[path] = global.CodeMirror.Doc(content == null ? '' : content, modeFor(path));
    }
    if (this.current === path) return;
    this.cm.swapDoc(this.docs[path]);
    this.cm.setOption('mode', modeFor(path));
    this.current = path;
    this.clearErrors();
    this.cm.refresh();
  };

  PyEditor.prototype.close = function (path) {
    delete this.docs[path];
    if (this.current === path) this.current = null;
  };

  PyEditor.prototype.rename = function (from, to) {
    if (!this.docs[from]) return;
    this.docs[to] = this.docs[from];
    delete this.docs[from];
    if (this.current === from) { this.current = to; this.cm.setOption('mode', modeFor(to)); }
  };

  PyEditor.prototype.value = function (path) {
    if (!path || path === this.current) return this.cm.getValue();
    return this.docs[path] ? this.docs[path].getValue() : null;
  };

  PyEditor.prototype.setValue = function (text) {
    this.cm.setValue(text == null ? '' : text);
  };

  PyEditor.prototype.insert = function (text) {
    this.cm.replaceSelection(text, 'end');
    this.cm.focus();
  };

  PyEditor.prototype.markError = function (line) {
    if (!line || line < 1 || line > this.cm.lineCount()) return;
    var handle = this.cm.addLineClass(line - 1, 'background', 'cm-err-line');
    this._errorMarks.push(handle);
    this.cm.scrollIntoView({ line: line - 1, ch: 0 }, 80);
  };

  PyEditor.prototype.clearErrors = function () {
    var self = this;
    this._errorMarks.forEach(function (h) {
      try { self.cm.removeLineClass(h, 'background', 'cm-err-line'); } catch (e) { /* ligne disparue */ }
    });
    this._errorMarks = [];
  };

  PyEditor.prototype.goTo = function (line) {
    this.cm.setCursor({ line: Math.max(0, line - 1), ch: 0 });
    this.cm.scrollIntoView({ line: Math.max(0, line - 1), ch: 0 }, 100);
    this.cm.focus();
  };

  PyEditor.prototype.applySettings = function (s) {
    this.cm.setOption('tabSize', s.tabSize);
    this.cm.setOption('indentUnit', s.tabSize);
    this.cm.setOption('lineWrapping', !!s.wrap);
    this.cm.getWrapperElement().style.setProperty('--editor-fs', s.fontSize + 'px');
    document.documentElement.style.setProperty('--editor-fs', s.fontSize + 'px');
    this.cm.refresh();
  };

  PyEditor.prototype.refresh = function () { this.cm.refresh(); };
  PyEditor.prototype.focus = function () { this.cm.focus(); };

  global.PyEditor = PyEditor;
})(window);
