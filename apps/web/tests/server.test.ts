// End-to-end: boots the real server.ts on a random port against the mock Inception API, then drives it
// over WebSocket and REST like the dashboard and `kudbee` CLI do. No network, Ollama, Janus or Upstash.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';
import { startMockInception, say, call, type MockInception } from './helpers/mock-inception.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEAD = 'http://127.0.0.1:9'; // nothing listens here: Ollama, Janus and Upstash are "offline"
let mock: MockInception;
let server: ChildProcess;
let base: string;
let tmpRoot: string;

async function waitForHealth(url: string, ms = 15000): Promise<void> {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    try {
      if ((await fetch(`${url}/api/health`)).ok) return;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 150));
  }
  throw new Error('server did not start');
}

before(async () => {
  mock = await startMockInception();
  tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-server-test-'));
  const port = 20000 + Math.floor(Math.random() * 20000);
  base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: {
      ...process.env,
      PORT: String(port),
      INCEPTION_API_KEY: 'test-key',
      INCEPTION_BASE_URL: mock.baseUrl,
      OLLAMA_BASE_URL: DEAD,
      JANUS_BASE_URL: DEAD,
      UPSTASH_VECTOR_REST_URL: DEAD,
      UPSTASH_VECTOR_REST_TOKEN: 'none',
      KUDBEE_DAILY_BUDGET_USD: '0',
      KUDBEE_DATA_DIR: path.join(tmpRoot, 'data'),
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

interface Client {
  ws: WebSocket;
  init: any;
  messages: any[];
  next(type: string, ms?: number): Promise<any>;
  send(msg: Record<string, unknown>): void;
}

async function connect(): Promise<Client> {
  const ws = new WebSocket(`${base.replace('http', 'ws')}/ws`, { origin: base });
  const messages: any[] = [];
  const waiters: Array<{ type: string; resolve: (m: any) => void }> = [];
  ws.on('message', (raw) => {
    const msg = JSON.parse(raw.toString());
    messages.push(msg);
    const i = waiters.findIndex((w) => w.type === msg.type);
    if (i >= 0) waiters.splice(i, 1)[0].resolve(msg);
  });
  const next = (type: string, ms = 10000) =>
    new Promise<any>((resolve, reject) => {
      const seen = messages.find((m) => m.type === type && !m.__taken);
      if (seen) {
        seen.__taken = true;
        return resolve(seen);
      }
      const timer = setTimeout(() => reject(new Error(`timed out waiting for ${type}`)), ms);
      waiters.push({
        type,
        resolve: (m) => {
          clearTimeout(timer);
          m.__taken = true;
          resolve(m);
        },
      });
    });
  const init = await next('init');
  return { ws, init, messages, next, send: (msg) => ws.send(JSON.stringify(msg)) };
}

const json = async (url: string, init?: RequestInit) => {
  const res = await fetch(`${base}${url}`, init);
  return { status: res.status, body: (await res.json()) as any };
};

test('init advertises mercury-2 as the default worker model and the plugins', async () => {
  const client = await connect();
  try {
    assert.equal(client.init.data.config.model, 'mercury-2');
    assert.equal(client.init.data.models[0].name, 'mercury-2');
    assert.ok(client.init.data.plugins.some((p: any) => p.name === 'git_repository'));
  } finally {
    client.ws.close();
  }
});

test('a goal runs end to end: file written, run persisted, episode saved to task memory', async () => {
  mock.script([call('write_file', { path: 'report.md', content: '# Report' }), say('Wrote report.md')]);
  const client = await connect();
  try {
    client.send({ type: 'run_goal', goal: 'Write the quarterly report', model: 'mercury-2' });
    const { data: result } = await client.next('result');
    assert.equal(result.success, true);
    assert.equal(result.result, 'Wrote report.md');
    assert.deepEqual(result.files, ['report.md']);
    assert.ok(result.cost_usd > 0);

    const files = await json(`/api/sessions/${client.init.data.sessionId}/files`);
    assert.deepEqual(files.body.files.map((f: any) => f.path), ['report.md']);

    const runRecord = await json(`/api/runs/${result.run_id}`);
    assert.equal(runRecord.body.status, 'completed');
    assert.deepEqual(runRecord.body.steps.map((s: any) => s.kind), ['model', 'tool', 'model']);

    await client.next('memory_changed');
    const memory = await json('/api/memory?layer=task');
    const episode = memory.body.items.find((i: any) => i.title === 'Write the quarterly report');
    assert.ok(episode, 'task episode written');
    const full = await json(`/api/memory/item?id=${encodeURIComponent(episode.id)}`);
    assert.match(full.body.content, /Outcome: completed/);
    assert.match(full.body.content, /Answer given \(unverified\):\nWrote report\.md/);
  } finally {
    client.ws.close();
  }
});

test('the next related goal recalls the earlier episode into the system prompt', async () => {
  mock.script([say('noted')]);
  const client = await connect();
  try {
    client.send({ type: 'run_goal', goal: 'Update the quarterly report', model: 'mercury-2' });
    const { data: result } = await client.next('result');
    assert.equal(result.success, true);
    const system = String(mock.requests[0].messages[0].content);
    assert.match(system, /Relevant memories:/);
    assert.match(system, /PAST RUN .*Write the quarterly report/);
    assert.doesNotMatch(system, /Wrote report\.md/, 'past answers are not fed back');
    const runRecord = await json(`/api/runs/${result.run_id}`);
    assert.ok(runRecord.body.recalled.length >= 1);
  } finally {
    client.ws.close();
  }
});

test('approval request over WebSocket: a denied overwrite keeps the original file', async () => {
  mock.script([
    call('write_file', { path: 'a.txt', content: 'first' }),
    call('write_file', { path: 'a.txt', content: 'second' }),
    say('done'),
  ]);
  const client = await connect();
  try {
    client.send({ type: 'run_goal', goal: 'write a.txt twice', model: 'mercury-2' });
    const request = await client.next('approval_request');
    assert.match(request.data.reason, /Overwrites existing file a\.txt/);
    client.send({ type: 'approval_response', id: request.data.id, approved: false });
    const { data: result } = await client.next('result');
    const content = await json(`/api/sessions/${client.init.data.sessionId}/files/content?path=a.txt`);
    assert.equal(content.body.content, 'first');
    const runRecord = await json(`/api/runs/${result.run_id}`);
    assert.deepEqual(runRecord.body.approvals, { approved: 0, denied: 1 });
  } finally {
    client.ws.close();
  }
});

test('stop ends a slow run and it is recorded as stopped', async () => {
  mock.script([{ content: 'too slow', delayMs: 5000 }]);
  const client = await connect();
  try {
    client.send({ type: 'run_goal', goal: 'slow goal', model: 'mercury-2' });
    await client.next('run_update');
    setTimeout(() => client.send({ type: 'stop' }), 200);
    const { data: result } = await client.next('result');
    assert.equal(result.success, false);
    assert.match(result.error, /Stopped by user/);
    const runRecord = await json(`/api/runs/${result.run_id}`);
    assert.equal(runRecord.body.status, 'stopped');
    assert.equal(runRecord.body.failure_kind, 'stopped');
  } finally {
    client.ws.close();
  }
});

test('stats reflect the runs and report the vector backend as offline', async () => {
  const stats = await json('/api/stats');
  assert.ok(stats.body.runs_total >= 4);
  assert.ok(stats.body.failures.stopped >= 1);
  assert.equal(stats.body.memory.vector.backend, 'upstash-sparse');
  const status = await json('/api/memory/status');
  assert.ok(status.body.counts.task >= 3);
});

test('memory REST: add, search (falls back to local), promote, delete; bad input rejected', async () => {
  const created = await json('/api/memory', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: 'Deploy checklist lives in docs', content: 'See docs/deploy.md before releasing.', tags: 'ops, deploy' }),
  });
  assert.equal(created.status, 201);
  assert.equal(created.body.layer, 'org');
  assert.deepEqual(created.body.tags, ['ops', 'deploy']);

  const search = await json('/api/memory?q=deploy%20checklist');
  assert.equal(search.body.backend, 'local-bm25 (vector offline)');
  assert.equal(search.body.items[0].id, created.body.id);

  const promoted = await json('/api/memory/promote', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: created.body.id }) });
  assert.equal(promoted.body.layer, 'verified');
  const removed = await json(`/api/memory/item?id=${encodeURIComponent(promoted.body.id)}`, { method: 'DELETE' });
  assert.equal(removed.body.success, true);

  assert.equal((await json('/api/memory', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: 'x' }) })).status, 400);
  assert.equal((await json('/api/memory', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ layer: 'task', title: 'x', content: 'y' }) })).status, 400);
  assert.equal((await json('/api/memory/item?id=../../etc/passwd')).status, 404);
});

