// Hermetic stand-in for the Inception OpenAI-compatible API (and a tiny web page for fetch_url tests).
// Each POST /v1/chat/completions pops the next scripted reply; requests are recorded for assertions.
import http from 'node:http';
import type { AddressInfo } from 'node:net';

export interface ScriptedReply {
  content?: string | null;
  tool_calls?: Array<{ name: string; args: Record<string, unknown> | string }>;
  status?: number;
  /** HTTP 200 whose body has no usable choices (some providers do this instead of an error status). */
  noChoices?: boolean;
  delayMs?: number;
  usage?: { prompt_tokens: number; completion_tokens: number };
}

export interface MockInception {
  baseUrl: string;
  pageUrl: string;
  origin: string;
  requests: Array<{ messages: Array<{ role: string; content: string | null; tool_call_id?: string }>; tools: unknown[] }>;
  script(replies: ScriptedReply[]): void;
  close(): Promise<void>;
}

export const say = (content: string): ScriptedReply => ({ content });
export const call = (name: string, args: Record<string, unknown> | string = {}): ScriptedReply => ({ tool_calls: [{ name, args }] });

export async function startMockInception(): Promise<MockInception> {
  let queue: ScriptedReply[] = [];
  let callId = 0;
  const requests: MockInception['requests'] = [];

  const server = http.createServer((req, res) => {
    if (req.method === 'GET' && req.url === '/page') {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end('<html><body><h1>Mock Page</h1><p>The answer is 42.</p></body></html>');
      return;
    }
    // Live-state endpoints for the evidence-beats-memory regression tests: nothing open, no CI runs, server down.
    if (req.method === 'GET' && req.url === '/api/pulls') { res.writeHead(200, { 'Content-Type': 'application/json' }); res.end('[]'); return; }
    if (req.method === 'GET' && req.url === '/api/ci') { res.writeHead(200, { 'Content-Type': 'application/json' }); res.end('{"total_count":0,"workflow_runs":[]}'); return; }
    if (req.method === 'GET' && req.url === '/api/missing') { res.writeHead(404, { 'Content-Type': 'application/json' }); res.end('{"message":"Not Found"}'); return; }
    if (req.method === 'GET' && req.url === '/api/pulls-page') { res.writeHead(200, { 'Content-Type': 'text/html' }); res.end('<html><body>Pull requests Open 0 Closed 304</body></html>'); return; }
    if (req.method === 'GET' && req.url === '/api/health') { res.writeHead(503, { 'Content-Type': 'text/plain' }); res.end('service unavailable'); return; }
    if (req.method === 'POST' && req.url === '/v1/chat/completions') {
      let body = '';
      req.on('data', (chunk) => (body += chunk));
      req.on('end', () => {
        requests.push(JSON.parse(body));
        const reply = queue.shift() ?? { content: '(script exhausted)' };
        const send = () => {
          if (reply.status && reply.status !== 200) {
            res.writeHead(reply.status, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: { message: 'mock failure' } }));
            return;
          }
          if (reply.noChoices) {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ choices: [], error: { message: 'mock empty' } }));
            return;
          }
          const tool_calls = reply.tool_calls?.map((tc) => ({
            id: `call_${++callId}`,
            type: 'function',
            function: { name: tc.name, arguments: typeof tc.args === 'string' ? tc.args : JSON.stringify(tc.args) },
          }));
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(
            JSON.stringify({
              choices: [{ message: { role: 'assistant', content: reply.content ?? null, tool_calls }, finish_reason: tool_calls ? 'tool_calls' : 'stop' }],
              usage: reply.usage ?? { prompt_tokens: 1000, completion_tokens: 100 },
            }),
          );
        };
        if (reply.delayMs) setTimeout(send, reply.delayMs);
        else send();
      });
      return;
    }
    res.writeHead(404);
    res.end();
  });

  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address() as AddressInfo;
  return {
    baseUrl: `http://127.0.0.1:${port}/v1`,
    pageUrl: `http://127.0.0.1:${port}/page`,
    origin: `http://127.0.0.1:${port}`,
    requests,
    script(replies) {
      queue = [...replies];
      requests.length = 0;
    },
    close: () =>
      new Promise((resolve) => {
        server.closeAllConnections();
        server.close(() => resolve());
      }),
  };
}
