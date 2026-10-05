// Runs an APPROVED convoy with the real workers (Layer 5: runtime). Everything that touches the world is injected, so the same code serves the server
// and its tests, and nothing here invents a result:
//   lookup workers      a local model (Qwen native tools / Gemma constrained JSON, local-tools.ts) or the Mercury worker agent restricted to the one
//                       governed tool `live_lookup`; every answer is checked by the one grounding validator.
//   specialist workers  the existing specialist job (waves, proof, evidence), with the convoy id as the job id.
// A failed worker stays failed with its error and partial evidence. A local worker that fails or fails grounding is retried ONCE on the worker
// agent through the same governed path (the plan named that escalation up front). The worker budget is enforced as the convoy runs.

import { randomUUID } from 'node:crypto';
import { newRunContext, type AgentHooks, type AgentRunResult } from './agent.ts';
import { beadId, laneOf } from './convoy-board.ts';
import type { ConvoyRecord, ConvoyStore, WorkerRecord } from './convoy.ts';
import { validateGrounding, type GroundingResult } from './grounding.ts';
import type { LookupEvidence } from './live-lookup.ts';
import { COLD_LOAD_MS, repoSpec, runLocalToolLoop, type LocalChat } from './local-tools.ts';
import { REPO_TOOLS, repoRoot, verifyQuoteOnDisk, type RepoEvidence } from './repo-tools.ts';
import type { RunRecord, RunStore } from './runs.ts';

export interface RunnerDeps {
  store: ConvoyStore;
  runStore: RunStore;
  chat: LocalChat;
  repo: string | null;
  isLocalModel: (model: string) => boolean;
  /** Creates the child run record for a worker (already tagged with the convoy id as jobId). */
  newChildRun: (goal: string, runId: string, model: string, convoyId: string, workerId: string) => RunRecord;
  /** The governed hooks for a run: allowlist, approvals, confinement, audit events. `capture` receives every tool's full output. */
  hooksFor: (record: RunRecord, signal: AbortSignal, allowedTools: string[]) => AgentHooks;
  /** The Mercury worker agent loop (agent.ts runToolAgent) for one goal. */
  runAgent: (goal: string, model: string, hooks: AgentHooks) => Promise<AgentRunResult>;
  /** The existing specialist job, with the convoy id as its job id. Resolves to the job artifact. */
  runSpecialists: (goal: string, convoyId: string, specialists: string[]) => Promise<Record<string, any>>;
  broadcast: (message: { type: string; data: unknown }) => void;
  signal: AbortSignal;
  now?: () => number;
  /** LEARN mode: turn one verified child run into Think Token candidates through the existing pipeline (no model is called). */
  learn?: (run: RunRecord) => Promise<Array<{ id: string; kind: string; status: string; title: string; duplicate?: boolean }>>;
}

type Grounding = Pick<GroundingResult, 'status' | 'classification' | 'unsupported' | 'checked'>;
const brief = (g: GroundingResult): Grounding => ({ status: g.status, classification: g.classification, unsupported: g.unsupported, checked: g.checked });

interface WorkerOutcome { ok: boolean; answer?: string; grounding: Grounding | null; evidence: LookupEvidence[]; failure?: { kind: string; message: string } }

export async function executeConvoy(deps: RunnerDeps, convoyId: string): Promise<ConvoyRecord> {
  const { store } = deps;
  const c = store.start(convoyId);
  const update = (): void => deps.broadcast({ type: 'convoy_update', data: summarize(c) });
  update();
  try {
    const kind = c.plan.workers[0]?.kind;
    if (kind === 'specialist') await runSpecialistConvoy(deps, c, update);
    else if (kind === 'repo') await runRepoConvoy(deps, c, update);
    else await runLookupConvoy(deps, c, update);
  } catch (err) {
    // An unexpected crash is a failure with its message, never a silent success; partial evidence on the record stays.
    for (const w of c.workers) if (w.status === 'running' || w.status === 'pending') w.status = 'failed';
    store.finish(c.id, 'failed', 'the convoy runner crashed', err instanceof Error ? err.message : String(err));
  }
  // LEARN mode: only a VERIFIED success teaches anything. A failed, partial or ungrounded convoy produces no token candidates.
  if (c.plan.think_mode === 'learn' && c.state === 'COMPLETED' && c.outcome === 'success' && deps.learn) {
    try {
      const learned: NonNullable<ConvoyRecord['learned_tokens']> = [];
      for (const id of c.run_ids) { const run = deps.runStore.get(id); if (run) learned.push(...(await deps.learn(run))); }
      c.learned_tokens = learned;
    } catch (err) { c.learn_error = err instanceof Error ? err.message : String(err); }
    store.save();
  }
  // An operator stop is reported as such, not as a generic failure.
  if (deps.signal.aborted && c.state === 'FAILED' && !String(c.error ?? '').startsWith('stopped by operator')) { c.error = `stopped by operator: ${c.error ?? ''}`.trim(); store.save(); }
  update();
  return c;
}

