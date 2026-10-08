// Run list, run detail, per-session run history and token-savings stats. Moved out of server.ts.
// /api/runs/history is registered BEFORE /api/runs/:id: it used to come later, so ":id" captured "history" and answered 404.
import type { Express, Response } from 'express';
import type { PersistenceLayer } from '../persistence.ts';
import type { RunRecord, RunStore } from '../runs.ts';
import { summarizeRun } from '../run-summary.ts';
import type { Request } from './types.ts';

export interface RunsRouteDeps {
  runStore: RunStore;
  persistence: Pick<PersistenceLayer, 'listRuns'>;
}

export function registerRunsRoutes(app: Express, deps: RunsRouteDeps): void {
  const { runStore, persistence } = deps;
  let runsListCache: { data: Record<string, unknown> | null; at: number } = { data: null, at: 0 };
  app.get('/api/runs', (req: Request, res: Response) => {
    const limit = Math.min(Number(req.query.limit) || 50, 500);
    const now = Date.now();
    // Cache runs list for 1s; on rapid polls this cuts response time significantly
    if (runsListCache.data && now - runsListCache.at < 1000) {
      const cached = runsListCache.data as Record<string, unknown>;
      const cachedRuns = cached.runs as Array<Record<string, unknown>>;
      if (req.query.children !== '1' && cachedRuns.length === Math.min(limit, runStore.list(500).filter((run) => !run.jobId).length)) {
        return res.json(runsListCache.data);
      }
    }
    // Runs that belong to a convoy / specialist job (jobId) are that parent's children: the dashboard shows the parent row and drills down to them,
    // so they are not listed as competing top-level runs unless asked for (?children=1).
    const top = req.query.children === '1' ? runStore.list(limit) : runStore.list(500).filter((run) => !run.jobId).slice(0, limit);
    const data = { runs: top.map((run) => ({ ...run, steps: undefined, step_count: run.steps.length })) };
    runsListCache = { data, at: now };
    res.json(data);
  });

  // ─── Run History (Persistent Storage) ──────────────────────────
  app.get('/api/runs/history', async (req: Request, res: Response) => {
    try {
      const sessionId = req.query.sessionId as string;
      const limit = Math.min(parseInt(req.query.limit as string, 10) || 50, 500);

      if (!sessionId) {
        return res.status(400).json({ error: 'sessionId required' });
      }

      // Try persistent DB first
      const dbRuns = await persistence.listRuns(sessionId, limit);
      if (dbRuns.length > 0) {
        return res.json({ runs: dbRuns, source: 'db' });
      }

      // Fallback to JSON run store
      const allRuns = runStore.list(1000).filter((r: RunRecord) => r.session_id === sessionId);
      const runs = allRuns
        .slice(0, limit)
        .map((r: RunRecord) => ({
          runId: r.id,
          sessionId: r.session_id,
          goal: r.goal,
          status: r.status,
          startTime: r.started_at,
          endTime: r.ended_at,
          metrics: { tokens: (r.prompt_tokens ?? 0) + (r.completion_tokens ?? 0), cost: r.cost_usd },
          files: r.files,
          createdAt: r.started_at
        }));

      res.json({ runs, source: 'json' });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  app.get('/api/runs/:id/summary', (req: Request, res: Response) => {
    const run = runStore.get(req.params.id);
    if (!run) return res.status(404).json({ error: 'Run not found' });
    res.json(summarizeRun(run));
  });

  app.get('/api/runs/:id', (req: Request, res: Response) => {
    const run = runStore.get(req.params.id);
    if (!run) return res.status(404).json({ error: 'Run not found' });
    res.json(run);
  });

  // Feature 5: Token stats for KPI dashboard
  app.get('/api/stats/tokens', async (req: Request, res: Response) => {
    try {
      const sessionId = req.query.sessionId as string;
      const limit = Math.min(parseInt(req.query.limit as string, 10) || 50, 500);

      if (!sessionId) {
        return res.status(400).json({ error: 'sessionId required' });
      }

      // listRuns() returns newest-first (createdAt DESC); a sparkline needs
      // chronological order (oldest→newest) or the trend line reads backwards.
      const runs = await persistence.listRuns(sessionId, limit);
      const chronological = [...runs].reverse();

      const savedPerRun = chronological.map((run) => (run.metrics?.tokens_saved_est as number) || 0);
      const totalTokensSavedEst = savedPerRun.reduce((sum, v) => sum + v, 0);

      const tokenStats = {
        totalTokensSavedEst,
        totalRunsTracked: runs.length,
        averageSavingsPerRun: runs.length > 0 ? Math.round(totalTokensSavedEst / runs.length) : 0,
        lastRunTokensSaved: runs.length > 0 ? ((runs[0].metrics?.tokens_saved_est as number) || 0) : 0,
        sparklineData: savedPerRun,
      };

      res.json(tokenStats);
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });
}
