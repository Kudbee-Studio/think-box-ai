// The convoy runner with fake workers: runtime budget enforcement, specialist result mapping, failures that stay failures, abort.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { executeConvoy, summarize, type RunnerDeps } from '../convoy-runner.ts';
import { ConvoyStore } from '../convoy.ts';
import { evaluatePolicy, planConvoy } from '../mayor.ts';
import { RunStore, type RunRecord } from '../runs.ts';
import type { OllamaChatTurn } from '../ollama-client.ts';
import { lookupHooks } from './helpers/lookup-hooks.ts';
import fs0 from 'node:fs';
import path0 from 'node:path';

const turn = (o: Partial<OllamaChatTurn>): OllamaChatTurn => ({ content: '', tool_calls: [], prompt_tokens: 10, completion_tokens: 5, latency_ms: 1, ...o });

function setup(goal: string, tweak: (plan: any) => void = () => {}, budget?: unknown) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'runner-'));
  const store = new ConvoyStore(path.join(dir, 'c.json'));
  const runStore = new RunStore(path.join(dir, 'r.json'));
  const planned = planConvoy({ goal, budget, lookupModel: 'gemma3:4b', agentModel: 'mercury-2', isLocalModel: (m) => !m.startsWith('mercury'), availableTools: ['live_lookup', 'repo_search', 'repo_read', 'fetch_url', 'read_rss', 'recall', 'read_file', 'write_file', 'remember'], now: 1, costOf: () => ({ usd: 0, basis: 'test' }) });
  assert.ok(planned.ok);
  const plan = (planned as any).plan;
  tweak(plan);
  const c = store.create(goal, plan, evaluatePolicy(plan));
  store.submit(c.id); store.decide(c.id, 'approve', 'human');
  const calls = { agent: 0, specialists: 0 };
  const broadcasts: any[] = [];
  const deps = (over: Partial<RunnerDeps> = {}): RunnerDeps => ({
    store, runStore, repo: 'Acme/widgets', isLocalModel: (m) => !m.startsWith('mercury'),
    chat: { modelCapabilities: async () => [], chatOnce: async () => turn({ content: JSON.stringify({ action: 'answer', answer: 'no lookup done' }) }) },
    newChildRun: (g, runId, model, convoyId, workerId) => runStore.create({ id: runId, session_id: 's', goal: g, model, provider: 'ollama', status: 'running', started_at: Date.now(), steps: [], current_step: 0, tool_calls: 0, prompt_tokens: 0, completion_tokens: 0, cost_usd: 0, approvals: { approved: 0, denied: 0 }, files: [], jobId: convoyId, specialistId: workerId } as RunRecord),
    hooksFor: (_r, signal, allowedTools) => ({ ...lookupHooks({ signal }).hooks, allowedTools }),
    runAgent: async () => { calls.agent += 1; return { success: true, result: 'agent answer', steps: 1, tool_calls: 0, prompt_tokens: 1, completion_tokens: 1, tokens: 2, cost_usd: 0.001 }; },
    runSpecialists: async () => { calls.specialists += 1; return { status: 'FAILED', specialistsExecuted: [] }; },
    broadcast: (m) => broadcasts.push(m), signal: new AbortController().signal, ...over,
  });
  return { store, runStore, c, deps, calls, broadcasts };
}

