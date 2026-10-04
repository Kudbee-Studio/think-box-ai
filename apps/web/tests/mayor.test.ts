// Mayor planner + policy: the plan is built without running anything, the worker budget is enforced, and the policy always needs a human.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { evaluatePolicy, normalizeBudget, planConvoy, DEFAULT_BUDGET, type PlanInput } from '../mayor.ts';

const TOOLS = ['list_files', 'read_file', 'write_file', 'fetch_url', 'live_lookup', 'read_rss', 'recall', 'remember', 'algorand', 'medication'];
const input = (goal: string, o: Partial<PlanInput> = {}): PlanInput => ({
  goal, lookupModel: 'gemma3:4b', agentModel: 'mercury-2', isLocalModel: (m) => !m.startsWith('mercury'), availableTools: TOOLS, now: 1_000,
  costOf: (m) => (m === 'mercury-2' ? { usd: 0.004, basis: 'average of 1 measured mercury-2 run' } : m ? { usd: 0, basis: 'local model, no API cost' } : { usd: null, basis: 'no model' }), ...o,
});
const plan = (goal: string, o: Partial<PlanInput> = {}) => { const r = planConvoy(input(goal, o)); assert.ok(r.ok, JSON.stringify(r)); return (r as any).plan; };

describe('normalizeBudget', () => {
  it('defaults, accepts partial budgets, and refuses nonsense', () => {
    assert.deepEqual(normalizeBudget(undefined), { ok: true, budget: { ...DEFAULT_BUDGET } });
    assert.deepEqual(normalizeBudget({ max_workers: 2 }), { ok: true, budget: { ...DEFAULT_BUDGET, max_workers: 2 } });
    for (const bad of ['x', [], { max_workers: 0 }, { max_workers: 99 }, { max_workers: 1.5 }, { max_cost_usd: -1 }, { max_cost_usd: Infinity }, { max_cost_usd: '1' }, { surprise: 1 }, { max_tool_calls: 1000 }]) {
      assert.equal(normalizeBudget(bad).ok, false, JSON.stringify(bad));
    }
  });
});

describe('planConvoy: a live-data goal', () => {
  it('is one read-only lookup worker on the chosen model, with the escalation named and everything measurable shown', () => {
    const p = plan('What is the last PR?');
    assert.equal(p.plan_only, true);
    assert.equal(p.side_effects, 'none');
    assert.deepEqual(p.workers.map((w: any) => [w.id, w.kind, w.model, w.tools, w.permission, w.wave]), [['lookup-1', 'lookup', 'gemma3:4b', ['live_lookup'], 'read_only', 1]]);
    assert.deepEqual(p.waves, [['lookup-1']]);
    assert.deepEqual(p.escalation && p.escalation.model, 'mercury-2');
    assert.equal(p.budget_use.workers, 1);
    assert.equal(p.budget_use.worst_case_workers, 2, 'the possible escalation counts against the budget');
    assert.equal(p.budget_use.estimated_cost_usd, 0);
    assert.equal(p.budget_use.worst_case_cost_usd, 0.004);
    assert.deepEqual(p.expected_convoy, { dashboard_rows: 1, children: 1, waves: 1 });
    assert.equal(p.executable, true);
    assert.deepEqual(p.blocked_reasons, []);
  });
  it('has no escalation when Mercury is the worker, or when no agent model exists', () => {
    assert.equal(plan('What is the last PR?', { lookupModel: 'mercury-2' }).escalation, null);
    assert.equal(plan('What is the last PR?', { agentModel: null }).escalation, null);
  });
  it('is not executable without a model', () => {
    const p = plan('What is the last PR?', { lookupModel: null });
    assert.equal(p.executable, false);
    assert.match(p.blocked_reasons.join(), /no model is available/);
  });
  it('is deterministic: the same input gives the same plan', () => {
    assert.deepEqual(plan('What is the last PR?'), plan('What is the last PR?'));
  });
});

