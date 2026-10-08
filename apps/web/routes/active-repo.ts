// Which cloned repository the agent works on (see active-repo.ts). Changing it needs the dashboard origin or the local token: it decides what the agent reads.
import type { Express, Response } from 'express';
import { ActiveRepoError, type ActiveRepoManager } from '../active-repo.ts';
import { errorMessage } from '../types.ts';
import { registerRepoChangesRoutes } from './repo-changes.ts';
import type { Request } from './types.ts';

export interface ActiveRepoRouteDeps { manager: ActiveRepoManager; profileId: () => string; isHuman: (req: Request) => boolean; /** Records the decision in the audit log (audit-log.ts). */ audit?: (kind: 'agent_repo_changed' | 'changes_undone', actor: string, summary: string, detail?: Record<string, unknown>) => void }

export function registerActiveRepoRoutes(app: Express, deps: ActiveRepoRouteDeps): void {
  const { manager, profileId, isHuman, audit } = deps;
  registerRepoChangesRoutes(app, deps); // reviewing what the agent changed belongs with choosing the repository
  const view = () => { const a = manager.active(profileId()); return { active: a ? { name: a.name, repo: a.repo } : null, repositories: manager.list(profileId()) }; };
  const fail = (res: Response, err: unknown) => res.status(err instanceof ActiveRepoError ? 400 : 500).json({ error: errorMessage(err) });

  app.get('/api/repo/active', (_req: Request, res: Response) => res.json(view()));
  app.post('/api/repo/active', (req: Request, res: Response) => {
    if (!isHuman(req)) return res.status(403).json({ error: 'Only the dashboard (or a request with the local token) can choose the agent repository' });
    try { const name = (req.body as { name?: unknown } | undefined)?.name; manager.set(profileId(), name); audit?.('agent_repo_changed', 'human', `agent repository set to ${String(name).slice(0, 80)}`, { profile: profileId() }); res.json(view()); } catch (err) { fail(res, err); }
  });
  app.delete('/api/repo/active', (req: Request, res: Response) => {
    if (!isHuman(req)) return res.status(403).json({ error: 'Only the dashboard (or a request with the local token) can choose the agent repository' });
    try { manager.clear(profileId()); audit?.('agent_repo_changed', 'human', 'agent repository cleared', { profile: profileId() }); res.json(view()); } catch (err) { fail(res, err); }
  });
}
