// Startup guard: the dashboard must never sit on a silent spinner.
// Boot needs two things: the live WebSocket connection and the model list that arrives with it. If either is missing after
// `timeoutMs`, or any uncaught error / unhandled rejection happens while booting, a visible error panel names what failed
// and offers Retry. The panel disappears by itself if the missing piece shows up later.
(function (root) {
  'use strict';

  var REQUIRED = { connection: 'live connection to the server (WebSocket)', models: 'model list' };

  function StartupGuard(options) {
    options = options || {};
    this.doc = options.document || root.document;
    this.win = options.window || root;
    this.timeoutMs = options.timeoutMs || 5000;
    this.retry = options.retry || (this.win.location ? function () { this.win.location.reload(); }.bind(this) : function () {});
    this.ready = {};
    this.errors = [];
    this.panel = null;
    this.timer = null;
  }

  StartupGuard.prototype.install = function () {
    var self = this;
    this.timer = setTimeout(function () { self.render(); }, this.timeoutMs);
    if (this.win.addEventListener) {
      this.win.addEventListener('error', function (e) { self.fail('script error', (e && (e.message || (e.error && e.error.message))) || 'unknown error'); });
      this.win.addEventListener('unhandledrejection', function (e) { var r = e && e.reason; self.fail('unhandled error', (r && r.message) || String(r || 'unknown rejection')); });
    }
    return this;
  };

  StartupGuard.prototype.booted = function () {
    for (var k in REQUIRED) if (!this.ready[k]) return false;
    return true;
  };

  StartupGuard.prototype.ok = function (name) {
    this.ready[name] = true;
    if (this.booted()) {
      if (this.timer) { clearTimeout(this.timer); this.timer = null; }
      this.errors = [];
      this.clear();
    } else if (this.panel) {
      this.render();
    }
  };

  // Record a failure; during boot it is shown at once. After a successful boot an error is only logged by the browser.
  StartupGuard.prototype.fail = function (what, reason) {
    if (this.booted()) return;
    this.errors.push({ what: String(what), reason: String(reason).slice(0, 300) });
    this.render();
  };

  StartupGuard.prototype.missing = function () {
    var out = [];
    for (var k in REQUIRED) if (!this.ready[k]) out.push(k);
    return out;
  };

  StartupGuard.prototype.clear = function () {
    if (this.panel && this.panel.parentNode) this.panel.parentNode.removeChild(this.panel);
    this.panel = null;
  };

  StartupGuard.prototype.render = function () {
    if (this.booted()) return;
    var doc = this.doc;
    var self = this;
    if (!doc.body) { if (doc.addEventListener) doc.addEventListener('DOMContentLoaded', function () { self.render(); }); return; }
    if (!this.panel) {
      this.panel = doc.createElement('div');
      this.panel.id = 'startup-error';
      this.panel.className = 'startup-error';
      this.panel.setAttribute('role', 'alert');
      doc.body.appendChild(this.panel);
    }
    var panel = this.panel;
    while (panel.firstChild) panel.removeChild(panel.firstChild);
    var h = doc.createElement('h2');
    h.textContent = 'The dashboard could not finish loading';
    panel.appendChild(h);
    var list = doc.createElement('ul');
    this.missing().forEach(function (k) {
      var li = doc.createElement('li');
      li.textContent = 'Still waiting for the ' + REQUIRED[k] + '.';
      list.appendChild(li);
    });
    this.errors.forEach(function (e) {
      var li = doc.createElement('li');
      li.textContent = e.what + ': ' + e.reason;
      list.appendChild(li);
    });
    panel.appendChild(list);
    var hint = doc.createElement('p');
    hint.textContent = 'Check that the server is running at ' + (this.win.location ? this.win.location.origin : 'this address') + '/api/health, then retry.';
    panel.appendChild(hint);
    var btn = doc.createElement('button');
    btn.type = 'button';
    btn.id = 'startup-retry';
    btn.className = 'startup-retry';
    btn.textContent = 'Retry';
    btn.addEventListener('click', function () { self.retry(); });
    panel.appendChild(btn);
  };

  StartupGuard.REQUIRED = REQUIRED;
  root.StartupGuard = StartupGuard;
  if (root.document && root.document.addEventListener && root.location) {
    root.startupGuard = new StartupGuard({}).install();
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
