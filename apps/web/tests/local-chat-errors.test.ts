// A local model that fails must make the run FAIL with Ollama's reason. Before: no res.ok check and {"error": ...} lines were ignored, so a
// missing model (Ollama answers 404 {"error":"model ... not found"}) or a cut-off stream ended as a "completed" run with an empty answer.
// Real server.ts against a fake Ollama that misbehaves on demand.
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
let behavior: 'ok' | 'notfound' | 'errline' | 'cutoff' | 'empty' | 'no-final-newline' = 'ok';
let ollama: http.Server;
let server: ChildProcess;
let base = '';
let tmp = '';

before(async () => {
  ollama = http.createServer((req, res) => {
    req.resume();
    req.on('end', () => {
      if (req.url === '/api/tags') { res.setHeader('content-type', 'application/json'); return void res.end(JSON.stringify({ models: [{ name: MODEL, size: 725_000_000 }] })); }
      if (req.url !== '/api/chat') { res.statusCode = 404; return void res.end('{}'); }
      if (behavior === 'notfound') { res.statusCode = 404; res.setHeader('content-type', 'application/json'); return void res.end(JSON.stringify({ error: `model '${MODEL}' not found` })); }
      res.setHeader('content-type', 'application/x-ndjson');
      if (behavior === 'empty') return void res.end();
      res.write(`${JSON.stringify({ message: { content: 'Four' }, done: false })}\n`);
      if (behavior === 'errline') return void res.end(`${JSON.stringify({ error: 'llama runner process has terminated: out of memory' })}\n`);
      if (behavior === 'cutoff') return void res.end(`${JSON.stringify({ message: { content: ' is' }, done: false })}\n`);
      if (behavior === 'no-final-newline') return void res.end(JSON.stringify({ message: { content: '' }, done: true }));
      res.end(`${JSON.stringify({ message: { content: '' }, done: true })}\n`);
    });
  });
  await new Promise<void>((r) => ollama.listen(0, '127.0.0.1', r));
  const ollamaUrl = `http://127.0.0.1:${(ollama.address() as { port: number }).port}`;
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-chat-err-'));
  const port = 20000 + Math.floor(Math.random() * 20000);
  base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: {
      ...process.env, PORT: String(port), INCEPTION_API_KEY: '', OLLAMA_BASE_URL: ollamaUrl, JANUS_BASE_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9',
      UPSTASH_VECTOR_REST_TOKEN: 'none', KUDBEE_DAILY_BUDGET_USD: '0', KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), THINKBOX_EMBEDDINGS: 'off', THINKBOX_LOCAL_MODEL: MODEL,
    },
    stdio: 'ignore',
  });
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) {
    try { if ((await fetch(`${base}/api/health`)).ok) return; } catch { /* starting */ }
  }
  throw new Error('server did not start');
});
after(async () => { server?.kill(); await new Promise((r) => ollama.close(r)); fs.rmSync(tmp, { recursive: true, force: true }); });

function runGoal(goal: string): Promise<{ result: any; stream: string }> {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`${base.replace('http', 'ws')}/ws`, { origin: base });
    let stream = '';
    const timer = setTimeout(() => reject(new Error('no result')), 15000);
    ws.on('error', reject);
    ws.on('message', (raw) => {
      const m = JSON.parse(raw.toString());
      if (m.type === 'init') ws.send(JSON.stringify({ type: 'run_goal', goal, model: MODEL }));
      if (m.type === 'stream') stream += m.data;
      if (m.type === 'result') { clearTimeout(timer); ws.close(); resolve({ result: m.data, stream }); }
    });
  });
}

test('a healthy local chat still completes (also when the last line has no trailing newline)', async () => {
  for (const mode of ['ok', 'no-final-newline'] as const) {
    behavior = mode;
    const { result, stream } = await runGoal(`What is 2 plus 2? (${mode})`);
    assert.equal(result.success, true, mode);
    assert.equal(result.result, 'Four', mode);
    assert.equal(stream, 'Four', mode);
  }
});

test('a missing model (HTTP 404 {"error": ...}) fails the run with Ollama\'s reason instead of completing with an empty answer', async () => {
  behavior = 'notfound';
  const { result } = await runGoal('Is the model there?');
  assert.equal(result.success, false);
  assert.match(result.error, /Ollama returned HTTP 404: model 'smollm2:360m' not found/);
});

test('an error reported mid-stream fails the run and keeps the reason', async () => {
  behavior = 'errline';
  const { result } = await runGoal('What color is the sky?');
  assert.equal(result.success, false);
  assert.match(result.error, /out of memory/);
});

test('a stream that ends without finishing, and an empty reply, are failures, not completed runs', async () => {
  behavior = 'cutoff';
  const cut = await runGoal('Cut off please.');
  assert.equal(cut.result.success, false);
  assert.match(cut.result.error, /ended the response without finishing it/);

  behavior = 'empty';
  const empty = await runGoal('Say nothing.');
  assert.equal(empty.result.success, false);
  assert.match(empty.result.error, /ended the response without finishing it/);
});

test('failed runs are recorded as failed in the run history', async () => {
  const runs = (await (await fetch(`${base}/api/runs`)).json()) as { runs: Array<{ status: string; goal: string; error?: string }> };
  const failed = runs.runs.filter((r) => r.status === 'failed');
  assert.ok(failed.length >= 4, `expected the four failed runs, found ${failed.length}`);
  assert.ok(failed.some((r) => /not found/.test(String(r.error))));
  assert.ok(runs.runs.some((r) => r.status === 'completed'), 'and the healthy ones are completed');
});
