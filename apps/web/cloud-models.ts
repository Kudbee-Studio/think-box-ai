// The cloud worker-agent registry: which cloud models exist, their endpoint, key variable, label and (estimated) price. No imports, so routing and the agent loop can both use it.
/** A cloud model the worker agent can run on. Both speak the OpenAI-compatible chat API; only the endpoint, the key and the price differ. */
export interface CloudModel { name: string; provider: 'inception' | 'deepseek' | 'xai'; vendor: string; keyEnv: string; baseUrlEnv: string; baseUrlDefault: string }
export const CLOUD_MODELS: CloudModel[] = [
  { name: 'mercury-2', provider: 'inception', vendor: 'Inception', keyEnv: 'INCEPTION_API_KEY', baseUrlEnv: 'INCEPTION_BASE_URL', baseUrlDefault: 'https://api.inceptionlabs.ai/v1' },
  { name: 'deepseek-flash', provider: 'deepseek', vendor: 'DeepSeek', keyEnv: 'DEEPSEEK_API_KEY', baseUrlEnv: 'DEEPSEEK_BASE_URL', baseUrlDefault: 'https://api.deepseek.com/v1' },
  { name: 'grok-4.3', provider: 'xai', vendor: 'xAI', keyEnv: 'XAI_API_KEY', baseUrlEnv: 'XAI_BASE_URL', baseUrlDefault: 'https://api.x.ai/v1' },
];
export const MERCURY = CLOUD_MODELS[0]!;

// USD per million tokens. mercury-2: Inception price list (/v1/models). deepseek-flash and grok-4.3: conservative ESTIMATES (not read from the providers' price pages), so budgets err on the side of stopping early; replace with the exact rates.
export const MODEL_PRICING: Record<string, { input: number; output: number }> = {
  'mercury-2': { input: 0.25, output: 0.75 },
  'deepseek-flash': { input: 0.30, output: 1.20 },
  'grok-4.3': { input: 3.00, output: 15.00 },
};

export function costUsd(model: string, promptTokens: number, completionTokens: number): number {
  const price = MODEL_PRICING[model];
  if (!price) return 0;
  return (promptTokens * price.input + completionTokens * price.output) / 1_000_000;
}

export const cloudModel = (model: string): CloudModel | undefined => CLOUD_MODELS.find((m) => m.name === model);
/** A model name outside the registry (an experiment's alias) keeps the original behaviour: Inception's endpoint and key. */
export const cloudOrMercury = (model: string): CloudModel => cloudModel(model) ?? MERCURY;

export function isCloudModel(model: string): boolean {
  return cloudModel(model) !== undefined;
}

/** The provider label recorded on a run for this model. */
export function providerOf(model: string): string {
  return cloudModel(model)?.provider ?? 'ollama';
}

export function cloudConfigured(model: string): boolean {
  return Boolean(process.env[cloudOrMercury(model).keyEnv]);
}

export function inceptionConfigured(): boolean {
  return cloudConfigured(MERCURY.name);
}

/** The cloud worker-agent models whose key is set, in registry order. */
export function configuredCloudModels(): CloudModel[] {
  return CLOUD_MODELS.filter((m) => cloudConfigured(m.name));
}

export const cloudBaseUrl = (model: string): string => { const m = cloudOrMercury(model); return process.env[m.baseUrlEnv] || m.baseUrlDefault; };
