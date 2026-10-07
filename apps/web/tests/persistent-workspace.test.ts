// Files an agent creates (and repositories you clone) survive a page reload and a server restart: interactive sessions share one workspace per profile
// instead of getting a new, empty folder each. Unit tests for the resolver, then the real server with two "page loads" and a restart.
import assert from 'node:assert/strict';
import { spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';
import { freePort } from './helpers/free-port.ts';
import { createWorkspaceResolver } from '../workspace-resolver.ts';

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const A = '11111111-1111-4111-8111-111111111111'; const B = '22222222-2222-4222-8222-222222222222'; const BOX = '33333333-3333-4333-8333-333333333333';
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-ws-'));
after(() => fs.rmSync(tmp, { recursive: true, force: true }));

test('resolver: interactive sessions share the active profile workspace; an isolated box and a legacy folder keep their own', () => {
  const root = path.join(tmp, 'unit'); fs.mkdirSync(root, { recursive: true });
  let profile = 'default';
  const r = createWorkspaceResolver({ root, activeProfile: () => profile });
  r.register(A); r.register(B);
  assert.equal(r.dirFor(A), r.dirFor(B)); assert.equal(r.dirFor(A), path.join(root, '_profiles', 'default')); assert.ok(fs.existsSync(r.dirFor(A)));
  profile = 'work'; assert.equal(r.dirFor(A), path.join(root, '_profiles', 'work'), 'switching profile switches the workspace');
  assert.equal(r.isolate(BOX), path.join(root, BOX)); assert.equal(r.dirFor(BOX), path.join(root, BOX)); assert.ok(fs.existsSync(path.join(root, BOX)));
  const legacy = '44444444-4444-4444-8444-444444444444'; fs.mkdirSync(path.join(root, legacy));
  assert.equal(r.dirFor(legacy), path.join(root, legacy)); assert.ok(r.exists(legacy));
  const unknown = '55555555-5555-4555-8555-555555555555'; assert.equal(r.exists(unknown), false); assert.equal(r.dirFor(unknown), path.join(root, unknown));
  assert.throws(() => r.dirFor('../../etc'), /Invalid session id/); assert.throws(() => r.register('x'), /Invalid session id/);
  assert.match(r.profileDir('we/ird name'), /_profiles\/p-[0-9a-f]{12}$/, 'an unsafe profile id is hashed, never used as a path');
});

test('resolver: pruneEmpty removes only empty, old, UUID-named folders', () => {
  const root = path.join(tmp, 'prune'); fs.mkdirSync(root, { recursive: true });
  const empty = '66666666-6666-4666-8666-666666666666'; const full = '77777777-7777-4777-8777-777777777777'; const fresh = '88888888-8888-4888-8888-888888888888';
  for (const d of [empty, full, fresh, 'notes', '_profiles']) fs.mkdirSync(path.join(root, d));
  fs.writeFileSync(path.join(root, full, 'a.md'), 'x');
  const old = new Date(Date.now() - 3600_000); fs.utimesSync(path.join(root, empty), old, old); fs.utimesSync(path.join(root, full), old, old);
  const r = createWorkspaceResolver({ root, activeProfile: () => 'default' });
  assert.equal(r.pruneEmpty(), 1);
  assert.ok(!fs.existsSync(path.join(root, empty)) && fs.existsSync(path.join(root, full)) && fs.existsSync(path.join(root, fresh)) && fs.existsSync(path.join(root, 'notes')) && fs.existsSync(path.join(root, '_profiles')));
  const boxed = '99999999-9999-4999-8999-999999999999'; const rr = createWorkspaceResolver({ root, activeProfile: () => 'default' }); rr.isolate(boxed); fs.utimesSync(path.join(root, boxed), old, old);
  assert.equal(rr.pruneEmpty(), 0, 'an isolated box folder is never pruned');
});

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
async function boot(): Promise<{ base: string; stop: () => void }> {
  const port = await freePort(); const base = `http://127.0.0.1:${port}`;
  const dead = 'http://127.0.0.1:9';
  const server: ChildProcess = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], { cwd: appDir, stdio: 'ignore', env: { ...process.env, PORT: String(port), HOST: '127.0.0.1', INCEPTION_API_KEY: '', DEEPSEEK_API_KEY: '', XAI_API_KEY: '', OLLAMA_BASE_URL: dead, JANUS_BASE_URL: dead, UPSTASH_VECTOR_REST_URL: dead, UPSTASH_VECTOR_REST_TOKEN: 'none', THINKBOX_EMBEDDINGS: 'off', KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_LEARNING_DB: path.join(tmp, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws') } });
  for (let i = 0; i < 100; i++) { try { if ((await fetch(`${base}/api/health`)).ok) return { base, stop: () => server.kill() }; } catch { /* starting */ } await new Promise((r) => setTimeout(r, 150)); }
  server.kill(); throw new Error('server did not start');
}
async function sessionId(base: string): Promise<{ id: string; close: () => void }> {
  const ws = new WebSocket(`${base.replace('http', 'ws')}/ws`, { origin: base });
  const id = await new Promise<string>((resolve, reject) => { const t = setTimeout(() => reject(new Error('no session id')), 10_000); ws.on('message', (raw) => { const m = JSON.parse(raw.toString()) as { type?: string; data?: { sessionId?: string } }; if (m.data?.sessionId) { clearTimeout(t); resolve(m.data.sessionId); } }); });
  return { id, close: () => ws.close() };
}
const listing = async (base: string, id: string): Promise<string[]> => ((await (await fetch(`${base}/api/sessions/${id}/files`)).json()) as { files: Array<{ path: string }> }).files.map((f) => f.path);

test('real server: a file made in one page load is in the next one, after a restart too, and no empty folder is left per page load', async () => {
  const wsRoot = path.join(tmp, 'ws'); fs.mkdirSync(wsRoot, { recursive: true });
  const stale = '12121212-1212-4212-8212-121212121212'; fs.mkdirSync(path.join(wsRoot, stale)); const old = new Date(Date.now() - 3600_000); fs.utimesSync(path.join(wsRoot, stale), old, old);
  let s = await boot();
  try {
    assert.ok(!fs.existsSync(path.join(wsRoot, stale)), 'the empty folder an earlier version left was removed at startup');
    const one = await sessionId(s.base);
    const form = new FormData(); form.append('files', new Blob(['hello from the agent']), 'main.md');
    assert.equal((await fetch(`${s.base}/api/sessions/${one.id}/files`, { method: 'POST', body: form })).status, 201);
    assert.deepEqual(await listing(s.base, one.id), ['main.md']); one.close();
    const two = await sessionId(s.base); assert.notEqual(two.id, one.id, 'a reload is a new session');
    assert.deepEqual(await listing(s.base, two.id), ['main.md'], 'but it sees the same files'); two.close();
    const dirs = fs.readdirSync(wsRoot).filter((d) => ID.test(d)); assert.deepEqual(dirs, [], 'no per-session folder was created');
    s.stop(); await new Promise((r) => setTimeout(r, 400)); s = await boot();
    const three = await sessionId(s.base); assert.deepEqual(await listing(s.base, three.id), ['main.md'], 'and after a server restart'); three.close();
    assert.equal(fs.readFileSync(path.join(wsRoot, '_profiles', fs.readdirSync(path.join(wsRoot, '_profiles'))[0]!, 'main.md'), 'utf8'), 'hello from the agent');
  } finally { s.stop(); }
});
