// Convoy API: plan (dry run), list, detail with child runs, submit for approval, reject, cancel. Approving AND running go through the
// authenticated dashboard/CLI WebSocket session only (server.ts `convoy_approve`), so there is one approval path and it needs a live human session.
import type { Express, Response } from 'express';
import { ConvoyError, verifyChain, type ConvoyRecord, type ConvoyStore } from '../convoy.ts';
import { summarize } from '../convoy-runner.ts';
import { draftPrConfig, draftPrEligibility } from '../draft-pr.ts';
import { projectJobState } from '../convoy-job-state.ts';
import { boardFor, laneOf } from '../convoy-board.ts';
import { beadsFor, type BeadStatus } from '../convoy-beads.ts';
import { THINK_MODES, type ThinkMode } from '../mayor.ts';
import type { RunRecord, RunStore } from '../runs.ts';
import type { Request } from './types.ts';

export interface ConvoyRouteDeps {
  convoyStore: ConvoyStore;
  runStore: RunStore;
  /** Builds a plan (and stores it as PLAN ONLY). Nothing runs. */
  plan: (goal: string, model: string | undefined, budget: unknown, mode: ThinkMode | undefined) => { ok: true; convoy: ConvoyRecord } | { ok: false; error: string };
  /** True when the request comes from the dashboard origin or carries the local token: a human operator, not some other local process. */
  isHuman: (req: Request) => boolean;
}

const status = (e: ConvoyError): number => (e.code === 'not_found' ? 404 : e.code === 'forbidden' ? 403 : 409);

/** The detail view: the convoy, plus each child run with its steps (tools and their output), which is the drill-down. */
export function convoyDetail(c: ConvoyRecord, runStore: RunStore): Record<string, unknown> {
  const runs = c.run_ids.map((id) => runStore.get(id)).filter((r): r is RunRecord => Boolean(r));
  const lanes = Object.fromEntries(c.workers.map((w) => [w.id, laneOf(c, w)]));
  const eligibility = draftPrEligibility(c, draftPrConfig());
  return { ...c, chain: verifyChain(c), summary: summarize(c), job_state: projectJobState(c), lanes, runs, draft_pr_available: eligibility.ok, draft_pr_reason: eligibility.ok ? null : eligibility.error };
}

export function registerConvoyRoutes(app: Express, deps: ConvoyRouteDeps): void {
  const { convoyStore, runStore } = deps;
  const fail = (res: Response, err: unknown): void => {
    if (err instanceof ConvoyError) { res.status(status(err)).json({ error: err.message, code: err.code }); return; }
    throw err;
  };

  // Dry run: the Mayor plans, the policy is evaluated, a PLAN ONLY convoy is stored. No worker starts, nothing is approved.
  app.post('/api/convoys/plan', (req: Request, res: Response) => {
    const body = (req.body ?? {}) as Record<string, unknown>;
    if (body.mode !== undefined && !THINK_MODES.includes(body.mode as ThinkMode)) return res.status(400).json({ error: `mode must be one of ${THINK_MODES.join(', ')}` });
    const result = deps.plan(typeof body.goal === 'string' ? body.goal : '', typeof body.model === 'string' ? body.model : undefined, body.worker_budget, body.mode as ThinkMode | undefined);
    if (!result.ok) return res.status(400).json({ error: result.error });
    res.status(201).json({ convoy: convoyDetail(result.convoy, runStore) });
  });

  app.get('/api/convoys', (req: Request, res: Response) => {
    const limit = Math.min(Math.max(Number(req.query.limit) || 50, 1), 200);
    res.json({ convoys: convoyStore.list(limit).map(summarize) });
  });

  // Beads: every convoy and every worker as a Gas City-style work item (id, type, status open/in_progress/closed, blockers, ready). A view over convoys.
  // ?status=open|in_progress|closed  ?ready=1  ?type=convoy|task
  app.get('/api/beads', (req: Request, res: Response) => {
    const status = typeof req.query.status === 'string' ? req.query.status : '';
    const type = typeof req.query.type === 'string' ? req.query.type : '';
    if (status && !['open', 'in_progress', 'closed'].includes(status)) return res.status(400).json({ error: 'status must be open, in_progress or closed' });
    if (type && !['convoy', 'task'].includes(type)) return res.status(400).json({ error: 'type must be convoy or task' });
    let beads = beadsFor(convoyStore.list(100));
    if (status) beads = beads.filter((b) => b.status === (status as BeadStatus));
    if (type) beads = beads.filter((b) => b.type === type);
    if (req.query.ready === '1') beads = beads.filter((b) => b.ready);
    res.json({ beads, counts: { open: beads.filter((b) => b.status === 'open').length, in_progress: beads.filter((b) => b.status === 'in_progress').length, closed: beads.filter((b) => b.status === 'closed').length, ready: beads.filter((b) => b.ready).length } });
  });

  // The agent board: READY / OPEN / REVIEW / FINISHED for every worker of the recent convoys. Registered before :id so it is not captured by it.
  app.get('/api/convoys/board', (_req: Request, res: Response) => {
    res.json(boardFor(convoyStore.list(100)));
  });

  app.get('/api/convoys/:id', (req: Request, res: Response) => {
    const c = convoyStore.get(String(req.params.id));
    if (!c) return res.status(404).json({ error: 'unknown convoy' });
    res.json({ convoy: convoyDetail(c, runStore) });
  });

  // Queue the frozen plan for human approval (PLANNED -> PENDING). Refused when the plan cannot run or policy denies it.
  app.post('/api/convoys/:id/submit', (req: Request, res: Response) => {
    try { res.json({ convoy: convoyDetail(convoyStore.submit(String(req.params.id)), runStore) }); } catch (err) { fail(res, err); }
  });

  for (const action of ['reject', 'cancel'] as const) {
    app.post(`/api/convoys/:id/${action}`, (req: Request, res: Response) => {
      if (!deps.isHuman(req)) return res.status(403).json({ error: `only a human operator can ${action} a convoy`, code: 'forbidden' });
      try {
        const note = typeof (req.body as Record<string, unknown>)?.note === 'string' ? String((req.body as Record<string, unknown>).note).slice(0, 300) : '';
        const id = String(req.params.id);
        res.json({ convoy: convoyDetail(action === 'reject' ? convoyStore.decide(id, 'reject', 'human', note) : convoyStore.cancel(id, 'human', note || 'cancelled'), runStore) });
      } catch (err) { fail(res, err); }
    });
  }
}
