// kudbEE Worker Agent — tool-calling loop over an OpenAI-compatible provider (Inception Mercury 2).
// Every tool is confined to the session workspace or to bounded HTTP(S) GETs; there is no shell access.
import fs from 'fs';
import path from 'path';
import { ALGORAND_ACTIONS, algorandHost, algorandQuery, parseAction, parseNetwork, validateAlgorandInput } from './algorand.ts';
import { EVIDENCE_JUDGE_SYSTEM, EVIDENCE_RULE, conflictCandidate, parseJudge, supersededFlags, type ToolEvidence } from './evidence.ts';
import { MEDICATION_ACTIONS, MEDICATION_SECTIONS, medicationQuery, validateMedicationInput } from './medication.ts';

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
  /** Optional per-run endpoint override, primarily for isolated runtimes and tests. */
  apiBaseUrl?: string;
  resolvePath: (relativePath: string) => string;
  onThought: (thought: Record<string, unknown>) => void;
  onEvent: (event: AgentEvent) => void;
  onFilesChanged: () => void;
  signal: AbortSignal;
  /** Returns an error message when the spend budget is exhausted, otherwise null. */
  checkBudget: () => string | null;
  approvedDomains: Set<string>;
  requestApproval: (tool: string, args: Record<string, unknown>, reason: string) => Promise<boolean>;
  remember: (title: string, content: string, tags: string[]) => Promise<Record<string, unknown>>;
  recall: (query: string, limit: number) => Promise<Record<string, unknown>>;
  rssFeed: (url: string, limit: number) => Promise<Record<string, unknown>>;
  /** When set, restricts this run to a named tool subset (see AGENT_PROFILES). A hallucinated
   *  or otherwise disallowed tool call is rejected before it ever reaches the approval gate —
   *  the model isn't even offered the tool in its function list, but this is the hard backstop. */
  allowedTools?: string[];
  /** Additional role context for a contract-backed specialist run. */
  roleContext?: string;
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
  /** Set when the final-answer check found the answer contradicting this run's own tool results (what the tools said, one sentence each). */
  evidence_conflicts?: string[];
}

