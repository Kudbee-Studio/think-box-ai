// Convoy: ONE parent record for a goal's planned and executed work (Layer 3: governance).
// A convoy groups the model/worker runs a goal needed under a single id, carries the plan, the worker budget, the policy evaluation and the approval,
// and aggregates the children's cost, tool calls and time. The dashboard shows exactly one row per convoy and drills down to its runs, their tools and
// their evidence; child runs are never separate top-level objects. The same record serves a dry run (PLAN ONLY) and a live execution.
//
// Every state change is appended to a hash-chained event log. The approval is one of those events, so "who approved what, when, under which policy"
// is part of the evidence chain and tampering with a past entry is detectable (verifyChain). Nothing here runs a worker or calls a model.

import { createHash, randomUUID } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import type { LookupEvidence } from './live-lookup.ts';
import type { GroundingResult } from './grounding.ts';
import type { ConvoyPlan, PlannedWorker, PolicyEvaluation, WorkerBudget } from './mayor.ts';

export type ConvoyMode = 'plan_only' | 'live';
export type ConvoyState = 'PLANNED' | 'PENDING' | 'APPROVED' | 'RUNNING' | 'COMPLETED' | 'PARTIAL' | 'FAILED' | 'REJECTED' | 'EXPIRED' | 'CANCELLED';
export type ConvoyOutcome = 'success' | 'partial' | 'failed' | 'grounding_failed';

/** What each state may become. Anything else is refused: a rejected convoy cannot run, a completed one cannot be re-approved. */
export const TRANSITIONS: Readonly<Record<ConvoyState, readonly ConvoyState[]>> = {
  PLANNED: ['PENDING', 'CANCELLED'],
  PENDING: ['APPROVED', 'REJECTED', 'EXPIRED', 'CANCELLED'],
  APPROVED: ['RUNNING', 'CANCELLED'],
  RUNNING: ['COMPLETED', 'PARTIAL', 'FAILED'],
  COMPLETED: [], PARTIAL: [], FAILED: [], REJECTED: [], EXPIRED: [], CANCELLED: [],
};

export const APPROVAL_TTL_MS = 15 * 60 * 1000;

export interface ConvoyEvent {
  seq: number;
  at: number;
  state: ConvoyState;
  /** Who caused it: `human`, `system` or `worker:<id>`. Only `human` may approve. */
  by: string;
  note: string;
  prev: string;
  hash: string;
}

export interface ApprovalRecord {
  id: string;
  convoy_id: string;
  state: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED' | 'CANCELLED';
  requested_at: number;
  expires_at: number;
  decided_at?: number;
  decided_by?: string;
  note?: string;
  /** What was put in front of the approver, frozen at submit time: the approval is for exactly this. */
  snapshot: {
    goal: string;
    workers: Array<Pick<PlannedWorker, 'id' | 'kind' | 'name' | 'model' | 'tools' | 'permission'>>;
    worker_budget: WorkerBudget;
    tools: string[];
    policy: PolicyEvaluation;
    estimated_cost_usd: number | null;
    risk: PolicyEvaluation['risk'];
  };
}

export interface WorkerRecord {
  id: string;
  kind: PlannedWorker['kind'];
  name: string;
  model: string | null;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  run_id?: string;
  cost_usd: number;
  duration_ms: number;
  tool_calls: number;
  tokens: number;
  failure?: { kind: string; message: string };
  /** The grounding verdict of this worker's answer, where it gave a live-data answer. */
  grounding?: Pick<GroundingResult, 'status' | 'classification' | 'unsupported' | 'checked'>;
  answer?: string;
}

export interface ConvoyRecord {
  id: string;
  goal: string;
  mode: ConvoyMode;
  state: ConvoyState;
  created_at: number;
  updated_at: number;
  profile_id?: string;
  plan: ConvoyPlan;
  policy: PolicyEvaluation;
  approval: ApprovalRecord | null;
  worker_budget: WorkerBudget;
  workers: WorkerRecord[];
  /** Child run ids (each run record holds its own steps, tools and evidence). */
  run_ids: string[];
  evidence: LookupEvidence[];
  cost_usd: number;
  tool_calls: number;
  tokens: number;
  /** Sum of the children's own running time (workers in a wave overlap, so this can exceed the wall time). */
  worker_duration_ms: number;
  started_at?: number;
  finished_at?: number;
  outcome?: ConvoyOutcome;
  final_answer?: string;
  /** Verified sentence only; absent when grounding failed. */
  grounding?: Pick<GroundingResult, 'status' | 'classification' | 'unsupported' | 'checked'>;
  error?: string;
  events: ConvoyEvent[];
}

