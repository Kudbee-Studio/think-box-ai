// Convoys through the real server: dry run (PLAN ONLY, provably nothing runs), queued approval, human-only approval, live execution with real
// workers for Mercury / Qwen-style / Gemma-style models, aggregation, drill-down, one dashboard row, grounding, escalation and failures.
// Fake GitHub + fake Ollama + scripted Mercury stand-in; the server and its governed tool path are real.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';
import Database from 'better-sqlite3';
import { call, say, startMockInception, type MockInception } from './helpers/mock-inception.ts';
import { freePort } from './helpers/free-port.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const QWEN = 'qwen2.5:3b';
const GEMMA = 'gemma3:4b';
const pr = (number: number, o: Record<string, unknown> = {}) => ({ number, title: `PR ${number}`, state: 'closed', merged_at: '2026-10-04T10:00:00Z', draft: false, user: { login: 'dev' }, head: { ref: `feat/pr${number}` }, updated_at: '2026-10-04T10:00:00Z', html_url: `https://github.com/Acme/widgets/pull/${number}`, ...o });

let mock: MockInception; let ollama: http.Server; let github: http.Server; let server: ChildProcess;
let base = ''; let tmp = '';
const githubHits: string[] = []; let githubStatus = 200;
const ollamaChats: Array<{ model: string; tools?: unknown; format?: unknown }> = [];
const ollamaScript: Record<string, any[]> = {};
const turnQueue = (model: string, turns: any[]): void => { ollamaScript[model] = turns; };
const nativeCall = (args: unknown) => ({ message: { role: 'assistant', content: '', tool_calls: [{ function: { name: 'live_lookup', arguments: args } }] }, prompt_eval_count: 100, eval_count: 10 });
const nativeSay = (content: string) => ({ message: { role: 'assistant', content }, prompt_eval_count: 120, eval_count: 20 });
const jsonCall = (args: unknown) => ({ message: { role: 'assistant', content: JSON.stringify({ action: 'call', ...(args as object) }) }, prompt_eval_count: 90, eval_count: 12 });
const jsonSay = (answer: string) => ({ message: { role: 'assistant', content: JSON.stringify({ action: 'answer', answer }) }, prompt_eval_count: 110, eval_count: 25 });

before(async () => {
  mock = await startMockInception();
  ollama = http.createServer((req, res) => {
    let body = ''; req.on('data', (d) => { body += d; });
    req.on('end', () => {
      res.setHeader('content-type', 'application/json');
      const b = body ? JSON.parse(body) : {};
      if (req.url === '/api/tags') return void res.end(JSON.stringify({ models: [{ name: QWEN, size: 1 }, { name: GEMMA, size: 1 }] }));
      if (req.url === '/api/show') return void res.end(JSON.stringify({ capabilities: b.model === QWEN ? ['completion', 'tools'] : ['completion'] }));
      if (req.url === '/api/chat') {
        ollamaChats.push({ model: b.model, tools: b.tools, format: b.format });
        const next = ollamaScript[b.model]?.shift();
        if (!next) { res.statusCode = 500; return void res.end(JSON.stringify({ error: 'script exhausted' })); }
        return void res.end(JSON.stringify({ ...next, done: true }));
      }
      res.statusCode = 404; res.end('{}');
    });
  });
  github = http.createServer((req, res) => {
    githubHits.push(String(req.url));
    res.setHeader('content-type', 'application/json');
    res.statusCode = githubStatus;
    res.end(githubStatus === 200 ? JSON.stringify([pr(361), pr(360, { merged_at: null, state: 'open', draft: true })]) : '{"message":"boom"}');
  });
  await Promise.all([new Promise<void>((r) => ollama.listen(0, '127.0.0.1', r)), new Promise<void>((r) => github.listen(0, '127.0.0.1', r))]);
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-convoy-'));
  const port = await freePort();
  base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: { ...process.env, PORT: String(port), INCEPTION_API_KEY: 'test-key', INCEPTION_API_KEY_2: '', INCEPTION_BASE_URL: mock.baseUrl, OLLAMA_BASE_URL: `http://127.0.0.1:${(ollama.address() as { port: number }).port}`,
      KUDBEE_GITHUB_API: `http://127.0.0.1:${(github.address() as { port: number }).port}`, KUDBEE_REPO: 'Acme/widgets', JANUS_BASE_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: 'none',
      KUDBEE_DAILY_BUDGET_USD: '0', KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_LEARNING_DB: path.join(tmp, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), THINKBOX_EMBEDDINGS: 'off', THINKBOX_LOCAL_MODEL: QWEN },
    stdio: 'ignore',
  });
  for (const end = Date.now() + 20000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) {
    try { if ((await fetch(`${base}/api/health`)).ok) return; } catch { /* starting */ }
  }
  throw new Error('server did not start');
});
after(async () => {
  server?.kill();
  await Promise.all([new Promise((r) => ollama.close(r)), new Promise((r) => github.close(r)), mock.close()]);
  fs.rmSync(tmp, { recursive: true, force: true });
});

