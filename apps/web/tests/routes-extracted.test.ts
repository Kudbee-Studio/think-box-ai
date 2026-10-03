// Route groups moved out of server.ts into routes/*.ts (diagnostics, runs, memory). Boots the REAL server on a random loopback port and
// exercises each moved group end to end, plus the one behavioural fix that came with the move: /api/runs/history was registered after
// /api/runs/:id, so ":id" captured "history" and the endpoint always answered 404 "Run not found".
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let tmp: string;
const procs: ChildProcess[] = [];
let url = '';
before(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-routes-'));
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
  url = `http://127.0.0.1:${port}`;
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) {
    try { if ((await fetch(`${url}/api/health`)).ok) return; } catch { /* starting */ }
  }
  throw new Error('server did not start');
});
after(() => { for (const p of procs) p.kill('SIGKILL'); fs.rmSync(tmp, { recursive: true, force: true }); });

const json = { 'Content-Type': 'application/json' };
const get = async (p: string) => { const r = await fetch(url + p); return { status: r.status, body: await r.json() as any }; };
const send = async (method: string, p: string, body?: unknown) => { const r = await fetch(url + p, { method, headers: json, body: body === undefined ? undefined : JSON.stringify(body) }); return { status: r.status, body: await r.json() as any }; };

test('diagnostics routes: health, stats (and its cache), monitor and the middleware test', async () => {
  const health = await get('/api/health');
  assert.equal(health.status, 200);
  assert.equal(health.body.status, 'ok');
  assert.equal(health.body.ready, true);
  assert.equal(typeof health.body.sdk_version, 'string');
  assert.ok(health.body.uptime_seconds >= 0 && health.body.memory_mb > 0);

  const stats = await get('/api/stats');
  assert.equal(stats.status, 200);
  assert.deepEqual(Object.keys(stats.body.capacity).sort(), ['connected_sessions', 'cores', 'load_avg', 'pending_approvals', 'queued_goals', 'running_agents', 'server_cpu_pct', 'server_rss_mb', 'system_mem_total_gb', 'system_mem_used_pct']);
  assert.deepEqual(Object.keys(stats.body.memory.counts).sort(), ['org', 'task', 'verified']);
  assert.deepEqual((await get('/api/stats')).body, stats.body, 'a second poll inside 500 ms is served from the cache');

  const monitor = await get('/api/monitor');
  assert.equal(monitor.status, 200);
  const byName = Object.fromEntries((monitor.body.checks as Array<{ name: string; status: string }>).map((c) => [c.name, c.status]));
  assert.equal(byName['Agent OS API'], 'ok');
  assert.equal(byName['Ollama models'], 'offline', 'Ollama is pointed at a dead port');
  assert.ok(monitor.body.agent.checks >= 1, 'the monitor agent counted this check');

  const mw = await get('/api/middleware/test');
  assert.equal(mw.status, 503, 'one of the three checks (Ollama) is down, so the middleware test fails');
  assert.equal(mw.body.passed, false);
  assert.equal(mw.body.checks.length, 3);
});

test('runs routes: list, unknown run, and /api/runs/history is reachable (it used to be shadowed by /api/runs/:id)', async () => {
  const list = await get('/api/runs');
  assert.equal(list.status, 200);
  assert.deepEqual(list.body.runs, []);

  const unknown = await get('/api/runs/not-a-run');
  assert.equal(unknown.status, 404);
  assert.deepEqual(unknown.body, { error: 'Run not found' });

  const noSession = await get('/api/runs/history');
  assert.equal(noSession.status, 400, 'reaches the history handler, not the :id handler');
  assert.deepEqual(noSession.body, { error: 'sessionId required' });

  const history = await get('/api/runs/history?sessionId=abc');
  assert.equal(history.status, 200);
  assert.deepEqual(history.body, { runs: [], source: 'json' });

  const tokens = await get('/api/stats/tokens');
  assert.equal(tokens.status, 400);
  const tokenStats = await get('/api/stats/tokens?sessionId=abc');
  assert.equal(tokenStats.status, 200);
  assert.deepEqual(tokenStats.body, { totalTokensSavedEst: 0, totalRunsTracked: 0, averageSavingsPerRun: 0, lastRunTokensSaved: 0, sparklineData: [] });
});

test('memory routes: write, list, search, read, promote, delete, and the validation errors', async () => {
  assert.equal((await get('/api/memory/status')).body.counts.org, 0);
  assert.equal((await send('POST', '/api/memory', { title: '', content: 'x' })).status, 400);
  assert.deepEqual((await send('POST', '/api/memory', { title: 't', content: 'c', layer: 'task' })).body, { error: 'Task memory is written automatically by runs' });

  const created = await send('POST', '/api/memory', { title: 'Port rule', content: 'The dashboard listens on loopback only.', tags: 'security, network' });
  assert.equal(created.status, 201);
  assert.equal(created.body.layer, 'org');
  assert.deepEqual(created.body.tags, ['security', 'network']);

  const listed = await get('/api/memory?layer=org');
  assert.equal(listed.body.backend, 'list');
  assert.equal(listed.body.items.length, 1);
  const found = await get('/api/memory?q=loopback');
  assert.equal(found.body.items[0].id, created.body.id, 'search finds it');

  assert.equal((await get(`/api/memory/item?id=${encodeURIComponent(created.body.id)}`)).body.title, 'Port rule');
  assert.equal((await get('/api/memory/item?id=missing')).status, 404);
  assert.equal((await send('POST', '/api/memory/promote', { id: 'missing' })).status, 400);

  const promoted = await send('POST', '/api/memory/promote', { id: created.body.id });
  assert.equal(promoted.status, 200);
  assert.equal(promoted.body.layer, 'verified');

  const removed = await send('DELETE', `/api/memory/item?id=${encodeURIComponent(promoted.body.id)}`);
  assert.deepEqual(removed.body, { success: true });
  assert.equal((await send('DELETE', '/api/memory/item?id=gone')).status, 404);
});

test('memory notes routes: validation, create and the soft delete', async () => {
  assert.equal((await get('/api/memory/notes')).status, 400);
  assert.deepEqual((await send('POST', '/api/memory/notes?sessionId=s1', { title: 'only a title' })).body, { error: 'sessionId, title, content required' });
  const note = await send('POST', '/api/memory/notes?sessionId=s1', { title: 'N', content: 'body', layer: 'org' });
  assert.equal(note.status, 200);
  assert.equal(note.body.title, 'N');
  assert.match(note.body.id, /^[0-9a-f-]{36}$/);
  const notes = await get('/api/memory/notes?sessionId=s1');
  assert.equal(notes.status, 200);
  assert.ok(notes.body.notes.some((n: { title: string }) => n.title === 'N'));
  assert.deepEqual((await send('DELETE', `/api/memory/notes/${note.body.id}`)).body, { deleted: note.body.id });
});

test('server.ts no longer defines the moved routes inline', () => {
  const src = fs.readFileSync(path.join(appDir, 'server.ts'), 'utf8');
  for (const gone of ["'/api/health'", "'/api/monitor'", "'/api/stats'", "'/api/runs'", "'/api/runs/history'", "'/api/memory'", "'/api/memory/notes'"]) {
    assert.ok(!src.includes(`app.get(${gone}`) && !src.includes(`app.post(${gone}`), `${gone} is registered from routes/*.ts`);
  }
  assert.ok(src.split('\n').length < 2500, 'server.ts keeps shrinking, not growing back');
});
