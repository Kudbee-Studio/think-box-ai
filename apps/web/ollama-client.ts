// Ollama chat/model listing and the optional Janus image service client. Moved out of server.ts unchanged; the base URLs and the
// Janus switch, which were module constants there, are passed in.
import { INCEPTION_MODELS, inceptionConfigured } from './agent.ts';
import { LOCAL_CHAT_OPTIONS } from './local-model.ts';
import { parseOllamaLine } from './ollama-line.ts';
import { errorMessage, type ChatMessage, type OllamaTokenMessage } from './types.ts';

export interface OllamaTag {
  name: string;
  [key: string]: unknown;
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
    const cloud = inceptionConfigured()
      ? INCEPTION_MODELS.map((name) => ({ name, provider: 'inception', agent: true }))
      : [];
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
  return { listOllamaModels, requestJanus, listModels, streamOllama };
}
