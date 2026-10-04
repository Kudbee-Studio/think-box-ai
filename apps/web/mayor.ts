// Mayor: turns a goal into an execution PLAN (Layer 3: governance, pure, no I/O).
// The Mayor never runs anything. It decides which workers a goal needs (a live-data lookup worker, or the specialists the Director would select),
// in which dependency order, with which tools, and checks that against a configurable WORKER BUDGET and a POLICY. The result is a frozen plan that a
// human approves (convoy.ts) before any worker starts. Planning has no side effects by construction: this module imports no filesystem, network,
// process or model code, and takes everything it needs (models, available tools, measured costs, the clock) as arguments.

import { matchRecipe, isGithubRecipe } from './local-recipes.ts';
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

export interface PlannedWorker {
  id: string;
  kind: 'lookup' | 'specialist';
  name: string;
  /** The model that will run this worker (null when none is available: the plan is then not executable). */
  model: string | null;
  tools: string[];
  permission: 'read_only' | 'read_write' | 'none';
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
  goal: string;
  created_at: number;
  workers: PlannedWorker[];
  waves: string[][];
  /** Specialists the Director would pick that need no model (the orchestrator handles them). */
  handled_by_orchestrator: string[];
  /** Local-model grounding failures are retried once on this model through the same governed path, when one is configured. */
  escalation: { model: string; when: string } | null;
  budget: WorkerBudget;
  budget_use: { workers: number; worst_case_workers: number; estimated_cost_usd: number | null; worst_case_cost_usd: number | null; estimated_tool_calls: number };
  expected_convoy: { dashboard_rows: 1; children: number; waves: number };
  executable: boolean;
  blocked_reasons: string[];
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
  /** The model for a live-data lookup (whichever the operator picked: mercury-2, qwen2.5:3b, gemma3:4b ...). */
  lookupModel: string | null;
  /** The worker-agent model for specialist work (and the escalation fallback). */
  agentModel: string | null;
  isLocalModel: (model: string) => boolean;
  /** Names of the tools this runtime really has (agent.ts TOOLS). */
  availableTools: string[];
  /** The measured average cost of one run on this model, or null when there are no measured runs. */
  costOf: (model: string | null) => { usd: number | null; basis: string };
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

  const recipe = matchRecipe(goal);
  if (recipe && isGithubRecipe(recipe)) {
    const cost = input.costOf(input.lookupModel);
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
      const contracts = selection.selected.map((id) => SPECIALISTS[id]!);
      handled = contracts.filter((c) => c.modelRequirements === 'none').map((c) => c.id);
      const runnable = contracts.filter((c) => c.modelRequirements !== 'none');
      if (!input.agentModel) blocked.push('no worker-agent model is configured (set INCEPTION_API_KEY)');
      const allocations = runnable.length ? allocateSpecialistJobs({ jobId: 'plan', intent: goal, specialists: runnable, jobContext: {} }) : [];
      let ordered: string[][] = [];
      try { ordered = planSpecialistWaves(allocations).map((w) => w.map((a) => a.specialistId)); } catch (err) { blocked.push((err as Error).message); }
      const cost = input.costOf(input.agentModel);
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

  const escalation = workers[0]?.kind === 'lookup' && workers[0].model && input.isLocalModel(workers[0].model) && input.agentModel
    ? { model: input.agentModel, when: 'the local model fails the grounding check or cannot complete the lookup' } : null;
  const known = workers.every((w) => w.estimated_cost_usd !== null);
  const estimatedCost = workers.length && known ? round6(workers.reduce((t, w) => t + (w.estimated_cost_usd ?? 0), 0)) : null;
  const escalationCost = escalation ? input.costOf(escalation.model).usd : 0;
  const worstCost = estimatedCost === null || escalationCost === null ? null : round6(estimatedCost + escalationCost);
  const estimatedCalls = workers.reduce((t, w) => t + w.estimated_tool_calls, 0);
  const worstWorkers = workers.length + (escalation ? 1 : 0);
  if (worstWorkers > budget.max_workers) blocked.push(`worker budget exceeded: ${worstWorkers} worker(s) possible (${workers.length} planned${escalation ? ' + 1 escalation' : ''}), budget allows ${budget.max_workers}`);
  if (worstCost !== null && worstCost > budget.max_cost_usd) blocked.push(`cost budget exceeded: up to $${worstCost} estimated, budget allows $${budget.max_cost_usd}`);
  if (estimatedCalls > budget.max_tool_calls) blocked.push(`tool-call budget exceeded: up to ${estimatedCalls} tool calls possible, budget allows ${budget.max_tool_calls}`);

  return {
    ok: true,
    plan: {
      plan_only: true, side_effects: 'none', goal, created_at: input.now, workers, waves, handled_by_orchestrator: handled, escalation, budget,
      budget_use: { workers: workers.length, worst_case_workers: worstWorkers, estimated_cost_usd: estimatedCost, worst_case_cost_usd: worstCost, estimated_tool_calls: estimatedCalls },
      expected_convoy: { dashboard_rows: 1, children: workers.length, waves: waves.length },
      executable: blocked.length === 0 && workers.length > 0,
      blocked_reasons: workers.length || blocked.length ? blocked : ['nothing to plan'],
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
  const write = withTool(WRITE_TOOLS);
  const exec = plan.workers.filter((w) => w.tools.includes('exec')).map((w) => w.id);
  let risk: PolicyEvaluation['risk'] = 'low';
  if (network.length) rules.push({ id: 'network-read', effect: 'info', reason: 'These workers read from the network; the first access to each host still asks for approval at run time.', workers: network });
  if (write.length) { risk = 'medium'; rules.push({ id: 'workspace-write', effect: 'require_approval', reason: 'These workers can write files or memory inside their own workspace.', workers: write }); restrictions.push('Writes stay inside the worker workspace; overwriting an existing file asks again.'); }
  if (exec.length) { risk = 'high'; rules.push({ id: 'command-execution', effect: 'deny', reason: 'Command execution is not available to convoys.', workers: exec }); }
  if (!plan.executable) rules.push({ id: 'plan-not-executable', effect: 'deny', reason: plan.blocked_reasons.join('; ') });
  if (plan.workers.some((w) => w.estimated_cost_usd === null)) rules.push({ id: 'cost-unmeasured', effect: 'info', reason: 'Cost could not be estimated (no measured runs on this model yet); the cost budget is enforced from actual spend while it runs.' });
  return { decision: rules.some((r) => r.effect === 'deny') ? 'denied' : 'requires_approval', rules, restrictions, risk };
}

const round6 = (n: number): number => Math.round(n * 1e6) / 1e6;
