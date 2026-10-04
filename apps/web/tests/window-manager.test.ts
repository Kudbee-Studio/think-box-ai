// DOM behaviour for the window manager (public/js/window-manager.js), driven through a small fake DOM:
// three windows open at once, drag, focus, minimize/maximize, close/reopen and reload persistence.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const jsDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../public/js');

type Ev = { target?: unknown; clientX?: number; clientY?: number; stopPropagation?(): void; preventDefault?(): void; stopImmediatePropagation?(): void };
const ev = (target: unknown, x = 0, y = 0): Ev => ({ target, clientX: x, clientY: y, stopPropagation() {}, preventDefault() {}, stopImmediatePropagation() {} });

function matches(el: El, rawSel: string): boolean {
  const sel = rawSel.trim();
  if (sel.includes(' ')) {
    const parts = sel.split(/\s+/);
    if (!matches(el, parts[parts.length - 1])) return false;
    const need = parts.slice(0, -1);
    let i = need.length - 1;
    let n = el.parentNode;
    while (n && i >= 0) { if (matches(n, need[i])) i--; n = n.parentNode; }
    return i < 0;
  }
  if (sel.startsWith('#')) return el.id === sel.slice(1);
  const attrs: string[] = [];
  const rest = sel.replace(/\[[^\]]+\]/g, (m) => { attrs.push(m.slice(1, -1)); return ''; });
  const classes = [...rest.matchAll(/\.([\w-]+)/g)].map((x) => x[1]);
  const tag = (rest.match(/^[\w-]+/) || [])[0];
  if (tag && el.tagName.toLowerCase() !== tag.toLowerCase()) return false;
  for (const c of classes) if (!el.classList.contains(c)) return false;
  for (const a of attrs) {
    const m = a.match(/^([\w-]+)(?:([~^$*|]?=)"?([^"]*)"?)?$/);
    if (!m) continue;
    const name = m[1];
    const op = m[2];
    const val = m[3] ?? '';
    const actual = name === 'id' ? el.id : (el.getAttribute(name) ?? '');
    if (op === '^=') { if (!String(actual).startsWith(val)) return false; }
    else if (op === '$=') { if (!String(actual).endsWith(val)) return false; }
    else if (op === '=') { if (String(actual) !== val) return false; }
    else if (!op && actual == null) return false;
  }
  return true;
}

class El {
  tagName: string; nodeType = 1; parentNode: El | null = null;
  children: El[] = []; style: Record<string, string> = {}; dataset: Record<string, string> = {};
  hidden = false; textContent = ''; id = ''; type = '';
  private classes = new Set<string>();
  private attrs: Record<string, string> = {};
  private listeners: Record<string, Array<(e: Ev) => void>> = {};
  constructor(tag: string) { this.tagName = tag.toUpperCase(); }
  get className(): string { return [...this.classes].join(' '); }
  set className(v: string) { this.classes = new Set(String(v || '').split(/\s+/).filter(Boolean)); }
  get classList() {
    const s = this;
    return {
      add: (...c: string[]) => c.forEach((x) => s.classes.add(x)),
      remove: (...c: string[]) => c.forEach((x) => s.classes.delete(x)),
      contains: (c: string) => s.classes.has(c),
      toggle: (c: string, on?: boolean) => { if (on === undefined) (s.classes.has(c) ? s.classes.delete(c) : s.classes.add(c)); else (on ? s.classes.add(c) : s.classes.delete(c)); },
    };
  }
  get firstChild(): El | null { return this.children[0] || null; }
  appendChild(n: El): El { n.parentNode = this; this.children.push(n); return n; }
  insertBefore(n: El, ref: El | null): El { n.parentNode = this; const i = ref ? this.children.indexOf(ref) : -1; if (i < 0) this.children.push(n); else this.children.splice(i, 0, n); return n; }
  removeChild(n: El): El { const i = this.children.indexOf(n); if (i >= 0) { this.children.splice(i, 1); n.parentNode = null; } return n; }
  remove(): void { if (this.parentNode) this.parentNode.removeChild(this); }
  setAttribute(k: string, v: string): void { this.attrs[k] = String(v); if (k === 'id') this.id = String(v); }
  getAttribute(k: string): string | null { return k in this.attrs ? this.attrs[k] : null; }
  addEventListener(t: string, fn: (e: Ev) => void): void { (this.listeners[t] = this.listeners[t] || []).push(fn); }
  removeEventListener(t: string, fn: (e: Ev) => void): void { const a = this.listeners[t] || []; const i = a.indexOf(fn); if (i >= 0) a.splice(i, 1); }
  dispatch(t: string, e: Ev): void { (this.listeners[t] || []).slice().forEach((fn) => fn(e)); }
  click(): void { this.dispatch('click', ev(this)); }
  querySelector(sel: string): El | null { return this.findAll(sel)[0] || null; }
  querySelectorAll(sel: string): El[] { return this.findAll(sel); }
  closest(sel: string): El | null { let n: El | null = this; while (n) { if (matches(n, sel)) return n; n = n.parentNode; } return null; }
  matches(sel: string): boolean { return matches(this, sel); }
  findAll(sel: string): El[] { const out: El[] = []; const visit = (n: El) => { for (const c of n.children) { if (matches(c, sel)) out.push(c); visit(c); } }; visit(this); return out; }
}