/** One-row summary for lists and live updates (the full record, with child runs, comes from the detail endpoint). */
export function summarize(c: ConvoyRecord): Record<string, unknown> {
  return {
    id: c.id, goal: c.goal, mode: c.mode, state: c.state, outcome: c.outcome ?? null, created_at: c.created_at, started_at: c.started_at ?? null, finished_at: c.finished_at ?? null,
    workers: c.workers.map((w) => ({ id: w.id, name: w.name, model: w.model, status: w.status, lane: laneOf(c, w)?.lane ?? null, run_id: w.run_id ?? null, bead: beadId(c.id, w.id) })), review: c.review?.state ?? null, cost_usd: c.cost_usd, tool_calls: c.tool_calls, tokens: c.tokens,
    worker_duration_ms: c.worker_duration_ms, duration_ms: c.finished_at && c.started_at ? c.finished_at - c.started_at : null, risk: c.policy.risk,
    grounding: c.grounding?.status ?? null, approval: c.approval?.state ?? null, think_mode: c.plan.think_mode, learned_tokens: c.learned_tokens?.length ?? 0,
  };
}

async function runLookupConvoy(deps: RunnerDeps, c: ConvoyRecord, update: () => void): Promise<void> {
  const { store } = deps;
  const primary = c.workers[0]!;
  let outcome = await runLookupWorker(deps, c, primary, update);
  const failedOrUngrounded = !outcome.ok || outcome.grounding?.status !== 'GROUNDED';
  const esc = c.plan.escalation;
  const deniedOrAborted = outcome.failure?.kind === 'tool_denied' || deps.signal.aborted;
  if (failedOrUngrounded && esc && primary.model && deps.isLocalModel(primary.model) && !deniedOrAborted) {
    // Budget: the escalation is one more worker and more spend; refuse it if the budget is already used up.
    if (c.workers.length + 1 > c.worker_budget.max_workers) store.worker(c, primary.id).failure ??= { kind: 'budget', message: 'no worker budget left to escalate' };
    else if (c.cost_usd >= c.worker_budget.max_cost_usd) store.worker(c, primary.id).failure ??= { kind: 'budget', message: 'no cost budget left to escalate' };
    else {
      const reason = outcome.ok ? `grounding failed (${outcome.grounding?.unsupported.map((u) => `${u.kind} ${u.claim}`).join('; ')})` : `${outcome.failure?.kind}: ${outcome.failure?.message}`;
      const worker: WorkerRecord = { id: 'escalation-1', kind: 'lookup', name: `Escalation to ${esc.model}`, model: esc.model, status: 'pending', cost_usd: 0, duration_ms: 0, tool_calls: 0, tokens: 0 };
      c.workers.push(worker);
      store.save();
      deps.broadcast({ type: 'thought', data: { type: 'routing', content: `Convoy ${c.id.slice(0, 8)}: ${primary.model} did not produce a verified answer (${reason}). Retrying once on ${esc.model} through the same governed lookup path.`, status: 'info', jobId: c.id } });
      const retry = await runLookupWorker(deps, c, worker, update);
      // The retry's result is the convoy's result when it produced an answer (verified or not) or when the first try had produced nothing at all.
      if (retry.ok || !outcome.ok) outcome = retry;
    }
  }
  store.aggregate(c);
  if (outcome.ok && outcome.grounding?.status === 'GROUNDED') {
    c.final_answer = outcome.answer;
    c.grounding = outcome.grounding;
    store.finish(c.id, 'success', 'verified answer produced; every claim traced to returned evidence');
  } else if (outcome.ok) {
    c.grounding = outcome.grounding ?? undefined;
    store.finish(c.id, 'grounding_failed', 'GROUNDING FAILED: the answer was not shown as verified', `GROUNDING FAILED (${outcome.grounding?.classification})`);
  } else {
    store.finish(c.id, 'failed', `worker failed: ${outcome.failure?.kind}`, `${outcome.failure?.kind}: ${outcome.failure?.message}`);
  }
}

