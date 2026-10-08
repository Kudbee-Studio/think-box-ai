// What was spent: the active profile's runs, per day and per model (spend-report.ts). Reading only. The cross-profile view is `kudbee spend`, which reads every profile's run file.
import type { Express } from 'express';
import { spendReport, type SpendRun } from '../spend-report.ts';
import type { Request } from './types.ts';

export function registerSpendRoutes(app: Express, deps: { runs: () => SpendRun[]; budget: { daily: number; run: number } }): void {
  app.get('/api/spend', (_req: Request, res) => res.json({ ...spendReport(deps.runs()), budget: deps.budget }));
}
