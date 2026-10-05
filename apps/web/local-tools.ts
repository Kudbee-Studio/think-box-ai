// Governed tool calling for local Ollama models (Layer 4: tools glue; the model and the tool run are injected, so it is testable without either).
// A local model asks for a tool exactly like Mercury does, and the request goes through the SAME governed path (`runGovernedTool`: allowlist,
// approval, execution, audit event). There is no second tool registry: the only difference is how the request is obtained.
//   native       the model supports Ollama `tools` (Qwen): the request is a `tool_calls` entry.
//   constrained  it does not (Gemma): a JSON schema `format` forces `{action, ...}`; the request is parsed from that.
// A request is validated BEFORE it runs. A malformed one is never executed: the model gets one repair turn, then the goal fails explicitly. A denied
// approval stops the loop. A tool failure is reported as a failure. Nothing here invents data or an answer.
// A LoopSpec says which tools a goal may use, how a call is validated, what counts as evidence and how the final result is judged. Two exist:
// live-data lookups (answer judged by the grounding validator) and read-only repository investigation (a FINDING judged against the repo evidence).

import { TOOLS, runGovernedTool, type AgentHooks, type RunContext } from './agent.ts';
import { parseFinding, validateFinding, validateGrounding, type GroundingResult, type RepoFinding } from './grounding.ts';
import { LOOKUP_RECIPES, renderFacts, validateLookupArgs, type LookupEvidence } from './live-lookup.ts';
import type { OllamaChatTurn } from './ollama-client.ts';
import { renderRepoEvidence, validateRepoReadArgs, validateRepoSearchArgs, type RepoEvidence } from './repo-tools.ts';

export type ToolMode = 'native' | 'constrained';
export type LocalFailureKind = 'malformed_tool_request' | 'no_tool_call' | 'tool_denied' | 'tool_failed' | 'model_error' | 'step_limit';

export interface LocalChat {
  chatOnce: (model: string, messages: unknown[], opts?: { tools?: unknown[]; format?: unknown; signal?: AbortSignal; timeoutMs?: number; numPredict?: number }) => Promise<OllamaChatTurn>;
  modelCapabilities: (model: string) => Promise<string[]>;
}

export interface LocalToolStep {
  step: number;
  mode: ToolMode;
  /** The model's raw request or answer text/arguments, kept for the record. */
  raw: string;
  request?: Record<string, unknown>;
  outcome: 'tool_ok' | 'tool_failed' | 'tool_denied' | 'malformed' | 'answer' | 'no_tool_call' | 'model_error';
  error?: string;
  latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
}

export interface LocalToolResult<E = LookupEvidence> {
  success: boolean;
  model: string;
  mode: ToolMode;
  answer?: string;
  /** Repository investigations end in a finding instead of an answer. */
  finding?: RepoFinding;
  evidence: E[];
  steps: LocalToolStep[];
  tool_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number;
  grounding: GroundingResult | null;
  failure?: { kind: LocalFailureKind; message: string };
}

/** What the model asked for this turn: a tool call, a final answer/finding, or nothing usable. */
export type ParsedTurn =
  | { kind: 'call'; name: string; request: Record<string, unknown>; raw: string }
  | { kind: 'answer'; text: string; raw: string }
  | { kind: 'final'; args: unknown; raw: string }
  | { kind: 'malformed'; reason: string; raw: string }
  | { kind: 'empty'; raw: string };

export interface LoopSpec<E> {
  nativeTools: unknown[];
  system: string;
  constrainedSystem: string;
  constrainedSchema: unknown;
  /** Governed tools the model may call. */
  toolNames: string[];
  /** A native "report" tool (and constrained action) that ends the loop with structured args instead of a text answer. */
  terminalTool?: string;
  /** Validate a requested call; the returned args are what runs. */
  checkCall: (name: string, args: unknown) => { ok: true; args: Record<string, unknown> } | { ok: false; error: string };
  evidenceOf: (output: Record<string, unknown>) => E | null;
  render: (e: E) => string;
  repairHint: string;
  /** Judge the model's final text or structured report against the evidence. */
  judge: (final: { text: string } | { args: unknown }, evidence: E[]) => { ok: true; answer?: string; finding?: RepoFinding; grounding: GroundingResult } | { ok: false; error: string };
}

const toolSchema = (name: string) => TOOLS.find((t) => t.function.name === name)!;

// ─── live-data lookups ──────────────────────────────────────────────────────

