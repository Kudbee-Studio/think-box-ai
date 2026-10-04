// Opt-in LIVE acceptance (npm run test:live-acceptance): a real server.ts, real Ollama (gemma3:4b, qwen2.5:3b), the real GitHub API and real Mercury.
//   1. "What is the last PR?" through Mercury, Gemma and Qwen: plan -> submit -> approve -> live convoy -> evidence -> grounding.
//   2. A goal that needs real multi-worker execution (specialists fetch a real page): DRY RUN (nothing runs) -> QUEUED APPROVAL (blocked while pending) -> approve -> LIVE.
// Tool approvals are granted by this script (stand-in for the human reviewer) and every grant is recorded. Spend is capped (KUDBEE_DAILY_BUDGET_USD).
// The Mercury key is read from the repo .env and never printed or written. Output: docs/evidence/p3.22-model-integration/live-acceptance.json
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const repoRoot = path.resolve(appDir, '../..');
const OUT = path.join(repoRoot, 'docs/evidence/p3.22-model-integration/live-acceptance.json');
const CAP = process.env.ACCEPTANCE_CAP_USD || '0.20';
const only = process.argv.slice(2);

const dotenv = fs.existsSync(path.join(repoRoot, '.env')) ? fs.readFileSync(path.join(repoRoot, '.env'), 'utf8') : '';
const keyOf = (name: string): string => dotenv.match(new RegExp(`^${name}=(.+)$`, 'm'))?.[1]?.trim().replace(/^["']|["']$/g, '') ?? '';
const inceptionKey = process.env.INCEPTION_API_KEY || keyOf('INCEPTION_API_KEY');
if (!inceptionKey) { console.error('No INCEPTION_API_KEY in the environment or the repo .env: cannot run Mercury'); process.exit(2); }

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-acceptance-'));
const port = 25000 + Math.floor(Math.random() * 8000);
const base = `http://127.0.0.1:${port}`;
const server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
  cwd: appDir, stdio: 'ignore',
  env: { ...process.env, PORT: String(port), INCEPTION_API_KEY: inceptionKey, INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434', JANUS_BASE_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: 'none', THINKBOX_EMBEDDINGS: 'off',
    KUDBEE_DAILY_BUDGET_USD: CAP, KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_LEARNING_DB: path.join(tmp, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), KUDBEE_REPO: 'Kudbee-Studio/think-box-ai', THINKBOX_LOCAL_MODEL: 'qwen2.5:3b' },
});
const stop = () => { try { server.kill(); } catch { /* gone */ } fs.rmSync(tmp, { recursive: true, force: true }); };
process.on('exit', stop);

