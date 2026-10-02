// One place that decides which local Ollama model the app uses, so the CLI, the server and the Think Token
// pipeline cannot disagree. Layer 1 (foundation): no network, no I/O.
//
// Precedence: THINKBOX_LOCAL_MODEL, then the older KUDBEE_LOCAL_MODEL, then DEFAULT_LOCAL_MODEL.
// The default is only a fallback name; the app never pulls models. Run `ollama list` and set
// THINKBOX_LOCAL_MODEL to a model you already have.

export const DEFAULT_LOCAL_MODEL = 'qwen2.5:1.5b';

export function resolveLocalModel(env: Record<string, string | undefined> = process.env): string {
  return (env.THINKBOX_LOCAL_MODEL || env.KUDBEE_LOCAL_MODEL || DEFAULT_LOCAL_MODEL).trim() || DEFAULT_LOCAL_MODEL;
}

/** Ollama lists an untagged pull as `name:latest`, so `smollm2` and `smollm2:latest` are the same installed model. */
export function sameLocalModel(configured: string, installed: string): boolean {
  const tagged = (n: string) => (n.includes(':') ? n : `${n}:latest`);
  return tagged(configured).toLowerCase() === tagged(installed).toLowerCase();
}

/** What to tell the operator when the configured local model is not in `ollama list`. Never suggests pulling as the only option. */
export function localModelHint(model: string): string {
  return `local model '${model}' not found in Ollama. Set THINKBOX_LOCAL_MODEL to a model from \`ollama list\` (or pull '${model}' yourself).`;
}
