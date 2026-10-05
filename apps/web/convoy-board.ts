// The agent board: READY, OPEN, REVIEW, FINISHED for every worker (Layer 3: governance, pure). A view over convoys, not a new store, so it cannot disagree with them.
// The words follow Gas City's work items (open, in progress, closed; "ready" is open work with no open blocker). Gas City has no review state, so REVIEW is
// ours and means one thing: the worker produced a result that a human has not yet accepted or rejected.
import type { ConvoyRecord, WorkerRecord } from './convoy.ts';

export type Lane = 'ready' | 'open' | 'review' | 'finished';
export const LANES: readonly Lane[] = ['ready', 'open', 'review', 'finished'];

/** The bead id of a convoy (`tb-1a2b3c4d`) or of one of its workers (`tb-1a2b3c4d.lookup-1`). */
export const beadId = (convoyId: string, workerId?: string): string => `tb-${convoyId.slice(0, 8)}${workerId ? `.${workerId}` : ''}`;

export interface BoardCard {
  /** The worker's bead (see convoy-beads.ts). */
  bead: string;
  blocked_by: string[];
  convoy_id: string;
  goal: string;
  worker_id: string;
  name: string;
  model: string | null;
  kind: string;
  lane: Lane;
  /** Why a finished card is finished: completed, failed, skipped, accepted, rejected, cancelled... */
  detail: string;
  at: number;
}

const WAITING = new Set(['PLANNED', 'PENDING']);
const DEAD = new Set(['REJECTED', 'EXPIRED', 'CANCELLED']);

/** The lane of one worker, or null when it is not on the board yet (its convoy is a plan or waits for approval, or its dependencies are not finished). */
export function laneOf(c: ConvoyRecord, w: WorkerRecord): { lane: Lane; detail: string } | null {
  if (WAITING.has(c.state)) return null;
  if (DEAD.has(c.state)) return { lane: 'finished', detail: c.state.toLowerCase() };
  if (w.status === 'running') return { lane: 'open', detail: 'running' };
  if (w.status === 'pending') {
    if (c.state === 'FAILED') return { lane: 'finished', detail: 'never started' };
    const planned = c.plan.workers.find((p) => p.id === w.id);
    const blocked = (planned?.depends_on ?? []).some((d) => {
      const dep = c.workers.find((x) => x.id === d);
      return !dep || (dep.status !== 'completed' && dep.status !== 'failed' && dep.status !== 'skipped');
    });
    // APPROVED/RUNNING with its blockers closed: ready for an agent to take.
    return blocked ? null : { lane: 'ready', detail: 'ready' };
  }
  if (w.status === 'skipped') return { lane: 'finished', detail: 'skipped' };
  // completed or failed: judged by a human first when there is something to judge
  const review = c.review;
  if (!['COMPLETED', 'PARTIAL', 'FAILED'].includes(c.state)) return { lane: 'finished', detail: w.status };
  if (w.status === 'completed' && review?.state === 'pending') return { lane: 'review', detail: 'awaiting human review' };
  if (review?.state === 'accepted' || review?.state === 'rejected') return { lane: 'finished', detail: `${w.status}, outcome ${review.state}` };
  return { lane: 'finished', detail: w.status === 'failed' ? `failed${w.failure ? `: ${w.failure.kind}` : ''}` : w.status };
}

export function boardFor(convoys: ConvoyRecord[]): { lanes: Record<Lane, BoardCard[]>; not_ready: number; counts: Record<Lane, number> } {
  const lanes: Record<Lane, BoardCard[]> = { ready: [], open: [], review: [], finished: [] };
  let notReady = 0;
  for (const c of convoys) {
    for (const w of c.workers) {
      const l = laneOf(c, w);
      if (!l) { notReady += 1; continue; }
      lanes[l.lane].push({ bead: beadId(c.id, w.id), blocked_by: (c.plan.workers.find((p) => p.id === w.id)?.depends_on ?? []).map((d) => beadId(c.id, d)).filter((b) => { const dep = c.workers.find((x) => beadId(c.id, x.id) === b); return !dep || (dep.status !== 'completed' && dep.status !== 'failed' && dep.status !== 'skipped'); }), convoy_id: c.id, goal: c.goal.slice(0, 120), worker_id: w.id, name: w.name, model: w.model, kind: w.kind, lane: l.lane, detail: l.detail, at: c.updated_at });
    }
  }
  for (const lane of LANES) lanes[lane].sort((a, b) => b.at - a.at);
  return { lanes, not_ready: notReady, counts: { ready: lanes.ready.length, open: lanes.open.length, review: lanes.review.length, finished: lanes.finished.length } };
}
