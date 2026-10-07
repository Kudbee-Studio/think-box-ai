// Which cloud worker-agent model to use, and what to do when its provider fails. The ranking comes from MEASURED runs (the P3.48-P3.52 SIMULATE experiments:
// verified-fix rate; median cost, time and tokens per task, with the cost basis stated: xAI's billed cost, a price list, or an estimate); it never claims a number it does not have. Failover only
// happens when the provider failed before the run did anything (no completed model call, no tool call), so a retry can never repeat a side effect.
import { runToolAgent, type AgentHooks, type AgentRunResult } from './agent.ts';
import { configuredCloudModels } from './cloud-models.ts';

export interface CloudMeasurement {
  model: string;
  /** Tasks run and verified (a fix the sandbox verified AND an independent test confirmed), pooled over `sources`. */
  tasks: number;
  success: number;
  /** Median cost, time and tokens of one task from the P3.57 runs only (`cost_sources`): the run after cost accounting was fixed (reasoning tokens counted, the provider's billed cost used). */
  median_usd: number;
  median_ms: number;
  median_tokens: number;
  /** Where the dollar figure comes from, stated so no estimate passes for a measurement. */
  cost_basis: 'provider-billed' | 'tokens at the provider price list' | 'tokens at an estimated price';
  sources: string[];
  cost_sources: string[];
}

const P357 = (m: string): string[] => [`docs/evidence/p3.57-cost-per-task/${m}-easy-results.json`, `docs/evidence/p3.57-cost-per-task/${m}-hard-results.json`];
/** Pooled easy + hard SIMULATE rows per model (66 each); deepseek-flash was run under its alias deepseek-chat in the earlier runs. */
export const CLOUD_MEASUREMENTS: CloudMeasurement[] = [
  { model: 'mercury-2', tasks: 66, success: 64, median_usd: 0.002052, median_ms: 2553, median_tokens: 6654, cost_basis: 'tokens at the provider price list', sources: ['docs/evidence/p3.48-local-simulate/run1-results.json', 'docs/evidence/p3.50-hard-tasks/run1-results.json', ...P357('mercury-2')], cost_sources: P357('mercury-2') },
  { model: 'deepseek-flash', tasks: 66, success: 66, median_usd: 0.002758, median_ms: 5353, median_tokens: 7989, cost_basis: 'tokens at an estimated price', sources: ['docs/evidence/p3.49-local-patch-interface/run2-deepseek-results.json', 'docs/evidence/p3.50-hard-tasks/run1-results.json', ...P357('deepseek-flash')], cost_sources: P357('deepseek-flash') },
  { model: 'grok-4.3', tasks: 66, success: 63, median_usd: 0.006427, median_ms: 6168, median_tokens: 7339, cost_basis: 'provider-billed', sources: ['docs/evidence/p3.52-xai/easy-results.json', 'docs/evidence/p3.52-xai/hard-results.json', ...P357('grok-4.3')], cost_sources: P357('grok-4.3') },
  { model: 'grok-4.7', tasks: 66, success: 63, median_usd: 0.012654, median_ms: 5948, median_tokens: 11943, cost_basis: 'provider-billed', sources: ['docs/evidence/p3.55-xai-models/grok-4.7-easy-results.json', 'docs/evidence/p3.55-xai-models/grok-4.7-hard-results.json', ...P357('grok-4.7')], cost_sources: P357('grok-4.7') },
  { model: 'grok-build-0.1', tasks: 66, success: 64, median_usd: 0.005978, median_ms: 9496, median_tokens: 9675, cost_basis: 'provider-billed', sources: ['docs/evidence/p3.55-xai-models/grok-build-0.1-easy-results.json', 'docs/evidence/p3.55-xai-models/grok-build-0.1-hard-results.json', ...P357('grok-build-0.1')], cost_sources: P357('grok-build-0.1') },
];
/** The evidence names deepseek-flash as the alias the experiment used. */
export const MEASUREMENT_ALIASES: Record<string, string> = { 'deepseek-chat': 'deepseek-flash' };

/** A model is eligible when it was measured on enough tasks with a high verified rate. */
export const MIN_TASKS = 20;
export const MIN_RATE = 0.9;

/** The measured cost of one median task, in USD. */
export const estCostPerTask = (m: CloudMeasurement): number => m.median_usd;

export interface Ranked { model: string; reason: string }

const usd = (n: number): string => `$${n.toFixed(4)}`;

/**
 * The configured models in the order to try them: eligible models first, cheapest estimated cost per task first (faster breaks a tie), then measured but
 * not eligible, then never measured (registry order). Each entry says why.
 */
export function rankCloudModels(configured: string[], table: CloudMeasurement[] = CLOUD_MEASUREMENTS): Ranked[] {
  const rows = configured.map((model, i) => ({ model, i, m: table.find((t) => t.model === model) }));
  const eligible = rows.filter((r) => r.m && r.m.tasks >= MIN_TASKS && r.m.success / r.m.tasks >= MIN_RATE)
    .sort((a, b) => estCostPerTask(a.m!) - estCostPerTask(b.m!) || a.m!.median_ms - b.m!.median_ms);
  const measured = rows.filter((r) => r.m && !eligible.includes(r));
  const unmeasured = rows.filter((r) => !r.m);
  return [
    ...eligible.map((r) => ({ model: r.model, reason: `${r.m!.success}/${r.m!.tasks} verified fixes, median ${(r.m!.median_ms / 1000).toFixed(1)} s, about ${usd(estCostPerTask(r.m!))} per task (${r.m!.cost_basis})` })),
    ...measured.map((r) => ({ model: r.model, reason: `measured ${r.m!.success}/${r.m!.tasks}, which is below the ${MIN_RATE * 100}% over ${MIN_TASKS} tasks rule, so it is tried after the qualified models` })),
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