async function runLookupWorker(deps: RunnerDeps, c: ConvoyRecord, worker: WorkerRecord, update: () => void): Promise<WorkerOutcome> {
  const { store, runStore } = deps;
  const model = worker.model!;
  const now = deps.now ?? Date.now;
  const startedAt = now();
  worker.status = 'running';
  const runId = randomUUID();
  const record = deps.newChildRun(c.goal, runId, model, c.id, worker.id);
  worker.run_id = record.id;
  c.run_ids.push(record.id);
  store.save();
  update();
  const evidence: LookupEvidence[] = [];
  let outcome: WorkerOutcome;
  let cost = 0; let tokens = 0; let toolCalls = 0;
  try {
    const hooks = deps.hooksFor(record, deps.signal, ['live_lookup']);
    const inner = hooks.onToolOutput;
    const failedTools: string[] = [];
    hooks.onToolOutput = (name, args, output) => {
      inner?.(name, args, output);
      if (name !== 'live_lookup') return;
      if (output.ok === true && (output as { evidence?: LookupEvidence }).evidence) evidence.push((output as { evidence: LookupEvidence }).evidence);
      else failedTools.push(String(output.error ?? 'the lookup failed'));
    };
    if (deps.isLocalModel(model)) {
      const r = await runLocalToolLoop({ model, goal: c.goal, hooks, context: newRunContext(), chat: deps.chat, repo: deps.repo, signal: deps.signal });
      tokens = r.prompt_tokens + r.completion_tokens; toolCalls = r.tool_calls;
      runStore.addEvent(record, { kind: 'model', step: r.steps.length + 3, latency_ms: 0, prompt_tokens: 0, completion_tokens: 0, cost_usd: 0, tool_calls: [], content: routeLine('lookup', r.model, r.mode, r.latency_ms, r.cold_load_ms) });
      outcome = r.success ? { ok: true, answer: r.answer, grounding: r.grounding ? brief(r.grounding) : null, evidence: r.evidence } : { ok: false, grounding: null, evidence: r.evidence, failure: r.failure };
      for (const step of r.steps) runStore.addEvent(record, { kind: 'model', step: step.step, latency_ms: step.latency_ms, prompt_tokens: step.prompt_tokens, completion_tokens: step.completion_tokens, cost_usd: 0, tool_calls: step.request ? ['live_lookup'] : [], content: `${step.outcome}${step.error ? `: ${step.error}` : ''} ${step.raw}`.slice(0, 600) });
    } else {
      const r = await deps.runAgent(c.goal, model, hooks);
      cost = r.cost_usd; tokens = r.tokens; toolCalls = r.tool_calls;
      if (!r.success) outcome = { ok: false, grounding: null, evidence, failure: { kind: r.stopped ? 'stopped' : 'agent_failed', message: r.error ?? 'the worker agent failed' } };
      // No evidence means no verified answer, and the cause is the lookup: a tool that failed (or was denied), or one that was never called.
      else if (!evidence.length) {
        const denied = failedTools.find((e) => /^Denied by human reviewer/.test(e));
        outcome = { ok: false, grounding: null, evidence, failure: denied ? { kind: 'tool_denied', message: denied } : failedTools.length ? { kind: 'tool_failed', message: failedTools[0]! } : { kind: 'no_tool_call', message: `${model} answered without looking anything up, so the answer cannot be verified` } };
      } else {
        const g = validateGrounding(r.result ?? '', evidence);
        outcome = { ok: true, answer: r.result, grounding: brief(g), evidence };
      }
    }
  } catch (err) {
    outcome = { ok: false, grounding: null, evidence, failure: { kind: deps.signal.aborted ? 'stopped' : 'error', message: err instanceof Error ? err.message : String(err) } };
  }
  worker.status = outcome.ok ? 'completed' : 'failed';
  worker.cost_usd = cost; worker.tokens = tokens; worker.tool_calls = toolCalls; worker.duration_ms = now() - startedAt;
  if (outcome.failure) worker.failure = outcome.failure;
  if (outcome.grounding) worker.grounding = outcome.grounding;
  if (outcome.answer) worker.answer = outcome.answer;
  record.grounding = outcome.grounding ?? undefined;
  c.evidence.push(...outcome.evidence); // partial evidence of a failed worker is kept too
  runStore.finish(record, outcome.ok
    ? { status: 'completed', result: outcome.answer }
    : { status: 'failed', error: `${outcome.failure?.kind}: ${outcome.failure?.message}`, failure_kind: outcome.failure?.kind === 'stopped' ? 'stopped' : outcome.failure?.kind === 'tool_denied' ? 'denied' : 'error' });
  store.aggregate(c);
  update();
  return outcome;
}

