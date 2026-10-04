// Convoy API: plan (dry run), list, detail with child runs, submit for approval, reject, cancel. Approving AND running go through the
// authenticated dashboard/CLI WebSocket session only (server.ts `convoy_approve`), so there is one approval path and it needs a live human session.
import type { Express, Response } from 'express';
import { ConvoyError, verifyChain, type ConvoyRecord, type ConvoyStore } from '../convoy.ts';
import { summarize } from '../convoy-runner.ts';
import type { RunRecord, RunStore } from '../runs.ts';
import type { Request } from './types.ts';

export interface ConvoyRouteDeps {
  convoyStore: ConvoyStore;
  runStore: RunStore;
  /** Builds a plan (and stores it as PLAN ONLY). Nothing runs. */
  plan: (goal: string, model: string | undefined, budget: unknown) => { ok: true; convoy: ConvoyRecord } | { ok: false; error: string };
  /** True when the request comes from the dashboard origin or carries the local token: a human operator, not some other local process. */
  isHuman: (req: Request) => boolean;
}

const status = (e: ConvoyError): number => (e.code === 'not_found' ? 404 : e.code === 'forbidden' ? 403 : 409);

/** The detail view: the convoy, plus each child run with its steps (tools and their output), which is the drill-down. */
export function convoyDetail(c: ConvoyRecord, runStore: RunStore): Record<string, unknown> {
  const runs = c.run_ids.map((id) => runStore.get(id)).filter((r): r is RunRecord => Boolean(r));
  return { ...c, chain: verifyChain(c), summary: summarize(c), runs };
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
    const result = deps.plan(typeof body.goal === 'string' ? body.goal : '', typeof body.model === 'string' ? body.model : undefined, body.worker_budget);
    if (!result.ok) return res.status(400).json({ error: result.error });
    res.status(201).json({ convoy: convoyDetail(result.convoy, runStore) });
  });

  app.get('/api/convoys', (req: Request, res: Response) => {
    const limit = Math.min(Math.max(Number(req.query.limit) || 50, 1), 200);
    res.json({ convoys: convoyStore.list(limit).map(summarize) });
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