describe('runtime budget while a lookup convoy runs', () => {
  const failingLocal = { chat: { modelCapabilities: async () => [], chatOnce: async () => turn({ content: 'not json' }) } };
  it('refuses the escalation when the cost budget is already spent, names why, and never calls the worker agent', async () => {
    const t = setup('What is the last PR?', (p) => { p.budget.max_cost_usd = 0; });
    const c = await executeConvoy(t.deps(failingLocal), t.c.id);
    assert.equal(t.calls.agent, 0);
    assert.equal(c.workers.length, 1);
    assert.equal(c.workers[0]!.failure?.kind, 'malformed_tool_request', 'the original failure is kept');
    assert.equal(c.state, 'FAILED');
    assert.equal(c.outcome, 'failed');
  });
  it('refuses the escalation when there is no worker budget left', async () => {
    const t = setup('What is the last PR?', (p) => { p.budget.max_workers = 1; });
    const c = await executeConvoy(t.deps(failingLocal), t.c.id);
    assert.equal(t.calls.agent, 0);
    assert.equal(c.workers.length, 1);
    assert.equal(c.state, 'FAILED');
  });
  it('does not escalate after a denied approval or an abort', async () => {
    const denied = setup('What is the last PR?');
    const dc = await executeConvoy(denied.deps({ chat: { modelCapabilities: async () => [], chatOnce: async () => turn({ content: JSON.stringify({ action: 'call', recipe: 'latest_pr' }) }) }, hooksFor: (_r, signal, allowedTools) => ({ ...lookupHooks({ signal }, false).hooks, allowedTools }) }), denied.c.id);
    assert.equal(dc.workers[0]!.failure?.kind, 'tool_denied');
    assert.equal(denied.calls.agent, 0);
    const ac = new AbortController(); ac.abort();
    const aborted = setup('What is the last PR?');
    const c = await executeConvoy(aborted.deps({ ...failingLocal, signal: ac.signal }), aborted.c.id);
    assert.equal(aborted.calls.agent, 0);
    assert.equal(c.state, 'FAILED');
  });
  it('a worker agent that throws is a failed worker with its message, never a success', async () => {
    const t = setup('What is the last PR?', (p) => { p.workers[0].model = 'mercury-2'; p.escalation = null; });
    const c = await executeConvoy(t.deps({ runAgent: async () => { throw new Error('Inception API HTTP 500'); } }), t.c.id);
    assert.equal(c.state, 'FAILED');
    assert.deepEqual(c.workers[0]!.failure, { kind: 'error', message: 'Inception API HTTP 500' });
    assert.match(c.error!, /error: Inception API HTTP 500/);
  });
  it('a worker agent that answers with no tool call (so no evidence) fails as no_tool_call', async () => {
    const t = setup('What is the last PR?', (p) => { p.workers[0].model = 'mercury-2'; p.escalation = null; });
    const c = await executeConvoy(t.deps(), t.c.id);
    assert.equal(c.state, 'FAILED');
    assert.equal(c.workers[0]!.failure?.kind, 'no_tool_call');
    assert.equal(c.final_answer, undefined);
  });
});

describe('specialist convoys map the existing specialist job result without hiding failures', () => {
  const goal = 'Research the latest release notes and write a short summary report';
  const exec = (id: string, status: 'completed' | 'failed', usage = { costUsd: 0.002, tokens: 500, durationMs: 800 }, extra: Record<string, unknown> = {}) => ({ specialistId: id, status, runId: `run-${id}`, resourceUsage: usage, events: [{ kind: 'tool' }, { kind: 'tool' }, { kind: 'model' }], output: `${id} output`, ...extra });
  const ids = (t: ReturnType<typeof setup>) => t.c.workers.map((w) => w.id);

  it('success: every worker completed and the proof was accepted; costs and tool calls are summed from the children', async () => {
    const t = setup(goal, undefined, { max_workers: 12, max_cost_usd: 1, max_tool_calls: 100 });
    const c = await executeConvoy(t.deps({ runSpecialists: async (_g, id, specialists) => { assert.equal(id, t.c.id, 'the convoy id is the job id'); assert.deepEqual(specialists, ids(t), 'exactly the approved plan\'s workers run'); return { status: 'COMPLETED', specialistsExecuted: ids(t).map((i) => exec(i, 'completed')) }; } }), t.c.id);
    assert.equal(c.state, 'COMPLETED');
    assert.equal(c.outcome, 'success');
    assert.equal(c.cost_usd, Math.round(0.002 * ids(t).length * 1e6) / 1e6);
    assert.equal(c.tool_calls, 2 * ids(t).length);
    assert.equal(c.tokens, 500 * ids(t).length);
    assert.deepEqual(c.run_ids, ids(t).map((i) => `run-${i}`));
    assert.ok(c.workers.every((w) => w.status === 'completed' && w.run_id));
  });
  it('partial: one failed worker keeps its failure, the others keep their results, the convoy is PARTIAL not COMPLETED', async () => {
    const t = setup(goal, undefined, { max_workers: 12, max_cost_usd: 1, max_tool_calls: 100 });
    const all = ids(t);
    const c = await executeConvoy(t.deps({ runSpecialists: async () => ({ status: 'FAILED', error: 'validator refused', specialistsExecuted: all.map((i, n) => (n === 0 ? exec(i, 'failed', undefined, { failure: 'tool exploded', output: undefined }) : exec(i, 'completed'))) }) }), t.c.id);
    assert.equal(c.state, 'PARTIAL');
    assert.equal(c.outcome, 'partial');
    assert.equal(c.workers[0]!.status, 'failed');
    assert.deepEqual(c.workers[0]!.failure, { kind: 'specialist_failed', message: 'tool exploded' });
    assert.ok(c.workers.slice(1).every((w) => w.status === 'completed'));
    assert.equal(c.final_answer, undefined, 'no combined answer is claimed from a failed job');
    assert.match(c.error!, /validator refused/);
  });
  it('a job whose proof is refused is not a success even if every worker finished', async () => {
    const t = setup(goal, undefined, { max_workers: 12, max_cost_usd: 1, max_tool_calls: 100 });
    const c = await executeConvoy(t.deps({ runSpecialists: async () => ({ status: 'FAILED', validation: { reason: 'evidence missing' }, specialistsExecuted: ids(t).map((i) => exec(i, 'completed')) }) }), t.c.id);
    assert.equal(c.state, 'PARTIAL');
    assert.match(c.error!, /evidence missing/);
  });
  it('failed: nothing completed, or the job was blocked and ran nothing (workers are skipped, not faked)', async () => {
    const t = setup(goal, undefined, { max_workers: 12, max_cost_usd: 1, max_tool_calls: 100 });
    const c = await executeConvoy(t.deps({ runSpecialists: async () => ({ status: 'BLOCKED', error: 'composition invalid', specialistsExecuted: [] }) }), t.c.id);
    assert.equal(c.state, 'FAILED');
    assert.ok(c.workers.every((w) => w.status === 'skipped' && w.failure?.kind === 'not_run'));
    assert.match(c.error!, /composition invalid/);
  });
  it('completed but over the cost budget is PARTIAL with the overspend named', async () => {
    const t = setup(goal, undefined, { max_workers: 12, max_cost_usd: 0.001, max_tool_calls: 100 });
    const c = await executeConvoy(t.deps({ runSpecialists: async () => ({ status: 'COMPLETED', specialistsExecuted: ids(t).map((i) => exec(i, 'completed')) }) }), t.c.id);
    assert.equal(c.state, 'PARTIAL');
    assert.equal(c.error, 'cost budget exceeded');
  });
  it('a crash in the specialist job fails the convoy with the message and fails every worker', async () => {
    const t = setup(goal, undefined, { max_workers: 12, max_cost_usd: 1, max_tool_calls: 100 });
    const c = await executeConvoy(t.deps({ runSpecialists: async () => { throw new Error('disk full'); } }), t.c.id);
    assert.equal(c.state, 'FAILED');
    assert.equal(c.error, 'disk full');
    assert.ok(c.workers.every((w) => w.status === 'failed'));
  });
});

