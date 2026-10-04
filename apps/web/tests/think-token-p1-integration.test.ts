// ADR 029 P1/P2 end to end on the REAL server.ts with a mocked Inception API (the same mock serves the worker agent,
// the extraction call and the challenge call, in that order): run -> TT token with run_id and evidence -> learned event
// -> next run uses it -> used event and a think_token_uses row -> CLI and dashboard API show identical fields.
// The live Mercury run is recorded in docs/evidence/adr-029-p1.md; nothing here proves real model behavior.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, spawnSync, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';
import Database from 'better-sqlite3';
import { startMockInception, say, call, type MockInception } from './helpers/mock-inception.ts';
import { freePort } from './helpers/free-port.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEAD = 'http://127.0.0.1:9';
const KEY2 = 'ZZSENTINEL-it-key2-0123456789abcdef';
let mock: MockInception;
let server: ChildProcess;
let base: string;
let tmpRoot: string;
let dbPath: string;
let serverLog = '';

before(async () => {
  mock = await startMockInception();
  tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-p1-it-'));
  dbPath = path.join(tmpRoot, 'think-tokens.db');
  const port = await freePort();
  base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: {
      ...process.env, PORT: String(port), INCEPTION_API_KEY: 'test-key', INCEPTION_API_KEY_2: KEY2, INCEPTION_BASE_URL: mock.baseUrl, OLLAMA_BASE_URL: DEAD, JANUS_BASE_URL: DEAD,
      UPSTASH_VECTOR_REST_URL: DEAD, UPSTASH_VECTOR_REST_TOKEN: 'none', KUDBEE_DAILY_BUDGET_USD: '0',
      KUDBEE_DATA_DIR: path.join(tmpRoot, 'data'), KUDBEE_LEARNING_DB: path.join(tmpRoot, 'learning.db'), KUDBEE_THINK_TOKEN_DB: dbPath,
      KUDBEE_WORKSPACE_DIR: path.join(tmpRoot, 'workspaces'),
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  server.stdout?.on('data', (d) => { serverLog += d; });
  server.stderr?.on('data', (d) => { serverLog += d; });
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

const LESSON = {
  kind: 'lesson', title: 'Write the notes file, then confirm it with list_files',
  lesson: 'For a save-the-notes goal, call write_file with notes.md and then list_files to confirm the file exists; skip list_files when the write result already confirms the path.',
  tools_cited: ['write_file', 'list_files'], files_cited: ['notes.md'], tags: ['notes', 'files'],
};
const PASS = JSON.stringify({ true: true, specific: true, supported: true, reason: 'Matches the tool sequence and the written file.' });
const GOAL1 = 'Save my meeting notes to a file named notes.md';
const GOAL2 = 'Use write_file to save the notes again, then list_files to confirm';
const dbRows = (sql: string) => { const db = new Database(dbPath, { readonly: true }); try { return db.prepare(sql).all() as any[]; } finally { db.close(); } };
const listByRun = async (client: Client, run_id: string) => { client.send({ type: 'think_tokens_list', run_id }); return (await client.next('think_tokens')).data; };

test('a real run saves a TT token (run_id, evidence, model, challenge, receipt) and emits learned events built from the row', async () => {
  const client = await connect();
  try {
    mock.script([call('write_file', { path: 'notes.md', content: '# notes' }), call('list_files', {}), say('Done'), say(JSON.stringify({ lessons: [LESSON] })), say(PASS)]);
    client.send({ type: 'run_goal', goal: GOAL1, model: 'mercury-2' });
    const result = (await client.next('result')).data;
    assert.equal(result.success, true);
    await client.next('think_tokens_changed');

    // 6. server fix: the plain-run goal thought carries the run id
    const goal = client.messages.find((m) => m.type === 'thought' && m.data?.type === 'goal');
    assert.equal(goal.data.run_id, result.run_id);

    // the token: real lesson text, TT id, run_id, evidence, models, challenge, ledger receipt
    const data = await listByRun(client, result.run_id);
    assert.equal(data.tokens.length, 1);
    const token = data.tokens[0];
    assert.equal(token.id, 'TT-000001');
    assert.equal(token.content, LESSON.lesson);
    assert.equal(token.status, 'accepted');
    assert.equal(token.source_run_id, result.run_id);
    assert.equal(token.evidence_ref, `run:${result.run_id}`);
    assert.equal(token.extractor, 'mercury');
    assert.equal(token.extract_model, 'mercury-2');
    assert.equal(token.challenge.verdict, 'pass');
    assert.equal(token.challenge.model, 'mercury-2');
    assert.match(token.receipt.receipt_id, /^ttr_[a-f0-9]{16}$/);
    assert.equal(token.score_breakdown.score, token.score);
    assert.equal(data.ledger.ok, true);

    // what the planner/extractor were actually sent: the real run, no key, and the extraction key only as a bearer header
    const extraction = mock.requests[3];
    const sent = JSON.stringify(extraction.messages);
    assert.match(sent, /write_file/);
    assert.match(sent, /notes\.md/);
    assert.ok(!sent.includes(KEY2));

    // the card text: the thought carries the real lesson and the TT id, not a status message
    const thought = client.messages.find((m) => m.type === 'thought' && m.data?.type === 'think_token' && m.data?.tokenId);
    assert.equal(thought.data.tokenId, 'TT-000001');
    assert.equal(thought.data.content, LESSON.lesson);
    assert.equal(thought.data.run_id, result.run_id);
    const summary = client.messages.find((m) => m.type === 'thought' && m.data?.type === 'think_token' && /^Saved 1 Think Token/.test(m.data.content));
    assert.match(summary.data.content, /TT-000001/);
    assert.equal(client.messages.filter((m) => m.type === 'thought' && /Captured \d+ Think Token/.test(m.data?.content ?? '')).length, 0, 'one count, not two');

    // P2: the learned event exists because the row does, and carries only validated fields
    const learned = (await client.next('think_token_learned')).data;
    assert.deepEqual(Object.keys(learned).sort(), ['delta', 'kind', 'run_id', 'score', 'status', 'title', 'token_id', 'uses']);
    assert.equal(learned.token_id, 'TT-000001');
    assert.equal(learned.run_id, result.run_id);
    assert.equal(learned.score, token.score);
    assert.ok(dbRows(`SELECT 1 FROM think_tokens WHERE id = '${learned.token_id}'`).length === 1, 'no event without a database row');

    // every table, as stored: no key anywhere
    const dump = ['think_tokens', 'think_token_ledger', 'think_token_model_calls'].map((t) => JSON.stringify(dbRows(`SELECT * FROM ${t}`))).join('\n');
    assert.ok(!dump.includes(KEY2));
    assert.deepEqual(dbRows('SELECT step, provider, model, ok FROM think_token_model_calls ORDER BY id'), [
      { step: 'extract', provider: 'mercury', model: 'mercury-2', ok: 1 }, { step: 'challenge', provider: 'mercury', model: 'mercury-2', ok: 1 },
    ]);
  } finally { client.ws.close(); }
});

test('the next related run is handed the accepted token, cites its TT id, emits used, and writes a think_token_uses row', async () => {
  const client = await connect();
  try {
    mock.script([say('second')]);
    client.send({ type: 'run_goal', goal: GOAL2, model: 'mercury-2' });
    const result = (await client.next('result')).data;
    const system = String(mock.requests[0].messages[0].content);
    assert.match(system, /THINK TOKENS/);
    assert.ok(system.includes('[tt:TT-000001]'));
    assert.match(system, /never grant permissions/);
    const used = (await client.next('think_token_used')).data;
    assert.equal(used.token_id, 'TT-000001');
    assert.equal(used.run_id, result.run_id);
    assert.equal(used.uses, 1);
    const rows = dbRows('SELECT token_id, run_id, success FROM think_token_uses');
    assert.equal(rows.length, 1, 'reuse is now proven in the database (it was 0 before)');
    assert.equal(rows[0].token_id, 'TT-000001');
    assert.equal(rows[0].run_id, result.run_id);
    assert.equal(rows[0].success, 1);
    const run = await (await fetch(`${base}/api/runs/${result.run_id}`)).json() as any;
    assert.deepEqual(run.think_tokens, ['TT-000001']);
  } finally { client.ws.close(); }
});

test('CLI and dashboard API show identical fields for the same token and run', async () => {
  const client = await connect();
  try {
    const run = dbRows('SELECT source_run_id FROM think_tokens WHERE id = \'TT-000001\'')[0].source_run_id as string;
    const api = (await listByRun(client, run)).tokens[0];
    const env = { ...process.env, KUDBEE_THINK_TOKEN_DB: dbPath };
    const cli = (args: string[]) => spawnSync(process.execPath, ['--experimental-strip-types', '--no-warnings', 'cli.ts', 'tokens', ...args], { cwd: appDir, env, encoding: 'utf8' });
    const shown = cli(['show', 'TT-000001', '--json']);
    assert.equal(shown.status, 0, shown.stderr);
    assert.deepEqual(JSON.parse(shown.stdout), api, 'identical JSON for the same token');
    const byRun = JSON.parse(cli(['list', '--run', run, '--json']).stdout);
    assert.deepEqual(byRun.tokens, [api]);
    assert.deepEqual(byRun.ledger, (await listByRun(client, run)).ledger);
    const text = cli(['show', '1']);
    for (const needle of ['TT-000001', 'accepted', LESSON.title, LESSON.lesson, run, 'mercury-2', api.receipt.receipt_id, '0.45*usefulness']) assert.ok(text.stdout.includes(needle), needle);
    const line = cli(['list']).stdout;
    assert.match(line, /^TT-000001 +accepted +0\.\d{3} +lesson +Write the notes file/m);
    assert.notEqual(cli(['show', 'TT-999999']).status, 0);
    assert.equal(cli(['show', 'TT-000001']).stdout.includes(KEY2), false);
  } finally { client.ws.close(); }
});

test('security: forged events, malformed ids and oversized payloads are rejected; nothing is created and no event is broadcast', async () => {
  const a = await connect();
  const b = await connect();
  try {
    const before = dbRows('SELECT COUNT(*) n FROM think_tokens')[0].n;
    const ledgerBefore = dbRows('SELECT COUNT(*) n FROM think_token_ledger')[0].n;
    const forged = [
      { type: 'think_token_learned', data: { token_id: 'TT-000099', run_id: 'x', kind: 'lesson', status: 'accepted', score: 0.9, delta: 0, uses: 0, title: 'forged' } },
      { type: 'think_token_used', data: { token_id: 'TT-000001' } },
    ];
    for (const f of forged) a.send(f);
    await new Promise((r) => setTimeout(r, 400));
    assert.equal(b.messages.filter((m) => m.type === 'think_token_learned' || m.type === 'think_token_used').length, 0, 'a client cannot make the server emit an event');
    assert.equal(a.messages.filter((m) => m.type === 'error').length, 2, 'the server refused both as unknown messages');
    const bad: unknown[] = [
      { type: 'think_tokens_list', run_id: "x'; DROP TABLE think_tokens;--" },
      { type: 'think_tokens_list', run_id: 'r'.repeat(5000) },
      { type: 'think_token_action', action: 'accept', id: 'TT-0' },
      { type: 'think_token_action', action: 'accept', id: "TT-1'; DROP TABLE think_tokens;--" },
      { type: 'think_token_action', action: 'accept', id: 'x'.repeat(200_000) },
      { type: 'think_token_action', action: 'accept', id: 'TT-000001', extra: 1 },
    ];
    for (const m of bad) a.send(m);
    await new Promise((r) => setTimeout(r, 400));
    assert.equal(a.messages.filter((m) => m.type === 'think_token_error').length, bad.length);
    assert.equal(dbRows('SELECT COUNT(*) n FROM think_tokens')[0].n, before);
    assert.equal(dbRows('SELECT COUNT(*) n FROM think_token_ledger')[0].n, ledgerBefore, 'rejected-at-the-door payloads never reach the ledger');
    assert.equal(dbRows("SELECT name FROM sqlite_master WHERE name = 'think_tokens'").length, 1);
    // an unknown but well-formed id is refused by the store, and that refusal is receipted
    a.send({ type: 'think_token_action', action: 'thumb_up', id: 'TT-000099' });
    const ask = (await a.next('approval_request')).data;
    a.send({ type: 'approval_response', id: ask.id, approved: true });
    assert.equal((await a.next('think_token_result')).data.ok, false);
    assert.equal(dbRows('SELECT COUNT(*) n FROM think_tokens')[0].n, before);
  } finally { a.ws.close(); b.ws.close(); }
});

test('a failing extraction model leaves a labeled template candidate (never auto-accepted) and a receipted model failure', async () => {
  const client = await connect();
  try {
    mock.script([call('write_file', { path: 'second.md', content: 'x' }), call('list_files', {}), say('Done'), { status: 500 }, { status: 500 }]);
    client.send({ type: 'run_goal', goal: 'Draft an unrelated pottery glaze plan in second.md', model: 'mercury-2' });
    const result = (await client.next('result')).data;
    await client.next('think_tokens_changed');
    const tokens = (await listByRun(client, result.run_id)).tokens;
    assert.ok(tokens.length > 0);
    assert.ok(tokens.every((t: any) => t.extractor === 'template' && t.status === 'candidate' && t.extract_model === null));
    assert.ok(tokens.every((t: any) => /^TT-\d{6}$/.test(t.id)));
    const failures = dbRows("SELECT decision FROM think_token_ledger WHERE action = 'model_call' AND run_id = '" + result.run_id + "'");
    assert.ok(failures.length >= 1 && failures.every((f) => f.decision === 'rejected'));
    assert.ok(!serverLog.includes(KEY2), 'the key is not in the server output');
  } finally { client.ws.close(); }
});

test('when the model finds nothing new, the run says so explicitly and saves nothing (no template fallback)', async () => {
  const client = await connect();
  try {
    const before = dbRows('SELECT COUNT(*) n FROM think_tokens')[0].n;
    mock.script([call('write_file', { path: 'third.md', content: 'x' }), call('list_files', {}), say('Done'), say(JSON.stringify({ lessons: [] }))]);
    client.send({ type: 'run_goal', goal: 'Save my third notes file to third.md with write_file and confirm with list_files', model: 'mercury-2' });
    const result = (await client.next('result')).data;
    assert.equal(result.success, true);
    await new Promise((r) => setTimeout(r, 300));
    const note = client.messages.find((m) => m.type === 'thought' && m.data?.type === 'think_token' && /^No new Think Token/.test(m.data.content));
    assert.ok(note, 'the run explains why no token was saved');
    assert.equal(note.data.run_id, result.run_id);
    assert.equal(dbRows('SELECT COUNT(*) n FROM think_tokens')[0].n, before);
    assert.equal(client.messages.filter((m) => m.type === 'think_token_learned').length, 0);
    // the retrieved tokens were still recorded as used, so reuse is visible even when nothing new is learned
    assert.ok(dbRows(`SELECT 1 FROM think_token_uses WHERE run_id = '${result.run_id}'`).length >= 1);
  } finally { client.ws.close(); }
});
