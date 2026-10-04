// Governed tool calling for local Ollama models (Layer 4: tools glue; the model and the tool run are injected, so it is testable without either).
// A local model asks for `live_lookup` exactly like Mercury does, and the request goes through the SAME governed path (`runGovernedTool`: allowlist,
// first-network approval, execution, audit event). There is no second tool registry: the only difference is how the request is obtained.
//   native       the model supports Ollama `tools` (Qwen): the request is a `tool_calls` entry.
//   constrained  it does not (Gemma): a JSON schema `format` forces `{action, recipe, branch, answer}`; the request is parsed from that.
// A request is validated BEFORE it runs. A malformed one is never executed: the model gets one repair turn, then the goal fails explicitly. A denied
// approval stops the loop. A tool failure is reported as a failure. Nothing here invents data or an answer.

import { TOOLS, runGovernedTool, type AgentHooks, type RunContext } from './agent.ts';
import { validateGrounding, type GroundingResult } from './grounding.ts';
import { LOOKUP_RECIPES, renderFacts, validateLookupArgs, type LookupArgs, type LookupEvidence } from './live-lookup.ts';
import type { OllamaChatTurn } from './ollama-client.ts';

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

export interface LocalToolResult {
  success: boolean;
  model: string;
  mode: ToolMode;
  answer?: string;
  evidence: LookupEvidence[];
  steps: LocalToolStep[];
  tool_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number;
  grounding: GroundingResult | null;
  failure?: { kind: LocalFailureKind; message: string };
}

const LIVE_LOOKUP = TOOLS.find((t) => t.function.name === 'live_lookup')!;

