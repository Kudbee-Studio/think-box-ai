// Browser-facing hardening of the local dashboard: response headers, cross-origin write refusal, and a ratchet on inline handlers.
// Unit tests use fakes; the last block boots the REAL server.ts on a random loopback port (never 3000, never the network).
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { contentSecurityPolicy, rejectCrossOriginWrites, securityHeaders, type HeaderReq, type HeaderRes } from '../http-security.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function fakeRes() {
  const headers = new Map<string, string>();
  const out = { code: 0, body: undefined as unknown };
  const res: HeaderRes = {
    setHeader: (n, v) => { headers.set(n.toLowerCase(), v); },
    status: (c) => { out.code = c; return { json: (b) => { out.body = b; } }; },
  };
  return { res, headers, out };
}

const allowed = (o: string | undefined) => o === 'http://127.0.0.1:3000';
function guard(method: string, headers: HeaderReq['headers']) {
  const { res, out } = fakeRes();
  let called = false;
  rejectCrossOriginWrites(allowed)({ method, headers }, res, () => { called = true; });
  return { passed: called, code: out.code };
}

test('CSP: scripts only from self, no eval, no inline handlers, no framing, no plugins, no <base>', () => {
  const csp = contentSecurityPolicy(3000);
  const dir = (name: string) => csp.split('; ').find((d) => d.startsWith(`${name} `)) ?? '';
  assert.equal(dir('script-src'), "script-src 'self'");
  assert.doesNotMatch(csp, /unsafe-eval/);
  assert.equal(dir('script-src-attr'), "script-src-attr 'none'");
  for (const d of csp.split('; ').filter((x) => x.startsWith('script-src'))) assert.doesNotMatch(d, /unsafe-inline|unsafe-eval|https?:/, `${d} must not allow inline script, eval or remote script`);
  assert.equal(dir('frame-ancestors'), "frame-ancestors 'none'");
  assert.equal(dir('object-src'), "object-src 'none'");
  assert.equal(dir('base-uri'), "base-uri 'none'");
  assert.equal(dir('form-action'), "form-action 'self'");
  assert.equal(dir('default-src'), "default-src 'self'");
  assert.match(dir('connect-src'), /ws:\/\/127\.0\.0\.1:3000 ws:\/\/localhost:3000/);
  assert.doesNotMatch(csp, /https?:\/\/(?!127\.0\.0\.1|localhost)/, 'no third-party origin is allowed');
  assert.match(contentSecurityPolicy(8123), /ws:\/\/127\.0\.0\.1:8123/);
});

test('securityHeaders sets every header and calls next', () => {
  const { res, headers } = fakeRes();
  let called = false;
  securityHeaders(3000)({ headers: {} }, res, () => { called = true; });
  assert.ok(called);
  assert.equal(headers.get('x-frame-options'), 'DENY');
  assert.equal(headers.get('x-content-type-options'), 'nosniff');
  assert.equal(headers.get('referrer-policy'), 'no-referrer');
  assert.equal(headers.get('cross-origin-opener-policy'), 'same-origin');
  assert.equal(headers.get('cross-origin-resource-policy'), 'same-origin');
  assert.match(headers.get('permissions-policy') ?? '', /camera=\(\).*microphone=\(\)/);
  assert.equal(headers.get('content-security-policy'), contentSecurityPolicy(3000));
});