test('workspace routes reject non-session ids and path traversal', async () => {
  assert.equal((await json('/api/sessions/..%2F..%2Fetc/files')).status, 404);
  const client = await connect();
  try {
    const res = await json(`/api/sessions/${client.init.data.sessionId}/files/content?path=../../server.ts`);
    assert.equal(res.status, 400);
    assert.match(res.body.error, /Invalid workspace path|escapes/);
  } finally {
    client.ws.close();
  }
});

test('goals sent while one runs are queued and run in order, one at a time', async () => {
  mock.script([{ content: 'first answer', delayMs: 300 }, say('second answer')]);
  const client = await connect();
  try {
    client.send({ type: 'run_goal', goal: 'first goal', model: 'mercury-2' });
    client.send({ type: 'run_goal', goal: 'second goal', model: 'mercury-2' });
    const queued = await client.next('queued');
    assert.equal(queued.data.goal, 'second goal');
    assert.equal(queued.data.position, 1);
    const queuedTask = client.messages.find((m) => m.type === 'task' && m.data.description === 'second goal');
    assert.equal(queuedTask.data.status, 'queued');

    const first = await client.next('result');
    const second = await client.next('result');
    assert.equal(first.data.result, 'first answer');
    assert.equal(second.data.result, 'second answer');
    // The queued task is reused (not duplicated) once it starts.
    const secondRun = await json(`/api/runs/${second.data.run_id}`);
    assert.equal(secondRun.body.id, queuedTask.data.id);
    assert.equal(mock.requests.length, 2, 'never two model calls in flight for one session');
  } finally {
    client.ws.close();
  }
});

