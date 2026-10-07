// The measured results of the cloud models (the evidence behind routing and the model list shown to people). Data only, no imports, so the CLI can show it without loading the agent.
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
