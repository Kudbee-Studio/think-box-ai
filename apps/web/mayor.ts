// Mayor: turns a goal into an execution PLAN (Layer 3: governance, pure, no I/O).
// The Mayor never runs anything. It decides which workers a goal needs (a live-data lookup worker, or the specialists the Director would select),
// in which dependency order, with which tools, and checks that against a configurable WORKER BUDGET and a POLICY. The result is a frozen plan that a
// human approves (convoy.ts) before any worker starts. Planning has no side effects by construction: this module imports no filesystem, network,
// process or model code, and takes everything it needs (models, available tools, measured costs, the clock) as arguments.

import { matchRecipe, matchRepoGoal, isGithubRecipe } from './local-recipes.ts';
import { allocateSpecialistJobs, planSpecialistWaves } from './specialist-executor.ts';
import { SPECIALISTS, selectSpecialists } from './specialist-contracts.ts';

export interface WorkerBudget {
  max_workers: number;
  max_cost_usd: number;
  max_tool_calls: number;
}

export const DEFAULT_BUDGET: Readonly<WorkerBudget> = Object.freeze({ max_workers: 4, max_cost_usd: 0.1, max_tool_calls: 20 });
const BUDGET_LIMITS = { max_workers: [1, 12], max_cost_usd: [0, 5], max_tool_calls: [1, 100] } as const;

/** A caller-supplied budget, checked: numbers inside sane limits, unknown keys refused, missing keys default. */
export function normalizeBudget(raw: unknown): { ok: true; budget: WorkerBudget } | { ok: false; error: string } {
  if (raw === undefined || raw === null) return { ok: true, budget: { ...DEFAULT_BUDGET } };
  if (typeof raw !== 'object' || Array.isArray(raw)) return { ok: false, error: 'worker_budget must be an object' };
  const budget: WorkerBudget = { ...DEFAULT_BUDGET };
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    if (!(key in BUDGET_LIMITS)) return { ok: false, error: `unknown worker_budget field "${key}"` };
    const [lo, hi] = BUDGET_LIMITS[key as keyof typeof BUDGET_LIMITS];
    if (typeof value !== 'number' || !Number.isFinite(value) || value < lo || value > hi) return { ok: false, error: `worker_budget.${key} must be a number from ${lo} to ${hi}` };
    if (key !== 'max_cost_usd' && !Number.isInteger(value)) return { ok: false, error: `worker_budget.${key} must be a whole number` };
    budget[key as keyof WorkerBudget] = value;
  }
  return { ok: true, budget };
}

/** How much a convoy may do. OBSERVE reads only; LEARN also lets the outcome feed Think Token candidates; SIMULATE proposes a change and verifies it in a sandbox (nothing is applied to the working tree). AUTONOMOUS is not available yet. */
export type ThinkMode = 'observe' | 'learn' | 'simulate' | 'autonomous';
export const THINK_MODES: readonly ThinkMode[] = ['observe', 'learn', 'simulate', 'autonomous'];
const AVAILABLE_MODES: readonly ThinkMode[] = ['observe', 'learn', 'simulate'];
const REPO_TOOL_NAMES = ['repo_search', 'repo_read'];
/** What a SIMULATE convoy needs: read the repo, propose edits, run the repository's own checks in the sandbox. */
const SIMULATE_TOOLS = ['repo_search', 'repo_read', 'propose_change', 'run_checks'];
const SIMULATE_CHECKS = ['lint', 'typecheck', 'tsc', 'test'];
/** The most propose/verify rounds a SIMULATE convoy may run, whatever the budget. */
const MAX_SIMULATE_ROUNDS = 3;
/** Upper bounds on tool calls per round: a first proposal reads the repo, a revision already has the failure report. */
const CALLS_FIRST_ROUND = 13;
export const CALLS_PER_REVISION = 7;

