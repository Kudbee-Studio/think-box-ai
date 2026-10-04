// Window manager — turns the dashboard's panels (modals/drawers) into floating, draggable, resizable windows with a taskbar.
//
// The panels keep creating and toggling their own .modal-backdrop elements; this script observes the DOM and adopts each
// visible modal into a window (title bar with minimize/maximize/close, drag, resize, z-index focus). It never rewrites a
// panel's internals: closing a window clicks the panel's own close control, so the panel's cleanup still runs.
//
// Classic script (shares the global scope with the panel scripts). No inline HTML strings: chrome is built with
// createElement/textContent, so no panel or window title is ever interpolated into markup.
(function (root) {
  'use strict';

  var Core = root.WindowManagerCore;
  var LAYOUT_KEY = 'kudbee.windowmanager.layout.v1';
  var TASKBAR_HEIGHT = 40;
  var MIN_W = 220;
  var MIN_H = 120;

  function WindowManager(options) {
    options = options || {};
    this.doc = options.document || root.document;
    this.win = options.window || root;
    this.storage = options.storage || root.localStorage;
    this.selectors = options.selectors || ['.modal-backdrop', '.panel[id$="-panel"]'];
    this.skip = options.skip || { 'approval-modal': true };
    this.windows = {};
    this.zTop = 1000;
    this.pendingOpener = null;
    this.active = null;
    this.layouts = Core.parseLayouts(this._read());
    this.observer = null;
    this.taskbar = null;
    this.taskbarWindows = null;
    this.persistent = {};
  }

  WindowManager.prototype._vw = function () { return (this.win && this.win.innerWidth) || 1280; };
  WindowManager.prototype._vh = function () { return (this.win && this.win.innerHeight) || 800; };
  // A panel may ask for a larger first-open window with data-wm-size="WIDTHxHEIGHT" (the workflow builder is three columns wide).
  WindowManager.prototype._sizeHint = function (el, layout) {
    var m = el && el.dataset && el.dataset.wmSize ? /^(\d{3,4})x(\d{3,4})$/.exec(el.dataset.wmSize) : null;
    if (!m) return layout;
    layout.w = Core.clamp(Number(m[1]), MIN_W, Math.max(MIN_W, this._vw() - 16));
    layout.h = Core.clamp(Number(m[2]), MIN_H, Math.max(MIN_H, this._vh() - TASKBAR_HEIGHT - 16));
    layout.x = Core.clamp(layout.x, 0, Math.max(0, this._vw() - layout.w));
    layout.y = Core.clamp(layout.y, 0, Math.max(0, this._vh() - TASKBAR_HEIGHT - layout.h));
    return layout;
  };

  // Where the page header ends: new windows open below it so they never cover the buttons that open the next window.
  WindowManager.prototype._topOffset = function () {
    var header = this.doc.querySelector ? this.doc.querySelector('header') : null;
    var rect = header && header.getBoundingClientRect ? header.getBoundingClientRect() : null;
    return rect && rect.bottom > 0 ? Math.min(Math.round(rect.bottom) + 12, Math.round(this._vh() / 3)) : 72;
  };

  WindowManager.prototype._read = function () {
    try { return this.storage ? this.storage.getItem(LAYOUT_KEY) : null; } catch (err) { return null; }
  };
  WindowManager.prototype._write = function () {
    try { if (this.storage) this.storage.setItem(LAYOUT_KEY, Core.serializeLayouts(this.layouts)); } catch (err) { /* storage full/blocked: positions just will not persist */ }
  };

  WindowManager.prototype._count = function () { return Object.keys(this.windows).length; };

  WindowManager.prototype._matches = function (el) {
    if (!el || el.nodeType !== 1) return false;
    for (var i = 0; i < this.selectors.length; i++) {
      var sel = this.selectors[i];
      if (typeof el.matches === 'function') {
        try { if (el.matches(sel)) return true; } catch (err) { /* invalid selector: fall through */ }
      } else if (el.classList && el.classList.contains(sel.replace(/^\./, ''))) {
        return true;
      }
    }
    return false;
  };

  WindowManager.prototype._visible = function (el) {
    if (!el) return false;
    if (el.hidden) return false;
    if (el.style && el.style.display === 'none') return false;
    if (typeof el.getAttribute === 'function' && el.getAttribute('aria-hidden') === 'true') return false;
    return true;
  };

  WindowManager.prototype._titleOf = function (el) {
    var node = el.querySelector && (el.querySelector('h2') || el.querySelector('h3') || el.querySelector('.modal-eyebrow'));
    var text = node && node.textContent ? String(node.textContent).trim() : '';
    return text || (el.getAttribute && el.getAttribute('data-window-title')) || el.id || 'Window';
  };

  WindowManager.prototype._keyOf = function (el, title) {
    if (el.dataset && el.dataset.wmKey) return el.dataset.wmKey;
    return Core.resolveKey(el.id, title || this._titleOf(el));
  };

  WindowManager.prototype.getLayout = function (key) {
    var rec = this.windows[key];
    return rec ? rec.layout : (this.layouts[key] || null);
  };
  WindowManager.prototype.getState = function () {
    var self = this;
    return Object.keys(this.windows).map(function (key) {
      var rec = self.windows[key];
      return { key: key, title: rec.title, opener: rec.opener, x: rec.layout.x, y: rec.layout.y, w: rec.layout.w, h: rec.layout.h, minimized: !!rec.layout.minimized, maximized: !!rec.layout.maximized };
    });
  };

  // ── chrome ──────────────────────────────────────────────────────────────

  WindowManager.prototype._control = function (cls, label, glyph) {
    var b = this.doc.createElement('button');
    b.className = 'wm-btn ' + cls;
    b.setAttribute('type', 'button');
    b.setAttribute('title', label);
    b.setAttribute('aria-label', label);
    b.textContent = glyph;
    return b;
  };

  WindowManager.prototype._buildChrome = function (rec) {
    var el = rec.el;
    var bar = this.doc.createElement('div');
    bar.className = 'wm-titlebar';
    var title = this.doc.createElement('span');
    title.className = 'wm-title';
    title.textContent = rec.title;
    var controls = this.doc.createElement('span');
    controls.className = 'wm-controls';
    var min = this._control('wm-min', 'Minimize', '\u2013');
    var max = this._control('wm-max', 'Maximize', '\u25A1');
    var close = this._control('wm-close', 'Close', '\u00D7');
    controls.appendChild(min);
    controls.appendChild(max);
    controls.appendChild(close);
    bar.appendChild(title);
    bar.appendChild(controls);
    el.insertBefore(bar, el.firstChild);
    var grip = this.doc.createElement('div');
    grip.className = 'wm-resize';
    grip.setAttribute('aria-hidden', 'true');
    el.appendChild(grip);
    rec.chrome = { bar: bar, min: min, max: max, close: close, grip: grip };
    this._wire(rec);
  };

  WindowManager.prototype._wire = function (rec) {
    var self = this;
    var key = rec.key;
    var c = rec.chrome;
    c.min.addEventListener('click', function (e) { e.stopPropagation && e.stopPropagation(); self.toggleMinimize(key); });
    c.max.addEventListener('click', function (e) { e.stopPropagation && e.stopPropagation(); self.toggleMaximize(key); });
    c.close.addEventListener('click', function (e) { e.stopPropagation && e.stopPropagation(); self.close(key); });
    c.bar.addEventListener('mousedown', function (e) {
      var t = e.target;
      if (t && t.closest && t.closest('.wm-btn')) return;
      self._startDrag(rec, e);
    });
    c.grip.addEventListener('mousedown', function (e) { self._startResize(rec, e); });
    rec.el.addEventListener('mousedown', function () { self.raise(key); });
  };

  WindowManager.prototype._applyPosition = function (rec) {
    var l = rec.layout;
    rec.el.style.left = l.x + 'px';
    rec.el.style.top = l.y + 'px';
    rec.el.style.width = l.w + 'px';
  };

  WindowManager.prototype._applyLayout = function (rec) {
    var el = rec.el;
    var l = rec.layout;
    if (l.maximized) {
      if (el.classList) el.classList.add('wm-maximized');
      el.style.left = '0px';
      el.style.top = '0px';
      el.style.width = '100vw';
      el.style.height = 'calc(100vh - ' + TASKBAR_HEIGHT + 'px)';
    } else {
      if (el.classList) el.classList.remove('wm-maximized');
      // A layout saved on a wider screen must not leave the window hanging off a narrower one.
      l.w = Core.clamp(l.w, MIN_W, Math.max(MIN_W, this._vw()));
      l.x = Core.clamp(l.x, 0, Math.max(0, this._vw() - l.w));
      this._applyPosition(rec);
      el.style.height = l.h + 'px';
    }
    if (el.classList) el.classList.toggle('wm-minimized', !!l.minimized);
  };

  // ── window operations ───────────────────────────────────────────────────

  WindowManager.prototype.adopt = function (el, opts) {
    if (!el || !this._matches(el) || !this._visible(el)) return null;
    if (el.id && this.skip[el.id]) return null;
    if (el.dataset && el.dataset.wmManaged === '1') return this._keyOf(el);
    var title = (opts && opts.title) || this._titleOf(el);
    var key = this._keyOf(el, title);
    if (el.dataset) el.dataset.wmKey = key;
    if (el.dataset) el.dataset.wmManaged = '1';
    if (el.classList) el.classList.add('wm-managed');
    // A second element for the same panel (a reopen that raced the close) is dropped, not shown twice.
    if (this.windows[key] && this.windows[key].el !== el) {
      this._drop(el);
      return key;
    }
    var saved = this.layouts[key];
    var rec = {
      key: key,
      el: el,
      title: title,
      // A saved layout remembers its own opener: restore() clicks several openers in one tick, so the shared pendingOpener would land on the wrong window.
      opener: (saved && saved.opener) || this.pendingOpener || null,
      layout: saved ? Core.normalizeLayout(saved) : this._sizeHint(el, Core.defaultLayout(this._count(), this._vw(), this._vh(), this._topOffset())),
      restore: null
    };
    rec.layout = rec.layout || Core.defaultLayout(this._count(), this._vw(), this._vh(), this._topOffset());
    this.pendingOpener = null;
    this.windows[key] = rec;
    rec.layout.open = true;
    this._buildChrome(rec);
    this._applyLayout(rec);
    this.raise(key);
    this._save(key);
    this._syncTaskbar();
    return key;
  };

  WindowManager.prototype._drop = function (el) {
    try { if (el.remove) el.remove(); else el.hidden = true; } catch (err) { /* ignore */ }
  };

  WindowManager.prototype.unadopt = function (el) {
    if (!el || !el.dataset || !el.dataset.wmKey) return;
    var key = el.dataset.wmKey;
    if (this.windows[key] && this.windows[key].el === el) {
      var rec = this.windows[key];
      delete this.windows[key];
      if (this.layouts[key]) { this.layouts[key].open = false; this._write(); }
      if (this.active === key) this.active = null;
      // A panel that stays in the page (closed by hiding it) must not keep its "managed" marker or the next open would be skipped:
      // no registry entry, no taskbar item, dead title-bar buttons. Strip the chrome so the next adopt() starts clean.
      if (rec.chrome && el.parentNode) this._stripChrome(rec);
    }
    this._syncTaskbar();
  };

  WindowManager.prototype._stripChrome = function (rec) {
    var el = rec.el;
    var c = rec.chrome;
    try {
      if (c.bar && c.bar.parentNode) c.bar.parentNode.removeChild(c.bar);
      if (c.grip && c.grip.parentNode) c.grip.parentNode.removeChild(c.grip);
    } catch (err) { /* ignore */ }
    if (el.dataset) { delete el.dataset.wmManaged; }
    if (el.classList) { el.classList.remove('wm-managed'); el.classList.remove('wm-active'); el.classList.remove('wm-minimized'); el.classList.remove('wm-maximized'); }
    if (el.style) { el.style.left = ''; el.style.top = ''; el.style.width = ''; el.style.height = ''; el.style.zIndex = ''; }
    rec.chrome = null;
  };

  WindowManager.prototype.close = function (key) {
    var rec = this.windows[key];
    if (!rec) return false;
    rec.layout.open = false;
    this._save(key);
    var target = this._closeTarget(rec.el);
    if (target && typeof target.click === 'function') {
      target.click();
      // If the panel has no handler (or removed a persistent node) finish the job ourselves.
      if (this.windows[key] && this.windows[key].el === rec.el && rec.el.hidden !== true && !(rec.el.parentNode === null)) {
        if (rec.el.dataset && rec.el.dataset.wmPersistent === '1') rec.el.hidden = true;
        else this._drop(rec.el);
      }
    } else if (rec.el.dataset && rec.el.dataset.wmPersistent === '1') {
      rec.el.hidden = true;
    } else {
      this._drop(rec.el);
    }
    this.unadopt(rec.el);
    return true;
  };

  WindowManager.prototype._closeTarget = function (el) {
    return el.querySelector && (el.querySelector('[data-action="close"]') || el.querySelector('[id^="close-"]'));
  };

  WindowManager.prototype.raise = function (key) {
    var rec = this.windows[key];
    if (!rec) return;
    rec.el.style.zIndex = String(++this.zTop);
    if (this.active && this.windows[this.active]) this.windows[this.active].el.classList.remove('wm-active');
    this.active = key;
    if (rec.el.classList) rec.el.classList.add('wm-active');
    this._syncTaskbar();
  };

  WindowManager.prototype.toggleMinimize = function (key) {
    var rec = this.windows[key];
    if (!rec) return;
    rec.layout.minimized = !rec.layout.minimized;
    this._applyLayout(rec);
    this._save(key);
    this._syncTaskbar();
  };

  WindowManager.prototype.toggleMaximize = function (key) {
    var rec = this.windows[key];
    if (!rec) return;
    if (!rec.layout.maximized) {
      rec.restore = { x: rec.layout.x, y: rec.layout.y, w: rec.layout.w, h: rec.layout.h };
      rec.layout.maximized = true;
    } else {
      rec.layout.maximized = false;
      if (rec.restore) { rec.layout.x = rec.restore.x; rec.layout.y = rec.restore.y; rec.layout.w = rec.restore.w; rec.layout.h = rec.restore.h; }
    }
    this._applyLayout(rec);
    this._save(key);
  };

  WindowManager.prototype.dragTo = function (key, x, y) {
    var rec = this.windows[key];
    if (!rec) return;
    var l = rec.layout;
    l.maximized = false;
    if (rec.el.classList) rec.el.classList.remove('wm-maximized');
    l.x = Core.clamp(x, 0, Math.max(0, this._vw() - l.w));
    l.y = Core.clamp(y, 0, Math.max(0, this._vh() - TASKBAR_HEIGHT - 40));
    this._applyPosition(rec);
  };

  WindowManager.prototype.resizeTo = function (key, w, h) {
    var rec = this.windows[key];
    if (!rec) return;
    rec.layout.maximized = false;
    rec.layout.w = Core.clamp(w, MIN_W, Math.max(MIN_W, this._vw()));
    rec.layout.h = Core.clamp(h, MIN_H, Math.max(MIN_H, this._vh() - TASKBAR_HEIGHT));
    rec.layout.x = Core.clamp(rec.layout.x, 0, Math.max(0, this._vw() - rec.layout.w));
    this._applyLayout(rec);
  };

  WindowManager.prototype._save = function (key) {
    var rec = this.windows[key];
    if (!rec) return;
    this.layouts[key] = {
      x: rec.layout.x, y: rec.layout.y, w: rec.layout.w, h: rec.layout.h,
      maximized: !!rec.layout.maximized, minimized: !!rec.layout.minimized,
      open: !!rec.layout.open, opener: rec.opener || null
    };
    this._write();
  };

  WindowManager.prototype._pointer = function (rec, startEvent, onMove, onDone) {
    var self = this;
    var doc = this.doc;
    var move = function (e) { onMove(e); };
    var up = function (e) {
      if (doc.removeEventListener) { doc.removeEventListener('mousemove', move); doc.removeEventListener('mouseup', up); }
      self._save(rec.key);
      if (onDone) onDone(e);
    };
    if (doc.addEventListener) { doc.addEventListener('mousemove', move); doc.addEventListener('mouseup', up); }
    if (startEvent && startEvent.preventDefault) startEvent.preventDefault();
  };

  WindowManager.prototype._startDrag = function (rec, e) {
    var sx = e.clientX || 0, sy = e.clientY || 0;
    var ox = rec.layout.x, oy = rec.layout.y;
    var self = this;
    this._pointer(rec, e, function (ev) { self.dragTo(rec.key, ox + ((ev.clientX || 0) - sx), oy + ((ev.clientY || 0) - sy)); });
  };

  WindowManager.prototype._startResize = function (rec, e) {
    var sx = e.clientX || 0, sy = e.clientY || 0;
    var ow = rec.layout.w, oh = rec.layout.h;
    var self = this;
    this._pointer(rec, e, function (ev) { self.resizeTo(rec.key, ow + ((ev.clientX || 0) - sx), oh + ((ev.clientY || 0) - sy)); });
  };

  // ── taskbar ─────────────────────────────────────────────────────────────

  WindowManager.prototype.buildTaskbar = function () {
    if (this.taskbar) return;
    var doc = this.doc;
    var bar = doc.createElement('div');
    bar.id = 'wm-taskbar';
    bar.className = 'wm-taskbar';
    bar.setAttribute('role', 'toolbar');
    bar.setAttribute('aria-label', 'Open windows and running agents');
    var wins = doc.createElement('div');
    wins.className = 'wm-taskbar-windows';
    wins.id = 'wm-taskbar-windows';
    var agents = doc.createElement('div');
    agents.className = 'wm-taskbar-agents';
    agents.id = 'wm-taskbar-agents';
    var dot = doc.createElement('span');
    dot.className = 'wm-agent-dot';
    dot.setAttribute('aria-hidden', 'true');
    var label = doc.createElement('span');
    label.className = 'wm-agent-label';
    label.textContent = 'Agents';
    var empty = doc.createElement('span');
    empty.className = 'wm-agent-empty';
    empty.textContent = 'none running';
    agents.appendChild(dot);
    agents.appendChild(label);
    agents.appendChild(empty);
    bar.appendChild(wins);
    bar.appendChild(agents);
    doc.body.appendChild(bar);
    this.taskbar = bar;
    this.taskbarWindows = wins;
    this._syncTaskbar();
  };

  WindowManager.prototype._syncTaskbar = function () {
    if (!this.taskbarWindows) return;
    var self = this;
    var container = this.taskbarWindows;
    var keys = Object.keys(this.windows);
    // Rebuilding the taskbar mutates the document the observer watches; skip the rebuild when nothing it shows changed,
    // otherwise every rebuild would trigger another one and the page would never yield.
    var signature = keys.map(function (k) { var r = self.windows[k]; return [k, r.title, self.active === k ? 1 : 0, r.layout.minimized ? 1 : 0].join('\u0001'); }).join('\u0002');
    if (signature === this._taskbarSignature) return;
    this._taskbarSignature = signature;
    while (container.firstChild) container.removeChild(container.firstChild);
    var empty = this.doc.createElement('span');
    empty.className = 'wm-taskbar-empty';
    empty.textContent = keys.length ? '' : 'No windows open';
    container.appendChild(empty);
    keys.forEach(function (key) {
      var rec = self.windows[key];
      var item = self.doc.createElement('div');
      item.className = 'wm-task-item' + (self.active === key ? ' is-active' : '') + (rec.layout.minimized ? ' is-minimized' : '');
      var open = self.doc.createElement('button');
      open.type = 'button';
      open.className = 'wm-task-open';
      open.setAttribute('title', rec.title);
      open.textContent = rec.title;
      open.addEventListener('click', function () { if (rec.layout.minimized) self.toggleMinimize(key); self.raise(key); });
      var shut = self.doc.createElement('button');
      shut.type = 'button';
      shut.className = 'wm-task-close';
      shut.setAttribute('title', 'Close ' + rec.title);
      shut.setAttribute('aria-label', 'Close ' + rec.title);
      shut.textContent = '\u00D7';
      shut.addEventListener('click', function (e) { if (e.stopPropagation) e.stopPropagation(); self.close(key); });
      item.appendChild(open);
      item.appendChild(shut);
      container.appendChild(item);
    });
  };

  // ── toggle header buttons ───────────────────────────────────────────────

  WindowManager.prototype.keyForOpener = function (buttonId) {
    var keys = Object.keys(this.windows);
    for (var i = 0; i < keys.length; i++) if (this.windows[keys[i]].opener === buttonId) return keys[i];
    return null;
  };

  // Capture-phase: a header button whose window is open closes it and suppresses the panel's own "open" click.
  WindowManager.prototype._onCaptureClick = function (e) {
    var target = e.target;
    var btn = target && target.closest ? target.closest('header button[id$="-button"]') : null;
    if (!btn || !btn.id) return;
    var openKey = this.keyForOpener(btn.id);
    if (openKey) {
      this.close(openKey);
      if (e.stopImmediatePropagation) e.stopImmediatePropagation();
      if (e.preventDefault) e.preventDefault();
      return;
    }
    this.pendingOpener = btn.id;
    var self = this;
    if (typeof setTimeout === 'function') setTimeout(function () { if (self.pendingOpener === btn.id) self.pendingOpener = null; }, 0);
  };

  // ── adopt existing/open modals ──────────────────────────────────────────

  WindowManager.prototype.scan = function () {
    for (var s = 0; s < this.selectors.length; s++) {
      var nodes = this.doc.querySelectorAll ? this.doc.querySelectorAll(this.selectors[s]) : [];
      for (var i = 0; i < nodes.length; i++) if (this._visible(nodes[i])) this.adopt(nodes[i]);
    }
    this._syncTaskbar();
  };

  // Reopen the windows that were open at the last unload. Clicking the opener button runs the panel's own open path,
  // so the panel builds its content and the observer adopts the new modal at its saved position.
  WindowManager.prototype.restore = function () {
    if (this._restored) return;
    this._restored = true;
    var keys = Object.keys(this.layouts);
    for (var i = 0; i < keys.length; i++) {
      var l = this.layouts[keys[i]];
      if (!l || !l.open || !l.opener) continue;
      var btn = this.doc.getElementById ? this.doc.getElementById(l.opener) : null;
      if (btn && typeof btn.click === 'function') btn.click();
    }
  };

  WindowManager.prototype._onMutations = function (records) {
    for (var r = 0; r < records.length; r++) {
      var rec = records[r];
      if (this.taskbar && rec.target && this.taskbar.contains && this.taskbar.contains(rec.target)) continue; // our own taskbar edits
      if (rec.type === 'childList') {
        var added = rec.addedNodes || [];
        for (var a = 0; a < added.length; a++) if (a in added || added[a]) this._scanNode(added[a]);
        var removed = rec.removedNodes || [];
        for (var d = 0; d < removed.length; d++) if (d in removed || removed[d]) this.unadopt(removed[d]);
      } else if (rec.type === 'attributes' && rec.target) {
        var el = rec.target;
        var key = el.dataset && el.dataset.wmKey;
        if (key && this.windows[key] && this.windows[key].el === el) {
          if (this._visible(el)) this.adopt(el); else this.unadopt(el);
        } else if (this._matches(el) && this._visible(el)) {
          this.adopt(el);
        }
      }
    }
    this._syncTaskbar();
  };

  WindowManager.prototype._scanNode = function (node) {
    if (!node || node.nodeType !== 1) return;
    if (this._matches(node) && this._visible(node)) this.adopt(node);
    for (var s = 0; s < this.selectors.length; s++) {
      var nodes = node.querySelectorAll ? node.querySelectorAll(this.selectors[s]) : [];
      for (var i = 0; i < nodes.length; i++) if (this._visible(nodes[i])) this.adopt(nodes[i]);
    }
  };

  WindowManager.prototype.markPersistent = function () {
    for (var s = 0; s < this.selectors.length; s++) {
      var nodes = this.doc.querySelectorAll ? this.doc.querySelectorAll(this.selectors[s]) : [];
      for (var i = 0; i < nodes.length; i++) if (nodes[i].dataset) nodes[i].dataset.wmPersistent = '1';
    }
  };

  WindowManager.prototype.install = function () {
    var self = this;
    this.buildTaskbar();
    this.markPersistent();
    this.scan();
    if (this.doc.addEventListener) this.doc.addEventListener('click', function (e) { self._onCaptureClick(e); }, true);
    if (this.win && this.win.addEventListener) this.win.addEventListener('resize', function () { Object.keys(self.windows).forEach(function (k) { self.dragTo(k, self.windows[k].layout.x, self.windows[k].layout.y); }); });
    // The observer must exist BEFORE restore(): restore clicks the saved panels open, and a panel nobody adopts stays a full-screen
    // backdrop that covers the whole dashboard.
    if (typeof root.MutationObserver === 'function' && this.doc.body) {
      this.observer = new root.MutationObserver(function (records) { self._onMutations(records); });
      this.observer.observe(this.doc.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden'] });
    }
    this.restore();
    this.scan();
  };

  root.WindowManager = WindowManager;
  if (root.document && root.document.addEventListener) {
    root.document.addEventListener('DOMContentLoaded', function () {
      if (!root.windowManager) {
        root.windowManager = new WindowManager({});
        root.windowManager.install();
      }
    });
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