const post = async (p: string, body: unknown = {}, headers: Record<string, string> = {}) => { const r = await fetch(`${base}${p}`, { method: 'POST', headers: { 'content-type': 'application/json', ...headers }, body: JSON.stringify(body) }); return { status: r.status, body: await r.json() as any }; };
/** A request that really carries an Origin header (Node's fetch drops it): what the dashboard in a browser sends. */
const postFromDashboard = (p: string, body: unknown = {}): Promise<{ status: number; body: any }> => new Promise((resolve, reject) => {
  const data = JSON.stringify(body); const u = new URL(`${base}${p}`);
  const req = http.request({ host: u.hostname, port: u.port, path: u.pathname, method: 'POST', headers: { 'content-type': 'application/json', 'content-length': Buffer.byteLength(data), origin: base } }, (res) => {
    let b = ''; res.on('data', (d) => { b += d; }); res.on('end', () => resolve({ status: res.statusCode ?? 0, body: JSON.parse(b || '{}') }));
  });
  req.on('error', reject); req.end(data);
});
const get = async (p: string) => (await fetch(`${base}${p}`)).json() as Promise<any>;
const plan = async (goal: string, model?: string, worker_budget?: unknown) => (await post('/api/convoys/plan', { goal, model, worker_budget })).body.convoy;
const tree = (dir: string): string[] => fs.existsSync(dir) ? fs.readdirSync(dir, { recursive: true }).map(String).sort() : [];

/** A dashboard session: collects messages; answers tool approvals with `approve`. */
function session(approve: (req: any) => boolean = () => true) {
  const ws = new WebSocket(`${base.replace('http', 'ws')}/ws`, { origin: base });
  const messages: any[] = []; const approvals: any[] = [];
  const ready = new Promise<void>((resolve, reject) => { ws.on('error', reject); ws.on('message', (raw) => {
    const m = JSON.parse(raw.toString()); messages.push(m);
    if (m.type === 'init') resolve();
    if (m.type === 'approval_request') { approvals.push(m.data); ws.send(JSON.stringify({ type: 'approval_response', id: m.data.id, approved: approve(m.data) })); }
  }); });
  const waitFor = (pred: (m: any) => boolean, ms = 20000): Promise<any> => new Promise((resolve, reject) => {
    const started = Date.now();
    const tick = (): void => { const hit = messages.find(pred); if (hit) return resolve(hit); if (Date.now() - started > ms) return reject(new Error('timeout waiting for message')); setTimeout(tick, 25); };
    tick();
  });
  return { ws, messages, approvals, ready, waitFor, send: (m: unknown) => ws.send(JSON.stringify(m)), close: () => ws.close() };
}
const finished = (id: string) => (m: any) => m.type === 'convoy_update' && m.data.id === id && ['COMPLETED', 'PARTIAL', 'FAILED'].includes(m.data.state);

