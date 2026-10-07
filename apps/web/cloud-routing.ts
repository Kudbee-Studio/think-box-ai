// Which cloud worker-agent model to use, and what to do when its provider fails. The ranking comes from MEASURED runs (the P3.48-P3.52 SIMULATE experiments:
// verified-fix rate, median time and tokens per task) and the ESTIMATED prices in cloud-models.ts; it never claims a number it does not have. Failover only
// happens when the provider failed before the run did anything (no completed model call, no tool call), so a retry can never repeat a side effect.
import { runToolAgent, type AgentHooks, type AgentRunResult } from './agent.ts';
import { MODEL_PRICING, configuredCloudModels, costUsd } from './cloud-models.ts';

export interface CloudMeasurement {
  model: string;
  /** Tasks run and verified (a fix the sandbox verified AND an independent test confirmed). */
  tasks: number;
  success: number;
  median_ms: number;
  median_tokens: number;
  /** The evidence files the numbers come from (a test recomputes them). */
  sources: string[];
}

/** Pooled easy (15) + hard (24) SIMULATE rows per model. deepseek-flash was run under its alias deepseek-chat. */
export const CLOUD_MEASUREMENTS: CloudMeasurement[] = [
  { model: 'mercury-2', tasks: 39, success: 39, median_ms: 2604, median_tokens: 6748, sources: ['docs/evidence/p3.48-local-simulate/run1-results.json', 'docs/evidence/p3.50-hard-tasks/run1-results.json'] },
  { model: 'deepseek-flash', tasks: 39, success: 39, median_ms: 5557, median_tokens: 7897, sources: ['docs/evidence/p3.49-local-patch-interface/run2-deepseek-results.json', 'docs/evidence/p3.50-hard-tasks/run1-results.json'] },
  { model: 'grok-4.3', tasks: 39, success: 37, median_ms: 6638, median_tokens: 7113, sources: ['docs/evidence/p3.52-xai/easy-results.json', 'docs/evidence/p3.52-xai/hard-results.json'] },
];
/** The evidence names deepseek-flash as the alias the experiment used. */
export const MEASUREMENT_ALIASES: Record<string, string> = { 'deepseek-chat': 'deepseek-flash' };

/** A model is eligible when it was measured on enough tasks with a high verified rate. */
export const MIN_TASKS = 20;
export const MIN_RATE = 0.9;
/** An agent loop is prompt-heavy: the price blend assumes this share of the tokens are input tokens (the rest output). An assumption, stated. */
export const INPUT_SHARE = 0.85;

/** Estimated USD for one median task on a model: median tokens at the blended ESTIMATED price, or null when the model has no price. */
export function estCostPerTask(m: CloudMeasurement): number | null {
  const price = MODEL_PRICING[m.model];
  if (!price) return null;
  return costUsd(m.model, m.median_tokens * INPUT_SHARE, m.median_tokens * (1 - INPUT_SHARE));
}

export interface Ranked { model: string; reason: string }

const usd = (n: number): string => `$${n.toFixed(4)}`;

/**
 * The configured models in the order to try them: eligible models first, cheapest estimated cost per task first (faster breaks a tie), then measured but
 * not eligible, then never measured (registry order). Each entry says why.
 */
export function rankCloudModels(configured: string[], table: CloudMeasurement[] = CLOUD_MEASUREMENTS): Ranked[] {
  const rows = configured.map((model, i) => ({ model, i, m: table.find((t) => t.model === model) }));
  const eligible = rows.filter((r) => r.m && r.m.tasks >= MIN_TASKS && r.m.success / r.m.tasks >= MIN_RATE && estCostPerTask(r.m) !== null)
    .sort((a, b) => estCostPerTask(a.m!)! - estCostPerTask(b.m!)! || a.m!.median_ms - b.m!.median_ms);
  const measured = rows.filter((r) => r.m && !eligible.includes(r));
  const unmeasured = rows.filter((r) => !r.m);
  return [
    ...eligible.map((r) => ({ model: r.model, reason: `${r.m!.success}/${r.m!.tasks} verified fixes, median ${(r.m!.median_ms / 1000).toFixed(1)} s, about ${usd(estCostPerTask(r.m!)!)} per task (estimated price)` })),
    ...measured.map((r) => ({ model: r.model, reason: `measured ${r.m!.success}/${r.m!.tasks}, which is below the ${MIN_RATE * 100}% over ${MIN_TASKS} tasks rule or has no price, so it is tried after the qualified models` })),
    ...unmeasured.map((r) => ({ model: r.model, reason: 'never measured on SIMULATE tasks, so it is tried last' })),
  ];
}

/** The agent model used when nothing else is chosen: the best-ranked configured cloud model, or null. `KUDBEE_CLOUD_ROUTING=off` keeps registry order. */
export function defaultAgentModel(env: Record<string, string | undefined> = process.env): string | null {
  const names = configuredCloudModels().map((m) => m.name);
  return env.KUDBEE_CLOUD_ROUTING === 'off' ? names[0] ?? null : rankCloudModels(names)[0]?.model ?? null;
}

/** An error that is the provider's or the network's, not the goal's: unauthorized, out of credit, rate limited, a server error, no route, a timeout, or no key set. */
export function isProviderFailure(error: string | undefined): boolean {
  return /API HTTP (401|402|403|408|429|5\d\d)\b|fetch failed|timeout|is not set in \.env/i.test(error ?? '');
}

/** True only when the run did nothing: no model call completed and no tool ran. Then retrying elsewhere cannot repeat a side effect. */
const didNothing = (r: AgentRunResult): boolean => r.tool_calls === 0 && r.tokens === 0;

export type FailoverResult = AgentRunResult & { model_used?: string };

/** runToolAgent, and if the provider fails before the run did anything, the same goal on the next-best configured cloud model (announced, never silent). */
export async function runToolAgentWithFailover(goal: string, model: string, maxIterations: number, temperature: number, history: Array<{ goal: string; result: string }>, hooks: AgentHooks, memoryContext = ''): Promise<FailoverResult> {
  const first = await runToolAgent(goal, model, maxIterations, temperature, history, hooks, memoryContext);
  if (first.success || first.stopped || process.env.KUDBEE_CLOUD_FAILOVER === 'off' || !isProviderFailure(first.error) || !didNothing(first)) return first;
  const tried = [model]; const failures = [`${model}: ${first.error}`];
  const next = rankCloudModels(configuredCloudModels().map((m) => m.name)).filter((r) => r.model !== model);
  for (const candidate of next) {
    if (hooks.signal.aborted) break;
    hooks.onThought({ type: 'routing', content: `${tried.at(-1)} failed before doing anything (${failures.at(-1)!.split(': ').slice(1).join(': ').slice(0, 120)}); retrying the same goal on ${candidate.model}: ${candidate.reason}`, status: 'info' });
    const r = await runToolAgent(goal, candidate.model, maxIterations, temperature, history, hooks, memoryContext);
    tried.push(candidate.model);
    if (r.success || r.stopped || !isProviderFailure(r.error) || !didNothing(r)) return { ...r, model_used: candidate.model };
    failures.push(`${candidate.model}: ${r.error}`);
  }
  return { ...first, error: `${first.error} (no fallback worked: ${failures.slice(1).join('; ') || 'none configured'})` };
}
