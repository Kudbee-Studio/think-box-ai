// The per-run budget on the real server: a run that has spent more than the cap stops before its next model call with a plain message, the stop is in the audit log,
// and the same goal without a cap completes. Mock model with scripted token usage.
import assert from 'node:assert/strict';
import { spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';
import { freePort } from './helpers/free-port.ts';
import { call, say, startMockInception, type MockInception } from './helpers/mock-inception.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let mock: MockInception; let tmp = ''; const servers: ChildProcess[] = [];
before(async () => { mock = await startMockInception(); tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-budget-')); });
after(async () => { for (const s of servers) s.kill(); await mock.close(); fs.rmSync(tmp, { recursive: true, force: true }); });

async function startServer(extra: Record<string, string>): Promise<string> {
  const port = await freePort(); const base = `http://127.0.0.1:${port}`; const dir = fs.mkdtempSync(path.join(tmp, 's-')); const dead = 'http://127.0.0.1:9';
  const server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], { cwd: appDir, stdio: 'ignore', env: { ...process.env, PORT: String(port), HOST: '127.0.0.1', INCEPTION_API_KEY: 'test-key', INCEPTION_API_KEY_2: '', DEEPSEEK_API_KEY: '', XAI_API_KEY: '', INCEPTION_BASE_URL: mock.baseUrl, OLLAMA_BASE_URL: dead, JANUS_BASE_URL: dead, UPSTASH_VECTOR_REST_URL: dead, UPSTASH_VECTOR_REST_TOKEN: 'none', THINKBOX_EMBEDDINGS: 'off', KUDBEE_DATA_DIR: path.join(dir, 'data'), KUDBEE_LEARNING_DB: path.join(dir, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(dir, 'ws'), KUDBEE_DAILY_BUDGET_USD: '', KUDBEE_RUN_BUDGET_USD: '', ...extra } });
  servers.push(server);
  for (let i = 0; ; i++) { try { if ((await fetch(`${base}/api/health`)).ok) return base; } catch { /* starting */ } if (i > 100) throw new Error('server did not start'); await new Promise((r) => setTimeout(r, 150)); }
}
const runGoal = (base: string, goal: string): Promise<{ success: boolean; error?: string; result?: string }> => new Promise((resolve, reject) => {
  const ws = new WebSocket(`${base.replace('http', 'ws')}/ws`, { origin: base }); const timer = setTimeout(() => reject(new Error('no result')), 20000); ws.on('error', reject);
  ws.on('message', (raw) => { const m = JSON.parse(raw.toString()); if (m.type === 'init') ws.send(JSON.stringify({ type: 'run_goal', goal, model: 'mercury-2' })); if (m.type === 'result') { clearTimeout(timer); ws.close(); resolve(m.data); } });
});
// each model reply is billed at 3000 prompt + 500 completion tokens: about $0.0011 at mercury-2's price
const script = (): void => mock.script([{ ...call('list_files'), usage: { prompt_tokens: 3000, completion_tokens: 500 } }, { content: 'The workspace is empty.', usage: { prompt_tokens: 3000, completion_tokens: 500 } }]);

test('a run over the per-run cap stops before its next model call; the stop is in the audit log', async () => {
  const base = await startServer({ KUDBEE_RUN_BUDGET_USD: '0.0005' }); script(); mock.requests.length = 0;
  const result = await runGoal(base, 'List the files in my workspace.');
  assert.equal(result.success, false); assert.equal(result.error, 'Run budget of $0.0005 reached (KUDBEE_RUN_BUDGET_USD)');
  assert.equal(mock.requests.length, 1, 'the second model call was never made');
  const { events } = await (await fetch(`${base}/api/audit?kind=budget_stop`)).json() as { events: Array<{ summary: string; run_id: string | null }> };
  assert.equal(events.length, 1); assert.match(events[0]!.summary, /Run budget of \$0\.0005/); assert.ok(events[0]!.run_id);
  const spend = await (await fetch(`${base}/api/spend`)).json() as { budget: { run: number }; by_model: Array<{ model: string; runs: number }> };
  assert.equal(spend.budget.run, 0.0005); assert.equal(spend.by_model[0]!.model, 'mercury-2'); assert.equal(spend.by_model[0]!.runs, 1);
});

test('the same goal with no cap completes', async () => {
  const base = await startServer({}); script();
  const result = await runGoal(base, 'List the files in my workspace.');
  assert.equal(result.success, true); assert.match(String(result.result), /workspace is empty/);
});
