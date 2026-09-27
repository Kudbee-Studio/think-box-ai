// kudbEE Worker Agent — tool-calling loop over an OpenAI-compatible provider (Inception Mercury 2).
// Every tool is confined to the session workspace or to bounded HTTP(S) GETs; there is no shell access.
import fs from 'fs';
import path from 'path';

const INCEPTION_BASE_URL = process.env.INCEPTION_BASE_URL || 'https://api.inceptionlabs.ai/v1';
export const INCEPTION_MODELS = ['mercury-2'];

// USD per million tokens (Inception price list, /v1/models).
const MODEL_PRICING: Record<string, { input: number; output: number }> = {
  'mercury-2': { input: 0.25, output: 0.75 },
};

export function costUsd(model: string, promptTokens: number, completionTokens: number): number {
  const price = MODEL_PRICING[model];
  if (!price) return 0;
  return (promptTokens * price.input + completionTokens * price.output) / 1_000_000;
}

export function inceptionConfigured(): boolean {
  return Boolean(process.env.INCEPTION_API_KEY);
}

export function isInceptionModel(model: string): boolean {
  return INCEPTION_MODELS.includes(model);
}

interface ToolCall {
  id: string;
  type: 'function';
  function: { name: string; arguments: string };
}

interface AgentMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string | null;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
}

export type AgentEvent =
  | {
      kind: 'model';
      step: number;
      latency_ms: number;
      prompt_tokens: number;
      completion_tokens: number;
      cost_usd: number;
      tool_calls: string[];
      content: string;
    }
  | {
      kind: 'tool';
      step: number;
      name: string;
      args: Record<string, unknown>;
      ok: boolean;
      latency_ms: number;
      output: string;
      error?: string;
      approval?: 'approved' | 'denied';
      approval_reason?: string;
    };

export interface AgentHooks {
  workspace: string;
  resolvePath: (relativePath: string) => string;
  onThought: (thought: Record<string, unknown>) => void;
  onEvent: (event: AgentEvent) => void;
  onFilesChanged: () => void;
  signal: AbortSignal;
  /** Returns an error message when the spend budget is exhausted, otherwise null. */
  checkBudget: () => string | null;
  approvedDomains: Set<string>;
  requestApproval: (tool: string, args: Record<string, unknown>, reason: string) => Promise<boolean>;
  rssFeed: (url: string, limit: number) => Promise<Record<string, unknown>>;
}

export interface AgentRunResult {
  success: boolean;
  stopped?: boolean;
  result?: string;
  error?: string;
  steps: number;
  tool_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  tokens: number;
  cost_usd: number;
}