class Doc {
  nodeType = 9; body: El;
  private listeners: Record<string, Array<(e: Ev) => void>> = {};
  constructor() { this.body = new El('body'); }
  createElement(t: string): El { return new El(t); }
  getElementById(id: string): El | null { return this.body.querySelector('#' + id); }
  querySelectorAll(sel: string): El[] { return this.body.querySelectorAll(sel); }
  addEventListener(t: string, fn: (e: Ev) => void): void { (this.listeners[t] = this.listeners[t] || []).push(fn); }
  removeEventListener(t: string, fn: (e: Ev) => void): void { const a = this.listeners[t] || []; const i = a.indexOf(fn); if (i >= 0) a.splice(i, 1); }
  dispatch(t: string, e: Ev): void { (this.listeners[t] || []).slice().forEach((fn) => fn(e)); }
}

class Storage {
  private m: Record<string, string> = {};
  getItem(k: string): string | null { return k in this.m ? this.m[k] : null; }
  setItem(k: string, v: string): void { this.m[k] = String(v); }
}

function boot(extra: Record<string, unknown> = {}): { WM: new (o: unknown) => unknown; doc: Doc; storage: Storage; win: { innerWidth: number; innerHeight: number; addEventListener(): void; removeEventListener(): void } } {
  const doc = new Doc();
  const storage = new Storage();
  const win = { innerWidth: 1200, innerHeight: 800, addEventListener() {}, removeEventListener() {} };
  const sandbox: Record<string, unknown> = { document: doc, localStorage: storage, console: { log() {}, warn() {}, error() {} }, setTimeout: () => 0, ...extra };
  vm.createContext(sandbox);
  sandbox.window = sandbox;
  for (const f of ['window-manager-core.js', 'window-manager.js']) vm.runInContext(fs.readFileSync(path.join(jsDir, f), 'utf8'), sandbox, { filename: f });
  return { WM: sandbox.WindowManager as new (o: unknown) => unknown, doc, storage, win };
}

function makeModal(doc: Doc, id: string, title: string): { el: El; close: El } {
  const el = doc.createElement('div');
  el.className = 'modal-backdrop';
  el.id = id;
  const h2 = doc.createElement('h2');
  h2.textContent = title;
  el.appendChild(h2);
  const close = doc.createElement('button');
  close.setAttribute('data-action', 'close');
  close.addEventListener('click', () => { el.remove(); });
  el.appendChild(close);
  doc.body.appendChild(el);
  return { el, close };
}

