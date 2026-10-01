// Model callers for Think Token extraction and challenge (ADR 029 P1). Layer 2 (providers).
//
// Preferred: Inception Mercury 2 with the key from INCEPTION_API_KEY_2. Fallback: the already-installed local Ollama
// model (THINKBOX_LOCAL_MODEL; see local-model.ts). Nothing here pulls a model.
//
// KEY HANDLING: the key is read from the environment at call time and used only for the Authorization header. It is never
// logged, stored or put in an error: every error message is scrubbed of the key first. Prompts leave the machine for
// Mercury, so callers pass text through sanitizeForModel (secrets and absolute paths removed, size capped).
import { localModelHint, resolveLocalModel } from './local-model.ts';
import { redact } from './think-token-store.ts';

export interface ModelMessage {
  role: 'system' | 'user';
  content: string;
}

export interface ModelResult {
  text: string;
  provider: 'mercury' | 'local';
  model: string;
  latency_ms: number;
  tokens_in: number;
  tokens_out: number;
}

export type ModelCaller = (messages: ModelMessage[], opts?: { maxTokens?: number }) => Promise<ModelResult>;

export interface TokenModels {
  mercury: ModelCaller | null;
  local: ModelCaller | null;
}

type Env = Record<string, string | undefined>;
type FetchLike = typeof fetch;

export const MAX_MODEL_INPUT_CHARS = 8000;
const CALL_TIMEOUT_MS = 30_000;

/** Remove secrets and machine-specific absolute paths, then cap the size, before text is sent to a model. */
export function sanitizeForModel(text: string, max: number = MAX_MODEL_INPUT_CHARS): string {
  const noPaths = redact(text)
    .replace(/\b[A-Za-z]:\\[^\s"'`<>|]+/g, '<path>')
    .replace(/(?:^|[\s"'`(=])((?:\/(?:home|Users|root|tmp|var|mnt|opt|etc|srv)\/)[^\s"'`)<>|]*)/g, (m, p) => m.replace(p, '<path>'));
  return noPaths.length > max ? `${noPaths.slice(0, max - 1)}…` : noPaths;
}

/** Strip a secret (and anything shaped like a bearer token) out of text that may reach logs, rows or events. */
export function scrubSecrets(text: string, secrets: Array<string | undefined>): string {
  let out = String(text);
  for (const secret of secrets) if (secret && secret.length >= 4) out = out.split(secret).join('[key]');
  return redact(out);
}

/** null when INCEPTION_API_KEY_2 is not set: the pipeline then falls back to the local model. */
export function createMercuryCaller(env: Env = process.env, fetchImpl: FetchLike = fetch): ModelCaller | null {
  if (!env.INCEPTION_API_KEY_2?.trim()) return null;
  return async (messages, opts = {}) => {
    const key = env.INCEPTION_API_KEY_2!.trim();
    const base = (env.INCEPTION_BASE_URL || 'https://api.inceptionlabs.ai/v1').replace(/\/$/, '');
    const model = env.THINKBOX_TOKEN_MODEL || 'mercury-2';
    const started = Date.now();
    let response: Response;
    try {
      response = await fetchImpl(`${base}/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${key}` },
        signal: AbortSignal.timeout(CALL_TIMEOUT_MS),
        body: JSON.stringify({ model, messages, temperature: 0.2, max_tokens: opts.maxTokens ?? 900 }),
      });
    } catch (err) {
      throw new Error(`mercury request failed: ${scrubSecrets(err instanceof Error ? err.name : 'error', [key])}`);
    }
    if (!response.ok) throw new Error(`mercury HTTP ${response.status}`);
    let body: any;
    try {
      body = await response.json();
    } catch {
      throw new Error('mercury returned a non-JSON body');
    }
    const text = body?.choices?.[0]?.message?.content;
    if (typeof text !== 'string' || !text.trim()) throw new Error('mercury returned no text');
    return {
      text,
      provider: 'mercury',
      model,
      latency_ms: Date.now() - started,
      tokens_in: Number(body?.usage?.prompt_tokens) || 0,
      tokens_out: Number(body?.usage?.completion_tokens) || 0,
    };
  };
}

/** The already-installed Ollama model. Reports a readable error (never pulls) when it is not installed or Ollama is down. */
export function createLocalCaller(env: Env = process.env, fetchImpl: FetchLike = fetch): ModelCaller {
  return async (messages, opts = {}) => {
    const base = (env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434').replace(/\/$/, '');
    const model = resolveLocalModel(env);
    const started = Date.now();
    let installed: boolean;
    try {
      const tags = await fetchImpl(`${base}/api/tags`, { signal: AbortSignal.timeout(3000) });
      const list = (await tags.json()) as { models?: Array<{ name?: string }> };
      installed = (list.models ?? []).some((m) => m.name === model);
    } catch {
      throw new Error('local model unavailable: Ollama is not reachable');
    }
    if (!installed) throw new Error(localModelHint(model));
    let body: any;
    try {
      const response = await fetchImpl(`${base}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: AbortSignal.timeout(CALL_TIMEOUT_MS),
        body: JSON.stringify({ model, stream: false, format: 'json', messages, options: { temperature: 0.2, num_predict: opts.maxTokens ?? 700 } }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      body = await response.json();
    } catch (err) {
      throw new Error(`local model call failed: ${err instanceof Error ? err.message.slice(0, 80) : 'error'}`);
    }
    const text = body?.message?.content;
    if (typeof text !== 'string' || !text.trim()) throw new Error('local model returned no text');
    return { text, provider: 'local', model, latency_ms: Date.now() - started, tokens_in: Number(body?.prompt_eval_count) || 0, tokens_out: Number(body?.eval_count) || 0 };
  };
}

export function createTokenModels(env: Env = process.env, fetchImpl: FetchLike = fetch): TokenModels {
  return { mercury: createMercuryCaller(env, fetchImpl), local: createLocalCaller(env, fetchImpl) };
}
