// A goal picked for the local model that needs tools or live data goes to the worker agent (visibly), or fails plainly when there is none.
// It is never answered from the small model's head. Real server.ts, a fake Ollama and a mock Inception.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';
import { startMockInception, say, type MockInception } from './helpers/mock-inception.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const MODEL = 'smollm2:360m';
let ollama: http.Server;
let ollamaUrl = '';
let mock: MockInception;
let tmp = '';
const chats: any[] = [];
const servers: ChildProcess[] = [];

before(async () => {
  mock = await startMockInception();
  ollama = http.createServer((req, res) => {
    let body = '';
    req.on('data', (d) => { body += d; });
    req.on('end', () => {
      if (req.url === '/api/tags') { res.setHeader('content-type', 'application/json'); return void res.end(JSON.stringify({ models: [{ name: MODEL, size: 725_000_000 }] })); }
      if (req.url === '/api/chat') {
        chats.push(JSON.parse(body));
        res.setHeader('content-type', 'application/x-ndjson');
        res.write(`${JSON.stringify({ message: { content: 'It is 4.' }, done: false })}\n`);
        return void res.end(`${JSON.stringify({ message: { content: '' }, done: true })}\n`);
      }
      res.statusCode = 404; res.end('{}');
    });
  });
  await new Promise<void>((r) => ollama.listen(0, '127.0.0.1', r));
  ollamaUrl = `http://127.0.0.1:${(ollama.address() as { port: number }).port}`;
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-escalate-'));
});
after(async () => {
  for (const s of servers) s.kill();
  await new Promise((r) => ollama.close(r));
  await mock.close();
  fs.rmSync(tmp, { recursive: true, force: true });
});

async function startServer(withWorkerAgent: boolean): Promise<string> {
  const port = 20000 + Math.floor(Math.random() * 20000);
  const base = `http://127.0.0.1:${port}`;
  const dir = fs.mkdtempSync(path.join(tmp, 's-'));
  const server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: { ...process.env, PORT: String(port), INCEPTION_API_KEY: withWorkerAgent ? 'test-key' : '', INCEPTION_API_KEY_2: '', INCEPTION_BASE_URL: mock.baseUrl, OLLAMA_BASE_URL: ollamaUrl, JANUS_BASE_URL: 'http://127.0.0.1:9',
      UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: 'none', KUDBEE_DAILY_BUDGET_USD: '0', KUDBEE_DATA_DIR: path.join(dir, 'data'), KUDBEE_WORKSPACE_DIR: path.join(dir, 'ws'), THINKBOX_EMBEDDINGS: 'off', THINKBOX_LOCAL_MODEL: MODEL },
    stdio: 'ignore',
  });
  servers.push(server);
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) {
    try { if ((await fetch(`${base}/api/health`)).ok) return base; } catch { /* starting */ }
  }
  throw new Error('server did not start');
}

const runGoal = (base: string, goal: string): Promise<any[]> => new Promise((resolve, reject) => {
  const ws = new WebSocket(`${base.replace('http', 'ws')}/ws`, { origin: base });
  const messages: any[] = [];
  const timer = setTimeout(() => reject(new Error('no result')), 20000);
  ws.on('error', reject);
  ws.on('message', (raw) => {
    const m = JSON.parse(raw.toString());
    messages.push(m);
    if (m.type === 'init') ws.send(JSON.stringify({ type: 'run_goal', goal, model: MODEL }));
    if (m.type === 'result') { clearTimeout(timer); ws.close(); resolve(messages); }
  });
});

test('with a worker agent: "WHAT PR ARE WE ON" on the local model is routed to mercury-2, the local model is never asked, and a thought says why', async () => {
  const base = await startServer(true);
  chats.length = 0;
  mock.script([say('We are on PR #330.')]);
  const messages = await runGoal(base, 'WHAT PR ARE WE ON');
  // (After the run the Think Token pipeline may use the local model as an extraction fallback; that is not the goal being chatted.)
  assert.ok(!chats.some((c) => c.messages.at(-1)?.content === 'WHAT PR ARE WE ON'), 'the goal was never sent to the small model as a chat');
  const routed = messages.filter((m) => m.type === 'thought').map((m) => m.data).find((t) => t.type === 'routing');
  assert.ok(routed, 'a routing thought is shown');
  assert.match(routed.content, /Routed to mercury-2 instead of smollm2:360m/);
  assert.match(routed.content, /pull requests|repository/);
  const result = messages.find((m) => m.type === 'result').data;
  assert.equal(result.success, true);
  assert.match(String(result.result), /PR #330/);
  assert.ok(mock.requests.length >= 1, 'the worker agent answered');
});

test('with a worker agent: a plain knowledge goal stays on the local model, no routing thought, Mercury untouched', async () => {
  const base = await startServer(true);
  chats.length = 0;
  const before = mock.requests.length;
  const messages = await runGoal(base, 'What is 2 plus 2? Answer in one short sentence.');
  assert.ok(chats.some((c) => c.messages.at(-1)?.content === 'What is 2 plus 2? Answer in one short sentence.'), 'chatted locally');
  assert.equal(mock.requests.length, before, 'Mercury untouched');
  assert.ok(!messages.some((m) => m.type === 'thought' && m.data?.type === 'routing'));
  assert.equal(messages.find((m) => m.type === 'result').data.result, 'It is 4.');
});

test('without a worker agent: the goal fails with a plain explanation, and the small model is never asked', async () => {
  const base = await startServer(false);
  chats.length = 0;
  const messages = await runGoal(base, 'WHAT PR ARE WE ON');
  assert.ok(!chats.some((c) => c.messages.at(-1)?.content === 'WHAT PR ARE WE ON'), 'no made-up answer: the goal was never chatted');
  const result = messages.find((m) => m.type === 'result').data;
  assert.equal(result.success, false);
  assert.match(result.error, /needs tools or live data/);
  assert.match(result.error, /INCEPTION_API_KEY/);
});