test('adopting a modal builds a title bar (min/max/close + resize) and a taskbar entry', () => {
  const { WM, doc, storage, win } = boot();
  const m: any = new WM({ document: doc, window: win, storage });
  m.buildTaskbar();
  const { el } = makeModal(doc, 'search-modal', 'Advanced Search');
  const key = m.adopt(el);
  assert.equal(key, 'search-modal');
  assert.equal(el.classList.contains('wm-managed'), true);
  assert.equal(el.querySelector('.wm-title')!.textContent, 'Advanced Search');
  assert.equal(el.querySelectorAll('.wm-btn').length, 3);
  assert.ok(el.querySelector('.wm-resize'));
  assert.equal(m.getState().length, 1);
  assert.equal(m.taskbar.querySelectorAll('.wm-task-item').length, 1);
  assert.ok(m.taskbar.querySelector('.wm-taskbar-agents'));
  assert.ok(m.taskbar.querySelector('.wm-agent-empty'));
});

test('three windows open at once and focus raises z-index', () => {
  const { WM, doc, storage, win } = boot();
  const m: any = new WM({ document: doc, window: win, storage });
  m.buildTaskbar();
  const a = makeModal(doc, 'search-modal', 'Advanced Search');
  const b = makeModal(doc, 'analytics-modal', 'Performance Analytics');
  const c = makeModal(doc, 'logs-modal', 'Execution Logs');
  const ka = m.adopt(a.el);
  const kb = m.adopt(b.el);
  const kc = m.adopt(c.el);
  assert.equal(m.getState().length, 3);
  assert.equal(m.taskbar.querySelectorAll('.wm-task-item').length, 3);
  assert.ok(Number(c.el.style.zIndex) > Number(b.el.style.zIndex));
  assert.ok(Number(b.el.style.zIndex) > Number(a.el.style.zIndex));
  m.raise(ka);
  assert.ok(Number(a.el.style.zIndex) > Number(c.el.style.zIndex));
  assert.equal(m.getState().map((s: { key: string }) => s.key).sort().join(','), [ka, kb, kc].sort().join(','));
});

test('a window drags with the title bar and resizes from the grip, clamped to the viewport', () => {
  const { WM, doc, storage, win } = boot();
  const m: any = new WM({ document: doc, window: win, storage });
  m.buildTaskbar();
  const a = makeModal(doc, 'search-modal', 'Advanced Search');
  const ka = m.adopt(a.el);
  const sx = m.getLayout(ka).x;
  const sy = m.getLayout(ka).y;
  const sw = m.getLayout(ka).w;
  const sh = m.getLayout(ka).h;
  const bar = a.el.querySelector('.wm-titlebar')!;
  bar.dispatch('mousedown', ev(bar, 100, 100));
  doc.dispatch('mousemove', ev(doc, 160, 140));
  doc.dispatch('mouseup', ev(doc, 160, 140));
  assert.equal(m.getLayout(ka).x, sx + 60);
  assert.equal(m.getLayout(ka).y, sy + 40);

  const grip = a.el.querySelector('.wm-resize')!;
  grip.dispatch('mousedown', ev(grip, 0, 0));
  doc.dispatch('mousemove', ev(doc, 120, 90));
  doc.dispatch('mouseup', ev(doc, 120, 90));
  assert.equal(m.getLayout(ka).w, sw + 120);
  assert.equal(m.getLayout(ka).h, sh + 90);

  m.dragTo(ka, -50, 99999);
  assert.ok(m.getLayout(ka).x >= 0 && m.getLayout(ka).y <= win.innerHeight);
});

test('minimize and maximize change the layout flags and size', () => {
  const { WM, doc, storage, win } = boot();
  const m: any = new WM({ document: doc, window: win, storage });
  m.buildTaskbar();
  const a = makeModal(doc, 'search-modal', 'Advanced Search');
  const ka = m.adopt(a.el);
  m.toggleMinimize(ka);
  assert.equal(m.getLayout(ka).minimized, true);
  assert.equal(a.el.classList.contains('wm-minimized'), true);
  m.toggleMinimize(ka);
  assert.equal(m.getLayout(ka).minimized, false);
  m.toggleMaximize(ka);
  assert.equal(m.getLayout(ka).maximized, true);
  assert.equal(a.el.style.width, '100vw');
  m.toggleMaximize(ka);
  assert.equal(m.getLayout(ka).maximized, false);
  assert.notEqual(a.el.style.width, '100vw');
});

