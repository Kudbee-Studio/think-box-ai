// The real server's plan endpoint for a repository goal with the model field blank and a Mercury key configured (P3.36): the table does not qualify any local model,
// and the plan must still start on a local model and name the escalation, instead of falling back to Mercury and being blocked. Fake Ollama, dummy key (nothing is called).
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { freePort } from './helpers/free-port.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const trials = (model: string, pass: number, total: number, cls = 'repo') => Array.from({ length: total }, (_, i) => ({ model, task: 't', class: cls, outcome: i < pass ? 'pass' : 'ungrounded', why: '', latency_ms: 9000, tool_calls: 1, tokens: 500, mode: 'native' }));
let ollama: http.Server; let server: ChildProcess; let base = ''; let tmp = '';
const GOAL = 'Find an exported function in src/billing.ts that has no test.';

before(async () => {
  ollama = http.createServer((req, res) => { res.setHeader('content-type', 'application/json'); res.end(req.url === '/api/tags' ? JSON.stringify({ models: [{ name: 'qwen2.5:3b', size: 1 }, { name: 'gemma3:4b', size: 1 }] }) : '{}'); });
  await new Promise<void>((r) => ollama.listen(0, '127.0.0.1', r));
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-repo-route-'));
  const table = path.join(tmp, 'local-eval.json');
  fs.writeFileSync(table, JSON.stringify({ generated_at: '2026-10-05T00:00:00Z', trials: trials('qwen2.5:3b', 4, 6) }));
  const port = await freePort(); base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir, stdio: 'ignore',
    env: { ...process.env, PORT: String(port), INCEPTION_API_KEY: 'dummy-never-called', INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: `http://127.0.0.1:${(ollama.address() as { port: number }).port}`, KUDBEE_LOCAL_EVAL: table,
      JANUS_BASE_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: 'none', KUDBEE_DAILY_BUDGET_USD: '0', KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), KUDBEE_LEARNING_DB: path.join(tmp, 'l.db') },
  });
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) { try { if ((await fetch(`${base}/api/health`)).ok) break; } catch { /* starting */ } }
  for (const end = Date.now() + 10000; Date.now() < end; await new Promise((r) => setTimeout(r, 200))) { try { if (JSON.stringify(await (await fetch(`${base}/api/models`)).json()).includes('gemma3:4b')) break; } catch { /* starting */ } }
});
after(async () => { server?.kill(); await new Promise((r) => ollama.close(r)); fs.rmSync(tmp, { recursive: true, force: true }); });

const plan = async (goal: string, model?: string): Promise<any> => (await (await fetch(`${base}/api/convoys/plan`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ goal, ...(model !== undefined ? { model } : {}) }) })).json()).convoy.plan;

test('a repo goal with a blank model starts on the best-measured local model and names the Mercury escalation (it used to be blocked)', async () => {
  const p = await plan(GOAL);
  assert.deepEqual(p.blocked_reasons, []);
  assert.equal(p.executable, true);
  assert.equal(p.workers[0].model, 'qwen2.5:3b');
  assert.equal(p.routing.source, 'default');
  assert.match(p.routing.reason, /starting on qwen2\.5:3b .*escalating to the agent model/);
  assert.equal(p.escalation?.model, 'mercury-2');
  assert.match(p.escalation.when, /no finding where the goal expects one/);
});

test('the operator\'s choice still wins, and a lookup with nothing measured still falls back to the agent model', async () => {
  const chosen = await plan(GOAL, 'qwen2.5:1.5b');
  assert.equal(chosen.workers[0].model, 'qwen2.5:1.5b'); assert.equal(chosen.routing.source, 'operator');
  const mercuryChosen = await plan(GOAL, 'mercury-2');
  assert.match(mercuryChosen.blocked_reasons.join(), /runs on local models in this version/, 'an explicit Mercury choice for a repo goal is still refused');
  const lookup = await plan('What is the last PR?');
  assert.equal(lookup.routing.source, 'default'); assert.equal(lookup.workers[0].model, 'mercury-2');
});