test('writes: a foreign, null or cross-site request is refused for every unsafe method; reads and our own origin pass', () => {
  for (const method of ['POST', 'PUT', 'PATCH', 'DELETE', 'post']) {
    assert.deepEqual(guard(method, { origin: 'https://evil.example' }), { passed: false, code: 403 }, method);
    assert.deepEqual(guard(method, { origin: 'http://127.0.0.1:9999' }), { passed: false, code: 403 }, `${method} other local port`);
    assert.deepEqual(guard(method, { origin: 'null' }), { passed: false, code: 403 }, `${method} null origin`);
    assert.deepEqual(guard(method, { 'sec-fetch-site': 'cross-site' }), { passed: false, code: 403 }, `${method} cross-site, no Origin`);
    assert.deepEqual(guard(method, { 'sec-fetch-site': 'Cross-Site', origin: 'http://127.0.0.1:3000' }), { passed: false, code: 403 }, `${method} cross-site wins over a spoofable-looking Origin`);
    assert.deepEqual(guard(method, { origin: 'http://127.0.0.1:3000' }), { passed: true, code: 0 }, `${method} own origin`);
    assert.deepEqual(guard(method, { origin: 'http://127.0.0.1:3000', 'sec-fetch-site': 'same-origin' }), { passed: true, code: 0 });
    assert.deepEqual(guard(method, {}), { passed: true, code: 0 }, `${method} no Origin (curl, CLI, tests)`);
  }
  for (const method of ['GET', 'HEAD', 'OPTIONS']) assert.deepEqual(guard(method, { origin: 'https://evil.example' }), { passed: true, code: 0 }, method);
  assert.deepEqual(guard('POST', { origin: ['https://evil.example', 'http://127.0.0.1:3000'] }), { passed: false, code: 403 }, 'repeated Origin header: first value is judged');
});

