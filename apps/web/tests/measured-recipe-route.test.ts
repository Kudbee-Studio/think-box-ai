// The dashboard goal path: a live lookup on a local model the measured table does not qualify is re-routed to the one it does, visibly, and the answer path
// is unchanged (governed lookup in code, the chosen model words it, grounded). Fake Ollama (two installed models), fake GitHub, a temp measured table.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';
import { freePort } from './helpers/free-port.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const WEAK = 'smollm2:360m'; const STRONG = 'gemma3:4b';
const trials = (model: string, pass: number, total: number) => Array.from({ length: total }, (_, i) => ({ model, task: 't', class: 'lookup', outcome: i < pass ? 'pass' : 'wrong', why: '', latency_ms: 9000, tool_calls: 1, tokens: 500, mode: 'constrained' }));
let ollama: http.Server; let github: http.Server; let server: ChildProcess; let base = ''; let tmp = '';
const chatModels: string[] = [];

before(async () => {
  ollama = http.createServer((req, res) => {
    let body = ''; req.on('data', (d) => { body += d; });
    req.on('end', () => {
      if (req.url === '/api/tags') { res.setHeader('content-type', 'application/json'); return void res.end(JSON.stringify({ models: [{ name: WEAK, size: 1 }, { name: STRONG, size: 1 }] })); }
      if (req.url === '/api/chat') {
        chatModels.push(JSON.parse(body).model);
        res.setHeader('content-type', 'application/x-ndjson');
        res.write(`${JSON.stringify({ message: { content: 'We are on PR #330, a draft.' }, done: false })}\n`);
        return void res.end(`${JSON.stringify({ message: { content: '' }, done: true })}\n`);
      }
      res.statusCode = 404; res.end('{}');
    });
  });
  github = http.createServer((_req, res) => { res.setHeader('content-type', 'application/json'); res.end(JSON.stringify([{ number: 330, title: 'P3.18: escalate goals', draft: true, user: { login: 'dev' }, updated_at: '2026-10-02T21:42:25Z', html_url: 'https://github.com/Acme/widgets/pull/330' }])); });
  await Promise.all([new Promise<void>((r) => ollama.listen(0, '127.0.0.1', r)), new Promise<void>((r) => github.listen(0, '127.0.0.1', r))]);
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-measured-'));
  const table = path.join(tmp, 'local-eval.json');
  fs.writeFileSync(table, JSON.stringify({ generated_at: '2026-10-05T00:00:00Z', trials: [...trials(STRONG, 15, 15), ...trials(WEAK, 3, 10)] }));
  const port = await freePort(); base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir, stdio: 'ignore',
    env: { ...process.env, PORT: String(port), INCEPTION_API_KEY: '', INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: `http://127.0.0.1:${(ollama.address() as { port: number }).port}`, KUDBEE_GITHUB_API: `http://127.0.0.1:${(github.address() as { port: number }).port}`, KUDBEE_REPO: 'Acme/widgets', KUDBEE_LOCAL_EVAL: table,
      JANUS_BASE_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: 'none', KUDBEE_DAILY_BUDGET_USD: '0', KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), THINKBOX_EMBEDDINGS: 'off', THINKBOX_LOCAL_MODEL: WEAK },
  });
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) { try { if ((await fetch(`${base}/api/health`)).ok) break; } catch { /* starting */ } }
  // the installed list is learned in the background: wait until the server has seen it
  for (const end = Date.now() + 10000; Date.now() < end; await new Promise((r) => setTimeout(r, 200))) { try { const m = (await (await fetch(`${base}/api/models`)).json()) as unknown; if (JSON.stringify(m).includes(STRONG)) break; } catch { /* retry */ } }
});
after(async () => {
  server?.kill();
  await Promise.all([new Promise((r) => ollama.close(r)), new Promise((r) => github.close(r))]);
  fs.rmSync(tmp, { recursive: true, force: true });
});

const run = (goal: string, model: string): Promise<any[]> => new Promise((resolve, reject) => {
  const ws = new WebSocket(`${base.replace('http', 'ws')}/ws`, { origin: base });
  const messages: any[] = []; const timer = setTimeout(() => reject(new Error('no result')), 20000);
  ws.on('error', reject);
  ws.on('message', (raw) => {
    const m = JSON.parse(raw.toString()); messages.push(m);
    if (m.type === 'init') ws.send(JSON.stringify({ type: 'run_goal', goal, model }));
    if (m.type === 'approval_request') ws.send(JSON.stringify({ type: 'approval_response', id: m.data.id, approved: true }));
    if (m.type === 'result') { clearTimeout(timer); ws.close(); resolve(messages); }
  });
});
const result = (messages: any[]) => messages.find((m) => m.type === 'result').data;

test('a lookup on a model the table does not qualify is re-routed to the one it does, and the thought line says why', async () => {
  chatModels.length = 0;
  const messages = await run('which pull requests are open?', WEAK);
  const r = result(messages);
  assert.equal(r.success, true, JSON.stringify(r));
  assert.equal(r.route.model, STRONG);
  assert.deepEqual(chatModels, [STRONG], 'the chosen model is the one that worded the answer');
  const thought = messages.find((m) => m.type === 'thought' && /^Routed to gemma3:4b instead of smollm2:360m/.test(m.data?.content ?? ''));
  assert.ok(thought, 'the re-route is on the record');
  assert.match(thought.data.content, /gemma3:4b measured 15\/15 on lookup goals with 0 ungrounded/);
  assert.match(thought.data.content, /smollm2:360m measured 3\/10 on lookups/);
  assert.equal(r.grounded, true);
});

test('a model that already meets the rule is left alone', async () => {
  chatModels.length = 0;
  const messages = await run('which pull requests are open?', STRONG);
  assert.equal(result(messages).route.model, STRONG);
  assert.deepEqual(chatModels, [STRONG]);
  assert.ok(!messages.some((m) => m.type === 'thought' && /^Routed to /.test(m.data?.content ?? '')));
});