const hashOf = (parts: Array<string | number>): string => createHash('sha256').update(parts.join('\u0000')).digest('hex');
const GENESIS = '0'.repeat(64);

function appendEvent(c: ConvoyRecord, state: ConvoyState, by: string, note: string, now: number): void {
  const prev = c.events.at(-1)?.hash ?? GENESIS;
  const seq = c.events.length + 1;
  c.events.push({ seq, at: now, state, by, note, prev, hash: hashOf([c.id, seq, now, state, by, note, prev]) });
}

/** True when no event of the convoy was altered, removed or reordered. */
export function verifyChain(c: Pick<ConvoyRecord, 'id' | 'events'>): { ok: true } | { ok: false; at: number } {
  let prev = GENESIS;
  for (const e of c.events) {
    if (e.prev !== prev || e.hash !== hashOf([c.id, e.seq, e.at, e.state, e.by, e.note, prev])) return { ok: false, at: e.seq };
    prev = e.hash;
  }
  return { ok: true };
}

/** The one-line mode of a convoy, worded identically in the dashboard badge and the CLI so PLAN ONLY and LIVE EXECUTION are never confused. */
export function modeLabel(state: ConvoyState): string {
  switch (state) {
    case 'PLANNED': return 'PLAN ONLY \u2014 NOTHING HAS RUN';
    case 'PENDING': return 'PENDING APPROVAL \u2014 NOTHING RUNS YET';
    case 'REJECTED': case 'EXPIRED': case 'CANCELLED': return `${state} \u2014 NEVER RAN`;
    case 'APPROVED': return 'APPROVED \u2014 STARTING LIVE';
    default: return 'LIVE EXECUTION';
  }
}

export class ConvoyError extends Error {
  readonly code: 'not_found' | 'bad_transition' | 'forbidden' | 'blocked';
  constructor(message: string, code: 'not_found' | 'bad_transition' | 'forbidden' | 'blocked') { super(message); this.code = code; }
}

/** Who may approve: only a human. A model, a worker or the system can never approve, whatever it claims. */
export const canApprove = (by: string): boolean => by === 'human';

export class ConvoyStore {
  private convoys: ConvoyRecord[] = [];
  private saveTimer: NodeJS.Timeout | null = null;
  private readonly file: string;
  private profileId: string | undefined;
  private readonly now: () => number;
  private readonly max: number;
  constructor(file: string, profileId?: string, now: () => number = Date.now, max = 300) {
    this.file = file; this.profileId = profileId; this.now = now; this.max = max;
    fs.mkdirSync(path.dirname(file), { recursive: true });
    try {
      this.convoys = JSON.parse(fs.readFileSync(file, 'utf8')) as ConvoyRecord[];
      // A convoy still RUNNING at boot was interrupted by a restart: it is a failure, not something that is still going.
      for (const c of this.convoys) if (c.state === 'RUNNING' || c.state === 'APPROVED') this.finishRecord(c, 'FAILED', 'system', 'Interrupted by server restart', 'failed', 'Interrupted by server restart');
    } catch (err) {
      this.convoys = [];
      if ((err as NodeJS.ErrnoException).code !== 'ENOENT') {
        const kept = `${file}.corrupt-${new Date().toISOString().replace(/[:.]/g, '-')}`;
        try { fs.copyFileSync(file, kept); } catch { /* unreadable */ }
        console.warn(`[convoys] could not read ${file}; starting empty, original kept at ${kept}`);
      }
    }
  }

  setProfile(profileId?: string): void { this.flush(); this.profileId = profileId; }
  private visible(): ConvoyRecord[] { return this.profileId ? this.convoys.filter((c) => c.profile_id === this.profileId) : this.convoys; }

