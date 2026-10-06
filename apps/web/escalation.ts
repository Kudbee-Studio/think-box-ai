// The escalation lane for repository investigations (Layer 5: runtime glue). A local model that does not produce a verified finding is retried ONCE on the
// stronger model through the SAME governed loop (same tools, grounding validator, absence engine and disk re-read). This file holds the one decision, "did the
// local attempt produce something we may accept?", and the one attempt function, so the convoy runner and the pre-registered experiment cannot drift apart.
import { newRunContext, type AgentHooks } from './agent.ts';
import { goalShape } from './investigation-assist.ts';
import { repoSpec, runLocalToolLoop, type LocalChat, type LocalToolResult } from './local-tools.ts';
import { repoRoot, verifyQuoteOnDisk, type RepoEvidence } from './repo-tools.ts';

export interface DiskCheck { disk_verified: boolean; reason?: string }
export interface RepoAttempt {
  model: string;
  result: LocalToolResult<RepoEvidence>;
  /** Present when the model reported a found finding that the validator grounded: the quote re-read from disk. */
  disk?: DiskCheck;
}

/** One governed repository investigation on `model`, with the finding's quote re-read from disk outside the model's loop. */
export async function attemptRepo(o: { model: string; goal: string; chat: LocalChat; hooks: AgentHooks; signal?: AbortSignal; maxSteps?: number; root?: string }): Promise<RepoAttempt> {
  const result = await runLocalToolLoop<RepoEvidence>({ model: o.model, goal: o.goal, hooks: o.hooks, context: newRunContext(), chat: o.chat, repo: null, spec: repoSpec(), maxSteps: o.maxSteps ?? 8, signal: o.signal });
  let disk: DiskCheck | undefined;
  const f = result.finding;
  if (result.success && f && f.found && result.grounding?.status === 'GROUNDED') {
    const d = await verifyQuoteOnDisk(String(f.file), Number(f.line), String(f.quote), o.root ?? repoRoot());
    disk = { disk_verified: d.ok, ...(d.reason ? { reason: d.reason } : {}) };
  }
  return { model: o.model, result, ...(disk ? { disk } : {}) };
}

/** True when this attempt produced a finding (or an honest "found nothing") that is grounded and, for a found finding, verified on disk. */
export function accepted(a: RepoAttempt): boolean {
  const r = a.result;
  if (!r.success || r.grounding?.status !== 'GROUNDED') return false;
  return r.finding?.found ? a.disk?.disk_verified === true : true;
}

/**
 * Why a local attempt should be retried on the stronger model, or null when it should not. Never for a denied approval or an operator stop (the human said
 * no). A grounded "found nothing" is retried only for goals that expect a positive finding (an untested function in a named file, the file that defines a
 * constant): there it is the dominant local failure. For "find a function named X" it is a legitimate answer and is kept.
 */
export function repoEscalationReason(goal: string, a: RepoAttempt, aborted = false): string | null {
  const r = a.result;
  if (aborted || r.failure?.kind === 'tool_denied') return null;
  if (!r.success) return `${r.failure?.kind ?? 'failed'}: ${r.failure?.message ?? 'no result'}`.slice(0, 200);
  if (r.grounding?.status !== 'GROUNDED') return `grounding failed (${r.grounding?.classification ?? 'none'})`;
  if (r.finding?.found && a.disk?.disk_verified !== true) return `the quote could not be re-read from disk (${a.disk?.reason ?? 'not checked'})`;
  if (r.finding && r.finding.found === false) {
    const shape = goalShape(goal)?.shape;
    if (shape === 'untested-function' || shape === 'defines-constant') return `reported no finding for a goal that expects one (${shape})`;
  }
  return null;
}
