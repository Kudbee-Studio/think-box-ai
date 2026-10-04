// Behaviour for the Actions button (public/js/action-button.js), driven through a small fake DOM:
// the button is enabled, the menu lists saved workflows, picking one dispatches workflow:run, and it closes.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const jsDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../public/js');

type Ev = { target?: unknown; key?: string; stopPropagation?(): void; preventDefault?(): void };
const evt = (target: unknown): Ev => ({ target, stopPropagation() {}, preventDefault() {} });

function matches(el: El, sel: string): boolean {
  const s = sel.trim();
  if (s.startsWith('.')) return el.classList.contains(s.slice(1));
  if (s.startsWith('#')) return el.id === s.slice(1);
  return el.tagName.toLowerCase() === s.toLowerCase();
}

class El {
  tagName: string; nodeType = 1; parentNode: El | null = null;
  children: El[] = []; style: Record<string, string> = {}; dataset: Record<string, string> = {};
  disabled = false; textContent = ''; id = ''; type = '';
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
    };
  }
  get firstChild(): El | null { return this.children[0] || null; }
  appendChild(n: El): El { n.parentNode = this; this.children.push(n); return n; }
  removeChild(n: El): El { const i = this.children.indexOf(n); if (i >= 0) { this.children.splice(i, 1); n.parentNode = null; } return n; }
  remove(): void { if (this.parentNode) this.parentNode.removeChild(this); }
  setAttribute(k: string, v: string): void { this.attrs[k] = String(v); if (k === 'id') this.id = String(v); }
  getAttribute(k: string): string | null { return k in this.attrs ? this.attrs[k] : null; }
  removeAttribute(k: string): void { delete this.attrs[k]; if (k === 'id') this.id = ''; }
  addEventListener(t: string, fn: (e: Ev) => void): void { (this.listeners[t] = this.listeners[t] || []).push(fn); }
  dispatch(t: string, e: Ev): void { (this.listeners[t] || []).slice().forEach((fn) => fn(e)); }
  click(): void { this.dispatch('click', evt(this)); }
  getBoundingClientRect(): { left: number; bottom: number } { return { left: 10, bottom: 20 }; }
  querySelector(sel: string): El | null { return this.findAll(sel)[0] || null; }
  querySelectorAll(sel: string): El[] { return this.findAll(sel); }
  findAll(sel: string): El[] { const out: El[] = []; const visit = (n: El) => { for (const c of n.children) { if (matches(c, sel)) out.push(c); visit(c); } }; visit(this); return out; }
}

class Doc {
  nodeType = 9; body = new El('body');
  private listeners: Record<string, Array<(e: Ev) => void>> = {};
  createElement(t: string): El { return new El(t); }
  getElementById(id: string): El | null { const found = (this.body as El).findAll('#' + id); return found[0] || null; }
  addEventListener(t: string, fn: (e: Ev) => void): void { (this.listeners[t] = this.listeners[t] || []).push(fn); }
  dispatch(t: string, e: Ev): void { (this.listeners[t] || []).slice().forEach((fn) => fn(e)); }
}

class Storage {
  private m: Record<string, string> = {};
  get length(): number { return Object.keys(this.m).length; }
  key(i: number): string | null { return Object.keys(this.m)[i] ?? null; }
  getItem(k: string): string | null { return k in this.m ? this.m[k] : null; }
  setItem(k: string, v: string): void { this.m[k] = String(v); }
  removeItem(k: string): void { delete this.m[k]; }
}