  /** A new convoy from a plan. `PLANNED` means PLAN ONLY: nothing has run and nothing has been approved. */
  create(goal: string, plan: ConvoyPlan, policy: PolicyEvaluation): ConvoyRecord {
    const now = this.now();
    const c: ConvoyRecord = {
      id: randomUUID(), goal, mode: 'plan_only', state: 'PLANNED', created_at: now, updated_at: now, profile_id: this.profileId,
      plan, policy, approval: null, worker_budget: plan.budget,
      workers: plan.workers.map((w) => ({ id: w.id, kind: w.kind, name: w.name, model: w.model, status: 'pending', cost_usd: 0, duration_ms: 0, tool_calls: 0, tokens: 0 })),
      run_ids: [], evidence: [], cost_usd: 0, tool_calls: 0, tokens: 0, worker_duration_ms: 0, events: [],
    };
    appendEvent(c, 'PLANNED', 'system', 'plan created (PLAN ONLY: no worker started, nothing approved)', now);
    this.convoys.push(c);
    if (this.convoys.length > this.max) this.convoys.splice(0, this.convoys.length - this.max);
    this.save();
    return c;
  }

  get(id: string): ConvoyRecord | undefined {
    const c = this.visible().find((x) => x.id === id);
    if (c) this.expireIfStale(c);
    return c;
  }

  list(limit = 50): ConvoyRecord[] {
    const items = this.visible().slice(-limit).reverse();
    for (const c of items) this.expireIfStale(c);
    return items;
  }

  private expireIfStale(c: ConvoyRecord): void {
    if (c.state === 'PENDING' && c.approval && this.now() >= c.approval.expires_at) {
      c.approval.state = 'EXPIRED';
      c.approval.decided_at = this.now();
      c.approval.decided_by = 'system';
      c.approval.note = 'approval window elapsed';
      this.move(c, 'EXPIRED', 'system', 'approval window elapsed: nothing ran');
    }
  }

  private move(c: ConvoyRecord, to: ConvoyState, by: string, note: string): void {
    if (!TRANSITIONS[c.state].includes(to)) throw new ConvoyError(`a ${c.state} convoy cannot become ${to}`, 'bad_transition');
    c.state = to;
    c.updated_at = this.now();
    appendEvent(c, to, by, note, c.updated_at);
    this.save();
  }

  /** PLANNED -> PENDING: put the frozen plan in front of a human. Refused when policy denies it or the plan cannot run. */
  submit(id: string): ConvoyRecord {
    const c = this.must(id);
    if (!c.plan.executable || c.policy.decision === 'denied') throw new ConvoyError(`this plan cannot be submitted: ${[...new Set([...c.plan.blocked_reasons, ...c.policy.rules.filter((r) => r.effect === 'deny').map((r) => r.reason)])].join('; ') || 'denied by policy'}`, 'blocked');
    const now = this.now();
    c.approval = {
      id: randomUUID(), convoy_id: c.id, state: 'PENDING', requested_at: now, expires_at: now + APPROVAL_TTL_MS,
      snapshot: {
        goal: c.goal,
        workers: c.plan.workers.map((w) => ({ id: w.id, kind: w.kind, name: w.name, model: w.model, tools: w.tools, permission: w.permission })),
        worker_budget: c.worker_budget, tools: [...new Set(c.plan.workers.flatMap((w) => w.tools))], policy: c.policy,
        estimated_cost_usd: c.plan.budget_use.estimated_cost_usd, risk: c.policy.risk,
      },
    };
    this.move(c, 'PENDING', 'system', `queued for human approval until ${new Date(c.approval.expires_at).toISOString()} (risk ${c.policy.risk})`);
    return c;
  }

  /** PENDING -> APPROVED or REJECTED. Only a human decides; a stale approval is already EXPIRED. */
  decide(id: string, decision: 'approve' | 'reject', by: string, note = ''): ConvoyRecord {
    const c = this.must(id);
    if (!canApprove(by)) throw new ConvoyError(`"${by}" cannot ${decision} a convoy: only a human decides`, 'forbidden');
    if (c.state !== 'PENDING' || !c.approval) throw new ConvoyError(`a ${c.state} convoy is not waiting for approval`, 'bad_transition');
    c.approval.state = decision === 'approve' ? 'APPROVED' : 'REJECTED';
    c.approval.decided_at = this.now();
    c.approval.decided_by = by;
    c.approval.note = note;
    this.move(c, decision === 'approve' ? 'APPROVED' : 'REJECTED', by, `${decision}d by ${by} for exactly this snapshot (${c.approval.snapshot.workers.length} worker(s), budget ${c.worker_budget.max_workers}/$${c.worker_budget.max_cost_usd}, risk ${c.approval.snapshot.risk})${note ? `: ${note}` : ''}`);
    return c;
  }

