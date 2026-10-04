// Local-only lockdown of the dashboard (no login): boots the REAL server.ts on random loopback ports.
// Proves: cross-origin / no-Origin / wrong-Host WebSocket upgrades are refused; every HTTP route refuses a
// non-loopback Host (DNS rebinding); shell_exec is off by default and needs approval when enabled;
// file_read/file_write are confined to the session workspace. Never touches port 3000 or the network.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';
import { freePort } from './helpers/free-port.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEAD = 'http://127.0.0.1:9';
let tmp: string;
const procs: ChildProcess[] = [];

interface Server { url: string; port: number; workspaces: string }

async function start(extra: Record<string, string> = {}): Promise<Server> {
  const port = await freePort();
  const dir = fs.mkdtempSync(path.join(tmp, 's-'));
  const workspaces = path.join(dir, 'w');
  const proc = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: {
      ...process.env, PORT: String(port), INCEPTION_API_KEY: 'test', INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: DEAD, JANUS_BASE_URL: DEAD,
      UPSTASH_VECTOR_REST_URL: DEAD, UPSTASH_VECTOR_REST_TOKEN: 'none', KUDBEE_DAILY_BUDGET_USD: '0',
      KUDBEE_DATA_DIR: path.join(dir, 'd'), KUDBEE_WORKSPACE_DIR: workspaces, THINKBOX_BACKEND_URL: DEAD,
      DASHBOARD_ENABLE_SHELL_EXEC: '', DASHBOARD_ALLOW_NO_ORIGIN: '', ...extra,
    },
    stdio: 'ignore',
  });
  procs.push(proc);
  const url = `http://127.0.0.1:${port}`;
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) {
    try { if ((await fetch(`${url}/api/health`)).ok) return { url, port, workspaces }; } catch { /* starting */ }
  }
  throw new Error('server did not start');
}

/** Raw request so the Host header can be forged (fetch does not allow it). */
function request(s: Server, method: string, p: string, host: string, body?: string): Promise<number> {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: '127.0.0.1', port: s.port, method, path: p, headers: { Host: host, 'Content-Type': 'application/json', 'X-Kudbee-Client': 'dashboard' } }, (res) => {
      res.resume();
      resolve(res.statusCode!);
    });
    req.on('error', reject);
    req.end(body);
  });
}

/** Attempt an upgrade; resolves 'open' or the HTTP status the server refused it with. */
function upgrade(s: Server, options: { origin?: string; host?: string }): Promise<'open' | number> {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`ws://127.0.0.1:${s.port}/ws`, {
      ...(options.origin ? { origin: options.origin } : {}),
      ...(options.host ? { headers: { Host: options.host } } : {}),
    });
    ws.on('open', () => { ws.close(); resolve('open'); });
    ws.on('unexpected-response', (_req, res) => resolve(res.statusCode!));
    ws.on('error', (e) => { if (!/Unexpected server response/.test(e.message)) reject(e); });
  });
}

interface Client { sessionId: string; call(msg: Record<string, unknown>, reply: string, approve?: boolean): Promise<any>; close(): void }

async function connect(s: Server): Promise<Client> {
  const ws = new WebSocket(`ws://127.0.0.1:${s.port}/ws`, { origin: s.url });
  const queue: any[] = [];
  const waiters: Array<(m: any) => void> = [];
  ws.on('message', (raw) => { const m = JSON.parse(raw.toString()); const w = waiters.shift(); if (w) w(m); else queue.push(m); });
  const nextOf = async (types: string[]): Promise<any> => {
    for (;;) {
      const m = queue.length ? queue.shift() : await new Promise<any>((r) => waiters.push(r));
      if (types.includes(m.type)) return m;
    }
  };
  const init = await nextOf(['init']);
  return {
    sessionId: init.data.sessionId,
    async call(msg, reply, approve) {
      ws.send(JSON.stringify(msg));
      for (;;) {
        const m = await nextOf([reply, 'approval_request']);
        if (m.type === reply) return m.data;
        if (approve === undefined) throw new Error(`unexpected approval_request for ${m.data.tool}`);
        ws.send(JSON.stringify({ type: 'approval_response', id: m.data.id, approved: approve }));
      }
    },
    close: () => ws.close(),
  };
}

const plugin = (c: Client, name: string, input: Record<string, unknown>, approve?: boolean) =>
  c.call({ type: 'plugin_execute', plugin: name, input }, 'plugin_result', approve).then((d) => d.result);