const post = async (p: string, body: unknown = {}) => { const r = await fetch(`${base}${p}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }); return { status: r.status, body: await r.json() as any }; };
const get = async (p: string) => (await fetch(`${base}${p}`)).json() as Promise<any>;
const counters = async () => ({ runs: (await get('/api/runs?children=1')).runs.length, convoys: (await get('/api/convoys')).convoys.length });

function session() {
  const ws = new WebSocket(`${base.replace('http', 'ws')}/ws`, { origin: base });
  const approvals: Array<{ at: string; tool: string; reason: string; granted: boolean }> = []; const messages: any[] = [];
  const ready = new Promise<void>((resolve, reject) => { ws.on('error', reject); ws.on('message', (raw) => {
    const m = JSON.parse(raw.toString()); messages.push(m);
    if (m.type === 'init') resolve();
    if (m.type === 'approval_request') { approvals.push({ at: new Date().toISOString(), tool: m.data.tool, reason: m.data.reason, granted: true }); ws.send(JSON.stringify({ type: 'approval_response', id: m.data.id, approved: true })); }
  }); });
  const finished = (id: string, ms: number) => new Promise<any>((resolve, reject) => {
    const t0 = Date.now();
    const tick = () => { const hit = messages.find((m) => m.type === 'convoy_update' && m.data.id === id && ['COMPLETED', 'PARTIAL', 'FAILED'].includes(m.data.state)); if (hit) return resolve(hit.data); if (Date.now() - t0 > ms) return reject(new Error(`convoy ${id} did not finish in ${ms} ms`)); setTimeout(tick, 200); };
    tick();
  });
  return { ws, ready, approvals, messages, finished, send: (m: unknown) => ws.send(JSON.stringify(m)), close: () => ws.close() };
}

async function lastPr(model: string, timeoutMs: number) {
  const s = session(); await s.ready;
  const t0 = Date.now();
  const planned = (await post('/api/convoys/plan', { goal: 'What is the last PR?', model })).body.convoy;
  const submitted = (await post(`/api/convoys/${planned.id}/submit`)).body.convoy;
  s.send({ type: 'convoy_approve', id: planned.id });
  await s.finished(planned.id, timeoutMs);
  const c = (await get(`/api/convoys/${planned.id}`)).convoy;
  s.close();
  const w = c.workers[0];
  const tool = c.runs[0]?.steps?.find((x: any) => x.kind === 'tool');
  console.log(`${c.state.padEnd(9)} ${model.padEnd(13)} ${Date.now() - t0}ms tools=${c.tool_calls} tokens=${c.tokens} $${c.cost_usd} grounding=${c.grounding?.status ?? 'n/a'} workers=${c.workers.map((x: any) => x.id).join('+')}\n    answer: ${c.final_answer ?? c.error ?? '(none)'}`);
  return { model, convoy_id: c.id, state: c.state, outcome: c.outcome, plan_state: planned.state, submitted_state: submitted.state, wall_ms: Date.now() - t0, run_ms: c.finished_at - c.started_at, worker: { id: w.id, model: w.model, status: w.status, failure: w.failure }, workers: c.workers.map((x: any) => ({ id: x.id, model: x.model, status: x.status, grounding: x.grounding?.status, cost_usd: x.cost_usd, tool_calls: x.tool_calls, tokens: x.tokens, duration_ms: x.duration_ms })),
    tool_or_recipe: tool ? { name: tool.name, args: tool.args, ok: tool.ok, latency_ms: tool.latency_ms, approval: tool.approval } : null, tool_calls: c.tool_calls, tokens: c.tokens, cost_usd: c.cost_usd, final_answer: c.final_answer ?? null, grounding: c.grounding ?? null, error: c.error ?? null,
    evidence: c.evidence, approvals_prompted: s.approvals, approval_record: { state: c.approval.state, decided_by: c.approval.decided_by, policy: c.approval.snapshot.policy.decision, risk: c.approval.snapshot.risk }, chain: c.chain, events: c.events.map((e: any) => ({ seq: e.seq, state: e.state, by: e.by, note: e.note })) };
}

async function governed() {
  const goal = 'Write a file notes.md containing exactly one sentence that says what a convoy is in this project';
  const before = await counters();
  const watcher = session(); await watcher.ready;
  const wsListBefore = fs.existsSync(path.join(tmp, 'ws')) ? fs.readdirSync(path.join(tmp, 'ws')).length : 0;
  // 1. DRY RUN
  const planned = (await post('/api/convoys/plan', { goal, model: 'mercury-2' })).body.convoy;
  await sleep(1500);
  const afterPlan = await counters();
  const dry = { convoy_id: planned.id, state: planned.state, mode: planned.mode, plan_only: planned.plan.plan_only, side_effects: planned.plan.side_effects, executable: planned.plan.executable, blocked: planned.plan.blocked_reasons,
    added_by_mayor: planned.plan.added_by_mayor, workers: planned.plan.workers.map((w: any) => ({ id: w.id, model: w.model, tools: w.tools, permission: w.permission, wave: w.wave, depends_on: w.depends_on, estimated_cost_usd: w.estimated_cost_usd, cost_basis: w.cost_basis })), waves: planned.plan.waves, budget: planned.plan.budget, budget_use: planned.plan.budget_use, expected_convoy: planned.plan.expected_convoy,
    policy: { decision: planned.policy.decision, risk: planned.policy.risk, rules: planned.policy.rules.map((r: any) => r.id) },
    nothing_ran: { runs_before: before.runs, runs_after: afterPlan.runs, tool_approvals_asked: watcher.approvals.length, convoy_updates_seen: watcher.messages.filter((m) => m.type === 'convoy_update').length, workspaces_before: wsListBefore, workspaces_after: fs.existsSync(path.join(tmp, 'ws')) ? fs.readdirSync(path.join(tmp, 'ws')).length : 0 } };
  console.log(`DRY RUN   state=${planned.state} workers=${planned.plan.workers.map((w: any) => w.id).join('+')} executable=${planned.plan.executable} runs ${before.runs}->${afterPlan.runs}`);
  if (!planned.plan.executable) return { goal, dry_run: dry, stopped: 'plan not executable', blocked: planned.plan.blocked_reasons };
  // 2. QUEUED APPROVAL
  await post(`/api/convoys/${planned.id}/submit`);
  await sleep(2000);
  const pending = (await get(`/api/convoys/${planned.id}`)).convoy;
  const queued = { state: pending.state, approval: { state: pending.approval.state, convoy_id: pending.approval.convoy_id, expires_at: pending.approval.expires_at, snapshot_goal: pending.approval.snapshot.goal, snapshot_workers: pending.approval.snapshot.workers.map((w: any) => w.id), snapshot_budget: pending.approval.snapshot.worker_budget, snapshot_policy: pending.approval.snapshot.policy.decision, snapshot_risk: pending.approval.snapshot.risk },
    blocked_while_pending: { runs: (await counters()).runs, workers_status: pending.workers.map((w: any) => w.status), run_ids: pending.run_ids } };
  console.log(`QUEUED    state=${pending.state} approval=${pending.approval.state} runs=${(await counters()).runs}`);
  // 3. APPROVE + LIVE
  const t0 = Date.now();
  watcher.send({ type: 'convoy_approve', id: planned.id });
  const end = await watcher.finished(planned.id, 600_000).catch((e) => ({ error: String(e) }));
  const c = (await get(`/api/convoys/${planned.id}`)).convoy;
  const live = { state: c.state, outcome: c.outcome, mode: c.mode, wall_ms: Date.now() - t0, run_ms: c.finished_at && c.started_at ? c.finished_at - c.started_at : null, workers: c.workers.map((w: any) => ({ id: w.id, model: w.model, status: w.status, run_id: w.run_id, cost_usd: w.cost_usd, tool_calls: w.tool_calls, tokens: w.tokens, duration_ms: w.duration_ms, failure: w.failure, answer: w.answer })),
    totals: { cost_usd: c.cost_usd, tool_calls: c.tool_calls, tokens: c.tokens, worker_duration_ms: c.worker_duration_ms }, child_runs: c.runs.map((r: any) => ({ id: r.id, jobId: r.jobId, model: r.model, status: r.status, cost_usd: r.cost_usd, steps: r.steps.length, tools: r.steps.filter((x: any) => x.kind === 'tool').map((x: any) => ({ name: x.name, ok: x.ok, args: x.args, approval: x.approval, latency_ms: x.latency_ms })) })),
    top_level_run_rows_for_children: (await get('/api/runs')).runs.filter((r: any) => r.jobId === c.id).length, convoy_rows: (await get('/api/convoys')).convoys.filter((x: any) => x.id === c.id).length, final_answer: c.final_answer ?? null, error: c.error ?? null, chain: c.chain, events: c.events.map((e: any) => ({ seq: e.seq, state: e.state, by: e.by, note: e.note })), tool_approvals_granted_by_script: watcher.approvals, finished_update: end };
  console.log(`LIVE      state=${c.state} outcome=${c.outcome} workers=${c.workers.map((w: any) => `${w.id}:${w.status}`).join(' ')} cost=$${c.cost_usd} tools=${c.tool_calls}${c.error ? ` error=${c.error}` : ''}`);
  watcher.close();
  return { goal, dry_run: dry, queued_approval: queued, live };
}

async function main() {
  for (let i = 0; i < 100; i++) { try { if ((await fetch(`${base}/api/health`)).ok) break; } catch { /* starting */ } await sleep(150); }
  const out: any = fs.existsSync(OUT) ? JSON.parse(fs.readFileSync(OUT, 'utf8')) : { last_pr: {} };
  out.generated_at = new Date().toISOString();
  out.setup = { repo: 'Kudbee-Studio/think-box-ai', github: 'real api.github.com (unauthenticated)', ollama: 'real local Ollama', mercury: 'real Inception mercury-2', spend_cap_usd: Number(CAP), approvals: 'granted by the script as a stand-in for the human reviewer; every grant is recorded' };
  for (const [name, model, ms] of [['qwen', 'qwen2.5:3b', 300_000], ['gemma', 'gemma3:4b', 900_000], ['mercury', 'mercury-2', 180_000]] as const) {
    if (only.length && !only.includes(name)) continue;
    out.last_pr[name] = await lastPr(model, ms).catch((e) => ({ model, error: String(e) }));
    fs.mkdirSync(path.dirname(OUT), { recursive: true }); fs.writeFileSync(OUT, `${JSON.stringify(out, null, 2)}\n`);
  }
  if (!only.length || only.includes('governed')) { out.governed = await governed().catch((e) => ({ error: String(e) })); fs.writeFileSync(OUT, `${JSON.stringify(out, null, 2)}\n`); }
  process.exit(0);
}
main().catch((e) => { console.error(e); process.exit(2); });
