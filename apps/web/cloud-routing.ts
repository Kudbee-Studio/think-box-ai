// Which cloud worker-agent model to use, and what to do when its provider fails. The ranking comes from MEASURED runs (the P3.48-P3.52 SIMULATE experiments:
// verified-fix rate; median cost, time and tokens per task, with the cost basis stated: xAI's billed cost, a price list, or an estimate); it never claims a number it does not have. Failover only
// happens when the provider failed before the run did anything (no completed model call, no tool call), so a retry can never repeat a side effect.
import { runToolAgent, type AgentHooks, type AgentRunResult } from './agent.ts';
import { configuredCloudModels } from './cloud-models.ts';

import { CLOUD_MEASUREMENTS, MEASUREMENT_ALIASES, MIN_RATE, MIN_TASKS, estCostPerTask, type CloudMeasurement } from './cloud-measurements.ts';
export { CLOUD_MEASUREMENTS, MEASUREMENT_ALIASES, MIN_RATE, MIN_TASKS, estCostPerTask, type CloudMeasurement };

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
