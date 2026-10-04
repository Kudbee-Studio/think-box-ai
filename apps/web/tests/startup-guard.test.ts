// The startup guard (public/js/startup-guard.js): a missing connection or model list, or any uncaught boot error,
// must produce a visible error panel with Retry instead of a silent spinner.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const src = fs.readFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../public/js/startup-guard.js'), 'utf8');

class El {
  children: El[] = []; parentNode: El | null = null; textContent = ''; id = ''; className = ''; type = ''; attrs: Record<string, string> = {}; handlers: Record<string, () => void> = {};
  tag: string;
  constructor(tag: string) { this.tag = tag; }
  get firstChild() { return this.children[0] ?? null; }
  appendChild(c: El) { c.parentNode = this; this.children.push(c); return c; }
  removeChild(c: El) { this.children = this.children.filter((x) => x !== c); c.parentNode = null; return c; }
  setAttribute(k: string, v: string) { this.attrs[k] = v; }
  addEventListener(t: string, fn: () => void) { this.handlers[t] = fn; }
  text(): string { return [this.textContent, ...this.children.map((c) => c.text())].join(' '); }
  find(id: string): El | null { if (this.id === id) return this; for (const c of this.children) { const f = c.find(id); if (f) return f; } return null; }
}

function boot(timeoutMs = 20) {
  const body = new El('body');
  const winHandlers: Record<string, (e: unknown) => void> = {};
  const doc = { body, createElement: (t: string) => new El(t), addEventListener() {} };
  const win: any = { addEventListener: (t: string, fn: (e: unknown) => void) => { winHandlers[t] = fn; }, location: { origin: 'http://127.0.0.1:3000', reload() { win.reloaded = true; } } };
  const ctx: any = { window: win, globalThis: undefined, setTimeout, clearTimeout };
  vm.runInNewContext(src, ctx);
  const guard = new ctx.window.StartupGuard({ document: doc, window: win, timeoutMs }).install();
  return { guard, body, win, winHandlers };
}
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

test('nothing is shown while boot is within the timeout, and nothing at all once both pieces arrive', async () => {
  const { guard, body } = boot(40);
  guard.ok('connection'); guard.ok('models');
  await wait(80);
  assert.equal(body.find('startup-error'), null);
});

test('a model list that never arrives shows a panel naming it, with a Retry button that retries', async () => {
  const { guard, body, win } = boot(20);
  guard.ok('connection');
  await wait(60);
  const panel = body.find('startup-error')!;
  assert.ok(panel, 'the panel is shown');
  assert.equal(panel.attrs.role, 'alert');
  assert.match(panel.text(), /model list/);
  assert.doesNotMatch(panel.text(), /WebSocket/);
  body.find('startup-retry')!.handlers.click();
  assert.equal(win.reloaded, true);
});

test('a connection that never opens is named too', async () => {
  const { body } = boot(20);
  await wait(60);
  assert.match(body.find('startup-error')!.text(), /live connection.*WebSocket/);
  assert.match(body.find('startup-error')!.text(), /model list/);
});

test('an uncaught error or rejection during boot shows the panel at once, with the message', () => {
  const a = boot(10_000);
  a.winHandlers.error({ message: 'x is not defined' });
  assert.match(a.body.find('startup-error')!.text(), /script error: x is not defined/);
  const b = boot(10_000);
  b.winHandlers.unhandledrejection({ reason: new Error('boom') });
  assert.match(b.body.find('startup-error')!.text(), /unhandled error: boom/);
  a.guard.ok('connection'); a.guard.ok('models'); b.guard.ok('connection'); b.guard.ok('models');
});

test('the panel clears itself when the missing piece arrives, and later errors never take over a booted dashboard', async () => {
  const { guard, body, winHandlers } = boot(20);
  guard.ok('connection');
  await wait(60);
  assert.ok(body.find('startup-error'));
  guard.ok('models');
  assert.equal(body.find('startup-error'), null);
  winHandlers.error({ message: 'late error' });
  assert.equal(body.find('startup-error'), null);
});

test('long error text is capped', () => {
  const { guard, body } = boot(10_000);
  guard.fail('script error', 'x'.repeat(5000));
  assert.ok(body.find('startup-error')!.text().length < 800);
  guard.ok('connection'); guard.ok('models');
});
