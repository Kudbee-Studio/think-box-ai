// The error-handling net (error-handling.ts) and three places that used to fail silently: a corrupt runs file, git status on a
// directory git cannot read, and requests that reach Express's default HTML error page. Unit tests use fakes; the integration tests
// boot the REAL server.ts on a random loopback port.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { stopProcs } from './helpers/stop-proc.ts';
import { EventEmitter } from 'node:events';
import { execFileSync, spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describeError, installProcessHandlers, jsonErrorHandler, type ErrRes } from '../error-handling.ts';
import { RunStore } from '../runs.ts';
import { GitRepoManager } from '../git-repo-manager.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let tmp: string;
const procs: ChildProcess[] = [];
before(() => { tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-err-')); });
after(async () => { await stopProcs(procs); fs.rmSync(tmp, { recursive: true, force: true }); });

test('describeError: Error message, name when the message is empty, strings, objects, and values JSON cannot hold', () => {
  assert.equal(describeError(new Error('boom')), 'boom');
  assert.equal(describeError(new TypeError('')), 'TypeError');
  assert.equal(describeError('plain'), 'plain');
  assert.equal(describeError({ code: 7 }), '{"code":7}');
  const cyclic: Record<string, unknown> = {}; cyclic.self = cyclic;
  assert.equal(describeError(cyclic), '[object Object]');
  assert.equal(describeError(undefined), 'undefined');
});

function handle(err: unknown, opts: { headersSent?: boolean; url?: string } = {}) {
  const logged: string[] = [];
  const out = { code: 0, body: undefined as unknown, nextCalled: undefined as unknown };
  const res: ErrRes = { headersSent: opts.headersSent, status: (c) => { out.code = c; return { json: (b) => { out.body = b; } }; } };
  jsonErrorHandler({ error: (...a) => { logged.push(a.join(' ')); } })(err, { method: 'POST', originalUrl: opts.url ?? '/api/x?token=secret' }, res, (e) => { out.nextCalled = e ?? true; });
  return { ...out, logged };
}

test('error handler: an unexpected error is a 500 with no detail, the stack goes to the log only, and the query string is never logged', () => {
  const err = new Error('db exploded at /home/u/secret/path');
  const r = handle(err);
  assert.equal(r.code, 500);
  assert.deepEqual(r.body, { error: 'internal_error' });
  assert.match(r.logged[0], /POST \/api\/x -> 500: db exploded/);
  assert.match(r.logged[0], /at /, 'the stack is logged');
  assert.ok(!r.logged[0].includes('secret') || r.logged[0].includes('/home/u/secret/path'), 'only the error text, never the ?token= query');
  assert.ok(!r.logged[0].includes('token=secret'));
  assert.equal(JSON.stringify(r.body).includes('secret'), false);
});

test('error handler: client errors keep their 4xx status with a stable code; only safe messages are exposed; a non-4xx status is a 500', () => {
  assert.deepEqual(handle(Object.assign(new SyntaxError('Unexpected token'), { status: 400, type: 'entity.parse.failed', expose: true })).body, { error: 'invalid_json', detail: 'Unexpected token' });
  const big = handle(Object.assign(new Error('request entity too large'), { status: 413, type: 'entity.too.large', expose: true }));
  assert.equal(big.code, 413);
  assert.deepEqual(big.body, { error: 'payload_too_large', detail: 'request entity too large' });
  const hidden = handle(Object.assign(new Error('internal hint'), { statusCode: 418 }));
  assert.deepEqual(hidden.body, { error: 'bad_request' }, 'no detail unless the error says it is safe to expose');
  assert.equal(handle(Object.assign(new Error('x'), { status: 302 })).code, 500);
  assert.equal(handle(Object.assign(new Error('x'), { status: 'nope' })).code, 500);
  assert.equal(handle(null).code, 500);
  assert.equal(handle('a thrown string').code, 500);
});

test('error handler: if the response already started, the error is passed on instead of writing a second response', () => {
  const r = handle(new Error('late'), { headersSent: true });
  assert.equal(r.code, 0);
  assert.ok(r.nextCalled instanceof Error);
  assert.equal(r.logged.length, 1);
});

test('process handlers: an unhandled rejection is logged and the process keeps running; an uncaught exception is logged and exits 1; uninstall works', () => {
  const exits: Array<number | undefined> = [];
  const proc = Object.assign(new EventEmitter(), { exit: ((code?: number) => { exits.push(code); }) as (code?: number) => never });
  const logged: string[] = [];
  const off = installProcessHandlers(proc, { error: (...a) => { logged.push(a.join(' ')); } });
  proc.emit('unhandledRejection', new Error('nobody awaited me'));
  assert.deepEqual(exits, [], 'a stray rejection does not take the server down');
  assert.match(logged[0], /unhandled rejection: nobody awaited me/);
  proc.emit('uncaughtException', new Error('invariant broken'));
  assert.deepEqual(exits, [1]);
  assert.match(logged[1], /uncaught exception, exiting: invariant broken/);
  proc.emit('unhandledRejection', 'a string reason');
  assert.match(logged[2], /a string reason/);
  off();
  assert.equal(proc.listenerCount('unhandledRejection') + proc.listenerCount('uncaughtException'), 0);
});

test('RunStore: a corrupt runs file is kept (not overwritten by the next save), loudly; a missing file is a quiet fresh start; a good file loads', () => {
  const warnings: string[] = [];
  const realWarn = console.warn;
  console.warn = (...a: unknown[]) => { warnings.push(a.join(' ')); };
  try {
    const dir = fs.mkdtempSync(path.join(tmp, 'runs-'));
    const file = path.join(dir, 'runs.json');

    new RunStore(file);
    assert.deepEqual(warnings, [], 'no file yet is not a warning');
    assert.deepEqual(fs.readdirSync(dir).filter((f) => f.includes('corrupt')), []);

    fs.writeFileSync(file, '[{"id":"r1","status":"completed"},{"id":"r2" TRUNCATED');
    new RunStore(file);
    const kept = fs.readdirSync(dir).filter((f) => f.startsWith('runs.json.corrupt-'));
    assert.equal(kept.length, 1, 'the unreadable file is preserved');
    assert.equal(fs.readFileSync(path.join(dir, kept[0]), 'utf8'), '[{"id":"r1","status":"completed"},{"id":"r2" TRUNCATED', 'byte for byte');
    assert.match(warnings[0], /could not read .*runs\.json.*starting empty, original kept at/);

    fs.writeFileSync(file, JSON.stringify([{ id: 'ok', status: 'running' }]));
    warnings.length = 0;
    const good = new RunStore(file) as unknown as { runs: Array<{ id: string; status: string; failure_kind?: string }> };
    assert.deepEqual(warnings, []);
    assert.equal(good.runs[0].status, 'failed', 'an interrupted run is marked as such');
    assert.equal(good.runs[0].failure_kind, 'interrupted');
  } finally {
    console.warn = realWarn;
  }
});

test('git status: a directory git cannot read reports an error instead of an empty (clean-looking) status; a real repo reports clean and dirty', () => {
  const base = fs.mkdtempSync(path.join(tmp, 'git-'));
  const m = new GitRepoManager(base);
  const notRepo = path.join(base, 'plain');
  fs.mkdirSync(notRepo);
  const bad = m.getRepositoryStatus(notRepo);
  assert.equal(bad.isDirty, false);
  assert.ok(bad.error && bad.error.length > 0, 'the failure is reported');
  assert.equal(bad.error!.includes('\n'), false, 'one line');

  const repo = path.join(base, 'repo');
  fs.mkdirSync(repo);
  execFileSync('git', ['init', '-q'], { cwd: repo });
  const clean = m.getRepositoryStatus(repo);
  assert.deepEqual(clean, { isDirty: false, changes: [] }, 'a clean repository has no error field');
  fs.writeFileSync(path.join(repo, 'new.txt'), 'x');
  assert.deepEqual(m.getRepositoryStatus(repo), { isDirty: true, changes: ['new.txt'] });
});

// ─── Real server ─────────────────────────────────────────────
async function start(): Promise<{ url: string; port: number }> {
  const port = 20000 + Math.floor(Math.random() * 20000);
  const dead = 'http://127.0.0.1:9';
  const proc = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: {
      ...process.env, PORT: String(port), INCEPTION_API_KEY: 'test', INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: dead, JANUS_BASE_URL: dead,
      UPSTASH_VECTOR_REST_URL: dead, UPSTASH_VECTOR_REST_TOKEN: 'none', KUDBEE_DAILY_BUDGET_USD: '0', THINKBOX_BACKEND_URL: dead,
      KUDBEE_DATA_DIR: path.join(tmp, `d-${port}`), KUDBEE_WORKSPACE_DIR: path.join(tmp, `w-${port}`),
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

test('real server: bad input gets a JSON error (not Express\'s HTML page with a stack trace), and unknown API paths are JSON 404s', async () => {
  const s = await start();
  const json = { 'Content-Type': 'application/json' };

  const malformed = await fetch(`${s.url}/api/git/clone`, { method: 'POST', headers: json, body: '{"url": ' });
  assert.equal(malformed.status, 400);
  assert.match(malformed.headers.get('content-type') ?? '', /application\/json/);
  const mb = await malformed.json() as { error: string; detail?: string };
  assert.equal(mb.error, 'invalid_json');

  const tooBig = await fetch(`${s.url}/api/git/clone`, { method: 'POST', headers: json, body: JSON.stringify({ url: 'x'.repeat(300_000) }) });
  assert.equal(tooBig.status, 413);
  assert.equal(((await tooBig.json()) as { error: string }).error, 'payload_too_large');

  const unknown = await fetch(`${s.url}/api/does/not/exist`);
  assert.equal(unknown.status, 404);
  assert.deepEqual(await unknown.json(), { error: 'not_found' });

  // multer fails on a broken multipart body inside the middleware chain: that used to be an HTML 500 with the stack
  const broken = await fetch(`${s.url}/api/sessions/00000000-0000-4000-8000-000000000000/files`, {
    method: 'POST', headers: { 'Content-Type': 'multipart/form-data; boundary=xyz' }, body: '--xyz\r\nContent-Disposition: form-data; name="files"; filename="a.txt"\r\n\r\nno closing boundary',
  });
  assert.ok(broken.status >= 400 && broken.status < 600);
  assert.match(broken.headers.get('content-type') ?? '', /application\/json/, 'JSON, not Express\'s HTML error page');
  const text = await broken.text();
  assert.ok(!/\sat\s.*\(.*:\d+:\d+\)/.test(text) && !text.includes('node_modules'), 'no stack trace in the response');
  assert.equal((await fetch(`${s.url}/api/health`)).status, 200, 'the server is still up');
});

test('server.ts installs the process handlers and mounts the error middleware after every route and before listen()', () => {
  const src = fs.readFileSync(path.join(appDir, 'server.ts'), 'utf8');
  const at = (needle: string) => src.lastIndexOf(needle);
  assert.ok(src.includes('installProcessHandlers(process);'), 'process handlers installed');
  const mount = src.indexOf('app.use(jsonErrorHandler());');
  assert.ok(mount > 0, 'error middleware mounted');
  const lastRoute = Math.max(at('\napp.get('), at('\napp.post('), at('\napp.put('), at('\napp.delete('), at('\napp.patch('), at("app.use('/api/git'"));
  assert.ok(mount > lastRoute, 'an error middleware only sees errors from routes registered before it');
  assert.ok(mount < src.indexOf('server.listen(PORT_NUM'), 'and it must be in place before the server listens');
  assert.ok(src.indexOf("app.use('/api', (_req: Request, res: Response) => { res.status(404)") < mount, 'the JSON 404 comes first so unknown API paths do not fall into the error handler');
});
