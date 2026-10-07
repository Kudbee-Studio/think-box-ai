// Ollama chat/model listing and the optional Janus image service client. Moved out of server.ts unchanged; the base URLs and the
// Janus switch, which were module constants there, are passed in.
import { configuredCloudModels } from './agent.ts';
import { CLOUD_MEASUREMENTS, MEASUREMENT_ALIASES, estCostPerTask } from './cloud-routing.ts';
import { LOCAL_CHAT_OPTIONS } from './local-model.ts';
import { parseOllamaLine } from './ollama-line.ts';
import { errorMessage, type ChatMessage, type OllamaTokenMessage } from './types.ts';

export interface OllamaTag {
  name: string;
  [key: string]: unknown;
}

export interface OllamaChatTurn {
  content: string;
  tool_calls: Array<{ function?: { name?: unknown; arguments?: unknown } }>;
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number;
  /** Milliseconds Ollama spent loading the model for this call (0 when it was already loaded): a cold start shows up here, not in generation. */
  load_ms?: number;
  error?: string;
}

export interface ModelClientConfig {
  ollamaBaseUrl: string;
  janusBaseUrl: string;
  janusEnabled: () => boolean;
}

export function createModelClients({ ollamaBaseUrl, janusBaseUrl, janusEnabled }: ModelClientConfig) {
  async function listOllamaModels(): Promise<OllamaTag[]> {
    try {
      const res = await fetch(`${ollamaBaseUrl}/api/tags`, { signal: AbortSignal.timeout(3000) });
      const data = (await res.json()) as { models?: OllamaTag[] };
      return (data.models ?? []).map((m) => ({ ...m, provider: 'ollama' }));
    } catch {
      return [];
    }
  }

  async function requestJanus(endpoint: 'analyze' | 'generate', payload: Record<string, string>): Promise<Record<string, string>> {
    if (!janusEnabled()) {
      throw new Error('Janus image service is disabled (set KUDBEE_JANUS_ENABLED=1 on loopback only)');
    }
    const response = await fetch(`${janusBaseUrl}/${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(10 * 60 * 1000),
    });
    const result = await response.json() as Record<string, string>;
    if (!response.ok) throw new Error(result.detail || `Janus service returned HTTP ${response.status}`);
    return result;
  }

  async function listModels(): Promise<OllamaTag[]> {
    // Each cloud agent carries what was measured for it (verified fixes, cost per task, time) so the dashboard can show it; absent when the model was never measured.
    const measured = (name: string) => { const m = CLOUD_MEASUREMENTS.find((x) => x.model === (MEASUREMENT_ALIASES[name] ?? name)); return m ? { verified: m.success, tasks: m.tasks, usd: estCostPerTask(m), secs: Math.round(m.median_ms / 100) / 10, estimated: m.cost_basis === 'tokens at an estimated price' } : undefined; };
    const cloud = configuredCloudModels().map((m) => ({ name: m.name, provider: m.provider, vendor: m.vendor, agent: true, measured: measured(m.name) }));
    return [...cloud, ...(await listOllamaModels())];
  }

  async function streamOllama(
    model: string,
    messages: ChatMessage[],
    onToken: (token: string) => void,
    onDone: (result: OllamaTokenMessage) => void,
  ): Promise<void> {
    try {
      const res = await fetch(`${ollamaBaseUrl}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model, messages, stream: true, options: LOCAL_CHAT_OPTIONS }),
      });

      // Ollama answers a missing model (and other failures) with a non-2xx status and {"error": "..."}; without this check that
      // looked like an empty successful reply.
      if (!res.ok) {
        const text = await res.text().catch(() => '');
        let detail = text.trim().slice(0, 300);
        try { const parsed = JSON.parse(text.split('\n')[0] ?? '') as { error?: unknown }; if (parsed?.error) detail = String(parsed.error); } catch { /* not JSON: keep the text */ }
        throw new Error(`Ollama returned HTTP ${res.status}${detail ? `: ${detail}` : ''}`);
      }
      if (!res.body) {
        throw new Error('Ollama response has no body');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let finished = false;
      const handle = (line: string) => {
        const json = parseOllamaLine<OllamaTokenMessage>(line);
        if (!json) return;
        if (json.error) throw new Error(String(json.error)); // Ollama reports a failure mid-stream as an {"error": ...} line
        if (json.message?.content) {
          onToken(json.message.content);
        }
        if (json.done) {
          finished = true;
          onDone(json);
        }
      };

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) handle(line);
      }
      if (buffer.trim()) handle(buffer); // a last line with no trailing newline still counts
      if (!finished) throw new Error('Ollama ended the response without finishing it');
    } catch (err) {
      const message = errorMessage(err);
      onToken(`[Error: ${message}]`);
      onDone({ error: message });
    }
  }

  const capabilityCache = new Map<string, string[]>();
  /** What Ollama says the model can do (`completion`, `tools`, `vision` ...). Empty when Ollama or the model cannot be reached; cached per model. */
  async function modelCapabilities(model: string): Promise<string[]> {
    const hit = capabilityCache.get(model);
    if (hit) return hit;
    try {
      const res = await fetch(`${ollamaBaseUrl}/api/show`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model }), signal: AbortSignal.timeout(5000) });
      if (!res.ok) return [];
      const data = (await res.json()) as { capabilities?: unknown };
      const caps = Array.isArray(data.capabilities) ? data.capabilities.map(String) : [];
      capabilityCache.set(model, caps);
      return caps;
    } catch {
      return [];
    }
  }

  /**
   * One non-streaming chat turn that may carry native `tools` or a constrained `format` (JSON schema). Returns the raw message, any tool calls, and the
   * measured token counts and time; never throws (a failure is `error`).
   */
  async function chatOnce(model: string, messages: unknown[], opts: { tools?: unknown[]; format?: unknown; signal?: AbortSignal; timeoutMs?: number; numPredict?: number; seed?: number } = {}): Promise<OllamaChatTurn> {
    const startedAt = Date.now();
    try {
      const res = await fetch(`${ollamaBaseUrl}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model, messages, stream: false, ...(opts.tools ? { tools: opts.tools } : {}), ...(opts.format ? { format: opts.format } : {}), options: { ...LOCAL_CHAT_OPTIONS, num_predict: opts.numPredict ?? 256, temperature: 0, ...(opts.seed !== undefined ? { seed: opts.seed } : {}) } }),
        signal: AbortSignal.any([...(opts.signal ? [opts.signal] : []), AbortSignal.timeout(opts.timeoutMs ?? 240_000)]),
      });
      const text = await res.text();
      let body: any = {};
      try { body = JSON.parse(text); } catch { /* handled below */ }
      if (!res.ok || body.error) return { content: '', tool_calls: [], prompt_tokens: 0, completion_tokens: 0, latency_ms: Date.now() - startedAt, error: String(body.error ?? `Ollama returned HTTP ${res.status}: ${text.slice(0, 200)}`) };
      return {
        content: String(body.message?.content ?? ''),
        tool_calls: Array.isArray(body.message?.tool_calls) ? body.message.tool_calls : [],
        prompt_tokens: Number(body.prompt_eval_count) || 0,
        completion_tokens: Number(body.eval_count) || 0,
        latency_ms: Date.now() - startedAt,
        load_ms: Math.round((Number(body.load_duration) || 0) / 1e6),
      };
    } catch (err) {
      return { content: '', tool_calls: [], prompt_tokens: 0, completion_tokens: 0, latency_ms: Date.now() - startedAt, error: errorMessage(err) };
    }
  }
  return { listOllamaModels, requestJanus, listModels, streamOllama, modelCapabilities, chatOnce };
}