async function runSpecialistConvoy(deps: RunnerDeps, c: ConvoyRecord, update: () => void): Promise<void> {
  const { store, runStore } = deps;
  for (const w of c.workers) w.status = 'running';
  update();
  const artifact = await deps.runSpecialists(c.goal, c.id, c.workers.map((w) => w.id)); // exactly the approved plan's workers
  const executions: Array<Record<string, any>> = Array.isArray(artifact.specialistsExecuted) ? artifact.specialistsExecuted : [];
  for (const w of c.workers) {
    const e = executions.find((x) => x.specialistId === w.id);
    if (!e) { w.status = 'skipped'; w.failure = { kind: 'not_run', message: String(artifact.error ?? artifact.status ?? 'the specialist job did not run this worker') }; continue; }
    w.status = e.status === 'completed' ? 'completed' : 'failed';
    w.run_id = e.runId;
    if (e.runId) c.run_ids.push(e.runId);
    w.cost_usd = Number(e.resourceUsage?.costUsd) || 0; w.tokens = Number(e.resourceUsage?.tokens) || 0; w.duration_ms = Number(e.resourceUsage?.durationMs) || 0;
    w.tool_calls = Array.isArray(e.events) ? e.events.filter((ev: any) => ev?.kind === 'tool').length : 0;
    if (e.failure) w.failure = { kind: 'specialist_failed', message: String(e.failure) };
    if (typeof e.output === 'string') w.answer = e.output.slice(0, 4000);
  }
  store.aggregate(c);
  const done = c.workers.filter((w) => w.status === 'completed').length;
  const budgetBlown = c.cost_usd > c.worker_budget.max_cost_usd;
  const completed = artifact.status === 'COMPLETED' && done === c.workers.length;
  c.final_answer = completed ? executions.map((e) => `${e.specialistId}: ${String(e.output ?? '').slice(0, 600)}`).join('\n\n') : undefined;
  void runStore;
  if (completed && !budgetBlown) store.finish(c.id, 'success', 'all specialists completed and the proof was accepted');
  else if (completed && budgetBlown) store.finish(c.id, 'partial', `completed, but spend $${c.cost_usd} exceeded the cost budget $${c.worker_budget.max_cost_usd}`, 'cost budget exceeded');
  else if (done > 0) store.finish(c.id, 'partial', `${done} of ${c.workers.length} worker(s) completed; partial evidence kept`, String(artifact.error ?? artifact.validation?.reason ?? 'one or more workers failed'));
  else store.finish(c.id, 'failed', 'no worker completed', String(artifact.error ?? 'all workers failed'));
}

/**
 * A read-only repository investigation: one local worker looks with repo_search / repo_read and reports one finding. The finding must trace to what its
 * own tool calls returned (grounding), and its quote is then re-read from disk by this code, outside the model's loop, before the convoy may succeed.
 * Nothing is written. A model that finds nothing and says so is a success; a fabricated file, line, quote or absence claim is not.
 */
/** One line for the record: which model ran which lane, how long it took, and whether the model had to be loaded (cold) or was already warm. */
export function routeLine(lane: 'lookup' | 'repo', model: string, mode: string, latencyMs: number, coldLoadMs: number): string {
  return `route: lane=${lane} model=${model} mode=${mode} latency=${(latencyMs / 1000).toFixed(1)}s ${coldLoadMs >= COLD_LOAD_MS ? `cold (model load ${(coldLoadMs / 1000).toFixed(1)}s)` : 'warm'}`;
}

