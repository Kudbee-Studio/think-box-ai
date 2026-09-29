// Dashboard auth in front of the governed bridge. Unit tests for auth.ts plus an end-to-end test that
// boots the real server.ts against a mock governed backend (loopback only; no UpCloud, no network).
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import type { AddressInfo } from 'node:net';
import { hashPassword, verifyPassword, DashboardAuth, authConfigFromEnv, SESSION_COOKIE } from '../auth.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PASSWORD = 'correct horse battery staple';
const HASH = hashPassword(PASSWORD);
const H = { 'Content-Type': 'application/json', 'X-Kudbee-Client': 'dashboard' };

// ---------- unit ----------
test('scrypt hash verifies only the right password and never contains it', () => {
  assert.ok(HASH.startsWith('scrypt$'));
  assert.equal(HASH.includes(PASSWORD), false);
  assert.equal(verifyPassword(PASSWORD, HASH), true);
  assert.equal(verifyPassword('wrong', HASH), false);
  assert.equal(verifyPassword(PASSWORD, 'plaintext'), false);
  assert.notEqual(hashPassword(PASSWORD), HASH, 'salted: same password hashes differently');
});

test('unconfigured auth is not "configured" (routes fail closed)', () => {
  assert.equal(new DashboardAuth(authConfigFromEnv({})).configured, false);
  assert.equal(new DashboardAuth(authConfigFromEnv({ KUDBEE_DASHBOARD_PASSWORD_HASH: 'hunter2' })).configured, false);
});

test('sessions expire on idle timeout', () => {
  let now = 1_000_000;
  const auth = new DashboardAuth({ ...authConfigFromEnv({ KUDBEE_DASHBOARD_PASSWORD_HASH: HASH }), idleMs: 1000 }, () => now);
  let cookie = '';
  const res: any = { status() { return this; }, json() { return this; }, setHeader(_k: string, v: string) { cookie = v; } };
  auth.login({ get: () => 'dashboard', body: { username: 'admin', password: PASSWORD }, headers: {}, ip: '1.1.1.1', socket: {} } as any, res);
  const sid = cookie.split(';')[0];
  const req = { headers: { cookie: sid } } as any;
  assert.ok(auth.current(req));
  now += 500; assert.ok(auth.current(req), 'activity keeps it alive');
  now += 1500; assert.equal(auth.current(req), null, 'idle expiry');
});

// ---------- end-to-end against real server.ts ----------
let backend: http.Server;
let backendHits: string[] = [];
let server: ChildProcess;
let base: string;
let tmp: string;

async function startWeb(extraEnv: Record<string, string>): Promise<{ proc: ChildProcess; url: string }> {
  const port = 20000 + Math.floor(Math.random() * 20000);
  const proc = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: {
      ...process.env, PORT: String(port), INCEPTION_API_KEY: 'test', OLLAMA_BASE_URL: 'http://127.0.0.1:9',
      JANUS_BASE_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: 'none',
      KUDBEE_DAILY_BUDGET_USD: '0', KUDBEE_DATA_DIR: path.join(tmp, `d${port}`), KUDBEE_WORKSPACE_DIR: path.join(tmp, `w${port}`),
      THINKBOX_BACKEND_URL: `http://127.0.0.1:${(backend.address() as AddressInfo).port}`, THINKBOX_API_KEY: 'server-side-key',
      KUDBEE_DASHBOARD_PASSWORD_HASH: '', ...extraEnv,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const url = `http://127.0.0.1:${port}`;
  const end = Date.now() + 15000;
  while (Date.now() < end) {
    try { if ((await fetch(`${url}/api/health`)).ok) return { proc, url }; } catch { /* starting */ }
    await new Promise((r) => setTimeout(r, 150));
  }
  proc.kill();
  throw new Error('web server did not start');
}

before(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-auth-test-'));
  backend = http.createServer((req, res) => {
    backendHits.push(req.url!);
    res.setHeader('Content-Type', 'application/json');
    if (req.url === '/api/v1/run/admission-token') return res.end(JSON.stringify({ agent_id: 'web-dashboard-agent', governance_token: 'SECRET-GOV-TOKEN' }));
    if (req.url === '/api/v1/run') return res.end(JSON.stringify({ engine_id: 'engine_abc', session_id: 's', summary: { receipt_id: 'r1' } }));
    if (req.url === '/api/v1/run/job/engine_abc/status') return res.end(JSON.stringify({ status: 'completed', poll: { terminal: true } }));
    res.statusCode = 404; res.end('{}');
  });
  await new Promise<void>((r) => backend.listen(0, '127.0.0.1', r));
  const web = await startWeb({ KUDBEE_DASHBOARD_PASSWORD_HASH: HASH, KUDBEE_DASHBOARD_USER: 'operator' });
  server = web.proc; base = web.url;
});

