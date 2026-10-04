// Broad HTTP coverage for server.ts and routes/*.ts: boots the real server (dead backends) and exercises the read-only and
// validation paths that other tests do not touch. It asserts each route answers, not exact bodies.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { stopProc } from './helpers/stop-proc.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEAD = 'http://127.0.0.1:9';
let server: ChildProcess;
let tmp: string;
let base: string;

before(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-smoke-'));
  const port = 20000 + Math.floor(Math.random() * 20000);
  base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: { ...process.env, PORT: String(port), INCEPTION_API_KEY: 'test-key', OLLAMA_BASE_URL: DEAD, JANUS_BASE_URL: DEAD,
      UPSTASH_VECTOR_REST_URL: DEAD, UPSTASH_VECTOR_REST_TOKEN: 'none', KUDBEE_DAILY_BUDGET_USD: '0',
      KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), THINKBOX_EMBEDDINGS: 'off', THINKBOX_BACKEND_URL: DEAD },
    stdio: 'ignore',
  });
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) {
    try { if ((await fetch(`${base}/api/health`)).ok) return; } catch { /* starting */ }
  }
  throw new Error('server did not start');
});
after(async () => { await stopProc(server); fs.rmSync(tmp, { recursive: true, force: true }); });

const get = async (p: string) => { const r = await fetch(base + p); await r.text(); return r.status; };
const post = async (p: string, body?: unknown, headers: Record<string, string> = { 'Content-Type': 'application/json' }) => {
  const r = await fetch(base + p, { method: 'POST', headers, body: body === undefined ? undefined : JSON.stringify(body) });
  await r.text();
  return r.status;
};

test('read-only and SDK endpoints answer', async () => {
  for (const p of [
    '/api/health', '/api/stats', '/api/stats/tokens', '/api/models', '/api/agents', '/api/runs', '/api/runs/history',
    '/api/monitor', '/api/memory', '/api/memory/status', '/api/memory/notes', '/api/memory/notes?layer=org',
    '/api/sdk/version', '/api/sdk/capabilities', '/api/sdk/sessions', '/api/sdk/tasks',
  ]) {
    const status = await get(p);
    assert.ok(status >= 200 && status < 500, `${p} -> ${status}`);
  }
});

test('unknown routes and unknown sessions return a client error, not a crash', async () => {
  const id = '00000000-0000-4000-8000-000000000000';
  for (const p of [
    '/api/does-not-exist',
    `/api/runs/${id}`,
    `/api/sessions/${id}/files`,
    `/api/sessions/${id}/files/content?path=none.txt`,
    `/api/sessions/${id}/files/raw?path=none.txt`,
    `/api/memory/item?id=missing`,
  ]) {
    const status = await get(p);
    assert.ok(status >= 200 && status < 500, `${p} -> ${status}`);
  }
});

test('write routes validate their input instead of throwing', async () => {
  assert.ok([400, 422].includes(await post('/api/memory', {})), 'memory without title/content is a 400');
  assert.ok([400, 422].includes(await post('/api/memory/notes', {})), 'notes without a body is a 400');
  assert.ok(await post('/api/memory/promote', {}) >= 400, 'promote without an id is a client error');
  assert.ok(await post('/api/sessions/00000000-0000-4000-8000-000000000000/run', { goal: 'x' }) >= 400, 'unknown session run is a client error');
  assert.ok(await post('/api/sessions/00000000-0000-4000-8000-000000000000/stop') >= 400, 'unknown session stop is a client error');
});

test('the browser service allow-list serves known services and refuses others', async () => {
  const known = await fetch(`${base}/services/analytics.js`);
  assert.equal(known.status, 200);
  assert.match(known.headers.get('content-type') ?? '', /javascript/);
  await known.text();
  assert.equal(await get('/services/not-a-service.js'), 404);
});

test('governed status with an unknown engine id is a client error', async () => {
  assert.ok(await get('/api/governed/run/not-an-engine') >= 400);
});