const TOOLS = [
  {
    type: 'function',
    function: {
      name: 'list_files',
      description: 'List files in the session workspace.',
      parameters: { type: 'object', properties: {}, required: [] },
    },
  },
  {
    type: 'function',
    function: {
      name: 'read_file',
      description: 'Read a UTF-8 text file from the session workspace.',
      parameters: {
        type: 'object',
        properties: { path: { type: 'string', description: 'Path relative to the workspace' } },
        required: ['path'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'write_file',
      description: 'Create or overwrite a text file in the session workspace. Use this to deliver reports, code and data.',
      parameters: {
        type: 'object',
        properties: {
          path: { type: 'string', description: 'Path relative to the workspace, e.g. report.md' },
          content: { type: 'string' },
        },
        required: ['path', 'content'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'fetch_url',
      description: 'HTTP GET a public web page or JSON API. Returns status and text (HTML tags stripped, truncated).',
      parameters: {
        type: 'object',
        properties: { url: { type: 'string', description: 'http(s) URL' } },
        required: ['url'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'read_rss',
      description: 'Fetch an RSS or Atom feed and return its latest items (title, url, date, summary).',
      parameters: {
        type: 'object',
        properties: { url: { type: 'string' }, limit: { type: 'number', description: 'Max items, default 10' } },
        required: ['url'],
      },
    },
  },
];

const SYSTEM_PROMPT = `You are kudbEE Worker, an autonomous agent inside kudbEE Agent OS.
You complete the user's goal by calling tools, not by describing what you would do.
- Your workspace is a private folder. Use list_files/read_file to inspect it and write_file to deliver results.
- Use fetch_url and read_rss to gather real, current information from the web. Never invent facts or URLs.
- When the goal asks for a report, summary, code or data, save it to a file with write_file.
- A human may deny a tool call. If denied, do not retry the same call; adapt or explain.
- Work in small steps. When finished, reply with a short summary of what you did and which files you created.`;

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}\n…[truncated ${text.length - max} chars]` : text;
}

function htmlToText(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/\s+/g, ' ')
    .trim();
}

export async function listWorkspace(root: string): Promise<Array<{ path: string; size: number }>> {
  const out: Array<{ path: string; size: number }> = [];
  async function walk(dir: string): Promise<void> {
    for (const entry of await fs.promises.readdir(dir, { withFileTypes: true })) {
      const abs = path.join(dir, entry.name);
      if (entry.isDirectory()) await walk(abs);
      else out.push({ path: path.relative(root, abs).replaceAll(path.sep, '/'), size: (await fs.promises.stat(abs)).size });
    }
  }
  await fs.promises.mkdir(root, { recursive: true });
  await walk(root);
  return out;
}

/** Keeps run records small: long string arguments (e.g. file contents) are clipped. */
function boundedArgs(args: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(args).map(([key, value]) => [key, typeof value === 'string' ? truncate(value, 1000) : value]));
}

function hostOf(rawUrl: unknown): string | null {
  try {
    return new URL(String(rawUrl)).hostname;
  } catch {
    return null;
  }
}

/** Governance gate: returns why a call needs human approval, or null when it may run. */
function approvalReason(name: string, args: Record<string, unknown>, hooks: AgentHooks): string | null {
  if (name === 'write_file') {
    try {
      if (fs.existsSync(hooks.resolvePath(String(args.path ?? '')))) return `Overwrites existing file ${args.path}`;
    } catch {
      return null; // Invalid paths are rejected by the tool itself.
    }
  }
  if (name === 'fetch_url' || name === 'read_rss') {
    const host = hostOf(args.url);
    if (host && !hooks.approvedDomains.has(host)) return `First network access to ${host} in this session`;
  }
  return null;
}

async function executeTool(name: string, args: Record<string, unknown>, hooks: AgentHooks): Promise<Record<string, unknown>> {
  switch (name) {
    case 'list_files':
      return { files: await listWorkspace(hooks.workspace) };
    case 'read_file': {
      const file = hooks.resolvePath(String(args.path ?? ''));
      const content = await fs.promises.readFile(file, 'utf8');
      return { path: args.path, content: truncate(content, 20000) };
    }
    case 'write_file': {
      const file = hooks.resolvePath(String(args.path ?? ''));
      const content = String(args.content ?? '');
      await fs.promises.mkdir(path.dirname(file), { recursive: true });
      await fs.promises.writeFile(file, content, 'utf8');
      hooks.onFilesChanged();
      return { path: args.path, bytes: Buffer.byteLength(content) };
    }
    case 'fetch_url': {
      const url = new URL(String(args.url ?? ''));
      if (!['http:', 'https:'].includes(url.protocol)) throw new Error('Only http(s) URLs are allowed');
      const response = await fetch(url, {
        headers: { 'User-Agent': 'kudbEE-Worker/1.0' },
        signal: AbortSignal.any([hooks.signal, AbortSignal.timeout(15000)]),
      });
      const raw = await response.text();
      const type = response.headers.get('content-type') ?? '';
      const text = type.includes('html') ? htmlToText(raw) : raw;
      return { url: url.toString(), status: response.status, content_type: type, text: truncate(text, 12000) };
    }
    case 'read_rss': {
      const limit = Math.min(Math.max(Number(args.limit) || 10, 1), 30);
      return hooks.rssFeed(String(args.url ?? ''), limit);
    }
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

async function chat(
  model: string,
  messages: AgentMessage[],
  temperature: number,
  signal: AbortSignal,
): Promise<{ message: AgentMessage; prompt: number; completion: number }> {
  const response = await fetch(`${INCEPTION_BASE_URL}/chat/completions`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${process.env.INCEPTION_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ model, messages, tools: TOOLS, temperature, max_tokens: 8000 }),
    signal: AbortSignal.any([signal, AbortSignal.timeout(90000)]),
  });
  if (!response.ok) {
    throw new Error(`Inception API HTTP ${response.status}: ${truncate(await response.text(), 300)}`);
  }
  const data = (await response.json()) as {
    choices: Array<{ message: AgentMessage }>;
    usage?: { prompt_tokens?: number; completion_tokens?: number };
  };
  return {
    message: data.choices[0].message,
    prompt: data.usage?.prompt_tokens ?? 0,
    completion: data.usage?.completion_tokens ?? 0,
  };
}

export async function runToolAgent(
  goal: string,
  model: string,
  maxIterations: number,
  temperature: number,
  history: Array<{ goal: string; result: string }>,
  hooks: AgentHooks,
): Promise<AgentRunResult> {
  const totals = { steps: 0, tool_calls: 0, prompt_tokens: 0, completion_tokens: 0, tokens: 0, cost_usd: 0 };
  const finish = (extra: Partial<AgentRunResult> & { success: boolean }): AgentRunResult => ({ ...totals, ...extra });

  if (!inceptionConfigured()) return finish({ success: false, error: 'INCEPTION_API_KEY is not set in .env' });

  const messages: AgentMessage[] = [{ role: 'system', content: SYSTEM_PROMPT }];
  for (const turn of history.slice(-5)) {
    messages.push({ role: 'user', content: turn.goal });
    messages.push({ role: 'assistant', content: turn.result });
  }
  messages.push({ role: 'user', content: goal });

  try {
    for (let step = 1; step <= maxIterations; step++) {
      if (hooks.signal.aborted) return finish({ success: false, stopped: true, error: 'Stopped by user' });
      const overBudget = hooks.checkBudget();
      if (overBudget) return finish({ success: false, error: overBudget });

      totals.steps = step;
      hooks.onThought({ type: 'reasoning', content: `Step ${step}: asking ${model}…`, status: 'thinking' });
      const startedAt = Date.now();
      const { message, prompt, completion } = await chat(model, messages, temperature, hooks.signal);
      const stepCost = costUsd(model, prompt, completion);
      totals.prompt_tokens += prompt;
      totals.completion_tokens += completion;
      totals.tokens += prompt + completion;
      totals.cost_usd += stepCost;
      messages.push({ role: 'assistant', content: message.content ?? null, tool_calls: message.tool_calls });
      hooks.onEvent({
        kind: 'model',
        step,
        latency_ms: Date.now() - startedAt,
        prompt_tokens: prompt,
        completion_tokens: completion,
        cost_usd: stepCost,
        tool_calls: (message.tool_calls ?? []).map((call) => call.function.name),
        content: truncate(message.content ?? '', 2000),
      });

      if (!message.tool_calls?.length) {
        const answer = message.content?.trim() || '(no answer)';
        hooks.onThought({
          type: 'answer',
          content: `Finished in ${step} step(s), ${totals.tool_calls} tool call(s), ${totals.tokens} tokens, $${totals.cost_usd.toFixed(5)}`,
          status: 'success',
        });
        return finish({ success: true, result: answer });
      }

      if (message.content?.trim()) hooks.onThought({ type: 'plan', content: message.content.trim(), status: 'info' });
      hooks.onThought({
        type: 'reasoning',
        content: `Model replied in ${Date.now() - startedAt}ms → ${message.tool_calls.map((call) => call.function.name).join(', ')}`,
        status: 'info',
      });

      for (const call of message.tool_calls) {
        totals.tool_calls++;
        const toolStartedAt = Date.now();
        let args: Record<string, unknown> = {};
        let output: Record<string, unknown>;
        let approval: 'approved' | 'denied' | undefined;
        let reason: string | null = null;
        try {
          args = JSON.parse(call.function.arguments || '{}') as Record<string, unknown>;
          hooks.onThought({ type: 'tool_call', plugin: call.function.name, content: `${call.function.name} ${truncate(JSON.stringify(args), 200)}`, status: 'running' });
          reason = approvalReason(call.function.name, args, hooks);
          if (reason) {
            hooks.onThought({ type: 'approval', content: `Waiting for approval: ${reason}`, status: 'thinking' });
            approval = (await hooks.requestApproval(call.function.name, args, reason)) ? 'approved' : 'denied';
            if (approval === 'denied') throw new Error(`Denied by human reviewer (${reason})`);
            const host = hostOf(args.url);
            if (host) hooks.approvedDomains.add(host);
          }
          output = { ok: true, ...(await executeTool(call.function.name, args, hooks)) };
          hooks.onThought({ type: 'tool_result', plugin: call.function.name, content: `${call.function.name} ✓ ${truncate(JSON.stringify(output), 200)}`, status: 'success' });
        } catch (err) {
          if (hooks.signal.aborted) return finish({ success: false, stopped: true, error: 'Stopped by user' });
          const error = err instanceof Error ? err.message : String(err);
          output = { ok: false, error };
          hooks.onThought({ type: 'tool_result', plugin: call.function.name, content: `${call.function.name} ✗ ${error}`, status: 'error' });
        }
        hooks.onEvent({
          kind: 'tool',
          step,
          name: call.function.name,
          args: boundedArgs(args),
          ok: output.ok === true,
          latency_ms: Date.now() - toolStartedAt,
          output: truncate(JSON.stringify(output), 1500),
          error: output.ok === true ? undefined : String(output.error),
          approval,
          approval_reason: reason ?? undefined,
        });
        messages.push({ role: 'tool', tool_call_id: call.id, content: truncate(JSON.stringify(output), 15000) });
      }
    }
  } catch (err) {
    if (hooks.signal.aborted) return finish({ success: false, stopped: true, error: 'Stopped by user' });
    return finish({ success: false, error: err instanceof Error ? err.message : String(err) });
  }

  return finish({ success: false, error: `Reached the ${maxIterations}-step limit without finishing` });
}