const LOOKUP_SYSTEM = [
  "You answer questions about this project's GitHub repository. You cannot know its live state from memory.",
  'To get live data, call the tool live_lookup. Never state a pull request, issue, branch or CI result you did not get from the tool.',
  'When you have the data, answer in one or two plain sentences and name the numbers and branches exactly as the tool gave them.',
].join(' ');

/** The JSON schema that forces a model without native tools to produce a call or an answer. */
export const CONSTRAINED_SCHEMA = {
  type: 'object',
  properties: {
    action: { type: 'string', enum: ['call', 'answer'] },
    recipe: { type: 'string', enum: [...LOOKUP_RECIPES] },
    branch: { type: 'string' },
    answer: { type: 'string' },
  },
  required: ['action'],
} as const;

export function lookupSpec(repo: string | null): LoopSpec<LookupEvidence> {
  return {
    nativeTools: [toolSchema('live_lookup')],
    system: LOOKUP_SYSTEM,
    constrainedSystem: `${LOOKUP_SYSTEM} Reply ONLY with JSON. To look something up: {"action":"call","recipe":"<one of ${LOOKUP_RECIPES.join(', ')}>"} (add "branch" only for ci_status). To answer once you have the data: {"action":"answer","answer":"<one or two sentences>"}.`,
    constrainedSchema: CONSTRAINED_SCHEMA,
    toolNames: ['live_lookup'],
    checkCall: (_name, args) => {
      const c = validateLookupArgs(args, repo);
      return c.ok ? { ok: true, args: { recipe: c.args.recipe, ...(c.args.branch ? { branch: c.args.branch } : {}) } } : c;
    },
    evidenceOf: (o) => ((o as { evidence?: LookupEvidence }).evidence ?? null),
    render: renderFacts,
    repairHint: `Valid recipes: ${LOOKUP_RECIPES.join(', ')}.`,
    judge: (final, evidence) => ('text' in final ? { ok: true, answer: final.text, grounding: validateGrounding(final.text, evidence) } : { ok: false, error: 'a lookup ends with a plain answer' }),
  };
}

// ─── read-only repository investigation ─────────────────────────────────────

const REPO_SYSTEM = [
  'You investigate the real source code of this repository with two read-only tools: repo_search (literal text search) and repo_read (numbered lines of one file).',
  'You cannot know the code from memory. Start by calling repo_search or repo_read: the report option only appears after you have looked. Then report ONE finding: the file, the line number, an exact quote copied from that line, and a short claim.',
  'To claim that something has no tests or is unused, you must first run repo_search for its name over the relevant folder and pass that same query and path as absence_search; a search that found matches does not prove absence.',
  'If you find nothing worth reporting, report found=false with a reason. Never report a file, line or quote you did not see in tool output.',
].join(' ');

const REPORT_FINDING_TOOL = {
  type: 'function',
  function: {
    name: 'report_finding',
    description: 'Report your single finding once you have looked. This ends the investigation.',
    parameters: {
      type: 'object',
      properties: {
        found: { type: 'boolean' },
        file: { type: 'string', description: 'repo-relative path you read' },
        line: { type: 'integer', description: 'line number of the quote' },
        quote: { type: 'string', description: 'exact text copied from that line' },
        claim: { type: 'string', description: 'what you found, in one sentence; put identifiers in backticks' },
        absence_search: { type: 'object', properties: { query: { type: 'string' }, path: { type: 'string' } }, description: 'for a claim of absence: the repo_search you ran that found nothing' },
        reason: { type: 'string', description: 'only when found is false' },
      },
      required: ['found'],
    },
  },
};

export const REPO_CONSTRAINED_SCHEMA = {
  type: 'object',
  properties: {
    action: { type: 'string', enum: ['call', 'finding'] },
    tool: { type: 'string', enum: ['repo_search', 'repo_read'] },
    query: { type: 'string' },
    path: { type: 'string' },
    start: { type: 'integer' },
    end: { type: 'integer' },
    finding: { type: 'object' },
  },
  required: ['action'],
} as const;