export interface PlannedWorker {
  id: string;
  kind: 'lookup' | 'specialist' | 'repo' | 'patch' | 'checks';
  name: string;
  /** The model that will run this worker (null when none is available: the plan is then not executable). */
  model: string | null;
  tools: string[];
  /** `sandbox_exec`: runs the repository's own checks in a throwaway copy with no network and no credentials; writes nothing outside that copy. */
  permission: 'read_only' | 'read_write' | 'none' | 'sandbox_exec';
  depends_on: string[];
  wave: number;
  purpose: string;
  /** Measured, or null. Never a guess: cost_basis says where the number came from or why there is none. */
  estimated_cost_usd: number | null;
  cost_basis: string;
  /** An upper bound, not a prediction. */
  estimated_tool_calls: number;
}

export interface ConvoyPlan {
  /** Always true here: this object describes work, it is not work. */
  plan_only: true;
  side_effects: 'none';
  /** Which model runs the lookup/investigation and why (the measured table, the operator, or the default). */
  routing: { source: 'operator' | 'measured' | 'default'; model: string | null; reason: string } | null;
  goal: string;
  created_at: number;
  workers: PlannedWorker[];
  waves: string[][];
  /** Specialists the Director would pick that need no model (the orchestrator handles them). */
  handled_by_orchestrator: string[];
  /** Workers the Mayor added to the Director's selection, and why (the specialist proof refuses a job without an independent Validator). */
  added_by_mayor: Array<{ id: string; reason: string }>;
  /** SIMULATE only: the commit it is pinned to and the repository checks the sandbox will run. Frozen with the plan, so the approval covers them. */
  simulation?: { ref: string; checks: string[]; /** Propose/verify rounds the budget allows (1 = no revision): a failing report goes back to the patch worker for another try, each sandbox run asking a human again. */ max_rounds: number };
  /** Local-model grounding failures are retried once on this model through the same governed path, when one is configured. */
  escalation: { model: string; when: string } | null;
  budget: WorkerBudget;
  budget_use: { workers: number; worst_case_workers: number; estimated_cost_usd: number | null; worst_case_cost_usd: number | null; estimated_tool_calls: number };
  expected_convoy: { dashboard_rows: 1; children: number; waves: number };
  executable: boolean;
  blocked_reasons: string[];
  /** The control mode this convoy was planned under. */
  think_mode: ThinkMode;
  /** Things the approver should know that do not block the plan. */
  warnings: string[];
}

export interface PolicyRule { id: string; effect: 'require_approval' | 'deny' | 'info'; reason: string; workers?: string[] }
export interface PolicyEvaluation {
  /** `requires_approval`: a human must approve. `denied`: it cannot be submitted at all. There is no "allowed without approval". */
  decision: 'requires_approval' | 'denied';
  rules: PolicyRule[];
  restrictions: string[];
  risk: 'low' | 'medium' | 'high';
}

export interface PlanInput {
  goal: string;
  budget?: unknown;
  mode?: ThinkMode;
  /** The model for a live-data lookup (whichever the operator picked: mercury-2, qwen2.5:3b, gemma3:4b ...). */
  lookupModel: string | null;
  /** How the lookup model was chosen (operator, the measured table, or the default), and why. Shown on the plan; not used to decide anything here. */
  routing?: { source: 'operator' | 'measured' | 'default'; model: string | null; reason: string };
  /** The worker-agent model for specialist work (and the escalation fallback). */
  agentModel: string | null;
  isLocalModel: (model: string) => boolean;
  /** Names of the tools this runtime really has (agent.ts TOOLS). */
  availableTools: string[];
  /** The measured average cost of one run on this model, or null when there are no measured runs. */
  costOf: (model: string | null, kind: PlannedWorker['kind']) => { usd: number | null; basis: string };
  now: number;
}

const NETWORK_TOOLS = new Set(['live_lookup', 'fetch_url', 'read_rss', 'algorand', 'medication']);
const WRITE_TOOLS = new Set(['write_file', 'remember']);