after(() => { server?.kill(); backend.close(); fs.rmSync(tmp, { recursive: true, force: true }); });

const run = (cookie?: string, body: unknown = { command: 'hostname' }, headers: Record<string, string> = H) =>
  fetch(`${base}/api/governed/run`, { method: 'POST', headers: { ...headers, ...(cookie ? { Cookie: cookie } : {}) }, body: JSON.stringify(body) });
const login = (username: string, password: string, headers: Record<string, string> = H) =>
  fetch(`${base}/api/auth/login`, { method: 'POST', headers, body: JSON.stringify({ username, password }) });

test('unauthenticated: governed run and status are rejected before reaching the backend', async () => {
  backendHits = [];
  assert.equal((await run()).status, 401);
  assert.equal((await run('kudbee_sid=forged-session-id')).status, 401);
  assert.equal((await fetch(`${base}/api/governed/run/engine_abc`, { headers: H })).status, 401);
  assert.deepEqual(backendHits, []);
  const me: any = await (await fetch(`${base}/api/auth/me`)).json();
  assert.deepEqual(me, { configured: true, authenticated: false, user: null });
});

test('bad credentials rejected; login requires the dashboard header', async () => {
  assert.equal((await login('operator', 'wrong password!!')).status, 401);
  assert.equal((await login('admin', PASSWORD)).status, 401, 'wrong username');
  assert.equal((await login('operator', PASSWORD, { 'Content-Type': 'application/json' })).status, 403, 'no header (CSRF guard)');
});