function boot(): { win: any; doc: Doc; storage: Storage } {
  const doc = new Doc();
  const storage = new Storage();
  const win: any = {
    document: doc, localStorage: storage, _events: [] as Array<{ type: string; detail?: any }>,
    addEventListener() {}, removeEventListener() {},
    dispatchEvent(ev: { type: string; detail?: unknown }): boolean { win._events.push(ev); return true; },
  };
  win.CustomEvent = class { type: string; detail: unknown; constructor(type: string, opts?: { detail?: unknown }) { this.type = type; this.detail = opts && opts.detail; } };
  const sandbox: Record<string, unknown> = { window: win, document: doc, localStorage: storage, CustomEvent: win.CustomEvent, console: { log() {}, warn() {}, error() {} }, setTimeout: () => 0 };
  vm.createContext(sandbox);
  for (const f of ['workflow-store.js', 'action-button.js']) vm.runInContext(fs.readFileSync(path.join(jsDir, f), 'utf8'), sandbox, { filename: f });
  return { win, doc, storage };
}

function button(doc: Doc, disabled = true): El {
  const b = doc.createElement('button');
  b.id = 'bulk-actions';
  b.disabled = disabled;
  if (disabled) b.setAttribute('disabled', '');
  doc.body.appendChild(b);
  return b;
}

test('mount enables the previously disabled button', () => {
  const { win, doc } = boot();
  const b = button(doc);
  const menu = new win.ActionMenu({ buttonId: 'bulk-actions' });
  assert.equal(menu.mount(), true);
  assert.equal(b.disabled, false);
  assert.equal(b.getAttribute('disabled'), null);
  assert.equal(menu.mount(), true, 'mount is idempotent');
});

test('mount returns false when the button is absent', () => {
  const { win } = boot();
  assert.equal(new win.ActionMenu({ buttonId: 'nope' }).mount(), false);
});

test('the menu lists saved workflows and picking one dispatches workflow:run', () => {
  const { win, doc, storage } = boot();
  button(doc);
  win.WorkflowStore.saveWorkflow(storage, { name: 'Deploy', nodes: [{ type: 'sequential', name: 'build' }] });
  win.WorkflowStore.saveWorkflow(storage, { name: 'Report', nodes: [{ type: 'parallel', name: 'gather' }] });
  const menu = new win.ActionMenu({ buttonId: 'bulk-actions' });
  menu.mount();
  menu.openMenu();
  const items = menu.menu.querySelectorAll('.action-menu-item');
  assert.equal(items.length, 3, 'two workflows + the New workflow item');
  const deploy = items.find((i: El) => i.textContent.indexOf('Deploy') === 0)!;
  assert.match(deploy.textContent, /1 step\(s\)/);
  deploy.click();
  assert.equal(win._events.length, 1);
  assert.equal(win._events[0].type, 'workflow:run');
  assert.equal(win._events[0].detail.name, 'Deploy');
  assert.equal(menu.menu, null, 'the menu closed after running');
});

test('an empty store shows the empty state and the New workflow item opens the builder', () => {
  const { win, doc } = boot();
  button(doc);
  const create = doc.createElement('button');
  create.id = 'create-workflow';
  let clicked = 0;
  create.addEventListener('click', () => { clicked++; });
  doc.body.appendChild(create);
  const menu = new win.ActionMenu({ buttonId: 'bulk-actions' });
  menu.mount();
  menu.openMenu();
  assert.ok(menu.menu.querySelector('.action-menu-empty'));
  menu.menu.querySelector('.action-menu-new').click();
  assert.equal(clicked, 1);
  assert.equal(menu.menu, null);
});

test('clicking the button toggles the menu and Escape closes it', () => {
  const { win, doc } = boot();
  const b = button(doc);
  const menu = new win.ActionMenu({ buttonId: 'bulk-actions' });
  menu.mount();
  b.click();
  assert.ok(menu.menu);
  b.click();
  assert.equal(menu.menu, null);
  b.click();
  assert.ok(menu.menu);
  doc.dispatch('keydown', { key: 'Escape' });
  assert.equal(menu.menu, null);
});

test('running a workflow with an empty store dispatches nothing', () => {
  const { win, doc } = boot();
  button(doc);
  const menu = new win.ActionMenu({ buttonId: 'bulk-actions' });
  menu.mount();
  menu.run(null);
  assert.equal(win._events.length, 0);
});
