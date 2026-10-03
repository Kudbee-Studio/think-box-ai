// One place that decides which local Ollama model the app uses, so the CLI, the server and the Think Token
// pipeline cannot disagree. Layer 1 (foundation): no network, no I/O.
//
// Precedence: THINKBOX_LOCAL_MODEL, then the older KUDBEE_LOCAL_MODEL, then DEFAULT_LOCAL_MODEL.
// The default is only a fallback name; the app never pulls models. Run `ollama list` and set
// THINKBOX_LOCAL_MODEL to a model you already have.

export const DEFAULT_LOCAL_MODEL = 'qwen2.5:1.5b' // P3.20 winner;

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

// A local Ollama model is a plain chat, exactly like `ollama run <model> "..."` in a terminal, where small models answer well: no system prompt, no
// tool list, default sampling. Telling a 360M model to "use the available plugins", or adding long instructions or a repeat penalty, made it invent a
// fake tool plan or answer with nothing. Only a reply cap (stops a runaway "0000000000") and a 2048 context (more of the model fits a 2 GiB GPU).
export const LOCAL_CHAT_OPTIONS = { num_predict: 512, num_ctx: 2048 };