test('stop aborts the running goal and cancels everything queued behind it', async () => {
  mock.script([{ content: 'slow', delayMs: 5000 }, say('must not run'), say('must not run')]);
  const client = await connect();
  try {
    client.send({ type: 'run_goal', goal: 'long goal', model: 'mercury-2' });
    client.send({ type: 'run_goal', goal: 'queued one', model: 'mercury-2' });
    client.send({ type: 'run_goal', goal: 'queued two', model: 'mercury-2' });
    await client.next('queued');
    await client.next('queued');
    client.send({ type: 'stop' });
    const results = [await client.next('result'), await client.next('result'), await client.next('result')].map((m) => m.data);
    assert.equal(results.filter((r) => r.cancelled).length, 2);
    assert.ok(results.some((r) => /Stopped by user/.test(String(r.error))));
    await new Promise((r) => setTimeout(r, 300));
    assert.equal(mock.requests.length, 1, 'queued goals never reached the model');
    const cancelledTasks = client.messages.filter((m) => m.type === 'task_update' && m.data.status === 'cancelled');
    assert.equal(cancelledTasks.length, 2);
  } finally {
    client.ws.close();
  }
});

test('REST run endpoint goes through the queue and answers 202', async () => {
  mock.script([say('rest answer')]);
  const client = await connect();
  try {
    const res = await json(`/api/sessions/${client.init.data.sessionId}/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal: 'from REST' }),
    });
    assert.equal(res.status, 202);
    assert.equal(res.body.queued, false);
    const { data } = await client.next('result');
    assert.equal(data.result, 'rest answer');
    assert.equal((await json(`/api/sessions/${client.init.data.sessionId}/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })).status, 400);
  } finally {
    client.ws.close();
  }
});