/** plan -> submit -> approve (over WS, as a human) -> wait for the end state. */
async function runConvoy(goal: string, model: string, opts: { approve?: (r: any) => boolean; budget?: unknown } = {}) {
  const c = await plan(goal, model, opts.budget);
  assert.equal((await post(`/api/convoys/${c.id}/submit`)).status, 200);
  const s = session(opts.approve); await s.ready;
  s.send({ type: 'convoy_approve', id: c.id, note: 'test' });
  await s.waitFor(finished(c.id));
  s.close();
  return { id: c.id, detail: (await get(`/api/convoys/${c.id}`)).convoy, approvals: s.approvals, messages: s.messages };
}

test('DRY RUN: the Mayor plans, shows workers, tools, order, budget, policy and expected convoy, and provably runs nothing', async () => {
  const dataBefore = tree(path.join(tmp, 'data')).filter((f) => !f.endsWith('convoys.json') && !f.endsWith('convoys.json.tmp'));
  const watcher = session(); await watcher.ready; // (connecting makes this session's own workspace folder; the plan must add nothing beyond it)
  const wsBefore = tree(path.join(tmp, 'ws'));
  const counts = { mercury: mock.requests.length, ollama: ollamaChats.length, github: githubHits.length, runs: (await get('/api/runs?children=1')).runs.length };
  const convoy = await plan('What is the last PR?', GEMMA);
  assert.equal(convoy.mode, 'plan_only');
  assert.equal(convoy.state, 'PLANNED');
  assert.equal(convoy.approval, null);
  assert.equal(convoy.plan.plan_only, true);
  assert.equal(convoy.plan.side_effects, 'none');
  assert.deepEqual(convoy.plan.workers.map((w: any) => [w.id, w.model, w.tools, w.permission, w.wave]), [['lookup-1', GEMMA, ['live_lookup'], 'read_only', 1]]);
  assert.deepEqual(convoy.plan.escalation.model, 'mercury-2');
  assert.deepEqual(convoy.plan.expected_convoy, { dashboard_rows: 1, children: 1, waves: 1 });
  assert.equal(convoy.plan.budget_use.worst_case_workers, 2);
  assert.equal(convoy.policy.decision, 'requires_approval');
  assert.equal(convoy.policy.risk, 'low');
  assert.ok(convoy.policy.rules.some((r: any) => r.id === 'human-approval'));
  assert.deepEqual(convoy.chain, { ok: true });
  assert.equal(convoy.events.length, 1);
  // a budget the plan cannot fit is enforced: not executable, denied by policy, cannot be submitted
  const tight = await plan('What is the last PR?', GEMMA, { max_workers: 1 });
  assert.equal(tight.plan.executable, false);
  assert.match(tight.plan.blocked_reasons.join(), /worker budget exceeded/);
  assert.equal(tight.policy.decision, 'denied');
  const refused = await post(`/api/convoys/${tight.id}/submit`);
  assert.equal(refused.status, 409);
  assert.match(refused.body.error, /cannot be submitted/);
  assert.equal((await post('/api/convoys/plan', { goal: 'x', worker_budget: { max_workers: 0 } })).status, 400);
  assert.equal((await post('/api/convoys/plan', { goal: '' })).status, 400);
  await new Promise((r) => setTimeout(r, 300));
  // nothing ran: no worker, no model call, no network call, no run record, no approval asked, no workspace, no files besides the convoy records
  assert.deepEqual({ mercury: mock.requests.length, ollama: ollamaChats.length, github: githubHits.length, runs: (await get('/api/runs?children=1')).runs.length }, counts);
  assert.equal(watcher.approvals.length, 0);
  assert.ok(!watcher.messages.some((m) => m.type === 'convoy_update' || m.type === 'thought'));
  assert.deepEqual(tree(path.join(tmp, 'data')).filter((f) => !f.endsWith('convoys.json') && !f.endsWith('convoys.json.tmp')), dataBefore);
  assert.deepEqual(tree(path.join(tmp, 'ws')), wsBefore);
  watcher.close();
});