/** The plan for a goal. Pure: the same input always gives the same plan, and nothing is started. */
export function planConvoy(input: PlanInput): { ok: true; plan: ConvoyPlan } | { ok: false; error: string } {
  const goal = String(input.goal ?? '').trim();
  if (!goal) return { ok: false, error: 'a goal is required' };
  if (goal.length > 2000) return { ok: false, error: 'the goal is too long (2000 characters at most)' };
  const budgetResult = normalizeBudget(input.budget);
  if (!budgetResult.ok) return budgetResult;
  const budget = budgetResult.budget;
  const blocked: string[] = [];
  const workers: PlannedWorker[] = [];
  const waves: string[][] = [];
  let handled: string[] = [];
  const added: Array<{ id: string; reason: string }> = [];

  const mode: ThinkMode = input.mode ?? 'observe';
  if (!THINK_MODES.includes(mode)) return { ok: false, error: `mode must be one of ${THINK_MODES.join(', ')}` };
  if (!AVAILABLE_MODES.includes(mode)) blocked.push(`${mode.toUpperCase()} mode is not available yet (only ${AVAILABLE_MODES.join(' and ')}): it needs a scratch workspace and a test runner`);

  const recipe = matchRecipe(goal);
  const warnings: string[] = [];
  let simulation: ConvoyPlan['simulation'];
  if (mode === 'simulate') {
    if ((recipe && isGithubRecipe(recipe)) || matchRepoGoal(goal)) blocked.push('SIMULATE proposes and verifies a change; this goal reads like a question or an investigation (use OBSERVE for that)');
    const missing = SIMULATE_TOOLS.filter((t) => !input.availableTools.includes(t));
    if (missing.length) blocked.push(`the tools SIMULATE needs are not available in this runtime: ${missing.join(', ')}`);
    if (!input.agentModel) blocked.push('SIMULATE needs the agent model (Mercury) to propose a change; none is configured');
    const cost = input.costOf(input.agentModel, 'patch');
    workers.push({
      id: 'patch-1', kind: 'patch', name: 'Propose a change (nothing is written)', model: input.agentModel, tools: ['repo_search', 'repo_read', 'propose_change'], permission: 'read_only', depends_on: [], wave: 1,
      purpose: 'Read the source and propose the change as exact text edits; the system builds the diff from the real files at one commit and checks that it applies. Nothing is written or run.',
      estimated_cost_usd: cost.usd, cost_basis: cost.basis, estimated_tool_calls: 12,
    });
    workers.push({
      id: 'checks-1', kind: 'checks', name: 'Verify in the sandbox', model: null, tools: ['run_checks'], permission: 'sandbox_exec', depends_on: ['patch-1'], wave: 2,
      purpose: `Run the repository's own checks (${SIMULATE_CHECKS.join(', ')}) on a throwaway copy of the commit with the proposed change applied: no network, no credentials, nothing touches your working tree. Asks for your approval again, showing the exact commit and patch.`,
      estimated_cost_usd: 0, cost_basis: 'no model: the repository\'s own checks run in a sandbox', estimated_tool_calls: 1,
    });
    waves.push(['patch-1'], ['checks-1']);
    {
      const rounds = Math.max(1, Math.min(MAX_SIMULATE_ROUNDS, Math.floor(budget.max_workers / 2), 1 + Math.floor((budget.max_tool_calls - CALLS_FIRST_ROUND) / CALLS_PER_REVISION)));
      warnings.push(rounds > 1
        ? `If the sandbox checks fail, the patch worker gets the failure report and may revise: up to ${rounds} round(s) in all, as the worker and tool-call budgets allow. Every round's sandbox run asks for your approval again, saying which round it is and what the last attempt got wrong.`
        : 'No revision round fits the worker or tool-call budget: a failing proposal is reported as it is.');
    }
    const rounds = Math.max(1, Math.min(MAX_SIMULATE_ROUNDS, Math.floor(budget.max_workers / 2), 1 + Math.floor((budget.max_tool_calls - CALLS_FIRST_ROUND) / CALLS_PER_REVISION)));
    simulation = { ref: 'HEAD', checks: [...SIMULATE_CHECKS], max_rounds: rounds };
  } else if (!(recipe && isGithubRecipe(recipe)) && matchRepoGoal(goal)) {
    const missing = REPO_TOOL_NAMES.filter((t) => !input.availableTools.includes(t));
    if (missing.length) blocked.push(`the repository tools are not available in this runtime: ${missing.join(', ')}`);
    if (!input.lookupModel) blocked.push('no model is available to run the investigation');
    else if (!input.isLocalModel(input.lookupModel)) blocked.push(`repository investigation runs on local models in this version; ${input.lookupModel} is not one (pick a local model)`);
    const cost = input.costOf(input.lookupModel, 'repo');
    workers.push({
      id: 'repo-1', kind: 'repo', name: 'Repository investigation (read-only)', model: input.lookupModel, tools: [...REPO_TOOL_NAMES], permission: 'read_only', depends_on: [], wave: 1,
      purpose: 'Look at the real source with read-only tools and report one finding (file, line, exact quote, claim); the finding is checked against what the tools returned and re-read from disk',
      estimated_cost_usd: cost.usd, cost_basis: cost.basis, estimated_tool_calls: 8,
    });
    waves.push(['repo-1']);
  } else if (recipe && isGithubRecipe(recipe)) {
    const cost = input.costOf(input.lookupModel, 'lookup');
    if (!input.lookupModel) blocked.push('no model is available to run the lookup');
    workers.push({
      id: 'lookup-1', kind: 'lookup', name: `Live lookup (${recipe.label})`, model: input.lookupModel, tools: ['live_lookup'], permission: 'read_only', depends_on: [], wave: 1,
      purpose: `Answer from live GitHub data through the governed live_lookup tool, then check every claim against the returned evidence`,
      estimated_cost_usd: cost.usd, cost_basis: cost.basis, estimated_tool_calls: 3,
    });
    waves.push(['lookup-1']);
  } else {
    const selection = selectSpecialists(goal);
    if (selection.blocked) blocked.push(selection.blockedReason ?? 'no specialist matched this goal');
    else {
      // The specialist proof refuses a job with no independent Validator execution, so a plan without one could never complete: add it, as the Director
      // already does when a Builder is selected. The reason is part of the plan the human approves.
      const selected = new Set(selection.selected);
      if (!selected.has('validator') && [...selected].some((id) => SPECIALISTS[id]!.modelRequirements !== 'none')) {
        selected.add('validator');
        added.push({ id: 'validator', reason: 'no specialist may claim success without independent verification: the job proof needs a successful Validator execution' });
      }
      const contracts = [...selected].sort().map((id) => SPECIALISTS[id]!);
      handled = contracts.filter((c) => c.modelRequirements === 'none').map((c) => c.id);
      const runnable = contracts.filter((c) => c.modelRequirements !== 'none');
      if (!input.agentModel) blocked.push('no worker-agent model is configured (set INCEPTION_API_KEY)');
      const allocations = runnable.length ? allocateSpecialistJobs({ jobId: 'plan', intent: goal, specialists: runnable, jobContext: {} }) : [];
      let ordered: string[][] = [];
      try { ordered = planSpecialistWaves(allocations).map((w) => w.map((a) => a.specialistId)); } catch (err) { blocked.push((err as Error).message); }
      const cost = input.costOf(input.agentModel, 'specialist');
      for (const [index, wave] of ordered.entries()) {
        for (const specialistId of wave) {
          const contract = SPECIALISTS[specialistId]!;
          const missing = contract.toolsRequired.filter((t) => !input.availableTools.includes(t));
          if (missing.length) blocked.push(`${contract.name} needs tool(s) this runtime does not have: ${missing.join(', ')}`);
          workers.push({
            id: specialistId, kind: 'specialist', name: contract.name, model: input.agentModel, tools: [...contract.toolsRequired], permission: contract.permissionsBoundary,
            depends_on: runnable.filter((o) => contract.handoffContract.acceptsFrom.includes(o.id)).map((o) => o.id).filter((id) => ordered.slice(0, index).some((w) => w.includes(id))),
            wave: index + 1, purpose: contract.capability, estimated_cost_usd: cost.usd, cost_basis: cost.basis, estimated_tool_calls: Math.max(1, contract.toolsRequired.length) * 2,
          });
        }
        waves.push(wave);
      }
    }
  }

  if (mode === 'simulate') warnings.push('The proposed change is never applied to your working tree and nothing is pushed: you get a patch, the files it touches and a verification report.', 'Running the checks asks for your approval again, showing the exact commit and the patch hash.', 'Verified means the repository\'s own checks passed on a throwaway copy; it is not proof the change is right.');
  if (workers.some((w) => w.kind === 'specialist') && !workers.some((w) => w.tools.includes('write_file'))) {
    warnings.push('No worker writes an artifact, so the Validator may have nothing to check and the specialist job proof can end PARTIAL even if every worker succeeds.');
  }
  if (workers.some((w) => w.id === 'researcher')) {
    warnings.push('The Researcher is read-only, so its evidence has no artifact for the Validator to re-read; the existing job proof refuses such evidence and the convoy can end PARTIAL even though every worker succeeded.');
  }
  const first = workers[0];
  const escalation = mode !== 'simulate' && (first?.kind === 'lookup' || first?.kind === 'repo') && first.model && input.isLocalModel(first.model) && input.agentModel
    ? { model: input.agentModel, when: first.kind === 'repo' ? 'the local model fails, is not grounded, cannot be verified on disk, or reports no finding where the goal expects one' : 'the local model fails the grounding check or cannot complete the lookup' } : null;
  const known = workers.every((w) => w.estimated_cost_usd !== null);
  const estimatedCost = workers.length && known ? round6(workers.reduce((t, w) => t + (w.estimated_cost_usd ?? 0), 0)) : null;
  const escalationCost = escalation ? input.costOf(escalation.model, first?.kind === 'repo' ? 'repo' : 'lookup').usd : 0;
  const worstCost = estimatedCost === null || escalationCost === null ? null : round6(estimatedCost + escalationCost);
  const estimatedCalls = workers.reduce((t, w) => t + w.estimated_tool_calls, 0);
  const worstWorkers = simulation ? 2 * simulation.max_rounds : workers.length + (escalation ? 1 : 0);
  if (worstWorkers > budget.max_workers) blocked.push(`worker budget exceeded: ${worstWorkers} worker(s) possible (${workers.length} planned${escalation ? ' + 1 escalation' : ''}), budget allows ${budget.max_workers}`);
  if (worstCost !== null && worstCost > budget.max_cost_usd) blocked.push(`cost budget exceeded: up to $${worstCost} estimated, budget allows $${budget.max_cost_usd}`);
  if (estimatedCalls > budget.max_tool_calls) blocked.push(`tool-call budget exceeded: up to ${estimatedCalls} tool calls possible, budget allows ${budget.max_tool_calls}`);

  return {
    ok: true,
    plan: {
      plan_only: true, side_effects: 'none', routing: input.routing ?? null, goal, created_at: input.now, workers, waves, handled_by_orchestrator: handled, added_by_mayor: added, escalation, ...(simulation ? { simulation } : {}), budget,
      budget_use: { workers: workers.length, worst_case_workers: worstWorkers, estimated_cost_usd: estimatedCost, worst_case_cost_usd: worstCost, estimated_tool_calls: estimatedCalls },
      expected_convoy: { dashboard_rows: 1, children: workers.length, waves: waves.length },
      executable: blocked.length === 0 && workers.length > 0,
      blocked_reasons: workers.length || blocked.length ? blocked : ['nothing to plan'], think_mode: mode, warnings,
    },
  };
}