test('authenticated session: secure cookie, governed run proceeds, credentials never reach the browser', async () => {
  backendHits = [];
  const res = await login('operator', PASSWORD);
  assert.equal(res.status, 200);
  const setCookie = res.headers.get('set-cookie') || '';
  assert.match(setCookie, new RegExp(`^${SESSION_COOKIE}=[A-Za-z0-9_-]{40,};`));
  assert.match(setCookie, /HttpOnly/); assert.match(setCookie, /SameSite=Strict/); assert.match(setCookie, /Path=\//);
  const cookie = setCookie.split(';')[0];
  const loginBody = await res.text();
  assert.equal(loginBody.includes(PASSWORD) || loginBody.includes('scrypt$'), false);

  const me: any = await (await fetch(`${base}/api/auth/me`, { headers: { Cookie: cookie } })).json();
  assert.equal(me.authenticated, true); assert.equal(me.user, 'operator');

  const r = await run(cookie);
  assert.equal(r.status, 202);
  const text = await r.text();
  assert.equal(text.includes('SECRET-GOV-TOKEN') || text.includes('server-side-key'), false);
  assert.deepEqual(backendHits, ['/api/v1/run/admission-token', '/api/v1/run']);
  assert.equal((await fetch(`${base}/api/governed/run/engine_abc`, { headers: { ...H, Cookie: cookie } })).status, 200);

  // PR #284 controls still apply behind auth
  backendHits = [];
  assert.equal((await run(cookie, { command: 'hostname; id' })).status, 400, 'allow-list');
  assert.equal((await run(cookie, { command: 'hostname' }, { 'Content-Type': 'application/json' })).status, 403, 'client header');
  assert.deepEqual(backendHits, []);

  // logout invalidates server-side: the old cookie no longer works
  assert.equal((await fetch(`${base}/api/auth/logout`, { method: 'POST', headers: { ...H, Cookie: cookie } })).status, 200);
  assert.equal((await run(cookie)).status, 401);
});

test('login rotates the session id (no fixation)', async () => {
  const a = (await login('operator', PASSWORD)).headers.get('set-cookie')!.split(';')[0];
  const b = (await login('operator', PASSWORD, { ...H, Cookie: a })).headers.get('set-cookie')!.split(';')[0];
  assert.notEqual(a, b);
  assert.equal((await run(a)).status, 401, 'pre-rotation id revoked');
  assert.equal((await run(b)).status, 202);
});

test('repeated failures lock the client out (429), even with the right password', async () => {
  for (let i = 0; i < 5; i += 1) await login('operator', `wrong-${i}-xxxxxxxx`);
  assert.equal((await login('operator', PASSWORD)).status, 429);
});

test('no password hash configured: governed routes fail closed (503), backend never contacted', async () => {
  const web = await startWeb({});
  try {
    backendHits = [];
    const r = await fetch(`${web.url}/api/governed/run`, { method: 'POST', headers: H, body: JSON.stringify({ command: 'hostname' }) });
    assert.equal(r.status, 503);
    assert.equal((await fetch(`${web.url}/api/auth/login`, { method: 'POST', headers: H, body: JSON.stringify({ username: 'admin', password: 'x' }) })).status, 503);
    assert.deepEqual(backendHits, []);
  } finally { web.proc.kill(); }
});

test('missing backend API key still fails closed behind auth (503)', async () => {
  const web = await startWeb({ KUDBEE_DASHBOARD_PASSWORD_HASH: HASH, THINKBOX_API_KEY: '', THINKBOX_API_KEYS: '' });
  try {
    const c = (await fetch(`${web.url}/api/auth/login`, { method: 'POST', headers: H, body: JSON.stringify({ username: 'admin', password: PASSWORD }) })).headers.get('set-cookie')!.split(';')[0];
    const r = await fetch(`${web.url}/api/governed/run`, { method: 'POST', headers: { ...H, Cookie: c }, body: JSON.stringify({ command: 'hostname' }) });
    assert.equal(r.status, 503);
  } finally { web.proc.kill(); }
});

// ---------- full dashboard boundary (PR #286) ----------
import { WebSocket as WsClient } from 'ws';

const PROTECTED: Array<[string, string, unknown?]> = [
  ['GET', '/api/stats'], ['GET', '/api/stats/tokens'], ['GET', '/api/monitor'], ['GET', '/api/middleware/test'],
  ['GET', '/api/runs'], ['GET', '/api/runs/history'], ['GET', '/api/runs/x'], ['GET', '/api/agents'], ['GET', '/api/models'],
  ['GET', '/api/algorand?action=status'], ['GET', '/api/sdk/capabilities'], ['GET', '/api/sdk/version'], ['GET', '/api/sdk/sessions'], ['GET', '/api/sdk/tasks'],
  ['GET', '/api/memory'], ['GET', '/api/memory/status'], ['GET', '/api/memory/item?id=x'], ['POST', '/api/memory', { title: 't', content: 'c', evidence: 'e' }],
  ['POST', '/api/memory/promote', { id: 'x' }], ['DELETE', '/api/memory/item?id=x'], ['GET', '/api/memory/notes'], ['POST', '/api/memory/notes', { content: 'x' }], ['DELETE', '/api/memory/notes/x'],
  ['GET', '/api/sessions/abc/files'], ['GET', '/api/sessions/abc/files/content?path=a'], ['GET', '/api/sessions/abc/files/raw?path=a'], ['POST', '/api/sessions/abc/files'], ['DELETE', '/api/sessions/abc/files'],
  ['POST', '/api/sessions/abc/run', { goal: 'x' }], ['POST', '/api/sessions/abc/stop'], ['POST', '/api/sessions/abc/images/generate', { prompt: 'x' }],
  ['POST', '/api/governed/run', { command: 'hostname' }], ['GET', '/api/governed/run/engine_abc'],
  ['GET', '/API/STATS'], ['GET', '/api/health/'], ['GET', '/api/nonexistent'],
];

function wsStatus(url: string, headers: Record<string, string> = {}): Promise<{ status: number; firstMessage: string | null }> {
  return new Promise((resolve) => {
    const ws = new WsClient(url.replace('http', 'ws') + '/ws', { headers });
    ws.on('unexpected-response', (_req, res) => resolve({ status: res.statusCode ?? 0, firstMessage: null }));
    ws.on('message', (raw) => { resolve({ status: 101, firstMessage: raw.toString().slice(0, 40) }); ws.close(); });
    ws.on('error', () => resolve({ status: -1, firstMessage: null }));
  });
}

test('unauthenticated: every protected /api route is rejected with 401', async () => {
  for (const [method, url, body] of PROTECTED) {
    const r = await fetch(`${base}${url}`, { method, headers: H, body: body === undefined ? undefined : JSON.stringify(body) });
    assert.equal(r.status, 401, `${method} ${url}`);
  }
});

test('unauthenticated WebSocket upgrade is refused before any session or data', async () => {
  const r = await wsStatus(base);
  assert.equal(r.status, 401);
  assert.equal(r.firstMessage, null);
  assert.equal((await wsStatus(base, { Cookie: 'kudbee_sid=forged' })).status, 401);
});

test('public surface: page, health (trimmed), auth endpoints', async () => {
  const page = await fetch(`${base}/`);
  assert.equal(page.status, 200);
  assert.match(await page.text(), /login-dialog/);
  const h: any = await (await fetch(`${base}/api/health`)).json();
  assert.deepEqual(h, { status: 'ok', ready: true }, 'no operational detail without a session');
  assert.equal((await fetch(`${base}/api/auth/me`)).status, 200);
});

test('authenticated: API, WebSocket and detailed health work with a session', async () => {
  // Fresh server: the lockout test above deliberately locked this client address out of the shared one.
  const web = await startWeb({ KUDBEE_DASHBOARD_PASSWORD_HASH: HASH, KUDBEE_DASHBOARD_USER: 'operator' });
  const base = web.url;
  try {
  const c = (await fetch(`${base}/api/auth/login`, { method: 'POST', headers: H, body: JSON.stringify({ username: 'operator', password: PASSWORD }) }))
    .headers.get('set-cookie')!.split(';')[0];
  for (const url of ['/api/stats', '/api/agents', '/api/memory/status', '/api/runs', '/api/sdk/version']) {
    assert.equal((await fetch(`${base}${url}`, { headers: { Cookie: c } })).status, 200, url);
  }
  const h: any = await (await fetch(`${base}/api/health`, { headers: { Cookie: c } })).json();
  assert.ok('sessions' in h && 'node_version' in h);
  const ws = await wsStatus(base, { Cookie: c });
  assert.equal(ws.status, 101);
  assert.match(ws.firstMessage ?? '', /"type":"init"/);
  await fetch(`${base}/api/auth/logout`, { method: 'POST', headers: { ...H, Cookie: c } });
  assert.equal((await wsStatus(base, { Cookie: c })).status, 401, 'logout revokes WebSocket access');
  assert.equal((await fetch(`${base}/api/stats`, { headers: { Cookie: c } })).status, 401);
  } finally { web.proc.kill(); }
});

test('unconfigured server: whole dashboard API and WebSocket fail closed (503), health stays up', async () => {
  const web = await startWeb({});
  try {
    assert.equal((await fetch(`${web.url}/api/stats`)).status, 503);
    assert.equal((await fetch(`${web.url}/api/health`)).status, 200);
    assert.equal((await wsStatus(web.url)).status, 503);
  } finally { web.proc.kill(); }
});