test('closing uses the panel\u2019s own close control, and a reload restores the dragged position', () => {
  const { WM, doc, storage, win } = boot();
  const m: any = new WM({ document: doc, window: win, storage });
  m.buildTaskbar();
  const a = makeModal(doc, 'search-modal', 'Advanced Search');
  const ka = m.adopt(a.el);
  m.dragTo(ka, 333, 177);
  m.close(ka);
  assert.equal(m.getState().length, 0);
  assert.equal(a.el.parentNode, null, 'the panel close control removed the modal');

  // Reload: a fresh manager over the same storage restores the saved position.
  const { WM: WM2 } = boot();
  const m2: any = new (WM2 as new (o: unknown) => unknown)({ document: doc, window: win, storage });
  m2.buildTaskbar();
  const b = makeModal(doc, 'search-modal', 'Advanced Search');
  const kb = m2.adopt(b.el);
  assert.equal(m2.getLayout(kb).x, 333);
  assert.equal(m2.getLayout(kb).y, 177);
});

test('windows that were open at unload are restored at their saved position on the next load', () => {
  const storage = new Storage();
  const { WM, win } = boot();
  // First page load: the panel button creates its modal; the manager adopts it, then it is dragged.
  const doc1 = new Doc();
  const m1: any = new WM({ document: doc1, window: win, storage });
  m1.buildTaskbar();
  const h1 = doc1.createElement('header');
  const b1 = doc1.createElement('button');
  b1.id = 'advanced-search-button';
  h1.appendChild(b1);
  doc1.body.appendChild(h1);
  b1.addEventListener('click', () => { makeModal(doc1, 'search-modal', 'Advanced Search'); });
  m1.pendingOpener = 'advanced-search-button';
  b1.click();
  m1.scan();
  m1.dragTo('search-modal', 250, 140);
  m1._save('search-modal');

  // Second page load: a fresh document over the same storage. install() reopens the saved window through its opener.
  const doc2 = new Doc();
  const m2: any = new WM({ document: doc2, window: win, storage });
  const h2 = doc2.createElement('header');
  const b2 = doc2.createElement('button');
  b2.id = 'advanced-search-button';
  h2.appendChild(b2);
  doc2.body.appendChild(h2);
  b2.addEventListener('click', () => { makeModal(doc2, 'search-modal', 'Advanced Search'); });
  m2.install();
  m2.scan(); // the MutationObserver would do this in a browser
  assert.equal(m2.getState().length, 1);
  assert.equal(m2.getLayout('search-modal').x, 250);
  assert.equal(m2.getLayout('search-modal').y, 140);
});

test('hidden panels are not windows until they are shown; drawer panels join the same manager', () => {
  const { WM, doc, storage, win } = boot();
  const m: any = new WM({ document: doc, window: win, storage });
  m.buildTaskbar();
  const hidden = makeModal(doc, 'plugin-modal', 'Test plugin');
  hidden.el.hidden = true;
  const panel = doc.createElement('div');
  panel.className = 'panel';
  panel.id = 'timeline-panel';
  panel.hidden = true;
  const header = doc.createElement('div');
  header.className = 'panel-header';
  const h3 = doc.createElement('h3');
  h3.textContent = 'Execution Timeline';
  header.appendChild(h3);
  const close = doc.createElement('button');
  close.setAttribute('id', 'close-timeline');
  close.addEventListener('click', () => { panel.hidden = true; });
  header.appendChild(close);
  panel.appendChild(header);
  doc.body.appendChild(panel);

  m.scan();
  assert.equal(m.getState().length, 0, 'hidden panels are not windows');

  hidden.el.hidden = false;
  panel.hidden = false;
  m.scan();
  assert.equal(m.getState().length, 2);
  assert.ok(m.getState().some((s: { key: string }) => s.key === 'timeline-panel'));
  assert.equal(panel.querySelector('.wm-title')!.textContent, 'Execution Timeline');
});