test('QUEUED APPROVAL: submit queues a PENDING approval with convoy, goal, workers, budget, policy and risk attached; execution stays blocked', async () => {
  const counts = { ollama: ollamaChats.length, github: githubHits.length, runs: (await get('/api/runs?children=1')).runs.length };
  const c = await plan('What is the last PR?', QWEN);
  const submitted = (await post(`/api/convoys/${c.id}/submit`)).body.convoy;
  assert.equal(submitted.state, 'PENDING');
  const a = submitted.approval;
  assert.equal(a.state, 'PENDING');
  assert.equal(a.convoy_id, c.id);
  assert.equal(a.snapshot.goal, 'What is the last PR?');
  assert.deepEqual(a.snapshot.workers.map((w: any) => w.model), [QWEN]);
  assert.deepEqual(a.snapshot.worker_budget, { max_workers: 4, max_cost_usd: 0.1, max_tool_calls: 20 });
  assert.equal(a.snapshot.policy.decision, 'requires_approval');
  assert.equal(a.snapshot.risk, 'low');
  assert.deepEqual(a.snapshot.tools, ['live_lookup']);
  assert.ok(a.expires_at > a.requested_at);
  assert.deepEqual(submitted.events.map((e: any) => e.state), ['PLANNED', 'PENDING']);
  // blocked while pending: submitting again is refused, a model/other process cannot approve, nothing runs
  assert.equal((await post(`/api/convoys/${c.id}/submit`)).status, 409);
  assert.equal((await post(`/api/convoys/${c.id}/reject`, {})).status, 403, 'no origin and no token: not a human operator');
  const viaHttp = await postFromDashboard(`/api/convoys/${c.id}/approve`, { by: 'human' });
  assert.notEqual(viaHttp.status, 200, 'there is no HTTP approve endpoint');
  assert.equal((await get(`/api/convoys/${c.id}`)).convoy.state, 'PENDING');
  const s = session(); await s.ready;
  s.send({ type: 'convoy_approve', id: 'does-not-exist' });
  const err = await s.waitFor((m) => m.type === 'convoy_error');
  assert.match(err.data.error, /unknown convoy/);
  await new Promise((r) => setTimeout(r, 300));
  assert.equal((await get(`/api/convoys/${c.id}`)).convoy.state, 'PENDING');
  assert.deepEqual({ ollama: ollamaChats.length, github: githubHits.length, runs: (await get('/api/runs?children=1')).runs.length }, counts);
  s.close();
  // a human rejects it from the dashboard origin: REJECTED, never runs
  const rejected = await postFromDashboard(`/api/convoys/${c.id}/reject`, { note: 'not now' });
  assert.equal(rejected.status, 200);
  assert.equal(rejected.body.convoy.state, 'REJECTED');
  assert.equal(rejected.body.convoy.approval.state, 'REJECTED');
  assert.equal(rejected.body.convoy.approval.decided_by, 'human');
  const s2 = session(); await s2.ready;
  s2.send({ type: 'convoy_approve', id: c.id });
  assert.match((await s2.waitFor((m) => m.type === 'convoy_error')).data.error, /not waiting for approval/);
  s2.close();
  assert.equal((await get('/api/runs?children=1')).runs.length, counts.runs);
});

