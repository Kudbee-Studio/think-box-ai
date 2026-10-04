// Window manager — pure layout/key/persistence logic (no DOM).
//
// The dashboard opens its panels as modals/drawers; the window manager turns them into floating windows. This file holds the
// parts that do not touch the DOM (key derivation, default placement, clamping, corrupt-safe localStorage serialization) so
// they are unit-testable in node; window-manager.js is the DOM layer that uses them.
//
// Loaded as a classic script in the browser (sets window.WindowManagerCore) and, in node tests, by importing the file
// (the guard below sets globalThis.WindowManagerCore and module.exports).
(function (root) {
  'use strict';

  function slugify(text) {
    var s = String(text == null ? '' : text)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 64);
    return s || 'window';
  }

  function clamp(n, min, max) {
    n = Number(n);
    if (!isFinite(n)) n = min;
    if (max < min) max = min;
    return Math.max(min, Math.min(max, n));
  }

  // Cascade new windows down the right side, never off the viewport.
  function defaultLayout(index, viewportWidth, viewportHeight) {
    var vw = Number(viewportWidth) > 0 ? Number(viewportWidth) : 1280;
    var vh = Number(viewportHeight) > 0 ? Number(viewportHeight) : 800;
    var w = Math.min(460, Math.max(300, Math.round(vw * 0.38)));
    var h = Math.min(360, Math.max(220, Math.round(vh * 0.46)));
    var step = ((index || 0) % 8) * 26;
    return {
      x: clamp(96 + step, 8, Math.max(8, vw - w - 8)),
      y: clamp(72 + step, 8, Math.max(8, vh - h - 64)),
      w: w,
      h: h,
      maximized: false,
      minimized: false,
      open: false,
      opener: null
    };
  }

  // Accept only a fully numeric layout; anything else is ignored so a corrupt entry cannot break a window.
  function normalizeLayout(raw) {
    if (!raw || typeof raw !== 'object') return null;
    var l = {
      x: Number(raw.x), y: Number(raw.y), w: Number(raw.w), h: Number(raw.h),
      maximized: !!raw.maximized, minimized: !!raw.minimized,
      open: !!raw.open,
      opener: typeof raw.opener === 'string' && raw.opener ? raw.opener : null
    };
    if (!isFinite(l.x) || !isFinite(l.y) || !isFinite(l.w) || !isFinite(l.h)) return null;
    l.w = Math.max(220, l.w);
    l.h = Math.max(120, l.h);
    return l;
  }

  function parseLayouts(json) {
    var out = {};
    try {
      var parsed = JSON.parse(json || '{}');
      if (parsed && typeof parsed === 'object') {
        for (var key in parsed) {
          if (Object.prototype.hasOwnProperty.call(parsed, key)) {
            var l = normalizeLayout(parsed[key]);
            if (l) out[key] = l;
          }
        }
      }
    } catch (err) {
      // A corrupt store is treated as empty; the next write replaces it.
    }
    return out;
  }

  function serializeLayouts(map) {
    var out = {};
    map = map || {};
    for (var key in map) {
      if (Object.prototype.hasOwnProperty.call(map, key)) {
        out[key] = {
          x: map[key].x, y: map[key].y, w: map[key].w, h: map[key].h,
          maximized: !!map[key].maximized, minimized: !!map[key].minimized,
          open: !!map[key].open,
          opener: typeof map[key].opener === 'string' ? map[key].opener : null
        };
      }
    }
    return JSON.stringify(out);
  }

  function resolveKey(id, title) {
    if (id) return String(id);
    return 'title:' + slugify(title);
  }

  var core = {
    slugify: slugify,
    clamp: clamp,
    defaultLayout: defaultLayout,
    normalizeLayout: normalizeLayout,
    parseLayouts: parseLayouts,
    serializeLayouts: serializeLayouts,
    resolveKey: resolveKey
  };

  root.WindowManagerCore = core;
  if (typeof module !== 'undefined' && module.exports) module.exports = core;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