export function repoSpec(): LoopSpec<RepoEvidence> {
  return {
    nativeTools: [toolSchema('repo_search'), toolSchema('repo_read'), REPORT_FINDING_TOOL],
    system: REPO_SYSTEM,
    constrainedSystem: `${REPO_SYSTEM} Reply ONLY with JSON. To look: {"action":"call","tool":"repo_search","query":"...","path":"optional folder"} or {"action":"call","tool":"repo_read","path":"file","start":1,"end":60}. To report: {"action":"finding","finding":{"found":true,"file":"...","line":1,"quote":"...","claim":"...","absence_search":{"query":"...","path":"..."}}} or {"action":"finding","finding":{"found":false,"reason":"..."}}.`,
    constrainedSchema: REPO_CONSTRAINED_SCHEMA,
    toolNames: ['repo_search', 'repo_read'],
    terminalTool: 'report_finding',
    checkCall: (name, args) => {
      const c = name === 'repo_search' ? validateRepoSearchArgs(args) : name === 'repo_read' ? validateRepoReadArgs(args) : ({ ok: false, error: `unknown tool "${name}"` } as const);
      return c.ok ? { ok: true, args: c.args as Record<string, unknown> } : c;
    },
    evidenceOf: (o) => ((o as { evidence?: RepoEvidence }).evidence ?? null),
    render: renderRepoEvidence,
    repairHint: 'Tools: repo_search {query, path?} and repo_read {path, start?, end?}.',
    judge: (final, evidence) => {
      if (!('args' in final)) return { ok: false, error: 'an investigation ends with report_finding, not a plain answer' };
      const parsed = parseFinding(final.args);
      if (!parsed.ok) return { ok: false, error: `the finding is malformed: ${parsed.error}` };
      return { ok: true, finding: parsed.finding, grounding: validateFinding(parsed.finding, evidence) };
    },
  };
}

export async function toolModeFor(model: string, chat: LocalChat): Promise<ToolMode> {
  return (await chat.modelCapabilities(model)).includes('tools') ? 'native' : 'constrained';
}

const rawOf = (turn: OllamaChatTurn): string => JSON.stringify(turn.tool_calls.length ? turn.tool_calls : turn.content).slice(0, 600);

export function parseNativeTurnFor(turn: OllamaChatTurn, spec: LoopSpec<unknown>): ParsedTurn {
  const raw = rawOf(turn);
  if (turn.tool_calls.length) {
    const call = turn.tool_calls[0]!.function;
    const name = String(call?.name);
    const allowed = [...spec.toolNames, ...(spec.terminalTool ? [spec.terminalTool] : [])];
    if (!allowed.includes(name)) return { kind: 'malformed', reason: `unknown tool "${name}" (the tools are ${allowed.join(', ')})`, raw };
    let args: unknown = call?.arguments;
    if (typeof args === 'string') { try { args = JSON.parse(args); } catch { return { kind: 'malformed', reason: 'the tool arguments were not valid JSON', raw }; } }
    if (name === spec.terminalTool) return { kind: 'final', args, raw };
    return { kind: 'call', name, request: (args && typeof args === 'object' ? args : {}) as Record<string, unknown>, raw };
  }
  return turn.content.trim() ? { kind: 'answer', text: turn.content.trim(), raw } : { kind: 'empty', raw };
}

export function parseConstrainedTurnFor(turn: OllamaChatTurn, spec: LoopSpec<unknown>): ParsedTurn {
  const raw = turn.content.slice(0, 600);
  let body: any;
  try { body = JSON.parse(turn.content); } catch { return { kind: 'malformed', reason: 'the reply was not valid JSON', raw }; }
  if (!body || typeof body !== 'object' || Array.isArray(body)) return { kind: 'malformed', reason: 'the reply was not a JSON object', raw };
  if (body.action === 'answer' && !spec.terminalTool) return typeof body.answer === 'string' && body.answer.trim() ? { kind: 'answer', text: body.answer.trim(), raw } : { kind: 'empty', raw };
  if (body.action === 'finding' && spec.terminalTool) return body.finding && typeof body.finding === 'object' ? { kind: 'final', args: body.finding, raw } : { kind: 'malformed', reason: 'a finding action needs a finding object', raw };
  if (body.action === 'call') {
    const { action: _a, answer: _answer, finding: _f, tool, ...request } = body;
    const name = typeof tool === 'string' ? tool : spec.toolNames[0]!;
    if (!spec.toolNames.includes(name)) return { kind: 'malformed', reason: `unknown tool "${name}" (the tools are ${spec.toolNames.join(', ')})`, raw };
    return { kind: 'call', name, request, raw };
  }
  return { kind: 'malformed', reason: `action must be ${spec.terminalTool ? '"call" or "finding"' : '"call" or "answer"'}`, raw };
}

// Lookup-specific forms (kept: the live lookup tests and callers use them).
export const parseNativeTurn = (turn: OllamaChatTurn): ParsedTurn => parseNativeTurnFor(turn, lookupSpec(null) as LoopSpec<unknown>);
export const parseConstrainedTurn = (turn: OllamaChatTurn): ParsedTurn => parseConstrainedTurnFor(turn, lookupSpec(null) as LoopSpec<unknown>);

