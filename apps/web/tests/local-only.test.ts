// Local-only operator console (dashboard login deferred): boots the real server.ts.
// Proves: non-loopback bind refused; dashboard API + WebSocket work without login; the governed bridge
// still enforces header/allow-list/API-key and sends the narrow capability. Loopback only; mock backend.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import type { AddressInfo } from 'node:net';
import { WebSocket } from 'ws';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEAD = 'http://127.0.0.1:9';
let tmp: string;
let backend: http.Server;
let hits: Array<{ url: string; body: any }> = [];
const recordedHits = (): Array<{ url: string; body: any }> => hits;

function env(extra: Record<string, string>): NodeJS.ProcessEnv {
  return {
    ...process.env, INCEPTION_API_KEY: 'test', INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: DEAD, JANUS_BASE_URL: DEAD, UPSTASH_VECTOR_REST_URL: DEAD,
    UPSTASH_VECTOR_REST_TOKEN: 'none', KUDBEE_DAILY_BUDGET_USD: '0', KUDBEE_DATA_DIR: path.join(tmp, 'd'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'w'),
    THINKBOX_BACKEND_URL: `http://127.0.0.1:${(backend.address() as AddressInfo).port}`, THINKBOX_API_KEY: 'server-side-key', ...extra,
  };
}

async function start(extra: Record<string, string> = {}): Promise<{ proc: ChildProcess; url: string }> {
  const port = 20000 + Math.floor(Math.random() * 20000);
  const proc = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], { cwd: appDir, env: env({ PORT: String(port), ...extra }), stdio: 'ignore' });
  const url = `http://127.0.0.1:${port}`;
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) {
    try { if ((await fetch(`${url}/api/health`)).ok) return { proc, url }; } catch { /* starting */ }
  }
  proc.kill();
  throw new Error('server did not start');
}

before(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-local-only-'));
  backend = http.createServer((req, res) => {
    let raw = '';
    req.on('data', (c) => (raw += c));
    req.on('end', () => {
      hits.push({ url: req.url!, body: raw ? JSON.parse(raw) : null });
      res.setHeader('Content-Type', 'application/json');
      if (req.url === '/api/v1/run/admission-token') return res.end(JSON.stringify({ agent_id: 'web-dashboard-agent', governance_token: 'SECRET-GOV', capability: 'shell:upcloud-ssh:readonly' }));
      if (req.url === '/api/v1/run') return res.end(JSON.stringify({ engine_id: 'engine_abc', session_id: 's', summary: { receipt_id: 'r' } }));
      res.statusCode = 404; res.end('{}');
    });
  });
  await new Promise<void>((r) => backend.listen(0, '127.0.0.1', r));
});
after(() => { backend.close(); fs.rmSync(tmp, { recursive: true, force: true }); });

test('non-loopback bind is refused (dashboard is local-only)', async () => {
  const proc = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], { cwd: appDir, env: env({ PORT: '0', LISTEN_ADDR: '0.0.0.0' }), stdio: ['ignore', 'ignore', 'pipe'] });
  let err = '';
  proc.stderr!.on('data', (c) => (err += c));
  const code = await new Promise<number | null>((r) => proc.on('exit', r));
  assert.equal(code, 1);
  assert.match(err, /Refusing to listen on 0\.0\.0\.0/);
});

test('dashboard API and WebSocket work locally without login', async () => {
  const web = await start();
  try {
    for (const u of ['/api/stats', '/api/agents', '/api/runs', '/api/memory/status']) assert.equal((await fetch(`${web.url}${u}`)).status, 200, u);
    const h: any = await (await fetch(`${web.url}/api/health`)).json();
    assert.equal(h.status, 'ok');
    const first = await new Promise<string>((resolve, reject) => {
      const ws = new WebSocket(web.url.replace('http', 'ws') + '/ws', { origin: web.url });
      ws.on('message', (m) => { resolve(m.toString()); ws.close(); });
      ws.on('error', reject);
    });
    assert.match(first, /"type":"init"/);
    assert.equal((await fetch(`${web.url}/api/auth/me`)).status, 404, 'no login endpoints');
  } finally { web.proc.kill(); }
});

test('governed bridge controls still apply on the real server', async () => {
  const web = await start();
  const H = { 'Content-Type': 'application/json', 'X-Kudbee-Client': 'dashboard' };
  try {
    hits = [];
    assert.equal((await fetch(`${web.url}/api/governed/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"command":"hostname"}' })).status, 403, 'client header');
    assert.equal((await fetch(`${web.url}/api/governed/run`, { method: 'POST', headers: H, body: '{"command":"hostname; id"}' })).status, 400, 'allow-list');
    // `deepEqual<T>(actual, expected): asserts actual is T` narrows `hits` by the literal's
    // inferred type; an untyped `[]` infers T=never[], which made every later `hits.find(...)`
    // element type `never`. Typing the literal keeps `hits` as its real element type afterward.
    assert.deepEqual(hits, [] as Array<{ url: string; body: any }>, 'rejected before the backend');
    const ok = await fetch(`${web.url}/api/governed/run`, { method: 'POST', headers: H, body: '{"command":"hostname"}' });
    assert.equal(ok.status, 202);
    assert.equal((await ok.text()).includes('SECRET-GOV'), false, 'token never reaches the browser');
    const run = recordedHits().find((h) => h.url === '/api/v1/run')!.body;
    assert.equal(run.capability, 'shell:upcloud-ssh:readonly');
    assert.equal(run.execution_substrate, 'upcloud-ssh');
  } finally { web.proc.kill(); }
  const noKey = await start({ THINKBOX_API_KEY: '', THINKBOX_API_KEYS: '' });
  try {
    assert.equal((await fetch(`${noKey.url}/api/governed/run`, { method: 'POST', headers: H, body: '{"command":"hostname"}' })).status, 503, 'no backend key');
  } finally { noKey.proc.kill(); }
});