const SYSTEM = [
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

const CONSTRAINED_SYSTEM = `${SYSTEM} Reply ONLY with JSON. To look something up: {"action":"call","recipe":"<one of ${LOOKUP_RECIPES.join(', ')}>"} (add "branch" only for ci_status). To answer once you have the data: {"action":"answer","answer":"<one or two sentences>"}.`;

export async function toolModeFor(model: string, chat: LocalChat): Promise<ToolMode> {
  return (await chat.modelCapabilities(model)).includes('tools') ? 'native' : 'constrained';
}

/** What the model asked for this turn: a lookup request, a final answer, or nothing usable. */
export type ParsedTurn =
  | { kind: 'call'; request: Record<string, unknown>; raw: string }
  | { kind: 'answer'; text: string; raw: string }
  | { kind: 'malformed'; reason: string; raw: string }
  | { kind: 'empty'; raw: string };

export function parseNativeTurn(turn: OllamaChatTurn): ParsedTurn {
  const raw = JSON.stringify(turn.tool_calls.length ? turn.tool_calls : turn.content).slice(0, 600);
  if (turn.tool_calls.length) {
    const call = turn.tool_calls[0]!.function;
    if (call?.name !== 'live_lookup') return { kind: 'malformed', reason: `unknown tool "${String(call?.name)}" (the only tool is live_lookup)`, raw };
    let args: unknown = call.arguments;
    if (typeof args === 'string') { try { args = JSON.parse(args); } catch { return { kind: 'malformed', reason: 'the tool arguments were not valid JSON', raw }; } }
    return { kind: 'call', request: (args && typeof args === 'object' ? args : {}) as Record<string, unknown>, raw };
  }
  return turn.content.trim() ? { kind: 'answer', text: turn.content.trim(), raw } : { kind: 'empty', raw };
}

export function parseConstrainedTurn(turn: OllamaChatTurn): ParsedTurn {
  const raw = turn.content.slice(0, 600);
  let body: any;
  try { body = JSON.parse(turn.content); } catch { return { kind: 'malformed', reason: 'the reply was not valid JSON', raw }; }
  if (!body || typeof body !== 'object' || Array.isArray(body)) return { kind: 'malformed', reason: 'the reply was not a JSON object', raw };
  if (body.action === 'answer') return typeof body.answer === 'string' && body.answer.trim() ? { kind: 'answer', text: body.answer.trim(), raw } : { kind: 'empty', raw };
  if (body.action === 'call') {
    const { action: _a, answer: _answer, ...request } = body;
    return { kind: 'call', request, raw };
  }
  return { kind: 'malformed', reason: 'action must be "call" or "answer"', raw };
}

export interface LocalToolOptions {
  model: string;
  goal: string;
  hooks: AgentHooks;
  context: RunContext;
  chat: LocalChat;
  repo: string | null;
  maxSteps?: number;
  signal?: AbortSignal;
}

/** Run one goal on a local model with governed tool calling: look up, (maybe look up again), answer, then check the answer against the evidence. */
export async function runLocalToolLoop(opts: LocalToolOptions): Promise<LocalToolResult> {
  const { model, goal, hooks, context, chat, repo } = opts;
  const maxSteps = opts.maxSteps ?? 3;
  const mode = await toolModeFor(model, chat);
  const startedAt = Date.now();
  const steps: LocalToolStep[] = [];
  const evidence: LookupEvidence[] = [];
  const messages: unknown[] = [{ role: 'system', content: mode === 'native' ? SYSTEM : CONSTRAINED_SYSTEM }, { role: 'user', content: goal }];
  let toolCalls = 0; let promptTokens = 0; let completionTokens = 0; let repairs = 0;
  const done = (partial: Partial<LocalToolResult>): LocalToolResult => ({ success: false, model, mode, evidence, steps, tool_calls: toolCalls, prompt_tokens: promptTokens, completion_tokens: completionTokens, latency_ms: Date.now() - startedAt, grounding: null, ...partial });
  const fail = (kind: LocalFailureKind, message: string): LocalToolResult => done({ failure: { kind, message } });

  for (let step = 1; step <= maxSteps + 2; step += 1) {
    const turn = await chat.chatOnce(model, messages, mode === 'native' ? { tools: [LIVE_LOOKUP], signal: opts.signal } : { format: CONSTRAINED_SCHEMA, signal: opts.signal });
    promptTokens += turn.prompt_tokens; completionTokens += turn.completion_tokens;
    const base = { step, mode, latency_ms: turn.latency_ms, prompt_tokens: turn.prompt_tokens, completion_tokens: turn.completion_tokens };
    if (turn.error) { steps.push({ ...base, raw: '', outcome: 'model_error', error: turn.error }); return fail('model_error', turn.error); }
    const parsed = mode === 'native' ? parseNativeTurn(turn) : parseConstrainedTurn(turn);

    if (parsed.kind === 'answer') {
      if (!evidence.length) { steps.push({ ...base, raw: parsed.raw, outcome: 'no_tool_call', error: 'answered without calling the tool' }); return fail('no_tool_call', `${model} answered without looking anything up, so the answer cannot be verified`); }
      steps.push({ ...base, raw: parsed.raw, outcome: 'answer' });
      const grounding = validateGrounding(parsed.text, evidence);
      return done({ success: true, answer: parsed.text, grounding });
    }
    if (parsed.kind === 'empty') { steps.push({ ...base, raw: parsed.raw, outcome: 'no_tool_call', error: 'empty reply' }); return fail('no_tool_call', `${model} returned neither a tool call nor an answer`); }

    // A request: validate before anything runs.
    const checked = parsed.kind === 'call' ? validateLookupArgs(parsed.request, repo) : null;
    if (parsed.kind === 'malformed' || (checked && !checked.ok)) {
      const reason = parsed.kind === 'malformed' ? parsed.reason : (checked as { error: string }).error;
      steps.push({ ...base, raw: parsed.raw, request: parsed.kind === 'call' ? parsed.request : undefined, outcome: 'malformed', error: reason });
      if (repairs >= 1) return fail('malformed_tool_request', `${model} made an invalid tool request twice: ${reason}`);
      repairs += 1;
      messages.push({ role: 'assistant', content: parsed.raw });
      messages.push({ role: 'user', content: `That request was invalid: ${reason}. Valid recipes: ${LOOKUP_RECIPES.join(', ')}. Try again.` });
      continue;
    }
    if (toolCalls >= maxSteps) { steps.push({ ...base, raw: parsed.raw, outcome: 'malformed', error: 'step limit' }); return fail('step_limit', `${model} asked for more than ${maxSteps} lookups`); }

    const args: LookupArgs & Record<string, unknown> = { ...(checked as { ok: true; args: LookupArgs }).args };
    toolCalls += 1;
    const gov = await runGovernedTool('live_lookup', { recipe: args.recipe, ...(args.branch ? { branch: args.branch } : {}) }, hooks, context, toolCalls);
    if (gov.approval === 'denied') { steps.push({ ...base, raw: parsed.raw, request: args, outcome: 'tool_denied', error: String(gov.output.error) }); return fail('tool_denied', String(gov.output.error)); }
    if (gov.output.ok !== true) { steps.push({ ...base, raw: parsed.raw, request: args, outcome: 'tool_failed', error: String(gov.output.error) }); return fail('tool_failed', String(gov.output.error)); }
    const found = (gov.output as { evidence: LookupEvidence }).evidence;
    evidence.push(found);
    steps.push({ ...base, raw: parsed.raw, request: args, outcome: 'tool_ok' });
    const facts = renderFacts(found);
    if (mode === 'native') {
      messages.push({ role: 'assistant', content: '', tool_calls: turnCalls(turn) });
      messages.push({ role: 'tool', tool_name: 'live_lookup', content: facts });
    } else {
      messages.push({ role: 'assistant', content: parsed.raw });
      messages.push({ role: 'user', content: `Tool result for ${String(args.recipe)}:\n${facts}\n\nIf this is enough, answer. If you still need another lookup, call it.` });
    }
  }
  return fail('step_limit', `${model} did not finish within ${maxSteps} lookups`);
}

const turnCalls = (turn: OllamaChatTurn): unknown[] => turn.tool_calls;
