// Review what the agent changed in the chosen repository: list, per-file diff, undo. Reading is open; undo needs the dashboard origin or the local token.
import type { Express, Response } from 'express';
import type { ActiveRepoManager } from '../active-repo.ts';
import type { ActiveRepoRouteDeps } from './active-repo.ts';
import { diffOf, listChanges, undoChanges } from '../repo-changes.ts';
import { errorMessage } from '../types.ts';
import type { Request } from './types.ts';

export interface RepoChangesRouteDeps { manager: ActiveRepoManager; profileId: () => string; isHuman: (req: Request) => boolean; audit?: ActiveRepoRouteDeps['audit'] }

export function registerRepoChangesRoutes(app: Express, deps: RepoChangesRouteDeps): void {
  const { manager, profileId, isHuman, audit } = deps;
  const fail = (res: Response, err: unknown) => res.status(400).json({ error: errorMessage(err) });
  const root = (): { name: string; root: string } | null => { const a = manager.active(profileId()); return a ? { name: a.name, root: a.root } : null; };

  app.get('/api/repo/changes', async (_req: Request, res: Response) => {
    const repo = root(); if (!repo) return res.json({ repo: null, files: [], truncated: false });
    try { res.json({ repo: repo.name, ...(await listChanges(repo.root)) }); } catch (err) { fail(res, err); }
  });
  app.get('/api/repo/changes/diff', async (req: Request, res: Response) => {
    const repo = root(); if (!repo) return res.status(400).json({ error: 'No repository is chosen for the agent' });
    try { res.json(await diffOf(repo.root, String(req.query.path ?? ''))); } catch (err) { fail(res, err); }
  });
  app.post('/api/repo/changes/undo', async (req: Request, res: Response) => {
    if (!isHuman(req)) return res.status(403).json({ error: 'Only the dashboard (or a request with the local token) can undo changes' });
    const repo = root(); if (!repo) return res.status(400).json({ error: 'No repository is chosen for the agent' });
    const file = (req.body as { path?: unknown } | undefined)?.path;
    try { const done = await undoChanges(repo.root, typeof file === 'string' && file ? file : undefined); audit?.('changes_undone', 'human', typeof file === 'string' && file ? `undid ${file.slice(0, 120)}` : 'undid every change', { repo: repo.name, restored: done.restored }); res.json(done); } catch (err) { fail(res, err); }
  });
}