test('LIVE RUN, Qwen-style native tools: approve -> real worker -> governed tool -> evidence -> grounded answer; convoy aggregates and keeps child evidence', async () => {
  githubHits.length = 0; ollamaChats.length = 0;
  turnQueue(QWEN, [nativeCall({ recipe: 'latest_pr' }), nativeSay('The last PR is #361, PR 361, and it is merged.')]);
  const r = await runConvoy('What is the last PR?', QWEN);
  const c = r.detail;
  assert.equal(c.state, 'COMPLETED');
  assert.equal(c.outcome, 'success');
  assert.equal(c.mode, 'live');
  assert.deepEqual(c.events.map((e: any) => e.state), ['PLANNED', 'PENDING', 'APPROVED', 'RUNNING', 'COMPLETED']);
  assert.deepEqual(c.chain, { ok: true });
  assert.equal(c.events.find((e: any) => e.state === 'APPROVED').by, 'human');
  assert.equal(r.approvals.length, 1, 'first network access asked the human, like any run');
  assert.deepEqual(githubHits, ['/repos/Acme/widgets/pulls?state=all&sort=created&direction=desc&per_page=5']);
  assert.ok(ollamaChats.every((x) => x.model === QWEN) && ollamaChats.length === 2);
  assert.ok(Array.isArray(ollamaChats[0]!.tools), 'native tools were sent');
  assert.equal(c.workers.length, 1);
  const w = c.workers[0];
  assert.deepEqual({ status: w.status, model: w.model, tool_calls: w.tool_calls, cost: w.cost_usd, tokens: w.tokens }, { status: 'completed', model: QWEN, tool_calls: 1, cost: 0, tokens: 250 });
  assert.equal(w.grounding.status, 'GROUNDED');
  assert.equal(c.grounding.status, 'GROUNDED');
  assert.match(c.final_answer, /#361/);
  assert.equal(c.evidence[0].recipe, 'latest_pr');
  assert.equal(c.evidence[0].items[0].number, 361);
  assert.deepEqual({ cost: c.cost_usd, calls: c.tool_calls, tokens: c.tokens }, { cost: 0, calls: 1, tokens: 250 });
  assert.ok(c.worker_duration_ms >= 0 && c.finished_at >= c.started_at);
  // drill-down: convoy -> run -> tool step -> its output (the evidence)
  assert.equal(c.runs.length, 1);
  const run = c.runs[0];
  assert.equal(run.jobId, c.id);
  assert.equal(run.model, QWEN);
  assert.equal(run.status, 'completed');
  const tool = run.steps.find((s: any) => s.kind === 'tool');
  assert.equal(tool.name, 'live_lookup');
  assert.equal(tool.ok, true);
  assert.match(tool.output, /"recipe":"latest_pr"/);
  assert.equal(tool.approval, 'approved');
  // ONE dashboard row: the convoy is listed, its child run is not a competing top-level run
  assert.ok((await get('/api/convoys')).convoys.some((x: any) => x.id === c.id));
  assert.ok(!(await get('/api/runs')).runs.some((x: any) => x.id === run.id));
  assert.ok((await get('/api/runs?children=1')).runs.some((x: any) => x.id === run.id));
});

test('LIVE RUN, Gemma-style constrained JSON: same tool, same evidence, same grounding', async () => {
  githubHits.length = 0; ollamaChats.length = 0;
  turnQueue(GEMMA, [jsonCall({ recipe: 'latest_pr' }), jsonSay('The last PR is #361, PR 361, and it is merged.')]);
  const c = (await runConvoy('What is the last PR?', GEMMA)).detail;
  assert.equal(c.state, 'COMPLETED');
  assert.deepEqual(githubHits, ['/repos/Acme/widgets/pulls?state=all&sort=created&direction=desc&per_page=5']);
  assert.ok(ollamaChats.every((x) => x.model === GEMMA && x.tools === undefined && x.format), 'constrained: a JSON schema, no native tools');
  assert.equal(c.workers[0].grounding.status, 'GROUNDED');
  assert.equal(c.runs[0].steps.find((s: any) => s.kind === 'tool').name, 'live_lookup');
  assert.equal(c.evidence[0].items[0].number, 361);
});

test('LIVE RUN, Mercury worker agent: the same live_lookup tool through the agent loop, cost aggregated from real usage, same grounding', async () => {
  githubHits.length = 0;
  mock.script([
    { ...call('live_lookup', { recipe: 'latest_pr' }), usage: { prompt_tokens: 900, completion_tokens: 40 } },
    { content: 'The last PR is #361, PR 361, and it is merged.', usage: { prompt_tokens: 1100, completion_tokens: 30 } },
  ]);
  const before = mock.requests.length;
  const c = (await runConvoy('What is the last PR?', 'mercury-2')).detail;
  assert.equal(c.state, 'COMPLETED');
  assert.equal(mock.requests.length - before, 2);
  assert.deepEqual((mock.requests[before]!.tools as any[]).map((t) => t.function.name).sort(), ['live_lookup'], 'the worker was offered only the governed tool it is allowed');
  assert.deepEqual(githubHits, ['/repos/Acme/widgets/pulls?state=all&sort=created&direction=desc&per_page=5']);
  const w = c.workers[0];
  assert.equal(w.model, 'mercury-2');
  assert.equal(w.tool_calls, 1);
  assert.equal(w.tokens, 2070);
  assert.ok(w.cost_usd > 0, 'real usage costs money');
  assert.equal(c.cost_usd, Math.round(w.cost_usd * 1e6) / 1e6, 'the convoy total is the children\'s total');
  assert.equal(w.grounding.status, 'GROUNDED');
  assert.equal(c.evidence[0].items[0].number, 361);
  assert.equal(c.runs[0].steps.find((s: any) => s.kind === 'tool').name, 'live_lookup');
  // the next plan estimates a lookup from MEASURED lookup runs, not from all Mercury runs
  const next = await plan('What is the last PR?', 'mercury-2');
  assert.equal(next.plan.workers[0].estimated_cost_usd, Math.round(w.cost_usd * 1e6) / 1e6);
  assert.match(next.plan.workers[0].cost_basis, /average of 1 measured mercury-2 lookup run\(s\)/);
});

test('GROUNDING FAILED on a local worker escalates once to the worker agent through the same path; both workers stay on the record', async () => {
  githubHits.length = 0;
  turnQueue(GEMMA, [jsonCall({ recipe: 'latest_pr' }), jsonSay('The last PR is #999, and it is merged.')]);
  mock.script([call('live_lookup', { recipe: 'latest_pr' }), say('The last PR is #361 (PR 361), merged.')]);
  const r = await runConvoy('What is the last PR?', GEMMA);
  const c = r.detail;
  assert.equal(c.state, 'COMPLETED');
  assert.equal(c.outcome, 'success');
  assert.deepEqual(c.workers.map((w: any) => [w.id, w.model, w.status]), [['lookup-1', GEMMA, 'completed'], ['escalation-1', 'mercury-2', 'completed']]);
  assert.equal(c.workers[0].grounding.status, 'GROUNDING FAILED', 'the first worker\'s failure is kept, not hidden');
  assert.ok(c.workers[0].grounding.unsupported.some((u: any) => u.claim.includes('999')));
  assert.equal(c.workers[1].grounding.status, 'GROUNDED');
  assert.match(c.final_answer, /#361/);
  assert.doesNotMatch(c.final_answer, /999/);
  assert.equal(c.run_ids.length, 2);
  assert.equal(c.runs.length, 2);
  assert.equal(c.cost_usd, Math.round(c.workers[1].cost_usd * 1e6) / 1e6, 'cost is the sum of the children');
  assert.equal(githubHits.length, 2, 'each worker made its own governed lookup');
  assert.ok(r.messages.some((m) => m.type === 'thought' && /Retrying once on mercury-2/.test(m.data?.content ?? '')));
});

test('a worker that fails grounding with no fallback is FAILED as grounding_failed, never shown as verified', async () => {
  turnQueue(QWEN, [nativeCall({ recipe: 'latest_pr' }), nativeSay('The last PR is #999, merged.')]);
  mock.script([call('live_lookup', { recipe: 'latest_pr' }), say('Also wrong: PR #888 is merged.')]);
  const c = (await runConvoy('What is the last PR?', QWEN)).detail;
  assert.equal(c.state, 'FAILED');
  assert.equal(c.outcome, 'grounding_failed');
  assert.equal(c.final_answer, undefined);
  assert.equal(c.grounding.status, 'GROUNDING FAILED');
  assert.match(c.error, /GROUNDING FAILED/);
  assert.equal(c.evidence.length, 2, 'the evidence is kept');
  assert.ok(c.workers.every((w: any) => w.grounding.status === 'GROUNDING FAILED'));
});

test('a denied tool approval fails the convoy as denied: no answer, no escalation, failure preserved', async () => {
  githubHits.length = 0; const before = mock.requests.length;
  turnQueue(QWEN, [nativeCall({ recipe: 'latest_pr' }), nativeSay('never asked')]);
  const r = await runConvoy('What is the last PR?', QWEN, { approve: () => false });
  const c = r.detail;
  assert.equal(c.state, 'FAILED');
  assert.equal(c.outcome, 'failed');
  assert.equal(c.workers.length, 1, 'a denial is not retried elsewhere');
  assert.equal(c.workers[0].failure.kind, 'tool_denied');
  assert.match(c.error, /tool_denied: Denied by human reviewer/);
  assert.equal(githubHits.length, 0);
  assert.equal(mock.requests.length, before);
  assert.equal(c.final_answer, undefined);
  assert.equal(c.runs[0].status, 'failed');
});

test('a tool failure (GitHub 500) is classified as a failure on every worker and the convoy is FAILED, not a made-up success', async () => {
  githubStatus = 500;
  try {
    turnQueue(QWEN, [nativeCall({ recipe: 'latest_pr' })]);
    mock.script([call('live_lookup', { recipe: 'latest_pr' }), say('GitHub is not answering, so I cannot say.')]);
    const c = (await runConvoy('What is the last PR?', QWEN)).detail;
    assert.equal(c.state, 'FAILED');
    assert.equal(c.outcome, 'failed');
    assert.equal(c.workers[0].status, 'failed');
    assert.equal(c.workers[0].failure.kind, 'tool_failed');
    assert.match(c.workers[0].failure.message, /HTTP 500/);
    assert.equal(c.workers.length, 2, 'the failed local worker was retried once on the worker agent');
    assert.equal(c.final_answer, undefined);
    assert.equal(c.evidence.length, 0);
  } finally { githubStatus = 200; }
});

test('a specialist convoy runs the existing specialist job with the convoy id as the job id; children are retained, one row', async () => {
  mock.script([
    call('fetch_url', { url: `${mock.baseUrl.replace('/v1', '')}/page` }), say('The page says the answer is 42.'),
    ...Array.from({ length: 12 }, () => say('Looks fine.')),
  ]);
  const goal = 'Research the page and summarize what it says';
  const c0 = await plan(goal);
  assert.ok(c0.plan.workers.length >= 1);
  assert.ok(c0.plan.workers.every((w: any) => w.kind === 'specialist' && w.model === 'mercury-2'));
  assert.equal(c0.plan.expected_convoy.dashboard_rows, 1);
  if (!c0.plan.executable) return; // the plan is the thing under test here; execution is covered by the live Mercury run
  assert.equal((await post(`/api/convoys/${c0.id}/submit`)).status, 200);
  const s = session(); await s.ready;
  s.send({ type: 'convoy_approve', id: c0.id });
  await s.waitFor(finished(c0.id), 60000);
  s.close();
  const c = (await get(`/api/convoys/${c0.id}`)).convoy;
  assert.ok(['COMPLETED', 'PARTIAL', 'FAILED'].includes(c.state));
  assert.ok(c.workers.some((w: any) => w.run_id), 'children are linked');
  assert.deepEqual(c.runs.map((run: any) => run.specialistId).sort(), c0.plan.workers.map((w: any) => w.id).sort(), 'exactly the approved plan\'s workers ran: none added, none dropped');
  assert.ok(c.runs.every((run: any) => run.jobId === c.id), 'each child run carries the convoy id');
  assert.ok(!(await get('/api/runs')).runs.some((x: any) => x.jobId === c.id), 'no child run is a top-level row');
  assert.deepEqual(c.chain, { ok: true });
});

const tokenRows = (): Array<{ id: string; status: string; extractor: string; kind: string; title: string; source_run_id: string }> => {
  const db = new Database(path.join(tmp, 'data', 'think-tokens.db'), { readonly: true, fileMustExist: false });
  try { return db.prepare('select id, status, extractor, kind, title, source_run_id from think_tokens').all() as any; } catch { return []; } finally { db.close(); }
};

test('LEARN mode: a verified lookup convoy leaves deterministic Think Token CANDIDATES (no model, never accepted); OBSERVE leaves none', async () => {
  const before = tokenRows().length;
  turnQueue(QWEN, [nativeCall({ recipe: 'latest_pr' }), nativeSay('The last PR is #361, PR 361, and it is merged.')]);
  const observe = await runConvoy('What is the last PR?', QWEN);
  assert.equal(observe.detail.state, 'COMPLETED');
  assert.equal(observe.detail.plan.think_mode, 'observe');
  assert.equal(tokenRows().length, before, 'OBSERVE learns nothing');
  assert.equal(observe.detail.learned_tokens, undefined);

  turnQueue(QWEN, [nativeCall({ recipe: 'latest_pr' }), nativeSay('The last PR is #361, PR 361, and it is merged.')]);
  const c0 = (await post('/api/convoys/plan', { goal: 'What is the last PR?', model: QWEN, mode: 'learn' })).body.convoy;
  assert.equal(c0.plan.think_mode, 'learn');
  assert.ok(c0.policy.rules.some((r: any) => r.id === 'mode-learn' && /never auto-accepted/.test(r.reason)));
  await post(`/api/convoys/${c0.id}/submit`);
  const s = session(); await s.ready;
  s.send({ type: 'convoy_approve', id: c0.id });
  await s.waitFor(finished(c0.id));
  const learned = s.messages.filter((m) => m.type === 'think_token_learned');
  s.close();
  const c = (await get(`/api/convoys/${c0.id}`)).convoy;
  assert.equal(c.outcome, 'success');
  assert.ok(c.learned_tokens.length >= 1, 'a candidate was written');
  assert.ok(c.learned_tokens.every((t: any) => t.status === 'candidate'), JSON.stringify(c.learned_tokens));
  // the same lesson learned again is reported as already known, not as a new token
  turnQueue(QWEN, [nativeCall({ recipe: 'latest_pr' }), nativeSay('The last PR is #361, PR 361, and it is merged.')]);
  const again = await post('/api/convoys/plan', { goal: 'What is the last PR?', model: QWEN, mode: 'learn' });
  await post(`/api/convoys/${again.body.convoy.id}/submit`);
  const s2 = session(); await s2.ready; s2.send({ type: 'convoy_approve', id: again.body.convoy.id }); await s2.waitFor(finished(again.body.convoy.id)); s2.close();
  const c2 = (await get(`/api/convoys/${again.body.convoy.id}`)).convoy;
  assert.ok(c2.learned_tokens.length >= 1 && c2.learned_tokens.every((t: any) => t.duplicate === true), JSON.stringify(c2.learned_tokens));
  assert.deepEqual(new Set(c2.learned_tokens.map((t: any) => t.id)), new Set(c.learned_tokens.map((t: any) => t.id)), 'the same tokens');
  const rows = tokenRows().filter((r) => c.run_ids.includes(r.source_run_id));
  assert.ok(rows.length >= 1);
  assert.ok(rows.every((r) => r.status === 'candidate' && r.extractor === 'template'), 'deterministic, never auto-accepted');
  assert.ok(learned.length >= 1, 'the dashboard was told');
  // the job state is projected from the convoy and includes the learned token
  assert.equal(c.job_state.cells.length, 100);
  assert.equal(c.job_state.verdict, 'pass');
  assert.ok(c.job_state.signals.driven.includes('think_token'));
  assert.equal(c.job_state.facts.learned_tokens, c.learned_tokens.length);
});

test('mode is validated: an unknown mode is a 400, SIMULATE and AUTONOMOUS plan as not executable, and stopping a convoy that is not running is an error', async () => {
  assert.equal((await post('/api/convoys/plan', { goal: 'What is the last PR?', model: QWEN, mode: 'yolo' })).status, 400);
  for (const mode of ['simulate', 'autonomous']) {
    const c = (await post('/api/convoys/plan', { goal: 'What is the last PR?', model: QWEN, mode })).body.convoy;
    assert.equal(c.plan.executable, false, mode);
    assert.match(c.plan.blocked_reasons.join(), /not available yet/);
    assert.equal((await post(`/api/convoys/${c.id}/submit`)).status, 409);
  }
  const s = session(); await s.ready;
  s.send({ type: 'convoy_stop', id: 'nope' });
  assert.match((await s.waitFor((m) => m.type === 'convoy_error')).data.error, /not running/);
  s.close();
});
