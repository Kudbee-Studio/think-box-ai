// Browser-boundary test for the dashboard Git panel (ROADMAP Phase 3 item 6).
//
// git-routes.test.ts already drives /api/git over HTTP with node fetch. This file closes the
// remaining gap: it loads the *real* dashboard module (public/js/git-integration.js) into a
// node:vm sandbox — the same convention as think-token-dashboard.test.ts and git-panel-escaping.test.ts —
// and lets its own `fetch('/api/git/...')` calls hit the real server.ts process. That proves the
// browser-facing path the dashboard actually uses, not just the route in isolation.
//
// A local browser/HTTP run is TEST VERIFIED; it is not LIVE VERIFIED (no external service).
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const panelSrc = fs.readFileSync(path.join(appDir, 'public/js/git-integration.js'), 'utf8');

let tmp: string, server: ChildProcess, base: string, gitRoot: string, canary: string;
const J = { 'Content-Type': 'application/json' };

/** A DOM good enough for the panel's non-visual methods; unknown calls return inert nodes. */
function makeDom(onReady: Array<() => void>) {
  const inert = () => {
    const el: any = {
      className: '', id: '', dataset: {}, hidden: false, innerHTML: '', value: '', textContent: '',
      style: { setProperty() {}, removeProperty() {} },
      appendChild(c: unknown) { return c; },
      addEventListener() {}, removeEventListener() {}, remove() {},
      querySelector() { return null; }, querySelectorAll() { return []; },
      closest() { return null; }, setAttribute() {}, getAttribute() { return null; },
    };
    return el;
  };
  return {
    getElementById: () => null,
    createElement: () => inert(),
    body: inert(),
    addEventListener(type: string, fn: () => void) { if (type === 'DOMContentLoaded') onReady.push(fn); },
    querySelector() { return null; },
  };
}

/**
 * Load the real panel with a `fetch` bound to the spawned server. The panel module uses relative
 * URLs, exactly like a browser page served by that origin — we resolve them against `base`.
 */
function loadPanel() {
  const ready: Array<() => void> = [];
  const window: Record<string, unknown> = { addEventListener() {}, dispatchEvent() { return true; } };
  const sandbox: Record<string, unknown> = {
    window,
    document: makeDom(ready),
    console: { log() {}, warn() {}, error() {} },
    setTimeout: (fn: () => void) => setTimeout(fn, 0),
    clearTimeout,
    CustomEvent: class { constructor(_type: string, _init?: unknown) {} },
    fetch: (input: string, init?: RequestInit) => fetch(`${base}${input}`, init),
  };
  vm.createContext(sandbox);
  vm.runInContext(panelSrc, sandbox, { filename: 'git-integration.js' });
  for (const fn of ready) fn();
  return (window as any).gitIntegration;
}

before(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-git-browser-'));
  canary = path.join(tmp, 'outside-secret.txt');
  fs.writeFileSync(canary, 'TOP-SECRET-CANARY');
  gitRoot = path.join(tmp, 'ws', '_git');
  const port = 20000 + Math.floor(Math.random() * 20000);
  base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir, stdio: 'ignore',
    env: { ...process.env, PORT: String(port), INCEPTION_API_KEY: 'test', INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: 'http://127.0.0.1:9', JANUS_BASE_URL: 'http://127.0.0.1:9',
      UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: 'n', KUDBEE_DAILY_BUDGET_USD: '0',
      KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws') },
  });
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) {
    try { if ((await fetch(`${base}/api/health`)).ok) return; } catch { /* starting */ }
  }
  throw new Error('server did not start');
});
after(() => { server?.kill(); fs.rmSync(tmp, { recursive: true, force: true }); });

test('the browser panel loads the repository list from the real /api/git/repos', async () => {
  const panel = loadPanel();
  await panel.loadRepositories();
  assert.deepEqual(panel.repositories, []);
});

test('the browser panel opens a file through the real route and gets content + language', async () => {
  const save = await fetch(`${base}/api/git/save`, { method: 'POST', headers: J, body: JSON.stringify({ path: 'src/demo.ts', content: 'export const n = 1;' }) });
  assert.equal(save.status, 200);

  // Capture what the panel hands to its editor without needing real rendering.
  const panel = loadPanel();
  const seen: { editor?: { path: string; content: string; language: string } } = {};
  panel.showFileEditor = (p: string, content: string, language: string) => { seen.editor = { path: p, content, language }; };

  await panel.openFile('src/demo.ts');
  assert.ok(seen.editor, 'openFile should reach the editor');
  assert.equal(seen.editor?.content, 'export const n = 1;');
  assert.equal(seen.editor?.language, 'typescript');
});

test('the browser panel path-traversal read is refused at the API boundary and the canary never leaks', async () => {
  const panel = loadPanel();
  let reached = false;
  let leaked = false;
  const statuses: number[] = [];
  panel.showFileEditor = (_p: string, content: string) => { reached = true; if (content.includes('TOP-SECRET-CANARY')) leaked = true; };
  panel.showNotification = () => {};

  // Drive the panel's own fetch path and record what the API boundary returned. The panel builds
  // `/api/git/file?path=<encoded>`; escaping paths must never open the editor.
  for (const p of [canary, '../outside-secret.txt', `${gitRoot}/../../outside-secret.txt`]) {
    const r = await fetch(`${base}/api/git/file?path=${encodeURIComponent(p)}`);
    statuses.push(r.status);
    await panel.openFile(p);
  }
  for (const s of statuses) assert.ok([400, 403].includes(s), `escaping read must be refused, got ${s}`);
  assert.equal(reached, false, 'no outside file should reach the editor');
  assert.equal(leaked, false, 'the canary must never be read through the panel');
});

test('the browser panel save path writes inside the workspace and the saved file reads back', async () => {
  const panel = loadPanel();
  panel.showNotification = () => {};
  const button = { closest: () => ({ querySelector: () => ({ value: 'print(1)' }), remove() {} }) };
  await panel.saveFile('gen/out.py', button);

  // Prove the write reached the real route and stayed inside the git workspace.
  const read = await fetch(`${base}/api/git/file?path=${encodeURIComponent('gen/out.py')}`);
  assert.equal(read.status, 200);
  const body: any = await read.json();
  assert.equal(body.content, 'print(1)');
  assert.equal(body.language, 'python');

  // The file on disk is under the confined git root, never outside it.
  const onDisk = fs.realpathSync(path.join(gitRoot, 'gen/out.py'));
  assert.ok(onDisk.startsWith(fs.realpathSync(gitRoot)), onDisk);
});
