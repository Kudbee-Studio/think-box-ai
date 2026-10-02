// A local Ollama model is a plain chat, not an agent: it must not be told to "use plugins" (it invented a fake tool plan for "2 plus 2"),
// and its answer must reach the terminal once, not three times. Real server.ts against a fake Ollama.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const MODEL = 'smollm2:360m';
const CHUNKS = ['Four', ' is the', ' answer.'];
const ANSWER = CHUNKS.join('');
let ollama: http.Server;
let server: ChildProcess;
let base = '';
let tmp = '';
const chats: any[] = [];

before(async () => {
  ollama = http.createServer((req, res) => {
    let body = '';
    req.on('data', (d) => { body += d; });
    req.on('end', () => {
      if (req.url === '/api/tags') { res.setHeader('content-type', 'application/json'); return void res.end(JSON.stringify({ models: [{ name: MODEL, size: 725_000_000 }] })); }
      if (req.url === '/api/chat') {
        chats.push(JSON.parse(body));
        res.setHeader('content-type', 'application/x-ndjson');
        for (const c of CHUNKS) res.write(`${JSON.stringify({ message: { content: c }, done: false })}\n`);
        return void res.end(`${JSON.stringify({ message: { content: '' }, done: true })}\n`);
      }
      res.statusCode = 404; res.end('{}');
    });
  });
  await new Promise<void>((r) => ollama.listen(0, '127.0.0.1', r));
  const ollamaUrl = `http://127.0.0.1:${(ollama.address() as { port: number }).port}`;
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-local-chat-'));
  const port = 20000 + Math.floor(Math.random() * 20000);
  base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: { ...process.env, PORT: String(port), INCEPTION_API_KEY: '', OLLAMA_BASE_URL: ollamaUrl, JANUS_BASE_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: 'none',
      KUDBEE_DAILY_BUDGET_USD: '0', KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), THINKBOX_EMBEDDINGS: 'off', THINKBOX_LOCAL_MODEL: MODEL },
    stdio: 'ignore',
  });
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) {
    try { if ((await fetch(`${base}/api/health`)).ok) return; } catch { /* starting */ }
  }
  throw new Error('server did not start');
});
after(async () => { server?.kill(); await new Promise((r) => ollama.close(r)); fs.rmSync(tmp, { recursive: true, force: true }); });

/** Runs the goals one after another on ONE connection (one session, so earlier answers are in its memory). Resolves with every message. */
const runGoal = (goal: string, ...then: string[]): Promise<any[]> => new Promise((resolve, reject) => {
  const ws = new WebSocket(`${base.replace('http', 'ws')}/ws`, { origin: base });
  const messages: any[] = [];
  const timer = setTimeout(() => reject(new Error('no result')), 15000);
  ws.on('error', reject);
  ws.on('message', (raw) => {
    const m = JSON.parse(raw.toString());
    messages.push(m);
    if (m.type === 'init') ws.send(JSON.stringify({ type: 'run_goal', goal, model: MODEL }));
    if (m.type === 'result') {
      const next = then.shift();
      if (next) return void ws.send(JSON.stringify({ type: 'run_goal', goal: next, model: MODEL }));
      clearTimeout(timer); ws.close(); resolve(messages);
    }
  });
});

test('the local model gets a plain chat like `ollama run`: no system prompt, no plugin list, no "execute step by step", default sampling', async () => {
  chats.length = 0;
  await runGoal('What is 2 plus 2? Answer in one short sentence.');
  const sent = chats.at(-1);
  assert.equal(sent.model, MODEL);
  const text = sent.messages.map((m: any) => m.content).join('\n');
  assert.doesNotMatch(text, /Available plugins|step by step|Use the available plugins/i);
  assert.ok(sent.messages.every((m: any) => m.role !== 'system'), 'no system prompt');
  assert.deepEqual(sent.options, { num_predict: 512, num_ctx: 2048 }, 'default sampling; only a reply cap and a small context');
  assert.equal(sent.messages.at(-1).role, 'user');
  assert.equal(sent.messages.at(-1).content, 'What is 2 plus 2? Answer in one short sentence.');
});

test('the answer reaches the client once as a stream; the thought and the result do not repeat it', async () => {
  const messages = await runGoal('Say it again.');
  const streamed = messages.filter((m) => m.type === 'stream').map((m) => m.data).join('');
  assert.equal(streamed, ANSWER);
  const result = messages.find((m) => m.type === 'result').data;
  assert.equal(result.success, true);
  assert.equal(result.result, ANSWER, 'the result still carries the text (API consumers)');
  assert.equal(result.streamed, true, 'and says it was already streamed, so terminals do not print it again');
  const thoughts = messages.filter((m) => m.type === 'thought').map((m) => String(m.data?.content ?? ''));
  assert.ok(thoughts.every((t) => !t.includes(ANSWER)), 'no thought repeats the answer');
  assert.ok(thoughts.some((t) => /local chat, no tools/.test(t)));
});

test('earlier answers are replayed as assistant turns, not as raw JSON user messages', async () => {
  chats.length = 0;
  await runGoal('First question.', 'Third question.');
  const roles = chats.at(-1).messages.map((m: any) => m.role);
  assert.ok(roles.includes('assistant'), 'a prior answer is replayed');
  for (const m of chats.at(-1).messages.filter((m: any) => m.role === 'user')) assert.doesNotMatch(m.content, /"timestamp"|"type":"response"/);
});

test('the CLI and dashboard terminals do not print a streamed answer a second time', () => {
  const cli = fs.readFileSync(path.join(appDir, 'cli.ts'), 'utf8');
  const app = fs.readFileSync(path.join(appDir, 'public/js/app.js'), 'utf8');
  assert.match(cli, /r\.streamed \? 'done'/);
  assert.match(app, /r\.streamed \? 'Done'/);
});
