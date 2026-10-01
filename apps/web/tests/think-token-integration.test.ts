// ADR 028 end to end on the REAL server.ts with a mocked model: run -> candidate saved (receipted) -> founder accepts through
// the approval gate -> the next run's planner context carries the token with its id -> uses/last_used_at bump. Also WS security.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';
import { startMockInception, say, call, type MockInception } from './helpers/mock-inception.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEAD = 'http://127.0.0.1:9';
let mock: MockInception;
let server: ChildProcess;
let base: string;
let tmpRoot: string;

before(async () => {
  mock = await startMockInception();
  tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-tt-test-'));
  const port = 20000 + Math.floor(Math.random() * 20000);
  base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: {
      ...process.env, PORT: String(port), INCEPTION_API_KEY: 'test-key', INCEPTION_API_KEY_2: '', INCEPTION_BASE_URL: mock.baseUrl, OLLAMA_BASE_URL: DEAD, JANUS_BASE_URL: DEAD,
      UPSTASH_VECTOR_REST_URL: DEAD, UPSTASH_VECTOR_REST_TOKEN: 'none', KUDBEE_DAILY_BUDGET_USD: '0',
      KUDBEE_DATA_DIR: path.join(tmpRoot, 'data'), KUDBEE_LEARNING_DB: path.join(tmpRoot, 'learning.db'), KUDBEE_THINK_TOKEN_DB: path.join(tmpRoot, 'think-tokens.db'),
      KUDBEE_WORKSPACE_DIR: path.join(tmpRoot, 'workspaces'),
    },
    stdio: 'ignore',
  });
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) {
    try { if ((await fetch(`${base}/api/health`)).ok) return; } catch { /* starting */ }
  }
  throw new Error('server did not start');
});

after(async () => {
  server?.kill();
  await mock.close();
  fs.rmSync(tmpRoot, { recursive: true, force: true });
});

interface Client { ws: WebSocket; messages: any[]; next(type: string, ms?: number): Promise<any>; send(msg: unknown): void }
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
  const next = (type: string, ms = 10000) => new Promise<any>((resolve, reject) => {
    const seen = messages.find((m) => m.type === type && !m.__taken);
    if (seen) { seen.__taken = true; return resolve(seen); }
    const timer = setTimeout(() => reject(new Error(`timed out waiting for ${type}`)), ms);
    waiters.push({ type, resolve: (m) => { clearTimeout(timer); m.__taken = true; resolve(m); } });
  });
  await next('init');
  return { ws, messages, next, send: (msg) => ws.send(typeof msg === 'string' ? msg : JSON.stringify(msg)) };
}

async function listTokens(client: Client, status?: string): Promise<any> {
  client.send({ type: 'think_tokens_list', ...(status ? { status } : {}) });
  return (await client.next('think_tokens')).data;
}