async function runRepoConvoy(deps: RunnerDeps, c: ConvoyRecord, update: () => void): Promise<void> {
  const { store, runStore } = deps;
  const worker = c.workers[0]!;
  const model = worker.model!;
  const now = deps.now ?? Date.now;
  const startedAt = now();
  worker.status = 'running';
  const record = deps.newChildRun(c.goal, randomUUID(), model, c.id, worker.id);
  worker.run_id = record.id;
  c.run_ids.push(record.id);
  store.save();
  update();
  let evidence: RepoEvidence[] = [];
  let tokens = 0; let toolCalls = 0;
  let failure: { kind: string; message: string } | undefined;
  let grounding: Grounding | null = null;
  let answer: string | undefined;
  let diskCheck: { disk_verified: boolean; reason?: string } | undefined;
  try {
    const hooks = deps.hooksFor(record, deps.signal, [...REPO_TOOLS]);
    const r = await runLocalToolLoop<RepoEvidence>({ model, goal: c.goal, hooks, context: newRunContext(), chat: deps.chat, repo: null, spec: repoSpec(), maxSteps: 8, signal: deps.signal });
    evidence = r.evidence; tokens = r.prompt_tokens + r.completion_tokens; toolCalls = r.tool_calls;
    runStore.addEvent(record, { kind: 'model', step: r.steps.length + 3, latency_ms: 0, prompt_tokens: 0, completion_tokens: 0, cost_usd: 0, tool_calls: [], content: routeLine('repo', r.model, r.mode, r.latency_ms, r.cold_load_ms) });
    for (const step of r.steps) runStore.addEvent(record, { kind: 'model', step: step.step, latency_ms: step.latency_ms, prompt_tokens: step.prompt_tokens, completion_tokens: step.completion_tokens, cost_usd: 0, tool_calls: step.request ? ['repo'] : [], content: `${step.outcome}${step.error ? `: ${step.error}` : ''} ${step.raw}`.slice(0, 600) });
    if (r.recovery) runStore.addEvent(record, { kind: 'model', step: r.steps.length + 2, latency_ms: 0, prompt_tokens: 0, completion_tokens: 0, cost_usd: 0, tool_calls: [], content: `empty-reply recovery: ${r.recovery.path}${r.recovery.recovered_by ? ` (recovered by ${r.recovery.recovered_by})` : r.recovery.path === 'exhausted' ? ' (needs a stronger lane; not auto-rerun yet)' : ''}, ${r.recovery.retries} retry, ${r.recovery.assist_calls} engine tool call(s)`.slice(0, 600) });
    if (r.absence) runStore.addEvent(record, { kind: 'model', step: r.steps.length + 1, latency_ms: 0, prompt_tokens: 0, completion_tokens: 0, cost_usd: 0, tool_calls: [], content: `absence check: ${r.absence.path}${r.absence.symbol ? ` for ${r.absence.symbol}` : ''}${r.absence.aliases.length ? ` (aliases ${r.absence.aliases.join(', ')})` : ''}, ${r.absence.contradicted} contradicting reference(s), ${r.absence.searches} engine search(es)${r.absence.reason ? `; ${r.absence.reason}` : ''}`.slice(0, 600) });
    if (!r.success) failure = r.failure;
    else {
      grounding = r.grounding ? brief(r.grounding) : null;
      c.finding = r.finding;
      if (r.finding && r.finding.found && grounding?.status === 'GROUNDED') {
        const disk = await verifyQuoteOnDisk(String(r.finding.file), Number(r.finding.line), String(r.finding.quote), repoRoot());
        diskCheck = { disk_verified: disk.ok, ...(disk.reason ? { reason: disk.reason } : {}) };
        c.finding_check = diskCheck;
      }
      answer = r.finding?.found ? `${r.finding.file}:${r.finding.line} \u2014 ${r.finding.claim}` : `No finding: ${r.finding?.reason ?? ''}`;
    }
  } catch (err) {
    failure = { kind: deps.signal.aborted ? 'stopped' : 'error', message: err instanceof Error ? err.message : String(err) };
  }
  c.repo_evidence.push(...evidence);
  const ok = !failure;
  worker.status = ok ? 'completed' : 'failed';
  worker.cost_usd = 0; worker.tokens = tokens; worker.tool_calls = toolCalls; worker.duration_ms = now() - startedAt;
  if (failure) worker.failure = failure;
  if (grounding) worker.grounding = grounding;
  if (answer) worker.answer = answer;
  record.grounding = grounding ?? undefined;
  runStore.finish(record, ok ? { status: 'completed', result: answer } : { status: 'failed', error: `${failure!.kind}: ${failure!.message}`, failure_kind: failure!.kind === 'stopped' ? 'stopped' : 'error' });
  store.aggregate(c);
  if (failure) { store.finish(c.id, 'failed', `worker failed: ${failure.kind}`, `${failure.kind}: ${failure.message}`); return; }
  if (grounding?.status !== 'GROUNDED') {
    c.grounding = grounding ?? undefined;
    const escalate = grounding?.classification === 'needs_escalation';
    store.finish(c.id, 'grounding_failed', escalate ? 'GROUNDING FAILED: this absence claim could not be checked here and needs a stronger lane (not auto-rerun yet)' : 'GROUNDING FAILED: the finding was not shown as verified', `GROUNDING FAILED (${grounding?.classification})`);
    return;
  }
  if (c.finding?.found && !diskCheck?.disk_verified) {
    c.grounding = grounding;
    store.finish(c.id, 'grounding_failed', 'the quote could not be re-read from disk', `disk re-check failed: ${diskCheck?.reason ?? 'unknown'}`);
    return;
  }
  c.grounding = grounding;
  c.final_answer = answer;
  store.finish(c.id, 'success', c.finding?.found ? 'finding grounded in the tool evidence and re-read from disk' : 'the worker looked and reported nothing worth flagging');
}
