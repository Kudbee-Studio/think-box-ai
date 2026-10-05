// A convoy's JOB STATE as the existing 100-cell cube (Layer 3: governance, pure). No new token model and no new store: the Convoy is the source of truth and this
// replays its real facts into the same reducer the dashboard cube already uses (`think-cube-state.js`). Recomputed on every read, so it can never disagree
// with the convoy. A stage is driven only by a fact the convoy actually holds; the stages with no signal stay off and are listed as such.
import { applyEvent, createInitialCubeState, summarize } from './public/js/think-cube-state.js';
import type { ConvoyRecord } from './convoy.ts';

export interface JobStateCell { index: number; role: string; active: boolean; locked: boolean; disrupted: boolean; shared: boolean }

export interface JobState {
  stage: string;
  verdict: 'pass' | 'fail' | null;
  stable: boolean;
  summary: { activeCount: number; lockedCount: number; disruptedCount: number; sharedCount: number };
  cells: JobStateCell[];
  /** The facts each stage was driven by, so the view can say what it is showing. */
  facts: { workers: number; tool_calls: number; evidence_records: number; unsupported_claims: number; failed_workers: number; learned_tokens: number };
  /** Stages driven by a real convoy fact, and stages that have no signal for a convoy (always off). */
  signals: { driven: string[]; no_signal: string[] };
}

const LIVE_STATES = new Set(['APPROVED', 'RUNNING', 'COMPLETED', 'PARTIAL', 'FAILED']);
const FINISHED = new Set(['COMPLETED', 'PARTIAL', 'FAILED']);

export function projectJobState(c: ConvoyRecord): JobState {
  const driven: string[] = [];
  let s = createInitialCubeState();
  const step = (stage: string, payload: Record<string, unknown> = {}): void => { s = applyEvent(s, { stage, payload }); driven.push(stage); };
  const evidenceRecords = c.evidence.length + (c.repo_evidence?.length ?? 0);
  const unsupported = c.grounding?.unsupported?.length ?? 0;
  const failedWorkers = c.workers.filter((w) => w.status === 'failed').length;
  const learned = c.learned_tokens?.length ?? 0;
  step('intent', { tokenId: c.id });
  step('decompose', { opportunities: c.plan.workers.length });
  if (LIVE_STATES.has(c.state)) {
    const launched = c.workers.filter((w) => w.status !== 'pending' && w.status !== 'skipped');
    if (launched.length) step('swarm', { boxIds: launched.map((w) => w.run_id ?? w.id), specialistIds: launched.map((w) => w.id) });
    if (c.tool_calls) step('execution', { step: c.tool_calls });
    if (evidenceRecords) step('evidence', { evidenceCount: evidenceRecords });
    if (unsupported + failedWorkers) step('challenge', { vulnerabilities: unsupported + failedWorkers });
    if (FINISHED.has(c.state)) {
      step('jury', { passed: c.outcome === 'success' && c.grounding?.status !== 'GROUNDING FAILED' });
      if (c.outcome === 'success') step('proof');
    }
    if (learned) step('think_token', { tokenId: c.learned_tokens![0]!.id });
  }
  const sum = summarize(s);
  return {
    stage: s.stage, verdict: s.verdict, stable: s.stable,
    summary: { activeCount: sum.activeCount, lockedCount: sum.lockedCount, disruptedCount: sum.disruptedCount, sharedCount: sum.sharedCount },
    cells: s.cells.map((x: any) => ({ index: x.index, role: x.role, active: x.active, locked: x.locked, disrupted: x.disrupted, shared: x.shared })),
    facts: { workers: c.plan.workers.length, tool_calls: c.tool_calls, evidence_records: evidenceRecords, unsupported_claims: unsupported, failed_workers: failedWorkers, learned_tokens: learned },
    signals: { driven: [...new Set(driven)], no_signal: ['repair', 'harvest', 'commons'] },
  };
}
