// Mercury (OpenAI-compatible) behind the same `LocalChat` interface the governed tool loop uses for Ollama models (Layer 2: provider). With it the
// escalation lane runs the SAME loop, tools, grounding validator, absence engine and disk re-read as the local lane; only the model that answers differs.
// The loop speaks Ollama's message shape (tool arguments as an object, tool replies keyed by name), so this converts both ways. Only the first tool call
// of a turn is returned, because the loop answers one call per turn and an OpenAI-style server refuses a history with an unanswered call id.
import { costUsd } from './agent.ts';
import type { LocalChat } from './local-tools.ts';
import type { OllamaChatTurn } from './ollama-client.ts';

const DEFAULT_BASE_URL = 'https://api.inceptionlabs.ai/v1';
const CALL_TIMEOUT_MS = 90_000;

type LoopMessage = { role?: unknown; content?: unknown; tool_calls?: Array<{ function?: { name?: unknown; arguments?: unknown } }> };

/** Ollama-shaped loop history to OpenAI chat messages: tool calls get ids, arguments become JSON text, each tool reply answers the call before it. */
export function toOpenAiMessages(messages: unknown[]): Array<Record<string, unknown>> {
  const out: Array<Record<string, unknown>> = [];
  let pending: string[] = [];
  let n = 0;
  for (const raw of messages) {
    const m = raw as LoopMessage;
    const content = typeof m.content === 'string' ? m.content : '';
    if (m.role === 'assistant' && m.tool_calls?.length) {
      const call = m.tool_calls[0]!;
      const id = `call_${++n}`;
      pending = [id];
      const args = call.function?.arguments;
      out.push({ role: 'assistant', content: content || null, tool_calls: [{ id, type: 'function', function: { name: String(call.function?.name), arguments: typeof args === 'string' ? args : JSON.stringify(args ?? {}) } }] });
    } else if (m.role === 'tool') {
      out.push({ role: 'tool', tool_call_id: pending.shift() ?? `call_${n}`, content });
    } else {
      out.push({ role: String(m.role), content });
    }
  }
  return out;
}

export interface MercuryChatOptions {
  apiKey?: () => string | undefined;
  baseUrl?: () => string;
  fetchImpl?: typeof fetch;
}

export function createMercuryChat(opts: MercuryChatOptions = {}): LocalChat {
  const apiKey = opts.apiKey ?? ((): string | undefined => process.env.INCEPTION_API_KEY);
  const baseUrl = opts.baseUrl ?? ((): string => process.env.INCEPTION_BASE_URL || DEFAULT_BASE_URL);
  const doFetch = opts.fetchImpl ?? fetch;
  const failed = (error: string, started: number): OllamaChatTurn => ({ content: '', tool_calls: [], prompt_tokens: 0, completion_tokens: 0, latency_ms: Date.now() - started, error });
  return {
    // The escalation lane needs native tool calls; Mercury has them.
    modelCapabilities: async () => ['tools'],
    chatOnce: async (model, messages, o = {}) => {
      const started = Date.now();
      const key = apiKey();
      if (!key) return failed('INCEPTION_API_KEY is not set', started);
      try {
        const res = await doFetch(`${baseUrl()}/chat/completions`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ model, messages: toOpenAiMessages(messages), ...(o.tools?.length ? { tools: o.tools } : {}), temperature: 0, max_tokens: 4000 }),
          signal: AbortSignal.any([...(o.signal ? [o.signal] : []), AbortSignal.timeout(o.timeoutMs ?? CALL_TIMEOUT_MS)]),
        });
        if (!res.ok) return failed(`Inception API HTTP ${res.status}: ${(await res.text()).slice(0, 200)}`, started);
        const data = (await res.json()) as { choices?: Array<{ message?: { content?: string | null; tool_calls?: Array<{ function?: { name?: string; arguments?: string } }> } }>; usage?: { prompt_tokens?: number; completion_tokens?: number } };
        const message = data.choices?.[0]?.message;
        if (!message) return failed('Inception API returned no choices', started);
        const first = message.tool_calls?.[0]?.function;
        return {
          content: message.content ?? '',
          tool_calls: first ? [{ function: { name: first.name, arguments: first.arguments ?? '{}' } }] : [],
          prompt_tokens: data.usage?.prompt_tokens ?? 0,
          completion_tokens: data.usage?.completion_tokens ?? 0,
          latency_ms: Date.now() - started,
        };
      } catch (err) {
        return failed(err instanceof Error ? err.message : String(err), started);
      }
    },
  };
}

/** What a loop run cost on `model`, from the token counts the provider reported. */
export const loopCostUsd = (model: string, r: { prompt_tokens: number; completion_tokens: number }): number => costUsd(model, r.prompt_tokens, r.completion_tokens);
