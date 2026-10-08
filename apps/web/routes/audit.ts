// Read the audit log (audit-log.ts): the newest events, and a check that the chain is intact. Read-only; nothing here can write or delete an event.
import type { Express } from 'express';
import type { AuditLog } from '../audit-log.ts';
import type { Request } from './types.ts';

export function registerAuditRoutes(app: Express, audit: AuditLog): void {
  app.get('/api/audit', (req: Request, res) => {
    const q = req.query;
    res.json({ events: audit.list({ limit: Number(q.limit) || 100, kind: typeof q.kind === 'string' ? q.kind : undefined, run_id: typeof q.run_id === 'string' ? q.run_id : undefined, since: Number(q.since) || undefined }) });
  });
  app.get('/api/audit/verify', (_req: Request, res) => res.json(audit.verify()));
}