/** The constrained schema with the action restricted to "call" (nothing to report before a tool has returned something). */
function callOnly(schema: unknown): unknown {
  const s = JSON.parse(JSON.stringify(schema)) as { properties?: { action?: { enum?: string[] } } };
  if (s.properties?.action) s.properties.action.enum = ['call'];
  return s;
}

export interface LocalToolOptions<E = LookupEvidence> {
  model: string;
  goal: string;
  hooks: AgentHooks;
  context: RunContext;
  chat: LocalChat;
  repo: string | null;
  maxSteps?: number;
  signal?: AbortSignal;
  /** Which toolset this goal uses; live-data lookups by default. */
  spec?: LoopSpec<E>;
}

/** Run one goal on a local model with governed tool calling: look, (maybe look again), finish, then judge the result against the evidence. */
export async function runLocalToolLoop<E = LookupEvidence>(opts: LocalToolOptions<E>): Promise<LocalToolResult<E>> {
  const { model, goal, hooks, context, chat } = opts;
  const spec = (opts.spec ?? lookupSpec(opts.repo)) as unknown as LoopSpec<E>;
  const maxSteps = opts.maxSteps ?? 3;
  const mode = await toolModeFor(model, chat);
  const startedAt = Date.now();
  const steps: LocalToolStep[] = [];
  const evidence: E[] = [];
  const messages: unknown[] = [{ role: 'system', content: mode === 'native' ? spec.system : spec.constrainedSystem }, { role: 'user', content: goal }];
  let toolCalls = 0; let promptTokens = 0; let completionTokens = 0; let repairs = 0; let groundingRetries = 0;
  const done = (partial: Partial<LocalToolResult<E>>): LocalToolResult<E> => ({ success: false, model, mode, evidence, steps, tool_calls: toolCalls, prompt_tokens: promptTokens, completion_tokens: completionTokens, latency_ms: Date.now() - startedAt, grounding: null, ...partial });
  const fail = (kind: LocalFailureKind, message: string): LocalToolResult<E> => done({ failure: { kind, message } });
  const noun = spec.terminalTool ? 'report' : 'answer';

  for (let step = 1; step <= maxSteps + 2; step += 1) {
    // Until a tool call has returned something there is nothing to report: the report option is not offered at all (a model offered it first invents a finding).
    const looked = evidence.length > 0;
    const tools = looked || !spec.terminalTool ? spec.nativeTools : spec.nativeTools.filter((t) => (t as { function?: { name?: string } }).function?.name !== spec.terminalTool);
    const format = looked || !spec.terminalTool ? spec.constrainedSchema : callOnly(spec.constrainedSchema);
    const turn = await chat.chatOnce(model, messages, mode === 'native' ? { tools, signal: opts.signal } : { format, signal: opts.signal });
    promptTokens += turn.prompt_tokens; completionTokens += turn.completion_tokens;
    const base = { step, mode, latency_ms: turn.latency_ms, prompt_tokens: turn.prompt_tokens, completion_tokens: turn.completion_tokens };
    if (turn.error) { steps.push({ ...base, raw: '', outcome: 'model_error', error: turn.error }); return fail('model_error', turn.error); }
    const parsed = mode === 'native' ? parseNativeTurnFor(turn, spec as LoopSpec<unknown>) : parseConstrainedTurnFor(turn, spec as LoopSpec<unknown>);

    if (parsed.kind === 'answer' || parsed.kind === 'final') {
      if (!evidence.length) { steps.push({ ...base, raw: parsed.raw, outcome: 'no_tool_call', error: `gave a ${noun} without calling a tool` }); return fail('no_tool_call', `${model} gave a ${noun} without looking anything up, so it cannot be verified`); }
      const judged = spec.judge(parsed.kind === 'answer' ? { text: parsed.text } : { args: parsed.args }, evidence);
      if (!judged.ok) {
        steps.push({ ...base, raw: parsed.raw, outcome: 'malformed', error: judged.error });
        if (repairs >= 1) return fail('malformed_tool_request', `${model} made an invalid ${noun} twice: ${judged.error}`);
        repairs += 1;
        messages.push({ role: 'assistant', content: parsed.raw });
        messages.push({ role: 'user', content: `That ${noun} was invalid: ${judged.error}. Try again.` });
        continue;
      }
      // A report that did not trace to the evidence gets ONE round of feedback naming the unsupported claims, so the model can run the missing tool call
      // and report again. The retry is a step on the record; a second failure is returned as it is.
      if (spec.terminalTool && judged.grounding.status !== 'GROUNDED' && groundingRetries < 1 && toolCalls < maxSteps) {
        groundingRetries += 1;
        steps.push({ ...base, raw: parsed.raw, outcome: 'malformed', error: `not grounded: ${judged.grounding.unsupported.map((u) => `${u.kind} ${u.claim}`).join('; ')}` });
        messages.push({ role: 'assistant', content: mode === 'native' ? '' : parsed.raw, ...(mode === 'native' ? { tool_calls: turn.tool_calls } : {}) });
        if (mode === 'native') messages.push({ role: 'tool', tool_name: spec.terminalTool, content: 'REJECTED' });
        messages.push({ role: 'user', content: `That report was not accepted because these claims are not supported by what the tools returned: ${judged.grounding.unsupported.map((u) => `${u.kind} "${u.claim}" (${u.why})`).join('; ')}. Use the tools to fix this (for a claim that something has no tests or is unused, run repo_search for its name over the folder, then pass that same query and path as absence_search), then report again, or report found=false.` });
        continue;
      }
      steps.push({ ...base, raw: parsed.raw, outcome: 'answer' });
      return done({ success: true, ...(judged.answer !== undefined ? { answer: judged.answer } : {}), ...(judged.finding ? { finding: judged.finding } : {}), grounding: judged.grounding });
    }
    if (parsed.kind === 'empty') { steps.push({ ...base, raw: parsed.raw, outcome: 'no_tool_call', error: 'empty reply' }); return fail('no_tool_call', `${model} returned neither a tool call nor a ${noun}`); }

    // A request: validate before anything runs.
    const checked = parsed.kind === 'call' ? spec.checkCall(parsed.name, parsed.request) : null;
    if (parsed.kind === 'malformed' || (checked && !checked.ok)) {
      const reason = parsed.kind === 'malformed' ? parsed.reason : (checked as { error: string }).error;
      steps.push({ ...base, raw: parsed.raw, request: parsed.kind === 'call' ? parsed.request : undefined, outcome: 'malformed', error: reason });
      if (repairs >= 1) return fail('malformed_tool_request', `${model} made an invalid tool request twice: ${reason}`);
      repairs += 1;
      messages.push({ role: 'assistant', content: parsed.raw });
      messages.push({ role: 'user', content: `That request was invalid: ${reason}. ${spec.repairHint} Try again.` });
      continue;
    }
    if (toolCalls >= maxSteps) { steps.push({ ...base, raw: parsed.raw, outcome: 'malformed', error: 'step limit' }); return fail('step_limit', `${model} asked for more than ${maxSteps} tool calls`); }

    const call = parsed as Extract<ParsedTurn, { kind: 'call' }>;
    const args = (checked as { ok: true; args: Record<string, unknown> }).args;
    toolCalls += 1;
    const gov = await runGovernedTool(call.name, args, hooks, context, toolCalls);
    if (gov.approval === 'denied') { steps.push({ ...base, raw: parsed.raw, request: args, outcome: 'tool_denied', error: String(gov.output.error) }); return fail('tool_denied', String(gov.output.error)); }
    if (gov.output.ok !== true) { steps.push({ ...base, raw: parsed.raw, request: args, outcome: 'tool_failed', error: String(gov.output.error) }); return fail('tool_failed', String(gov.output.error)); }
    const found = spec.evidenceOf(gov.output);
    if (!found) { steps.push({ ...base, raw: parsed.raw, request: args, outcome: 'tool_failed', error: 'the tool returned no evidence' }); return fail('tool_failed', 'the tool returned no evidence'); }
    evidence.push(found);
    steps.push({ ...base, raw: parsed.raw, request: args, outcome: 'tool_ok' });
    const facts = spec.render(found);
    if (mode === 'native') {
      messages.push({ role: 'assistant', content: '', tool_calls: turn.tool_calls });
      messages.push({ role: 'tool', tool_name: call.name, content: facts });
    } else {
      messages.push({ role: 'assistant', content: parsed.raw });
      messages.push({ role: 'user', content: `Tool result for ${call.name}:\n${facts}\n\n${spec.terminalTool ? 'If you have enough, report your finding. If you still need to look, call another tool.' : 'If this is enough, answer. If you still need another lookup, call it.'}` });
    }
  }
  return fail('step_limit', `${model} did not finish within ${maxSteps} tool calls`);
}