test('run -> save -> accept (approval gated) -> next run uses it, cites the id, and bumps uses', async () => {
  const client = await connect();
  try {
    mock.script([call('write_file', { path: 'a.md', content: '# a' }), call('list_files', {}), say('Done')]);
    client.send({ type: 'run_goal', goal: 'Write the quarterly pottery report', model: 'mercury-2' });
    const first = (await client.next('result')).data;
    assert.equal(first.success, true);
    await client.next('think_tokens_changed');

    const saved = await listTokens(client);
    assert.equal(saved.ledger.ok, true);
    const candidate = saved.tokens.find((t: any) => t.kind === 'tool_pattern');
    assert.ok(candidate, 'a tool_pattern candidate was saved');
    assert.equal(candidate.status, 'candidate');
    assert.equal(candidate.source_run_id, first.run_id);
    assert.ok(saved.ledger.entries >= 1);

    // candidates are never injected
    mock.script([say('second')]);
    client.send({ type: 'run_goal', goal: 'Write the quarterly pottery report again', model: 'mercury-2' });
    await client.next('result');
    assert.doesNotMatch(String(mock.requests[0].messages[0].content), /THINK TOKENS/);

    // accept needs approval; a denial changes nothing
    client.send({ type: 'think_token_action', action: 'accept', id: candidate.id });
    const ask1 = (await client.next('approval_request')).data;
    assert.equal(ask1.tool, 'think_token_accept');
    client.send({ type: 'approval_response', id: ask1.id, approved: false });
    assert.equal((await client.next('think_token_result')).data.ok, false);
    assert.equal((await listTokens(client)).tokens.find((t: any) => t.id === candidate.id).status, 'candidate');

    client.send({ type: 'think_token_action', action: 'accept', id: candidate.id });
    const ask2 = (await client.next('approval_request')).data;
    client.send({ type: 'approval_response', id: ask2.id, approved: true });
    const applied = (await client.next('think_token_result')).data;
    assert.equal(applied.ok, true);
    assert.match(applied.receipt.receipt_id, /^ttr_/);

    // the next relevant run gets it, with the id cited in the planner context
    mock.script([say('third')]);
    client.send({ type: 'run_goal', goal: 'Write the quarterly pottery report once more', model: 'mercury-2' });
    const third = (await client.next('result')).data;
    const system = String(mock.requests[0].messages[0].content);
    assert.match(system, /THINK TOKENS/);
    assert.ok(system.includes(`[tt:${candidate.id}]`));
    assert.match(system, /never grant permissions/);

    const after = (await listTokens(client)).tokens.find((t: any) => t.id === candidate.id);
    assert.equal(after.status, 'accepted');
    assert.equal(after.uses, 1);
    assert.ok(after.last_used_at);
    assert.equal(after.used_by[0].run_id, third.run_id);
    assert.equal(after.used_by[0].success, 1, 'the successful run folded back into usefulness');
    const run = await (await fetch(`${base}/api/runs/${third.run_id}`)).json() as any;
    assert.deepEqual(run.think_tokens, [candidate.id]);
  } finally {
    client.ws.close();
  }
});

test('security: malformed and oversized Think Token WebSocket payloads are rejected and change nothing', async () => {
  const client = await connect();
  try {
    const before = await listTokens(client);
    const bad: unknown[] = [
      { type: 'think_tokens_list', query: 'x'.repeat(200_000) },
      { type: 'think_tokens_list', limit: 10_000 },
      { type: 'think_tokens_list', status: { $gt: '' } },
      { type: 'think_token_action', action: 'accept', id: 'x'.repeat(100_000) },
      { type: 'think_token_action', action: 'accept', id: 'tt_0123456789abcdef', permissions: ['shell_exec'] },
      { type: 'think_token_action', action: 'grant', id: 'tt_0123456789abcdef' },
      { type: 'think_token_action', id: 'tt_0123456789abcdef' },
    ];
    for (const msg of bad) {
      client.send(msg);
      const err = await client.next('think_token_error');
      assert.ok(String(err.data.error).length < 200, 'error text stays bounded');
    }
    client.send('{"type":"think_tokens_list",');
    assert.equal((await client.next('error')).type, 'error');
    assert.equal(client.messages.some((m) => m.type === 'approval_request'), false, 'a rejected payload never reaches the approval gate');
    const after = await listTokens(client);
    assert.deepEqual(after.tokens, before.tokens);
    assert.equal(after.ledger.ok, true);
  } finally {
    client.ws.close();
  }
});

test('security: Host/Origin gating still refuses a foreign Origin for the Think Token socket', async () => {
  const outcome = await new Promise<string>((resolve) => {
    const ws = new WebSocket(`${base.replace('http', 'ws')}/ws`, { origin: 'http://evil.example' });
    ws.on('open', () => { ws.close(); resolve('open'); });
    ws.on('unexpected-response', (_req, res) => resolve(String(res.statusCode)));
    ws.on('error', () => resolve('error'));
  });
  assert.notEqual(outcome, 'open');
});