/**
 * The policy a plan is evaluated against. Every convoy needs a human to approve it (a model never approves its own execution); the rules
 * below add what the approver should know and what is refused outright. Runtime tool gates (first network access per host, overwriting a file)
 * still apply on top of this and are never bypassed by an approved convoy.
 */
export function evaluatePolicy(plan: ConvoyPlan): PolicyEvaluation {
  const rules: PolicyRule[] = [{ id: 'human-approval', effect: 'require_approval', reason: 'A human must approve before any worker starts. A model, a worker or the system can never approve.' }];
  const restrictions = ['Tool calls still pass the runtime gates: allowlist, first network access per host, overwrite confirmation.', 'Workers are limited to the tools listed in the plan.'];
  const withTool = (set: Set<string>): string[] => plan.workers.filter((w) => w.tools.some((t) => set.has(t))).map((w) => w.id);
  const network = withTool(NETWORK_TOOLS);
  const repoReaders = plan.workers.filter((w) => w.kind === 'repo').map((w) => w.id);
  const write = withTool(WRITE_TOOLS);
  const exec = plan.workers.filter((w) => w.tools.includes('exec')).map((w) => w.id);
  let risk: PolicyEvaluation['risk'] = 'low';
  rules.push({ id: `mode-${plan.think_mode}`, effect: 'info', reason: plan.think_mode === 'observe' ? 'OBSERVE: read-only. No file is changed and nothing is learned from this convoy.' : plan.think_mode === 'learn' ? 'LEARN: read-only like OBSERVE, and the verified outcome may produce Think Token candidates (never auto-accepted).' : plan.think_mode === 'simulate' ? 'SIMULATE: proposes a change and verifies it in a sandbox. The change is never applied to your working tree and nothing is pushed or opened as a pull request.' : `${plan.think_mode.toUpperCase()}: not available yet.` });
  if (repoReaders.length) rules.push({ id: 'repo-read', effect: 'info', reason: 'These workers read this repository\'s source through read-only tools. Secrets, .env files, keys, databases, .git and node_modules are not readable. Source text a local model reads stays on this machine.', workers: repoReaders });
  const patchers = plan.workers.filter((w) => w.kind === 'patch').map((w) => w.id);
  const sandboxed = plan.workers.filter((w) => w.permission === 'sandbox_exec').map((w) => w.id);
  if (patchers.length) rules.push({ id: 'source-leaves-machine', effect: 'info', reason: 'The patch worker runs on the agent model (a cloud API): the source it reads and the change it writes are sent to that provider. Secrets, .env files, keys, databases, .git and node_modules are not readable by its tools. It cannot write or run anything: it only proposes.', workers: patchers });
  if (plan.simulation && plan.simulation.max_rounds > 1) rules.push({ id: 'revision-rounds', effect: 'info', reason: `If the sandbox checks fail, the patch worker is shown the failure output (data from the repository's own commands, clipped) and may propose a revision: up to ${plan.simulation.max_rounds} round(s) in all. Every round's sandbox run asks for your approval again; the cost and worker budgets are re-checked before each revision.`, workers: patchers });
  if (sandboxed.length) { risk = 'medium'; rules.push({ id: 'sandboxed-checks', effect: 'require_approval', reason: 'This worker runs the repository\'s own checks on a throwaway copy of one commit with the proposed change applied, inside a sandbox with no network, no home directory and no credentials. Nothing touches your working tree. It asks for your approval again when it runs, showing the exact commit, the checks and the patch.', workers: sandboxed }); restrictions.push('Checks run only in the sandbox, only after a second approval that names the exact commit and patch.'); }
  if (network.length) rules.push({ id: 'network-read', effect: 'info', reason: 'These workers read from the network; the first access to each host still asks for approval at run time.', workers: network });
  if (write.length) { risk = 'medium'; rules.push({ id: 'workspace-write', effect: 'require_approval', reason: 'These workers can write files or memory inside their own workspace.', workers: write }); restrictions.push('Writes stay inside the worker workspace; overwriting an existing file asks again.'); }
  if (exec.length) { risk = 'high'; rules.push({ id: 'command-execution', effect: 'deny', reason: 'Command execution is not available to convoys.', workers: exec }); }
  if (!plan.executable) rules.push({ id: 'plan-not-executable', effect: 'deny', reason: plan.blocked_reasons.join('; ') });
  if (plan.workers.some((w) => w.estimated_cost_usd === null)) rules.push({ id: 'cost-unmeasured', effect: 'info', reason: 'Cost could not be estimated (no measured runs on this model yet); the cost budget is enforced from actual spend while it runs.' });
  return { decision: rules.some((r) => r.effect === 'deny') ? 'denied' : 'requires_approval', rules, restrictions, risk };
}

const round6 = (n: number): number => Math.round(n * 1e6) / 1e6;