test('a header button toggles its open window closed and stops the panel from opening a second', () => {
  const { WM, doc, storage, win } = boot();
  const m: any = new WM({ document: doc, window: win, storage });
  m.buildTaskbar();
  const header = doc.createElement('header');
  const button = doc.createElement('button');
  button.id = 'advanced-search-button';
  header.appendChild(button);
  doc.body.appendChild(header);
  m.pendingOpener = 'advanced-search-button';
  const a = makeModal(doc, 'search-modal', 'Advanced Search');
  const ka = m.adopt(a.el);
  assert.equal(m.keyForOpener('advanced-search-button'), ka);
  let stopped = false;
  let prevented = false;
  m._onCaptureClick({ target: button, stopImmediatePropagation() { stopped = true; }, preventDefault() { prevented = true; } });
  assert.equal(m.getState().length, 0);
  assert.equal(stopped, true);
  assert.equal(prevented, true);
});

test('a second element for the same panel is dropped instead of shown twice, and approval-modal is skipped', () => {
  const { WM, doc, storage, win } = boot();
  const m: any = new WM({ document: doc, window: win, storage });
  m.buildTaskbar();
  const a = makeModal(doc, 'search-modal', 'Advanced Search');
  m.adopt(a.el);
  const dup = makeModal(doc, 'search-modal', 'Advanced Search');
  m.adopt(dup.el);
  assert.equal(m.getState().length, 1);
  assert.equal(dup.el.parentNode, null, 'the duplicate was removed');

  const approval = makeModal(doc, 'approval-modal', 'Approval');
  assert.equal(m.adopt(approval.el), null);
  assert.equal(approval.el.parentNode, doc.body, 'approval-modal stays a modal');
});

test('syncing an unchanged taskbar does not touch the DOM (a rebuild inside the observed body re-triggered the observer forever and froze the page)', () => {
  const { WM, doc, storage, win } = boot();
  const m: any = new WM({ document: doc, window: win, storage });
  m.buildTaskbar();
  const { el } = makeModal(doc, 'search-modal', 'Advanced Search');
  m.adopt(el);
  const wins = m.taskbarWindows;
  const first = wins.firstChild;
  m._syncTaskbar();
  m._syncTaskbar();
  assert.equal(wins.firstChild, first, 'the taskbar nodes were kept, not rebuilt');
  m.toggleMinimize('search-modal');
  assert.notEqual(wins.firstChild, first, 'a real change (minimized) does rebuild it');
});

test('mutations inside the taskbar itself are ignored by the observer callback', () => {
  const { WM, doc, storage, win } = boot();
  const m: any = new WM({ document: doc, window: win, storage });
  m.buildTaskbar();
  let syncs = 0;
  const real = m._syncTaskbar.bind(m);
  m._syncTaskbar = () => { syncs += 1; real(); };
  m._onMutations([{ type: 'childList', target: m.taskbarWindows, addedNodes: [], removedNodes: [] }]);
  assert.equal(syncs, 1, 'only the single trailing sync, no scan of the taskbar nodes');
});

test('a window cannot be dragged or resized partly off the right edge of the viewport', () => {
  const { WM, doc, storage, win } = boot();
  const m: any = new WM({ document: doc, window: win, storage });
  m.buildTaskbar();
  const { el } = makeModal(doc, 'search-modal', 'Advanced Search');
  const key = m.adopt(el);
  m.dragTo(key, 99999, 10);
  let s = m.getState()[0];
  assert.ok(s.x + s.w <= win.innerWidth, `x ${s.x} + w ${s.w} > ${win.innerWidth}`);
  m.resizeTo(key, win.innerWidth, 300);
  s = m.getState()[0];
  assert.ok(s.x + s.w <= win.innerWidth, 'after resize the window still fits');
});

test('install() starts observing BEFORE it restores saved windows, so a restored panel is adopted instead of left as a full-screen backdrop', () => {
  const order: string[] = [];
  class FakeObserver { constructor() { order.push('observer-created'); } observe() { order.push('observing'); } }
  const { WM, doc, storage, win } = boot({ MutationObserver: FakeObserver });
  const m: any = new WM({ document: doc, window: win, storage });
  const realRestore = m.restore.bind(m);
  m.restore = () => { order.push('restore'); realRestore(); };
  m.install();
  assert.ok(order.indexOf('observing') !== -1 && order.indexOf('restore') !== -1, `order was ${order.join(',')}`);
  assert.ok(order.indexOf('observing') < order.indexOf('restore'), `observer started after restore: ${order.join(',')}`);
});

