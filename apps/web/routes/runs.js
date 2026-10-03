// Run list, run detail, per-session run history and token-savings stats. Moved out of server.ts.
// /api/runs/history is registered BEFORE /api/runs/:id: it used to come later, so ":id" captured "history" and answered 404.
                                                 
                                                          
                                                      
                                          

                                
                     
                                                  
 

export function registerRunsRoutes(app         , deps               )       {
  const { runStore, persistence } = deps;
  let runsListCache                                                       = { data: null, at: 0 };
  app.get('/api/runs', (req         , res          ) => {
    const limit = Math.min(Number(req.query.limit) || 50, 500);
    const now = Date.now();
    // Cache runs list for 1s; on rapid polls this cuts response time significantly
    if (runsListCache.data && now - runsListCache.at < 1000) {
      const cached = runsListCache.data                           ;
      const cachedRuns = cached.runs                                  ;
      if (cachedRuns.length === runStore.list(1).length) {
        return res.json(runsListCache.data);
      }
    }
    const data = { runs: runStore.list(limit).map((run) => ({ ...run, steps: undefined, step_count: run.steps.length })) };
    runsListCache = { data, at: now };
    res.json(data);
  });

  // ─── Run History (Persistent Storage) ──────────────────────────
  app.get('/api/runs/history', async (req         , res          ) => {
    try {
      const sessionId = req.query.sessionId          ;
      const limit = Math.min(parseInt(req.query.limit          , 10) || 50, 500);

      if (!sessionId) {
        return res.status(400).json({ error: 'sessionId required' });
      }

      // Try persistent DB first
      const dbRuns = await persistence.listRuns(sessionId, limit);
      if (dbRuns.length > 0) {
        return res.json({ runs: dbRuns, source: 'db' });
      }

      // Fallback to JSON run store
      const allRuns = runStore.list(1000).filter((r           ) => r.session_id === sessionId);
      const runs = allRuns
        .slice(0, limit)
        .map((r           ) => ({
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

  app.get('/api/runs/:id', (req         , res          ) => {
    const run = runStore.get(req.params.id);
    if (!run) return res.status(404).json({ error: 'Run not found' });
    res.json(run);
  });

  // Feature 5: Token stats for KPI dashboard
  app.get('/api/stats/tokens', async (req         , res          ) => {
    try {
      const sessionId = req.query.sessionId          ;
      const limit = Math.min(parseInt(req.query.limit          , 10) || 50, 500);

      if (!sessionId) {
        return res.status(400).json({ error: 'sessionId required' });
      }

      // listRuns() returns newest-first (createdAt DESC); a sparkline needs
      // chronological order (oldest→newest) or the trend line reads backwards.
      const runs = await persistence.listRuns(sessionId, limit);
      const chronological = [...runs].reverse();

      const savedPerRun = chronological.map((run) => (run.metrics?.tokens_saved_est          ) || 0);
      const totalTokensSavedEst = savedPerRun.reduce((sum, v) => sum + v, 0);

      const tokenStats = {
        totalTokensSavedEst,
        totalRunsTracked: runs.length,
        averageSavingsPerRun: runs.length > 0 ? Math.round(totalTokensSavedEst / runs.length) : 0,
        lastRunTokensSaved: runs.length > 0 ? ((runs[0].metrics?.tokens_saved_est          ) || 0) : 0,
        sparklineData: savedPerRun,
      };

      res.json(tokenStats);
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });
}
