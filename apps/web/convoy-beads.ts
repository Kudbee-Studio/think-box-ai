// Beads: the unit of work, in Gas City's words (Layer 3: governance, pure). A bead has an id, a title, a type and a status that moves
// `open` -> `in_progress` -> `closed`; a bead with an open blocker is not ready, and a convoy is a bead that groups others. In Think Box a convoy IS a
// convoy bead and each of its workers IS a task bead: this is a VIEW over the convoy records (so it can never disagree with them), not another store.
// Think Box adds one thing Gas City leaves to configuration: a worker's result stays `in_progress` (lane REVIEW) until a human accepts or rejects it.
import { beadId, laneOf, type Lane } from './convoy-board.ts';
import type { ConvoyRecord } from './convoy.ts';

export type BeadStatus = 'open' | 'in_progress' | 'closed';

export interface Bead {
  id: string;
  type: 'convoy' | 'task';
  title: string;
  status: BeadStatus;
  /** Task beads only: where it sits on the agent board; null while it is not on the board yet. */
  lane: Lane | null;
  /** Open and nothing open blocks it: an agent may take it now. */
  ready: boolean;
  /** Bead ids that must close before this one can start. */
  blocked_by: string[];
  /** What an open bead is waiting for, when it is not ready: a human's approval of the plan, or other beads. */
  waiting_for: 'approval' | 'dependencies' | null;
  parent: string | null;
  children: string[];
  assignee: string | null;
  detail: string;
  convoy_id: string;
  worker_id: string | null;
  updated_at: number;
}

const WAITING = new Set(['PLANNED', 'PENDING']);
const FINISHED = new Set(['COMPLETED', 'PARTIAL', 'FAILED', 'REJECTED', 'EXPIRED', 'CANCELLED']);

export function beadsFor(convoys: ConvoyRecord[]): Bead[] {
  const out: Bead[] = [];
  for (const c of convoys) {
    const convoyBead = beadId(c.id);
    const workerBeads: Bead[] = [];
    for (const w of c.workers) {
      const l = laneOf(c, w);
      const planned = c.plan.workers.find((p) => p.id === w.id);
      const closedWorker = (id: string): boolean => { const d = c.workers.find((x) => x.id === id); return Boolean(d && (d.status === 'completed' || d.status === 'failed' || d.status === 'skipped')); };
      const blocking = (planned?.depends_on ?? []).filter((d) => !closedWorker(d)).map((d) => beadId(c.id, d));
      const waiting = !l && WAITING.has(c.state);
      const status: BeadStatus = !l ? 'open' : l.lane === 'ready' ? 'open' : l.lane === 'finished' ? 'closed' : 'in_progress';
      workerBeads.push({
        id: beadId(c.id, w.id), type: 'task', title: `${w.name} — ${c.goal}`.slice(0, 160), status, lane: l?.lane ?? null,
        ready: l?.lane === 'ready', blocked_by: blocking, waiting_for: l?.lane === 'ready' || status !== 'open' ? null : waiting ? 'approval' : blocking.length ? 'dependencies' : null,
        parent: convoyBead, children: [], assignee: w.model, detail: l?.detail ?? (waiting ? 'plan not approved yet' : 'waiting for its dependencies'),
        convoy_id: c.id, worker_id: w.id, updated_at: c.updated_at,
      });
    }
    const allClosed = workerBeads.length > 0 && workerBeads.every((b) => b.status === 'closed');
    const reviewing = c.review?.state === 'pending';
    const status: BeadStatus = WAITING.has(c.state) ? 'open' : FINISHED.has(c.state) && !reviewing && allClosed ? 'closed' : FINISHED.has(c.state) && !reviewing && !workerBeads.length ? 'closed' : 'in_progress';
    out.push({
      id: convoyBead, type: 'convoy', title: c.goal.slice(0, 160), status, lane: null, ready: false, blocked_by: [], waiting_for: WAITING.has(c.state) ? 'approval' : null,
      parent: null, children: workerBeads.map((b) => b.id), assignee: null,
      detail: reviewing ? 'awaiting human review' : `${c.state.toLowerCase()}${c.outcome ? ` · ${c.outcome}` : ''}`, convoy_id: c.id, worker_id: null, updated_at: c.updated_at,
    });
    out.push(...workerBeads);
  }
  return out;
}