test('no inline on*= handler anywhere in the front end (the CSP forbids them, so one would silently do nothing)', () => {
  const pub = path.join(appDir, 'public');
  const files = ['index.html', ...fs.readdirSync(path.join(pub, 'js')).filter((f) => f.endsWith('.js') && f !== 'app-mock.js').map((f) => `js/${f}`)];
  const found: string[] = [];
  for (const f of files) {
    const text = fs.readFileSync(path.join(pub, f), 'utf8').split('\n');
    text.forEach((line, i) => { if (/\son(?:click|change|input|submit|keydown|keyup|mouseover|focus|blur)=["']/.test(line) && !/^\s*(?:\/\/|\*)/.test(line)) found.push(`${f}:${i + 1}`); });
  }
  assert.deepEqual(found, [], `inline handlers: use addEventListener (data-action + a delegated listener)\n  ${found.join('\n  ')}`);
});

// ─── Real server ─────────────────────────────────────────────
let tmp: string;
const procs: ChildProcess[] = [];
before(() => { tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-sec-')); });
after(() => { for (const p of procs) p.kill('SIGKILL'); fs.rmSync(tmp, { recursive: true, force: true }); });

async function start(): Promise<{ url: string; port: number }> {
  const port = 20000 + Math.floor(Math.random() * 20000);
  const dead = 'http://127.0.0.1:9';
  const proc = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: {
      ...process.env, PORT: String(port), INCEPTION_API_KEY: 'test', INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: dead, JANUS_BASE_URL: dead,
      UPSTASH_VECTOR_REST_URL: dead, UPSTASH_VECTOR_REST_TOKEN: 'none', KUDBEE_DAILY_BUDGET_USD: '0', THINKBOX_BACKEND_URL: dead,
      KUDBEE_DATA_DIR: path.join(tmp, 'd'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'w'),
    },
    stdio: 'ignore',
  });
  procs.push(proc);
  const url = `http://127.0.0.1:${port}`;
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) {
    try { if ((await fetch(`${url}/api/health`)).ok) return { url, port }; } catch { /* starting */ }
  }
  throw new Error('server did not start');
}

test('real server: security headers on the page and the API, no X-Powered-By, and foreign-origin writes are refused before any handler runs', async () => {
  const s = await start();
  for (const p of ['/', '/api/health', '/js/app.js']) {
    const r = await fetch(s.url + p);
    assert.equal(r.headers.get('x-frame-options'), 'DENY', p);
    assert.equal(r.headers.get('content-security-policy'), contentSecurityPolicy(s.port), p);
    assert.equal(r.headers.get('x-powered-by'), null, p);
  }
  const post = (headers: Record<string, string>) => fetch(`${s.url}/api/git/clone`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: '{}' });
  assert.equal((await post({ Origin: 'https://evil.example' })).status, 403, 'foreign origin');
  assert.equal((await post({ 'Sec-Fetch-Site': 'cross-site' })).status, 403, 'cross-site');
  assert.equal((await post({ Origin: s.url })).status, 400, 'own origin reaches the handler (400: no repository URL)');
  assert.equal((await post({})).status, 400, 'no Origin reaches the handler');
  const upload = await fetch(`${s.url}/api/sessions/x/files`, { method: 'POST', headers: { Origin: 'https://evil.example' }, body: new FormData() });
  assert.equal(upload.status, 403, 'multipart (a no-preflight "simple" request) from a foreign origin');
  assert.equal((await fetch(`${s.url}/api/health`, { headers: { Origin: 'https://evil.example' } })).status, 200, 'reads are unchanged');
});

// ─── Rate limiting ───────────────────────────────────────────
import { rateLimit } from '../http-security.ts';

function hit(limiter: ReturnType<typeof rateLimit>, headers: HeaderReq['headers'] = {}) {
  const { res, headers: out, out: result } = fakeRes();
  let passed = false;
  limiter({ method: 'GET', headers }, res, () => { passed = true; });
  return { passed, code: result.code, retryAfter: out.get('retry-after') };
}

test('rateLimit: allows max requests per window, then 429 with Retry-After, and opens again in the next window', () => {
  let t = 1000;
  const limiter = rateLimit({ windowMs: 10_000, max: 3, now: () => t });
  for (let i = 0; i < 3; i++) assert.equal(hit(limiter).passed, true, `request ${i + 1}`);
  const blocked = hit(limiter);
  assert.deepEqual({ passed: blocked.passed, code: blocked.code }, { passed: false, code: 429 });
  assert.equal(blocked.retryAfter, '10');
  t += 4000;
  assert.equal(hit(limiter).retryAfter, '6', 'Retry-After counts down within the window');
  t += 6000;
  assert.equal(hit(limiter).passed, true, 'a new window starts');
});

test('rateLimit: cross-site requests have their own small budget and cannot use up the dashboard\'s', () => {
  let t = 0;
  const limiter = rateLimit({ windowMs: 10_000, max: 50, crossSiteMax: 2, now: () => t });
  assert.equal(hit(limiter, { 'sec-fetch-site': 'cross-site' }).passed, true);
  assert.equal(hit(limiter, { 'sec-fetch-site': 'cross-site' }).passed, true);
  for (let i = 0; i < 5; i++) assert.equal(hit(limiter, { 'sec-fetch-site': 'cross-site' }).code, 429);
  for (let i = 0; i < 50; i++) assert.equal(hit(limiter, { 'sec-fetch-site': 'same-origin' }).passed, true, `dashboard request ${i + 1} still allowed`);
  assert.equal(hit(limiter, {}).code, 429, 'the dashboard budget itself is finite');
  assert.equal(rateLimit({ windowMs: 1, max: 100 }) instanceof Function, true);
});

test('real server: the file-system routes are rate limited for cross-site callers while same-origin use is unaffected', async () => {
  const s = await start();
  const url = `${s.url}/api/sessions/00000000-0000-4000-8000-000000000000/files`;
  const codes: number[] = [];
  for (let i = 0; i < 40; i++) codes.push((await fetch(url, { headers: { 'Sec-Fetch-Site': 'cross-site' } })).status);
  assert.equal(codes[0], 404, 'reaches the handler first (no such session)');
  assert.ok(codes.includes(429), 'a cross-site burst is cut off');
  assert.equal((await fetch(url)).status, 404, 'a same-origin/CLI request is not affected by the cross-site burst');
  const r = await fetch(url, { headers: { 'Sec-Fetch-Site': 'cross-site' } });
  assert.ok(r.status === 429 && Number(r.headers.get('retry-after')) >= 1);
});
