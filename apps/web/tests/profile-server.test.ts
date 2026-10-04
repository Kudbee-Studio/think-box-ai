// End-to-end profiles against the real server.ts: memory and run history are isolated per profile and
// restored when switching back. Uses the mock Inception API; no network, Ollama, Janus or Upstash.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { startMockInception, say, type MockInception } from './helpers/mock-inception.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEAD = 'http://127.0.0.1:9';
let mock: MockInception;
let server: ChildProcess;
let base: string;
let tmpRoot: string;

async function waitForHealth(url: string, ms = 15000): Promise<void> {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    try {
      if ((await fetch(`${url}/api/health`)).ok) return;
    } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 150));
  }
  throw new Error('server did not start');
}

before(async () => {
  mock = await startMockInception();
  tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-profile-e2e-'));
  const port = 20000 + Math.floor(Math.random() * 20000);
  base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: {
      ...process.env,
      PORT: String(port),
      INCEPTION_API_KEY: 'test-key', INCEPTION_API_KEY_2: '',
      INCEPTION_BASE_URL: mock.baseUrl,
      OLLAMA_BASE_URL: DEAD,
      JANUS_BASE_URL: DEAD,
      UPSTASH_VECTOR_REST_URL: DEAD,
      UPSTASH_VECTOR_REST_TOKEN: 'none',
      THINKBOX_EMBEDDINGS: 'off',
      KUDBEE_DAILY_BUDGET_USD: '0',
      KUDBEE_DATA_DIR: path.join(tmpRoot, 'data'),
      KUDBEE_LEARNING_DB: path.join(tmpRoot, 'learning.db'),
      KUDBEE_WORKSPACE_DIR: path.join(tmpRoot, 'workspaces'),
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  await waitForHealth(base);
});

after(async () => {
  server?.kill();
  await mock.close();
});

const json = async (url: string, init?: RequestInit) => {
  const res = await fetch(`${base}${url}`, init);
  return { status: res.status, body: (await res.json()) as any };
};
const post = (url: string, body: unknown) => json(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

test('profiles isolate memory and runs, and export/import uses a fresh UUID', async () => {
  // The default profile exists and is active.
  const initial = await json('/api/profiles');
  assert.equal(initial.status, 200);
  assert.equal(initial.body.profiles.length, 1);
  const defaultId = initial.body.active as string;
  assert.equal(initial.body.profiles[0].is_active, true);

  // Create Alpha and switch to it.
  const alpha = (await post('/api/profiles', { name: 'Alpha', description: 'work', settings: { theme: 'dark' } })).body;
  assert.equal(alpha.name, 'Alpha');
  const activated = await post(`/api/profiles/${alpha.id}/activate`, {});
  assert.equal(activated.status, 200);
  assert.equal(activated.body.id, alpha.id);
  assert.equal((await json('/api/profiles/active')).body.id, alpha.id);

  // Write memory under Alpha.
  const written = await post('/api/memory', { layer: 'org', title: 'Alpha-only fact', content: 'The Alpha profile knows this.' });
  assert.equal(written.status, 201);
  const alphaMemory = await json('/api/memory?limit=50');
  assert.ok(alphaMemory.body.items.some((i: any) => i.title === 'Alpha-only fact'), 'Alpha sees its own memory');
  const alphaCounts = (await json('/api/memory/status')).body.counts;
  assert.equal(alphaCounts.org, 1);

  // Create Beta and switch: memory is gone.
  const beta = (await post('/api/profiles', { name: 'Beta' })).body;
  await post(`/api/profiles/${beta.id}/activate`, {});
  const betaMemory = await json('/api/memory?limit=50');
  assert.equal(betaMemory.body.items.length, 0, 'Beta sees none of Alpha memory');
  assert.deepEqual((await json('/api/memory/status')).body.counts, { task: 0, org: 0, verified: 0 });

  // Beta writes its own; Alpha must not see it.
  await post('/api/memory', { layer: 'org', title: 'Beta-only fact', content: 'The Beta profile knows this.' });
  await post(`/api/profiles/${alpha.id}/activate`, {});
  const alphaAgain = await json('/api/memory?limit=50');
  assert.ok(alphaAgain.body.items.some((i: any) => i.title === 'Alpha-only fact'), 'Alpha memory restored');
  assert.ok(!alphaAgain.body.items.some((i: any) => i.title === 'Beta-only fact'), 'Beta memory invisible to Alpha');

  // Export Alpha; the bundle carries its memory and runs list.
  const bundle = (await json(`/api/profiles/${alpha.id}/export`)).body;
  assert.equal(bundle.format, 'kudbee-profile');
  assert.equal(bundle.profile.name, 'Alpha');
  assert.ok(bundle.memory.org.some((i: any) => i.title === 'Alpha-only fact'));
  assert.ok(Array.isArray(bundle.runs));

  // Import: a new profile with a fresh UUID and the memory copied in.
  const imported = await post('/api/profiles/import', bundle);
  assert.equal(imported.status, 201);
  assert.notEqual(imported.body.id, alpha.id);
  assert.match(imported.body.name, /imported/);
  const importMemory = (await json(`/api/profiles/${imported.body.id}/export`)).body.memory.org;
  assert.ok(importMemory.some((i: any) => i.title === 'Alpha-only fact'), 'memory rides along with the import');

  // Clean up the extra profiles so the runs-filter test below starts from a known state.
  await post(`/api/profiles/${beta.id}/activate`, {});
  assert.equal((await json(`/api/profiles/${beta.id}`, { method: 'DELETE' })).status, 200);
  assert.equal((await json(`/api/profiles/${imported.body.id}`, { method: 'DELETE' })).status, 200);
  assert.equal((await json(`/api/profiles/${alpha.id}`, { method: 'DELETE' })).status, 200);
  assert.equal((await json('/api/profiles/active')).body.id, defaultId, 'deleting active profile falls back');
});

test('run history is filtered to the active profile', async () => {
  const activeId = (await json('/api/profiles/active')).body.id;
  const before = (await json('/api/runs?limit=50')).body;
  assert.ok(Array.isArray(before.runs));

  // A goal streamed over WS creates a run stamped with the active profile.
  mock.script([say('{"answer": 42}')]);
  const { WebSocket } = await import('ws');
  const ws = new WebSocket(`${base.replace('http', 'ws')}/ws`, { origin: base });
  const messages: any[] = [];
  ws.on('message', (raw) => messages.push(JSON.parse(raw.toString())));
  await new Promise<void>((resolve) => ws.on('open', () => resolve()));
  ws.send(JSON.stringify({ type: 'run_goal', goal: 'profile run test' }));
  const end = Date.now() + 10000;
  while (Date.now() < end && !messages.some((m) => m.type === 'result')) await new Promise((r) => setTimeout(r, 100));
  ws.close();
  assert.ok(mock.requests.length > 0, 'the mock model was actually called');

  const after = (await json('/api/runs?limit=50')).body;
  const mine = after.runs.filter((r: any) => r.profile_id === activeId);
  assert.ok(mine.length >= 1, 'the new run is listed for the active profile');
  assert.ok(after.runs.every((r: any) => r.profile_id === undefined || r.profile_id === activeId), 'only the active profile runs are listed');
});
