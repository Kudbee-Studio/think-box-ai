// Job templates for the dashboard (job-templates.ts): the list, and a template filled with the person's input. Filling only returns text; it never starts a run.
import type { Express } from 'express';
import { JOB_TEMPLATES, fillGoal } from '../job-templates.ts';
import type { Request } from './types.ts';

export function registerJobTemplateRoutes(app: Express): void {
  app.get('/api/job-templates', (_req: Request, res) => res.json({ templates: JOB_TEMPLATES.map(({ goal: _goal, ...t }) => t) }));
  app.post('/api/job-templates/:id', (req: Request, res) => {
    const input = (req.body as { input?: unknown } | undefined)?.input;
    const r = fillGoal(req.params.id, typeof input === 'string' ? input : undefined);
    res.status(r.ok ? 200 : 400).json(r);
  });
}
