// A small fake DOM + window for tests that load the dashboard's classic scripts in a vm.
// It implements the subset of the DOM those scripts use and a real event target for CustomEvents.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

export type Ev = {
  target?: unknown; key?: string; clientX?: number; clientY?: number; detail?: unknown;
  stopPropagation?(): void; preventDefault?(): void; stopImmediatePropagation?(): void;
};
export const evt = (target: unknown, x = 0, y = 0): Ev => ({ target, clientX: x, clientY: y, stopPropagation() {}, preventDefault() {}, stopImmediatePropagation() {} });

export function matches(el: El, rawSel: string): boolean {
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

export class El {
  tagName: string; nodeType = 1; parentNode: El | null = null;
  children: El[] = []; style: Record<string, string> = {}; dataset: Record<string, string> = {};
  hidden = false; textContent = ''; id = ''; type = ''; disabled = false;
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
  removeAttribute(k: string): void { delete this.attrs[k]; if (k === 'id') this.id = ''; }
  addEventListener(t: string, fn: (e: Ev) => void): void { (this.listeners[t] = this.listeners[t] || []).push(fn); }
  removeEventListener(t: string, fn: (e: Ev) => void): void { const a = this.listeners[t] || []; const i = a.indexOf(fn); if (i >= 0) a.splice(i, 1); }
  dispatch(t: string, e: Ev): void { (this.listeners[t] || []).slice().forEach((fn) => fn(e)); }
  click(): void { this.dispatch('click', evt(this)); }
  getBoundingClientRect(): { left: number; bottom: number } { return { left: 10, bottom: 20 }; }
  matches(sel: string): boolean { return matches(this, sel); }
  closest(sel: string): El | null { let n: El | null = this; while (n) { if (matches(n, sel)) return n; n = n.parentNode; } return null; }
  querySelector(sel: string): El | null { return this.findAll(sel)[0] || null; }
  querySelectorAll(sel: string): El[] { return this.findAll(sel); }
  findAll(sel: string): El[] { const out: El[] = []; const visit = (n: El) => { for (const c of n.children) { if (matches(c, sel)) out.push(c); visit(c); } }; visit(this); return out; }
}

export class Doc {
  nodeType = 9; body = new El('body');
  private listeners: Record<string, Array<(e: Ev) => void>> = {};
  createElement(t: string): El { return new El(t); }
  getElementById(id: string): El | null { return this.body.findAll('#' + id)[0] || null; }
  querySelectorAll(sel: string): El[] { return this.body.querySelectorAll(sel); }
  addEventListener(t: string, fn: (e: Ev) => void): void { (this.listeners[t] = this.listeners[t] || []).push(fn); }
  removeEventListener(t: string, fn: (e: Ev) => void): void { const a = this.listeners[t] || []; const i = a.indexOf(fn); if (i >= 0) a.splice(i, 1); }
  dispatch(t: string, e: Ev): void { (this.listeners[t] || []).slice().forEach((fn) => fn(e)); }
}

export class Storage {
  private m: Record<string, string> = {};
  get length(): number { return Object.keys(this.m).length; }
  key(i: number): string | null { return Object.keys(this.m)[i] ?? null; }
  getItem(k: string): string | null { return k in this.m ? this.m[k] : null; }
  setItem(k: string, v: string): void { this.m[k] = String(v); }
  removeItem(k: string): void { delete this.m[k]; }
}

export class FakeWindow {
  document: Doc; localStorage: Storage; innerWidth = 1200; innerHeight = 800;
  events: Array<{ type: string; detail?: unknown }> = [];
  private listeners: Record<string, Array<(e: Ev) => void>> = {};
  CustomEvent = class { type: string; detail: unknown; constructor(type: string, opts?: { detail?: unknown }) { this.type = type; this.detail = opts && opts.detail; } };
  constructor(doc: Doc, storage: Storage) { this.document = doc; this.localStorage = storage; }
  addEventListener(t: string, fn: (e: Ev) => void): void { (this.listeners[t] = this.listeners[t] || []).push(fn); }
  removeEventListener(t: string, fn: (e: Ev) => void): void { const a = this.listeners[t] || []; const i = a.indexOf(fn); if (i >= 0) a.splice(i, 1); }
  dispatchEvent(e: { type: string; detail?: unknown }): boolean { this.events.push(e); (this.listeners[e.type] || []).slice().forEach((fn) => fn(e as Ev)); return true; }
}

export interface Booted { win: FakeWindow; doc: Doc; storage: Storage; sandbox: Record<string, unknown> }

export function bootScripts(jsDir: string, files: string[], extra: Record<string, unknown> = {}): Booted {
  const doc = new Doc();
  const storage = new Storage();
  const win = new FakeWindow(doc, storage);
  const sandbox: Record<string, unknown> = {
    window: win, document: doc, localStorage: storage, CustomEvent: win.CustomEvent,
    console: { log() {}, warn() {}, error() {} }, setTimeout: () => 0, MutationObserver: undefined, ...extra,
  };
  vm.createContext(sandbox);
  for (const f of files) vm.runInContext(fs.readFileSync(path.join(jsDir, f), 'utf8'), sandbox, { filename: f });
  return { win, doc, storage, sandbox };
}
