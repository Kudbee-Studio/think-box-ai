// One place that decides which local Ollama model the app uses, so the CLI, the server and the Think Token
// pipeline cannot disagree. Layer 1 (foundation): no network, no I/O.
//
// Precedence: THINKBOX_LOCAL_MODEL, then the older KUDBEE_LOCAL_MODEL, then DEFAULT_LOCAL_MODEL.
// The default is only a fallback name; the app never pulls models. Run `ollama list` and set
// THINKBOX_LOCAL_MODEL to a model you already have.

export const DEFAULT_LOCAL_MODEL = 'qwen2.5:1.5b';

// 'smollm2' is a legacy alias kept for anyone with older config referencing the earlier model name.
const LEGACY_ALIASES: Record<string, string> = { smollm2: DEFAULT_LOCAL_MODEL, 'smollm2:135m': DEFAULT_LOCAL_MODEL };

export function resolveLocalModel(env: Record<string, string | undefined> = process.env): string {
  const raw = (env.THINKBOX_LOCAL_MODEL || env.KUDBEE_LOCAL_MODEL || DEFAULT_LOCAL_MODEL).trim() || DEFAULT_LOCAL_MODEL;
  return LEGACY_ALIASES[raw.toLowerCase()] || raw;
}

/** What to tell the operator when the configured local model is not in `ollama list`. Never suggests pulling as the only option. */
export function localModelHint(model: string): string {
  return `local model '${model}' not found in Ollama. Set THINKBOX_LOCAL_MODEL to a model from \`ollama list\` (or pull '${model}' yourself).`;
}
