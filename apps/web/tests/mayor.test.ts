// Mayor planner + policy: the plan is built without running anything, the worker budget is enforced, and the policy always needs a human.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { evaluatePolicy, normalizeBudget, planConvoy, DEFAULT_BUDGET, type PlanInput } from '../mayor.ts';
import { matchRepoGoal } from '../local-recipes.ts';

const TOOLS = ['list_files', 'read_file', 'write_file', 'fetch_url', 'live_lookup', 'repo_search', 'repo_read', 'read_rss', 'recall', 'remember', 'algorand', 'medication'];
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
  it('adds the Validator the specialist proof needs, with the reason, when the Director did not select one', () => {
    const p = plan('Research the latest release notes and summarize them');
    assert.deepEqual(p.workers.map((w: any) => w.id).sort(), ['researcher', 'synthesizer', 'validator']);
    assert.equal(p.added_by_mayor.length, 1);
    assert.equal(p.added_by_mayor[0].id, 'validator');
    assert.match(p.added_by_mayor[0].reason, /independent verification/);
    const withBuilder = plan('Research the latest release notes and write a short summary report');
    assert.deepEqual(withBuilder.added_by_mayor, [], 'the Director already selected it');
  });
  it('warns when no worker writes an artifact (the proof needs something for the Validator to check) and not when one does', () => {
    assert.match(plan('Research the latest release notes and summarize them').warnings.join(), /No worker writes an artifact/);
    assert.deepEqual(plan('What is the last PR?').warnings, [], 'a lookup convoy has no proof step');
    assert.match(plan('Research the latest release notes and write a short summary report').warnings.join(), /Researcher is read-only/);
    assert.deepEqual(plan('Write a file notes.md with one sentence about convoys').warnings, [], 'builder + validator + security: the designed, checkable path');
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

describe('repository investigation plans (OBSERVE)', () => {
  const goal = 'Find one function in apps/web that has no test';
  it('matches investigation goals and nothing else: not GitHub questions, not change requests', () => {
    for (const g of [goal, 'Inspect the code for unused exports', 'Which files have a TODO?', 'audit the source for duplicated code', 'find untested modules']) assert.equal(matchRepoGoal(g), true, g);
    for (const g of ['What is the last PR?', 'did CI pass', 'fix the failing test', 'write a file notes.md', 'delete the unused functions', 'find the weather', 'hello', 'list the files in my workspace', 'show me what is in the workspace folder', 'read notes.md', '', 'find a function at https://x.io/a.ts', 'x'.repeat(700)]) assert.equal(matchRepoGoal(g), false, g);
  });
  it('is one read-only worker on a local model with the two repo tools, in OBSERVE mode, low risk, and one named escalation to the agent model', () => {
    const p = plan(goal, { lookupModel: 'qwen2.5:3b' });
    assert.equal(p.think_mode, 'observe');
    assert.deepEqual(p.workers.map((w: any) => [w.id, w.kind, w.model, w.tools, w.permission]), [['repo-1', 'repo', 'qwen2.5:3b', ['repo_search', 'repo_read'], 'read_only']]);
    assert.ok(p.escalation && /no finding where the goal expects one/.test(p.escalation.when), JSON.stringify(p.escalation));
    assert.equal(plan(goal, { lookupModel: 'qwen2.5:3b', agentModel: null }).escalation, null);
    assert.equal(p.executable, true);
    const pol = evaluatePolicy(p);
    assert.equal(pol.risk, 'low');
    assert.equal(pol.decision, 'requires_approval');
    assert.ok(pol.rules.some((r) => r.id === 'mode-observe' && /read-only/.test(r.reason)));
    assert.ok(pol.rules.some((r) => r.id === 'repo-read' && /\.env/.test(r.reason)));
    assert.ok(!pol.rules.some((r) => r.id === 'network-read'));
  });
  it('is not executable on Mercury in this version, without the repo tools, or without a model', () => {
    assert.match(plan(goal, { lookupModel: 'mercury-2' }).blocked_reasons.join(), /runs on local models in this version/);
    assert.match(plan(goal, { lookupModel: 'qwen2.5:3b', availableTools: ['live_lookup'] }).blocked_reasons.join(), /repository tools are not available/);
    assert.match(plan(goal, { lookupModel: null }).blocked_reasons.join(), /no model is available/);
  });
  it('gates modes: observe, learn and simulate plan, autonomous is refused until it exists, and an unknown mode is an error', () => {
    assert.equal(plan(goal, { lookupModel: 'qwen2.5:3b', mode: 'learn' }).executable, true);
    assert.match(evaluatePolicy(plan(goal, { lookupModel: 'qwen2.5:3b', mode: 'learn' })).rules.find((r) => r.id === 'mode-learn')!.reason, /never auto-accepted/);
    const p = plan(goal, { lookupModel: 'qwen2.5:3b', mode: 'autonomous' });
    assert.equal(p.executable, false);
    assert.match(p.blocked_reasons.join(), /AUTONOMOUS mode is not available yet/);
    assert.equal(evaluatePolicy(p).decision, 'denied');
    assert.equal(planConvoy(input(goal, { mode: 'yolo' as any })).ok, false);
  });
  it('a live GitHub question is still a lookup, and the default mode is observe', () => {
    assert.equal(plan('What is the last PR?').workers[0].kind, 'lookup');
    assert.equal(plan('What is the last PR?').think_mode, 'observe');
  });
});

describe('SIMULATE plans: propose a change, verify it in the sandbox (P3.40)', () => {
  const goal = 'Fix the typo in the greeting so the greeting test passes';
  const SIM_TOOLS = [...TOOLS, 'propose_change', 'run_checks'];
  const sim = (o: Partial<PlanInput> = {}) => plan(goal, { mode: 'simulate', availableTools: SIM_TOOLS, ...o });
  it('is a patch worker on the agent model, then a sandbox checks worker with no model, pinned to HEAD, executable, with no escalation', () => {
    const p = sim();
    assert.equal(p.think_mode, 'simulate'); assert.equal(p.executable, true); assert.deepEqual(p.blocked_reasons, []);
    assert.deepEqual(p.workers.map((w: any) => [w.id, w.kind, w.model, w.tools, w.permission, w.depends_on, w.wave]), [
      ['patch-1', 'patch', 'mercury-2', ['repo_search', 'repo_read', 'propose_change'], 'read_only', [], 1],
      ['checks-1', 'checks', null, ['run_checks'], 'sandbox_exec', ['patch-1'], 2],
    ]);
    assert.deepEqual(p.waves, [['patch-1'], ['checks-1']]);
    assert.deepEqual(p.simulation, { ref: 'HEAD', checks: ['lint', 'typecheck', 'tsc', 'test'], patch_local: false, max_rounds: 2 });
    assert.equal(p.escalation, null);
    assert.equal(p.workers[1].estimated_cost_usd, 0);
    assert.match(p.workers[0].cost_basis, /average of 1 measured mercury-2 run|no measured/);
    assert.ok(p.warnings.some((w: string) => /never applied to your working tree and nothing is pushed/.test(w)));
    assert.ok(p.warnings.some((w: string) => /asks for your approval again/.test(w)));
    assert.ok(p.warnings.some((w: string) => /not proof the change is right/.test(w)));
  });
  it('the plan carries no simulation block in any other mode, and the same input always gives the same plan', () => {
    assert.equal(plan(goal, { lookupModel: 'qwen2.5:3b' }).simulation, undefined);
    assert.deepEqual(sim(), sim());
  });
  it('policy: a human must approve, risk is medium, and the approver is told the source goes to the agent model and what the sandbox is', () => {
    const pol = evaluatePolicy(sim());
    assert.equal(pol.decision, 'requires_approval'); assert.equal(pol.risk, 'medium');
    const rule = (id: string) => pol.rules.find((r) => r.id === id)!;
    assert.match(rule('mode-simulate').reason, /never applied to your working tree and nothing is pushed or opened as a pull request/);
    assert.match(rule('source-leaves-machine').reason, /sent to that provider/); assert.deepEqual(rule('source-leaves-machine').workers, ['patch-1']);
    assert.match(rule('sandboxed-checks').reason, /no network, no home directory and no credentials.*asks for your approval again/); assert.deepEqual(rule('sandboxed-checks').workers, ['checks-1']);
    assert.equal(rule('sandboxed-checks').effect, 'require_approval');
    assert.ok(pol.restrictions.some((r) => /second approval that names the exact commit and patch/.test(r)));
    assert.ok(!pol.rules.some((r) => r.id === 'command-execution'), 'the sandbox is not "command execution"');
  });
  it('is not executable without the agent model, without the tools, or for a question or an investigation', () => {
    assert.match(sim({ agentModel: null }).blocked_reasons.join(), /needs the agent model \(Mercury\)/);
    assert.match(plan(goal, { mode: 'simulate', availableTools: TOOLS }).blocked_reasons.join(), /tools SIMULATE needs are not available.*propose_change, run_checks/);
    assert.match(plan(goal, { mode: 'simulate', availableTools: [...TOOLS, 'run_checks'] }).blocked_reasons.join(), /propose_change/);
    for (const q of ['What is the last PR?', 'Which pull requests are open?', 'Find one function in apps/web that has no test']) {
      const p = sim() && plan(q, { mode: 'simulate', availableTools: SIM_TOOLS }); assert.equal(p.executable, false, q); assert.match(p.blocked_reasons.join(), /reads like a question or an investigation/, q);
      assert.equal(evaluatePolicy(p).decision, 'denied');
    }
  });
  it('a local model the OPERATOR picked becomes the patch worker (the source stays on this machine, and the policy says so); no other routing ever does', () => {
    const local = sim({ lookupModel: 'qwen2.5:3b', routing: { source: 'operator', model: 'qwen2.5:3b', reason: 'chosen by the operator' } });
    assert.equal(local.executable, true); assert.equal(local.workers[0].model, 'qwen2.5:3b'); assert.equal(local.simulation.patch_local, true); assert.equal(local.workers[0].estimated_cost_usd, 0);
    const pol = evaluatePolicy(local); const ids = pol.rules.map((r) => r.id);
    assert.ok(ids.includes('source-stays-local')); assert.ok(!ids.includes('source-leaves-machine'));
    assert.match(pol.rules.find((r) => r.id === 'source-stays-local')!.reason, /local model \(qwen2\.5:3b\).*stay on this machine/); assert.deepEqual(pol.rules.find((r) => r.id === 'source-stays-local')!.workers, ['patch-1']);
    // the operator picking Mercury, the measured table or the default all leave Mercury as the patch worker and say the source goes to a cloud API
    for (const routing of [{ source: 'operator' as const, model: 'mercury-2', reason: 'x' }, { source: 'measured' as const, model: 'gemma3:4b', reason: 'x' }, { source: 'default' as const, model: 'qwen2.5:3b', reason: 'x' }, undefined]) {
      const p = sim({ lookupModel: routing?.model ?? 'gemma3:4b', routing }); assert.equal(p.workers[0].model, 'mercury-2', JSON.stringify(routing)); assert.equal(p.simulation.patch_local, false);
      assert.ok(evaluatePolicy(p).rules.some((r) => r.id === 'source-leaves-machine'));
    }
  });
  it('a local patch model needs no Mercury key: SIMULATE is executable with no agent model when the operator chose a local one', () => {
    const p = sim({ agentModel: null, lookupModel: 'gemma3:4b', routing: { source: 'operator', model: 'gemma3:4b', reason: 'x' } });
    assert.equal(p.executable, true, p.blocked_reasons.join()); assert.equal(p.workers[0].model, 'gemma3:4b');
    assert.match(sim({ agentModel: null }).blocked_reasons.join(), /needs the agent model \(Mercury\).*no local model was chosen/);
  });
  it('a change request that merely mentions a PR is plannable (the live P3.43 goal was blocked as "a question or an investigation")', () => {
    for (const g of ["Change the phrase '4 (the next PR, below)' to '4 (PR #381, below)' in the Status line of docs/scratch-runner-design.md. Change nothing else.", 'In docs/scratch-runner-design.md the Status line says slice 4 is the next PR. That PR is now merged as #381. Replace that phrase with PR #381.']) {
      const p = plan(g, { mode: 'simulate', availableTools: SIM_TOOLS }); assert.equal(p.executable, true, `${g}: ${p.blocked_reasons.join()}`); assert.deepEqual(p.workers.map((w: any) => w.id), ['patch-1', 'checks-1']);
    }
  });
  it('the worker budget still applies: one worker is not enough for two', () => {
    assert.match(sim({ budget: { max_workers: 1 } }).blocked_reasons.join(), /worker budget exceeded: 2 worker\(s\) possible/);
    assert.equal(sim({ budget: { max_workers: 2 } }).executable, true);
  });
});

describe('SIMULATE revision rounds in the plan (P3.41): the budget decides how many', () => {
  const SIM_TOOLS = [...TOOLS, 'propose_change', 'run_checks'];
  const sim = (budget?: unknown) => plan('Fix the typo in the greeting', { mode: 'simulate', availableTools: SIM_TOOLS, ...(budget ? { budget } : {}) });
  it('the default budget (4 workers, 20 tool calls) allows exactly two rounds, says so, and counts the worst case', () => {
    const p = sim();
    assert.equal(p.simulation.max_rounds, 2); assert.equal(p.budget_use.worst_case_workers, 4);
    assert.ok(p.warnings.some((w: string) => /up to 2 round\(s\) in all.*asks for your approval again, saying which round it is/.test(w)));
    const rule = evaluatePolicy(p).rules.find((r) => r.id === 'revision-rounds')!;
    assert.match(rule.reason, /failure output \(data from the repository's own commands, clipped\).*up to 2 round\(s\).*approval again.*budgets are re-checked before each revision/); assert.deepEqual(rule.workers, ['patch-1']);
  });
  it('rounds follow the worker and tool-call budgets and never exceed three', () => {
    const rounds = (b: unknown) => sim(b).simulation.max_rounds;
    assert.equal(rounds({ max_workers: 2 }), 1); assert.equal(rounds({ max_workers: 3 }), 1); assert.equal(rounds({ max_workers: 4 }), 2); assert.equal(rounds({ max_workers: 5 }), 2);
    assert.equal(rounds({ max_workers: 12, max_tool_calls: 100 }), 3); assert.equal(rounds({ max_workers: 6, max_tool_calls: 27 }), 3); assert.equal(rounds({ max_workers: 6, max_tool_calls: 26 }), 2);
    assert.equal(rounds({ max_tool_calls: 13 }), 1); assert.equal(rounds({ max_tool_calls: 19 }), 1); assert.equal(rounds({ max_tool_calls: 20 }), 2);
  });
  it('with no room for a revision the plan says so and has no revision rule; with no room for even the first round it is blocked', () => {
    const one = sim({ max_workers: 2 });
    assert.equal(one.executable, true); assert.ok(one.warnings.some((w: string) => /No revision round fits/.test(w)));
    assert.ok(!evaluatePolicy(one).rules.some((r) => r.id === 'revision-rounds'));
    assert.match(sim({ max_tool_calls: 12 }).blocked_reasons.join(), /tool-call budget exceeded: up to 13 tool calls possible/);
    assert.match(sim({ max_workers: 1 }).blocked_reasons.join(), /worker budget exceeded: 2 worker\(s\) possible/);
  });
});