before(() => { tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-lockdown-')); });
after(() => { for (const p of procs) p.kill(); fs.rmSync(tmp, { recursive: true, force: true }); });

test('audit attack: cross-origin, no-Origin and wrong-Host WebSocket upgrades are refused', async () => {
  const s = await start();
  assert.equal(await upgrade(s, { origin: 'https://evil.example' }), 401, 'cross-site page');
  assert.equal(await upgrade(s, { origin: `http://attacker.example:${s.port}` }), 401, 'DNS-rebinding origin');
  assert.equal(await upgrade(s, {}), 401, 'no Origin');
  assert.equal(await upgrade(s, { origin: s.url, host: `attacker.example:${s.port}` }), 401, 'rebinding Host');
  assert.equal(await upgrade(s, { origin: s.url }), 'open', 'same origin');
  assert.equal(await upgrade(s, { origin: `http://localhost:${s.port}` }), 'open', 'localhost origin');
});

test('DASHBOARD_ALLOW_NO_ORIGIN=1 admits a no-Origin client but still refuses a foreign one', async () => {
  const s = await start({ DASHBOARD_ALLOW_NO_ORIGIN: '1' });
  assert.equal(await upgrade(s, {}), 'open');
  assert.equal(await upgrade(s, { origin: 'https://evil.example' }), 401);
});

test('every HTTP route refuses a non-loopback Host (DNS rebinding) and serves loopback Hosts', async () => {
  const s = await start();
  const evil = `attacker.example:${s.port}`;
  for (const [method, p, body] of [
    ['GET', '/api/health'], ['GET', '/api/memory'], ['GET', '/api/git/repos'], ['GET', '/'],
    ['POST', '/api/git/clone', '{"url":"https://github.com/a/b"}'], ['POST', '/api/governed/run', '{"command":"hostname"}'],
    ['POST', '/api/memory', '{"title":"x","content":"y"}'],
  ] as Array<[string, string, string?]>) {
    assert.equal(await request(s, method, p, evil, body), 421, `${method} ${p}`);
  }
  assert.equal(await request(s, 'GET', '/api/health', `127.0.0.1:${s.port}`), 200);
  assert.equal(await request(s, 'GET', '/api/health', `localhost:${s.port}`), 200);
  assert.equal(await request(s, 'GET', '/api/health', `127.0.0.1:${s.port + 1}`), 421, 'wrong port');
});

test('shell_exec is disabled by default and never runs', async () => {
  const s = await start();
  const marker = path.join(tmp, `shell-default-${Date.now()}`);
  const c = await connect(s);
  try {
    const r = await plugin(c, 'shell_exec', { command: `touch ${marker}` });
    assert.equal(r.success, false);
    assert.match(r.error, /Plugin disabled: shell_exec/);
    assert.equal(fs.existsSync(marker), false);
  } finally { c.close(); }
});

test('enabled shell_exec still requires human approval: denied never runs, approved runs', async () => {
  const s = await start({ DASHBOARD_ENABLE_SHELL_EXEC: '1' });
  const marker = path.join(tmp, `shell-enabled-${Date.now()}`);
  const c = await connect(s);
  try {
    const denied = await plugin(c, 'shell_exec', { command: `touch ${marker}` }, false);
    assert.equal(denied.success, false);
    assert.match(denied.error, /Denied by human reviewer/);
    assert.equal(fs.existsSync(marker), false);
    const approved = await plugin(c, 'shell_exec', { command: `touch ${marker}` }, true);
    assert.equal(approved.success, true);
    assert.equal(fs.existsSync(marker), true);
  } finally { c.close(); }
});

test('file_read/file_write are confined to the session workspace', async () => {
  const s = await start();
  const c = await connect(s);
  try {
    assert.match((await plugin(c, 'file_read', { path: '/etc/passwd' })).error, /Absolute paths are not allowed/);
    assert.match((await plugin(c, 'file_read', { path: '../../../../etc/passwd' })).error, /Invalid workspace path/);
    const outside = path.join(tmp, `outside-${Date.now()}.txt`);
    assert.match((await plugin(c, 'file_write', { path: outside, content: 'x' }, true)).error, /Absolute paths are not allowed/);
    assert.equal(fs.existsSync(outside), false);

    const ws = path.join(s.workspaces, c.sessionId);
    fs.mkdirSync(ws, { recursive: true });
    fs.symlinkSync(tmp, path.join(ws, 'escape'));
    fs.writeFileSync(path.join(tmp, 'secret.txt'), 'secret');
    assert.match((await plugin(c, 'file_read', { path: 'escape/secret.txt' })).error, /Path escapes workspace/);
    assert.match((await plugin(c, 'file_write', { path: 'escape/new.txt', content: 'x' }, true)).error, /Path escapes workspace/);
    assert.equal(fs.existsSync(path.join(tmp, 'new.txt')), false);

    const denied = await plugin(c, 'file_write', { path: 'notes.txt', content: 'hello' }, false);
    assert.match(denied.error, /Denied by human reviewer/);
    assert.equal(fs.existsSync(path.join(ws, 'notes.txt')), false);
    assert.equal((await plugin(c, 'file_write', { path: 'notes.txt', content: 'hello' }, true)).success, true);
    const read = await plugin(c, 'file_read', { path: 'notes.txt' });
    assert.equal(read.success, true);
    assert.equal(read.content, 'hello');
  } finally { c.close(); }
});

test('a caller cannot point plugins at another session', async () => {
  const s = await start();
  const a = await connect(s);
  const b = await connect(s);
  try {
    fs.mkdirSync(path.join(s.workspaces, a.sessionId), { recursive: true });
    fs.writeFileSync(path.join(s.workspaces, a.sessionId, 'a.txt'), 'only-a');
    const r = await plugin(b, 'file_read', { path: 'a.txt', sessionId: a.sessionId });
    assert.equal(r.success, false, 'sessionId in input is overwritten with the caller session');
  } finally { a.close(); b.close(); }
});