  cancel(id: string, by: string, note = 'cancelled'): ConvoyRecord {
    const c = this.must(id);
    if (c.approval && c.approval.state === 'PENDING') { c.approval.state = 'CANCELLED'; c.approval.decided_at = this.now(); c.approval.decided_by = by; }
    this.move(c, 'CANCELLED', by, note);
    return c;
  }

  /** APPROVED -> RUNNING. Refused unless a human approved: there is no other way to a running convoy. */
  start(id: string): ConvoyRecord {
    const c = this.must(id);
    if (c.state !== 'APPROVED' || c.approval?.state !== 'APPROVED' || !canApprove(c.approval.decided_by ?? '')) throw new ConvoyError('a convoy only runs after a human approved it', 'forbidden');
    c.mode = 'live';
    c.started_at = this.now();
    this.move(c, 'RUNNING', 'system', 'execution started under the approved plan');
    return c;
  }

  worker(c: ConvoyRecord, id: string): WorkerRecord {
    const w = c.workers.find((x) => x.id === id);
    if (!w) throw new ConvoyError(`unknown worker ${id}`, 'not_found');
    return w;
  }

  /** Called after any change to a worker or its runs: re-derives the totals from the children. */
  aggregate(c: ConvoyRecord): ConvoyRecord {
    c.cost_usd = round6(c.workers.reduce((t, w) => t + w.cost_usd, 0));
    c.tool_calls = c.workers.reduce((t, w) => t + w.tool_calls, 0);
    c.tokens = c.workers.reduce((t, w) => t + w.tokens, 0);
    c.worker_duration_ms = c.workers.reduce((t, w) => t + w.duration_ms, 0);
    c.updated_at = this.now();
    this.save();
    return c;
  }

  private finishRecord(c: ConvoyRecord, to: 'COMPLETED' | 'PARTIAL' | 'FAILED', by: string, note: string, outcome: ConvoyOutcome, error?: string): void {
    c.state = to; // (boot recovery may finish from APPROVED/RUNNING)
    c.outcome = outcome;
    c.finished_at = this.now();
    c.updated_at = c.finished_at;
    if (error) c.error = error;
    appendEvent(c, to, by, note, c.updated_at);
  }

  /** RUNNING -> COMPLETED / PARTIAL / FAILED. A failed worker is never turned into a success: partial evidence stays on the record. */
  finish(id: string, outcome: ConvoyOutcome, note: string, error?: string): ConvoyRecord {
    const c = this.must(id);
    const to = outcome === 'success' ? 'COMPLETED' : outcome === 'partial' ? 'PARTIAL' : 'FAILED';
    if (!TRANSITIONS[c.state].includes(to)) throw new ConvoyError(`a ${c.state} convoy cannot become ${to}`, 'bad_transition');
    this.aggregate(c);
    this.finishRecord(c, to, 'system', note, outcome, error);
    this.save();
    return c;
  }

  private must(id: string): ConvoyRecord {
    const c = this.convoys.find((x) => x.id === id);
    if (!c) throw new ConvoyError(`unknown convoy ${id}`, 'not_found');
    this.expireIfStale(c);
    return c;
  }

  save(): void {
    if (this.saveTimer) return;
    this.saveTimer = setTimeout(() => { this.saveTimer = null; this.flush(); }, 50);
    this.saveTimer.unref?.();
  }
  flush(): void {
    if (this.saveTimer) { clearTimeout(this.saveTimer); this.saveTimer = null; }
    const tmp = `${this.file}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(this.convoys));
    fs.renameSync(tmp, this.file);
  }
}

const round6 = (n: number): number => Math.round(n * 1e6) / 1e6;
