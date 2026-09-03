/* ==========================================================================
   terminal.js — console de sortie + historique du REPL
   ========================================================================== */
(function (global) {
  'use strict';

  var MAX_NODES = 900;          // au-dela, on elague le haut de la console
  var ANSI = /\x1b\[[0-9;?]*[ -\/]*[@-~]/g;

  function Terminal(outEl, inputEl, promptEl) {
    this.out = outEl;
    this.input = inputEl;
    this.promptEl = promptEl;
    this.history = [];
    this.hIndex = 0;
    this._buffer = { out: '', err: '' };
    this._flushTimer = null;
    this._loadHistory();
  }

  Terminal.prototype._loadHistory = function () {
    try {
      var raw = global.localStorage.getItem('pyterm.history.v1');
      var arr = raw ? JSON.parse(raw) : [];
      if (Array.isArray(arr)) this.history = arr.slice(-200);
    } catch (e) { this.history = []; }
    this.hIndex = this.history.length;
  };

  Terminal.prototype._saveHistory = function () {
    try {
      global.localStorage.setItem('pyterm.history.v1', JSON.stringify(this.history.slice(-200)));
    } catch (e) { /* quota : l'historique n'est pas critique */ }
  };

  Terminal.prototype.remember = function (line) {
    if (!line.trim()) return;
    if (this.history[this.history.length - 1] !== line) this.history.push(line);
    this.hIndex = this.history.length;
    this._saveHistory();
  };

  Terminal.prototype.recall = function (delta) {
    if (!this.history.length) return null;
    this.hIndex = Math.max(0, Math.min(this.history.length, this.hIndex + delta));
    return this.hIndex === this.history.length ? '' : this.history[this.hIndex];
  };

  /** Ajoute un noeud, en elaguant si la console devient trop longue. */
  Terminal.prototype._append = function (node) {
    var atBottom = this.out.scrollHeight - this.out.scrollTop - this.out.clientHeight < 60;
    this.out.appendChild(node);
    while (this.out.childNodes.length > MAX_NODES) this.out.removeChild(this.out.firstChild);
    if (atBottom) this.out.scrollTop = this.out.scrollHeight;
  };

  Terminal.prototype.write = function (text, cls) {
    if (text === '' || text == null) return;
    var span = document.createElement('span');
    span.className = 't-' + (cls || 'out');
    span.textContent = String(text).replace(ANSI, '');
    this._append(span);
  };

  Terminal.prototype.line = function (text, cls) {
    this.write(String(text) + '\n', cls);
  };

  /** Sorties du programme : regroupees par frame pour rester fluides. */
  Terminal.prototype.stream = function (text, channel) {
    var key = channel === 'err' ? 'err' : 'out';
    this._buffer[key] += String(text);
    if (this._flushTimer) return;
    var self = this;
    this._flushTimer = global.requestAnimationFrame(function () {
      self._flushTimer = null;
      if (self._buffer.out) { self.write(self._buffer.out, 'out'); self._buffer.out = ''; }
      if (self._buffer.err) { self.write(self._buffer.err, 'err'); self._buffer.err = ''; }
    });
  };

  Terminal.prototype.flush = function () {
    if (this._flushTimer) { global.cancelAnimationFrame(this._flushTimer); this._flushTimer = null; }
    if (this._buffer.out) { this.write(this._buffer.out, 'out'); this._buffer.out = ''; }
    if (this._buffer.err) { this.write(this._buffer.err, 'err'); this._buffer.err = ''; }
  };

  /** Ligne d'echo du REPL : ">>> expression". */
  Terminal.prototype.echo = function (text) {
    var span = document.createElement('span');
    span.className = 't-echo';
    var b = document.createElement('b');
    b.textContent = '>>> ';
    span.appendChild(b);
    span.appendChild(document.createTextNode(String(text) + '\n'));
    this._append(span);
  };

  /** Bandeau discret de debut d'execution. */
  Terminal.prototype.banner = function (text) {
    var span = document.createElement('span');
    span.className = 't-run';
    span.textContent = text + '\n';
    this._append(span);
  };

  Terminal.prototype.clear = function () {
    this.flush();
    this.out.textContent = '';
  };

  Terminal.prototype.setPrompt = function (text) {
    if (this.promptEl) this.promptEl.textContent = text;
  };

  Terminal.prototype.focus = function () {
    if (this.input) this.input.focus();
  };

  global.PyTerminal = Terminal;
})(window);