describe('summarize and live updates', () => {
  it('broadcasts convoy_update at start and end and summarizes one row with state, cost and grounding', async () => {
    const t = setup('What is the last PR?', (p) => { p.workers[0].model = 'mercury-2'; p.escalation = null; });
    const c = await executeConvoy(t.deps(), t.c.id);
    const updates = t.broadcasts.filter((b) => b.type === 'convoy_update').map((b) => b.data.state);
    assert.equal(updates[0], 'RUNNING');
    assert.equal(updates.at(-1), 'FAILED');
    const row = summarize(c) as any;
    assert.deepEqual({ id: row.id, state: row.state, outcome: row.outcome, risk: row.risk, approval: row.approval }, { id: c.id, state: 'FAILED', outcome: 'failed', risk: 'low', approval: 'APPROVED' });
    assert.ok(row.duration_ms >= 0);
  });
});

describe('repository investigation convoys', () => {
  function repoSetup(model = 'qwen2.5:3b') {
    const t = setup('Find one function that has no test', (p) => { p.workers = [{ ...p.workers[0], id: 'repo-1', kind: 'repo', name: 'Repository investigation (read-only)', model, tools: ['repo_search', 'repo_read'], permission: 'read_only' }]; p.escalation = null; p.think_mode = 'observe'; });
    return t;
  }
  const root = fs0.mkdtempSync(path0.join(os.tmpdir(), 'runner-repo-'));
  fs0.mkdirSync(path0.join(root, 'src'), { recursive: true });
  fs0.mkdirSync(path0.join(root, 'tests'), { recursive: true });
  fs0.writeFileSync(path0.join(root, 'src/alpha.ts'), 'export function alpha() {\n  return 1;\n}\nexport function orphan() {\n  return 7;\n}\n');
  fs0.writeFileSync(path0.join(root, 'tests/alpha.test.ts'), 'alpha();\n');
  const call = (name: string, args: object) => turn({ tool_calls: [{ function: { name, arguments: args } }] });
  const script = (turns: OllamaChatTurn[]) => ({ modelCapabilities: async () => ['tools'], chatOnce: async () => turns.shift() ?? turn({ error: 'script exhausted' }) });
  const good = { found: true, file: 'src/alpha.ts', line: 4, quote: 'export function orphan()', claim: 'The function `orphan` has no tests.', absence_search: { query: 'orphan', path: 'tests' } };
  const run = (finish: object, mutate?: () => void) => {
    process.env.KUDBEE_REPO_ROOT = root;
    const t = repoSetup();
    const chat = script([call('repo_read', { path: 'src/alpha.ts', start: 1, end: 6 }), call('repo_search', { query: 'orphan', path: 'tests' }), call('report_finding', finish), call('report_finding', finish)]);
    return { t, promise: executeConvoy(t.deps({ chat }), t.c.id).finally(() => { delete process.env.KUDBEE_REPO_ROOT; mutate?.(); }) };
  };
  it('a grounded finding that is also on disk ends COMPLETED with the evidence, the finding and the disk check recorded', async () => {
    const { t, promise } = run(good);
    const c = await promise;
    assert.equal(c.state, 'COMPLETED');
    assert.equal(c.outcome, 'success');
    assert.equal(c.finding?.file, 'src/alpha.ts');
    assert.deepEqual(c.finding_check, { disk_verified: true });
    assert.deepEqual(c.repo_evidence.map((e) => e.tool), ['repo_read', 'repo_search']);
    assert.equal(c.grounding?.status, 'GROUNDED');
    assert.equal(c.final_answer, 'src/alpha.ts:4 \u2014 The function `orphan` has no tests.');
    assert.equal(c.cost_usd, 0);
    assert.equal(c.tool_calls, 2);
    assert.equal(c.workers[0]!.status, 'completed');
    assert.equal(t.calls.agent, 0, 'no paid model was involved');
    assert.equal(t.runStore.get(c.run_ids[0]!)?.jobId, c.id);
  });
  it('a fabricated line fails grounding: GROUNDING FAILED, no final answer, the evidence is kept', async () => {
    const c = await run({ ...good, line: 5 }).promise;
    assert.equal(c.state, 'FAILED');
    assert.equal(c.outcome, 'grounding_failed');
    assert.equal(c.final_answer, undefined);
    assert.equal(c.repo_evidence.length, 2);
    assert.ok(c.grounding!.unsupported.length > 0);
    assert.equal(c.finding_check, undefined, 'the disk check only runs for a grounded finding');
  });
  it('a quote that no longer matches the disk (the file changed after the worker read it) is not a success', async () => {
    process.env.KUDBEE_REPO_ROOT = root;
    const t = repoSetup();
    let read = 0;
    const turns = [call('repo_read', { path: 'src/alpha.ts', start: 1, end: 6 }), call('repo_search', { query: 'orphan', path: 'tests' }), call('report_finding', good)];
    const chat = { modelCapabilities: async () => ['tools'], chatOnce: async () => { read += 1; if (read === 3) fs0.writeFileSync(path0.join(root, 'src/alpha.ts'), 'export function other() {\n  return 1;\n}\n'); return turns.shift() ?? turn({ error: 'exhausted' }); } };
    const c = await executeConvoy(t.deps({ chat }), t.c.id);
    fs0.writeFileSync(path0.join(root, 'src/alpha.ts'), 'export function alpha() {\n  return 1;\n}\nexport function orphan() {\n  return 7;\n}\n');
    delete process.env.KUDBEE_REPO_ROOT;
    assert.equal(c.outcome, 'grounding_failed');
    assert.equal(c.finding_check?.disk_verified, false);
    assert.match(c.error!, /disk re-check failed/);
    assert.equal(c.final_answer, undefined);
  });
  it('"nothing worth reporting" after looking completes with that said, and a model that never looks fails', async () => {
    const none = await run({ found: false, reason: 'every function is exercised' }).promise;
    assert.equal(none.outcome, 'success');
    assert.equal(none.final_answer, 'No finding: every function is exercised');
    process.env.KUDBEE_REPO_ROOT = root;
    const t = repoSetup();
    const c = await executeConvoy(t.deps({ chat: script([call('report_finding', good)]) }), t.c.id);
    delete process.env.KUDBEE_REPO_ROOT;
    assert.equal(c.state, 'FAILED');
    assert.equal(c.workers[0]!.failure?.kind, 'no_tool_call');
  });
});