test('after a reload each restored window keeps ITS OWN opener, so a header button closes the window it opened', () => {
  const { WM, doc: _unused, storage, win } = boot();
  void _unused;
  const seed = new Doc();
  const m1: any = new WM({ document: seed, window: win, storage });
  m1.buildTaskbar();
  const ids = [['advanced-search-button', 'search-modal', 'Advanced Search'], ['execution-logs-button', 'logs-modal', 'Execution Logs']];
  const header1 = seed.createElement('header'); seed.body.appendChild(header1);
  for (const [btnId, modalId, title] of ids) {
    const b = seed.createElement('button'); b.id = btnId; header1.appendChild(b);
    b.addEventListener('click', () => { makeModal(seed, modalId, title); });
    m1.pendingOpener = btnId; b.click(); m1.scan(); m1._save(modalId);
  }
  const doc2 = new Doc();
  const m2: any = new WM({ document: doc2, window: win, storage });
  const header2 = doc2.createElement('header'); doc2.body.appendChild(header2);
  for (const [btnId, modalId, title] of ids) {
    const b = doc2.createElement('button'); b.id = btnId; header2.appendChild(b);
    b.addEventListener('click', () => { makeModal(doc2, modalId, title); });
  }
  m2.install();
  m2.scan();
  assert.equal(m2.keyForOpener('advanced-search-button'), 'search-modal');
  assert.equal(m2.keyForOpener('execution-logs-button'), 'logs-modal');
});

test('a panel can ask for a larger first-open window with data-wm-size, still clamped to the viewport', () => {
  const { WM, doc, storage, win } = boot();
  const m: any = new WM({ document: doc, window: win, storage });
  m.buildTaskbar();
  const big = makeModal(doc, 'workflow-modal', 'Create task workflow');
  big.el.dataset.wmSize = '760x560';
  const key = m.adopt(big.el);
  assert.equal(m.getLayout(key).w, 760);
  assert.equal(m.getLayout(key).h, 560);
  const huge = makeModal(doc, 'huge-modal', 'Huge');
  huge.el.dataset.wmSize = '3000x3000';
  const hk = m.adopt(huge.el);
  assert.ok(m.getLayout(hk).w <= win.innerWidth && m.getLayout(hk).h <= win.innerHeight);
  const bad = makeModal(doc, 'bad-modal', 'Bad');
  bad.el.dataset.wmSize = 'nonsense';
  assert.ok(m.getLayout(m.adopt(bad.el)).w <= 460, 'a malformed hint is ignored');
});

test('a panel that stays in the page and is closed by hiding it is a full window again when it is reopened (taskbar entry, working title bar)', () => {
  const { WM, doc, storage, win } = boot();
  const m: any = new WM({ document: doc, window: win, storage });
  m.buildTaskbar();
  const { el } = makeModal(doc, 'workflow-modal', 'Create task workflow');
  el.dataset.wmPersistent = '1';
  m.adopt(el);
  assert.equal(m.getState().length, 1);
  el.hidden = true;
  m.unadopt(el);
  assert.equal(m.getState().length, 0);
  assert.equal(el.querySelectorAll('.wm-titlebar').length, 0, 'the old title bar was removed, not left to stack');
  el.hidden = false;
  m.scan();
  assert.equal(m.getState().length, 1, 'reopened panel is registered again');
  assert.equal(m.taskbar.querySelectorAll('.wm-task-item').length, 1, 'and has its taskbar entry');
  assert.equal(el.querySelectorAll('.wm-titlebar').length, 1, 'exactly one title bar');
  m.toggleMinimize('workflow-modal');
  assert.equal(m.getLayout('workflow-modal').minimized, true, 'its controls work');
});