export const TOOLS = [
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
  {
    type: 'function',
    function: {
      name: 'algorand',
      description:
        'Read-only Algorand blockchain lookups via public nodes (no wallet, cannot sign or send). ' +
        'Actions: status; account (address: balance, holdings); asset (id); application (id: creator, decoded global state); ' +
        'transaction (txid); account_transactions (address, limit). Default network testnet.',
      parameters: {
        type: 'object',
        properties: {
          action: { type: 'string', enum: [...ALGORAND_ACTIONS] },
          network: { type: 'string', enum: ['testnet', 'mainnet'] },
          address: { type: 'string', description: '58-character Algorand address' },
          id: { type: 'string', description: 'Asset or application id' },
          txid: { type: 'string', description: '52-character transaction id' },
          limit: { type: 'number' },
        },
        required: ['action'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'medication',
      description:
        'Read-only medication label lookups via the public openFDA API (FDA-approved drug labeling; no key). ' +
        'This does NOT compute or verify whether two drugs interact — it only returns each drug\'s own label ' +
        'section (drug_interactions, boxed_warning, contraindications, or warnings_and_cautions). ' +
        'Actions: lookup (drug, section?) — one drug\'s label section; ' +
        'compare (drugs: 2-5 names, section?) — the same section for several drugs side by side, for a human ' +
        'to compare — never state a drug combination is safe or unsafe yourself; always tell the user to confirm ' +
        'with a licensed pharmacist or physician.',
      parameters: {
        type: 'object',
        properties: {
          action: { type: 'string', enum: [...MEDICATION_ACTIONS] },
          drug: { type: 'string', description: 'Generic or brand drug name (for action: lookup)' },
          drugs: { type: 'array', items: { type: 'string' }, description: '2-5 generic or brand drug names (for action: compare)' },
          section: { type: 'string', enum: [...MEDICATION_SECTIONS], description: 'Defaults to drug_interactions' },
        },
        required: ['action'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'recall',
      description: 'Search long-term memory (verified knowledge, organizational notes, past runs) for anything relevant.',
      parameters: {
        type: 'object',
        properties: { query: { type: 'string' }, limit: { type: 'number', description: 'Max results, default 5' } },
        required: ['query'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'remember',
      description:
        'Save a durable, reusable lesson or fact to organizational memory (e.g. a reliable data source, a user preference, a pitfall to avoid). Only store things you observed or were told — never guesses. A human reviews and may promote it to verified knowledge.',
      parameters: {
        type: 'object',
        properties: {
          title: { type: 'string', description: 'Short, specific title' },
          content: { type: 'string', description: 'The lesson or fact' },
          evidence: { type: 'string', description: 'Where you observed it in this run (URL, file, tool result) or "user said"' },
          tags: { type: 'array', items: { type: 'string' } },
        },
        required: ['title', 'content', 'evidence'],
      },
    },
  },
];

// Named tool-scoped agent lanes. A profile restricts which tools a run may call — enforced both
// by filtering the function list sent to the model (chat()) and, as a hard backstop, by rejecting
// any disallowed tool_call before it reaches the approval gate (see the dispatch loop below).
export interface AgentProfile {
  name: string;
  description: string;
  allowedTools: string[];
  roleContext: string;
}

export const HERMES_ALLOWED_TOOLS = ['algorand', 'recall', 'remember'];

export const ASCLEPIUS_ALLOWED_TOOLS = ['medication', 'recall', 'remember'];

export const AGENT_PROFILES: Record<string, AgentProfile> = {
  hermes: {
    name: 'HERMES',
    description: 'Algorand read-only research assistant — chain queries + memory, no wallet or signing',
    allowedTools: HERMES_ALLOWED_TOOLS,
    roleContext:
      'You are HERMES, an Algorand research assistant. You may only look things up (account balances, ' +
      'assets, applications, transactions via the algorand tool) and save/recall research notes via ' +
      'remember/recall. You have no wallet, no private keys, and cannot sign or send anything — if asked ' +
      'to sign a transaction, send funds, import a mnemonic, or do anything else outside chain lookups and ' +
      'note-taking, refuse and explain that wallet/signing support is a deliberately separate, deferred ' +
      'capability pending an explicit founder decision on wallet strategy.',
  },
  asclepius: {
    name: 'ASCLEPIUS',
    description: 'Medication label research assistant — openFDA label lookups + memory, never a safety verdict',
    allowedTools: ASCLEPIUS_ALLOWED_TOOLS,
    roleContext:
      'You are ASCLEPIUS, a medication label research assistant. You may only look up FDA-approved drug label ' +
      'sections via the medication tool (drug_interactions, boxed_warning, contraindications, ' +
      'warnings_and_cautions) and save/recall research notes via remember/recall. ' +
      'CRITICAL SAFETY RULE: the medication tool returns each drug\'s OWN label text — it does not compute or ' +
      'verify whether specific drugs interact with each other. You must NEVER tell a user that a combination ' +
      'of medications is "safe", "fine", "not a problem", or conversely definitively "dangerous" — you are not ' +
      'a pharmacist and label text for drug A was not written with knowledge of the user\'s specific drug B. ' +
      'When comparing drugs, present what each label actually says (quote or closely paraphrase it), note ' +
      'anything that mentions the other drug or its drug class, and always end by telling the user to confirm ' +
      'with a licensed pharmacist or physician before making any medication decision. If asked for dosing, ' +
      'diagnosis, or treatment advice, decline and redirect to a healthcare professional — that is out of scope ' +
      'for a label-lookup tool.',
  },
};

const SYSTEM_PROMPT = `You are kudbEE Worker, an autonomous agent inside kudbEE Agent OS.
You complete the user's goal by calling tools, not by describing what you would do.
- Your workspace is a private folder. Use list_files/read_file to inspect it and write_file to deliver results.
  If list_files returns an empty list the workspace is empty: do not read_file guessed names like pr_status.md; work from the tool results you already have.
- Use fetch_url and read_rss to gather real, current information from the web. Never invent facts or URLs.
- When the goal asks for a report, summary, code or data, save it to a file with write_file.
- A human may deny a tool call. If denied, do not retry the same call; adapt or explain.
- You have long-term memory. Relevant memories may be listed below; use recall to search for more.
  VERIFIED items are trusted; ORG items are unverified notes with evidence. PAST RUN items only record what an
  earlier run did — an earlier answer is NOT evidence and may have been wrong. Prefer VERIFIED, then ORG.
  If memory does not settle the question, say so instead of guessing.
- When you learn something reusable (a reliable source, a user preference, a mistake to avoid), save it with remember.
- ${EVIDENCE_RULE}
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

function algorandTarget(args: Record<string, unknown>): string | null {
  try {
    validateAlgorandInput(args);
    return algorandHost(parseAction(args.action), parseNetwork(args.network));
  } catch {
    return null; // invalid input is rejected by the tool itself
  }
}

function medicationTarget(args: Record<string, unknown>): string | null {
  try {
    validateMedicationInput(args);
    return 'api.fda.gov';
  } catch {
    return null; // invalid input is rejected by the tool itself
  }
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
  if (name === 'algorand') {
    const host = algorandTarget(args);
    if (host && !hooks.approvedDomains.has(host)) return `First network access to ${host} in this session`;
  }
  if (name === 'medication') {
    const host = medicationTarget(args);
    if (host && !hooks.approvedDomains.has(host)) return `First network access to ${host} in this session`;
  }
  return null;
}

interface RunContext {
  /** True once the run has read external data or a file that existed before the run. */
  observed: boolean;
  userAskedToRemember: boolean;
  /** Files this run wrote; reading them back is not evidence of anything. */
  written: Set<string>;
  rememberRefusals: number;
  /** list_files returned nothing and nothing has been written since: the workspace is empty, so reading a guessed file cannot succeed. */
  workspaceEmpty?: boolean;
}

function normalizePath(value: unknown): string {
  return String(value ?? '').replaceAll('\\', '/').replace(/^\.?\/+/, '');
}

function isObservation(name: string, args: Record<string, unknown>, context: RunContext): boolean {
  if (name === 'fetch_url' || name === 'read_rss' || name === 'algorand' || name === 'medication') return true;
  if (name === 'read_file') return !context.written.has(normalizePath(args.path));
  return false;
}

async function executeTool(name: string, args: Record<string, unknown>, hooks: AgentHooks, context: RunContext): Promise<Record<string, unknown>> {
  switch (name) {
    case 'list_files':
      {
        const files = await listWorkspace(hooks.workspace);
        context.workspaceEmpty = files.length === 0;
        return { files };
      }
    case 'read_file': {
      if (context.workspaceEmpty && !context.written.has(normalizePath(args.path))) {
        throw new Error('The workspace is empty (list_files returned nothing), so there is no such file to read. Do not guess file names: use the tool results you already have, or write the file first.');
      }
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
    case 'algorand':
      return algorandQuery(args, { signal: hooks.signal });
    case 'medication':
      return medicationQuery(args, { signal: hooks.signal });
    case 'recall':
      return hooks.recall(String(args.query ?? ''), Math.min(Math.max(Number(args.limit) || 5, 1), 10));
    case 'remember': {
      const title = String(args.title ?? '').trim();
      const content = String(args.content ?? '').trim();
      const evidence = String(args.evidence ?? '').trim();
      if (!title || !content || !evidence) throw new Error('remember needs title, content and evidence');
      // Governance (AGENTS.md §1.3): no speculative claims in org memory. A memory must rest on something
      // this run observed, or on an explicit instruction from the user in the goal.
      if (context.rememberRefusals >= 2) {
        throw new Error('remember is disabled for the rest of this run. Stop trying to store this; tell the user it was not saved and why.');
      }
      if (!context.observed && !context.userAskedToRemember) {
        context.rememberRefusals += 1;
        throw new Error(
          'Refused: this run has not observed any external evidence (fetch_url, read_rss, or reading a file that existed before this run). ' +
            'Files you wrote yourself and recall results do not count. Do not work around this — either fetch a real source or tell the user the fact was not stored.',
        );
      }
      const tags = Array.isArray(args.tags) ? args.tags.map(String) : [];
      return hooks.remember(title, `${content}\n\nEvidence: ${evidence}`, tags);
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
  tools: typeof TOOLS = TOOLS,
  apiBaseUrl = process.env.INCEPTION_BASE_URL || INCEPTION_BASE_URL,
): Promise<{ message: AgentMessage; prompt: number; completion: number }> {
  const response = await fetch(`${apiBaseUrl}/chat/completions`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${process.env.INCEPTION_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ model, messages, ...(tools.length ? { tools } : {}), temperature, max_tokens: 8000 }),
    signal: AbortSignal.any([signal, AbortSignal.timeout(90000)]),
  });
  if (!response.ok) {
    throw new Error(`Inception API HTTP ${response.status}: ${truncate(await response.text(), 300)}`);
  }
  const data = (await response.json()) as {
    choices: Array<{ message: AgentMessage }>;
    usage?: { prompt_tokens?: number; completion_tokens?: number };
  };
  const message = data.choices?.[0]?.message;
  if (!message) {
    throw new Error(`Inception API returned no choices: ${truncate(JSON.stringify(data), 300)}`);
  }
  return {
    message,
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
  memoryContext = '',
): Promise<AgentRunResult> {
  const totals = { steps: 0, tool_calls: 0, prompt_tokens: 0, completion_tokens: 0, tokens: 0, cost_usd: 0 };
  const finish = (extra: Partial<AgentRunResult> & { success: boolean }): AgentRunResult => ({ ...totals, ...extra });

  if (!inceptionConfigured()) return finish({ success: false, error: 'INCEPTION_API_KEY is not set in .env' });

  const tools = hooks.allowedTools ? TOOLS.filter((t) => hooks.allowedTools!.includes(t.function.name)) : TOOLS;
  const roleContext = hooks.roleContext ?? (hooks.allowedTools ? Object.values(AGENT_PROFILES).find((p) => p.allowedTools === hooks.allowedTools)?.roleContext : undefined);

  const evidence: ToolEvidence[] = [];
  const conflicts: string[] = [];
  const context: RunContext = { observed: false, written: new Set(), rememberRefusals: 0, userAskedToRemember: /\b(remember (that|this|to)|memori[sz]e|note that|(save|add|store) (this|that|it) (to|in) memory)\b/i.test(goal) };
  const system = [SYSTEM_PROMPT, roleContext, memoryContext ? `Relevant memories:\n${memoryContext}` : undefined]
    .filter(Boolean)
    .join('\n\n');
  const messages: AgentMessage[] = [{ role: 'system', content: system }];
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
      const { message, prompt, completion } = await chat(model, messages, temperature, hooks.signal, tools, hooks.apiBaseUrl);
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
        let answer = message.content?.trim() || '(no answer)';
        // Final-answer check: an answer that asserts state while this run's own tool results say nothing/failed is confirmed by a model, retried once
        // with the conflict spelled out, and if it still conflicts the answer is replaced by what the tools said, flagged.
        if (process.env.THINKBOX_EVIDENCE_CHECK !== 'off' && conflictCandidate(answer, evidence)) {
          const check = async (text: string): Promise<{ conflict: boolean; detail: string } | null> => {
            const judged = await chat(model, [
              { role: 'system', content: EVIDENCE_JUDGE_SYSTEM },
              { role: 'user', content: JSON.stringify({ answer: text, tool_results: evidence.map((e, i) => ({ order: i + 1, tool: e.name, ok: e.ok, output: e.output, superseded_by_later_success: supersededFlags(evidence)[i] })) }) },
            ], 0, hooks.signal, [], hooks.apiBaseUrl);
            totals.prompt_tokens += judged.prompt;
            totals.completion_tokens += judged.completion;
            totals.tokens += judged.prompt + judged.completion;
            totals.cost_usd += costUsd(model, judged.prompt, judged.completion);
            return parseJudge(judged.message.content ?? '');
          };
          const first = await check(answer);
          if (first?.conflict) {
            conflicts.push(first.detail || 'the answer contradicted a tool result');
            hooks.onThought({ type: 'reasoning', content: `Evidence check: the answer conflicts with this run's tool results (${first.detail}). Retrying once. First answer: ${truncate(answer.replace(/\s+/g, ' '), 300)}`, status: 'info' });
            messages.push({ role: 'user', content: `Your answer conflicts with this run's tool results: ${first.detail}\nTool results from THIS run outrank memory. Answer again from the tool results only, and say which memory or lesson was stale.` });
            const retry = await chat(model, messages, temperature, hooks.signal, [], hooks.apiBaseUrl);
            totals.prompt_tokens += retry.prompt;
            totals.completion_tokens += retry.completion;
            totals.tokens += retry.prompt + retry.completion;
            totals.cost_usd += costUsd(model, retry.prompt, retry.completion);
            const retried = retry.message.content?.trim() || '';
            const second = retried ? await check(retried) : null;
            if (retried && second && !second.conflict) {
              answer = retried;
            } else {
              answer = `FLAGGED: my answer conflicted with this run's tool results and could not be reconciled. What the tools said: ${first.detail}`;
              conflicts.push(second?.detail || 'the retry still conflicted');
            }
          }
        }
        hooks.onThought({
          type: 'answer',
          content: `Finished in ${step} step(s), ${totals.tool_calls} tool call(s), ${totals.tokens} tokens, $${totals.cost_usd.toFixed(5)}`,
          status: 'success',
        });
        return finish({ success: true, result: answer, ...(conflicts.length ? { evidence_conflicts: conflicts } : {}) });
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
          // Hard backstop: even a hallucinated or prompt-injected tool_call for a name outside
          // this run's allowlist is rejected before it ever reaches the approval gate — filtering
          // the model's function list is a UX nicety, not the actual security boundary.
          if (hooks.allowedTools && !hooks.allowedTools.includes(call.function.name)) {
            throw new Error(`Tool '${call.function.name}' is not available to this agent profile`);
          }
          reason = approvalReason(call.function.name, args, hooks);
          if (reason) {
            hooks.onThought({ type: 'approval', content: `Waiting for approval: ${reason}`, status: 'thinking' });
            approval = (await hooks.requestApproval(call.function.name, args, reason)) ? 'approved' : 'denied';
            if (approval === 'denied') throw new Error(`Denied by human reviewer (${reason})`);
            const host = call.function.name === 'algorand' ? algorandTarget(args)
              : call.function.name === 'medication' ? medicationTarget(args)
              : hostOf(args.url);
            if (host) hooks.approvedDomains.add(host);
          }
          output = { ok: true, ...(await executeTool(call.function.name, args, hooks, context)) };
          if (isObservation(call.function.name, args, context)) context.observed = true;
          if (call.function.name === 'write_file') { context.written.add(normalizePath(args.path)); context.workspaceEmpty = false; }
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
        evidence.push({ name: call.function.name, ok: output.ok === true, output: truncate(JSON.stringify(output), 1500) });
        messages.push({ role: 'tool', tool_call_id: call.id, content: truncate(JSON.stringify(output), 15000) });
      }
    }
  } catch (err) {
    if (hooks.signal.aborted) return finish({ success: false, stopped: true, error: 'Stopped by user' });
    return finish({ success: false, error: err instanceof Error ? err.message : String(err) });
  }

  return finish({ success: false, error: `Reached the ${maxIterations}-step limit without finishing` });
}