describe('planConvoy: specialist work', () => {
  const goal = 'Research the latest release notes and write a short summary report';
  it('selects the specialists the Director would, orders them by handoff, and shows tools per worker', () => {
    const p = plan(goal);
    const ids = p.workers.map((w: any) => w.id);
    assert.ok(ids.includes('researcher'));
    assert.ok(p.workers.every((w: any) => w.kind === 'specialist' && w.model === 'mercury-2'));
    const researcher = p.workers.find((w: any) => w.id === 'researcher');
    assert.deepEqual(researcher.tools, ['fetch_url', 'read_rss', 'recall']);
    assert.equal(researcher.estimated_cost_usd, 0.004);
    assert.equal(p.waves.flat().length, p.workers.length);
    assert.equal(p.expected_convoy.dashboard_rows, 1);
    assert.equal(p.expected_convoy.children, p.workers.length);
  });
  it('enforces the worker budget: too many workers makes the plan not executable, with the numbers', () => {
    const p = plan(goal, { budget: { max_workers: 1 } });
    assert.equal(p.executable, false);
    assert.match(p.blocked_reasons.join(), /worker budget exceeded: \d+ worker\(s\) possible .* budget allows 1/);
  });
  it('enforces the cost and tool-call budgets', () => {
    assert.match(plan(goal, { budget: { max_workers: 12, max_cost_usd: 0.001 } }).blocked_reasons.join(), /cost budget exceeded/);
    assert.match(plan(goal, { budget: { max_workers: 12, max_tool_calls: 1 } }).blocked_reasons.join(), /tool-call budget exceeded/);
  });
  it('reports unmeasured cost as unmeasured, never a guess', () => {
    const p = plan(goal, { costOf: () => ({ usd: null, basis: 'no measured runs on this model yet' }) });
    assert.equal(p.budget_use.estimated_cost_usd, null);
    assert.equal(p.workers[0].estimated_cost_usd, null);
    assert.match(p.workers[0].cost_basis, /no measured runs/);
    assert.ok(evaluatePolicy(p).rules.some((r) => r.id === 'cost-unmeasured'));
  });
  it('blocks a worker whose tool this runtime does not have', () => {
    const p = plan('run the test suite and verify tests', { availableTools: TOOLS });
    assert.equal(p.executable, false);
    assert.match(p.blocked_reasons.join(), /needs tool\(s\) this runtime does not have: exec/);
  });
  it('blocks a goal no specialist matches, and a missing worker-agent model', () => {
    assert.equal(plan('hello there').executable, false);
    assert.match(plan(goal, { agentModel: null }).blocked_reasons.join(), /no worker-agent model/);
  });
  it('rejects an empty or oversized goal and a bad budget', () => {
    assert.equal(planConvoy(input('  ')).ok, false);
    assert.equal(planConvoy(input('x'.repeat(2001))).ok, false);
    assert.equal(planConvoy(input('What is the last PR?', { budget: { max_workers: 0 } })).ok, false);
  });
});

describe('evaluatePolicy', () => {
  it('always requires a human, lists network use, and rates a read-only lookup low risk', () => {
    const pol = evaluatePolicy(plan('What is the last PR?'));
    assert.equal(pol.decision, 'requires_approval');
    assert.equal(pol.risk, 'low');
    assert.ok(pol.rules.some((r) => r.id === 'human-approval' && r.effect === 'require_approval' && /can never approve/.test(r.reason)));
    assert.ok(pol.rules.some((r) => r.id === 'network-read' && r.workers?.includes('lookup-1')));
    assert.ok(pol.restrictions.some((r) => /first network access per host/.test(r)));
  });
  it('rates a plan with file-writing workers medium risk and names them', () => {
    const pol = evaluatePolicy(plan('Research the latest release notes and write a short summary report'));
    assert.equal(pol.risk, 'medium');
    assert.ok(pol.rules.some((r) => r.id === 'workspace-write' && r.workers && r.workers.length));
  });
  it('denies a plan that is not executable', () => {
    const pol = evaluatePolicy(plan('run the test suite and verify tests'));
    assert.equal(pol.decision, 'denied');
    assert.ok(pol.rules.some((r) => r.id === 'plan-not-executable'));
  });
});

describe('planning is side-effect free by construction', () => {
  it('mayor.ts imports no filesystem, network, process, server, model or tool-runtime code', () => {
    const src = fs.readFileSync(new URL('../mayor.ts', import.meta.url), 'utf8');
    const imports = [...src.matchAll(/^import .* from '([^']+)'/gm)].map((m) => m[1]!);
    assert.deepEqual(imports.sort(), ['./local-recipes.ts', './specialist-contracts.ts', './specialist-executor.ts']);
    for (const banned of [/\bfetch\(/, /\bfs\./, /child_process/, /node:http/, /writeFile/, /process\.env/, /Date\.now\(/, /spawn/]) assert.doesNotMatch(src, banned, String(banned));
  });
});
