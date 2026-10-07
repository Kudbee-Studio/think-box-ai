// Where an agent session's files live. A dashboard or CLI session used to get a brand-new folder on every connection, so a page reload showed an empty
// Files panel and left one empty folder per page load behind. Interactive sessions now share ONE persistent workspace per profile
// (<root>/_profiles/<profile>/), so files the agent creates and repositories you clone are still there after a reload or a restart. A specialist's
// isolated Think Box keeps its own folder (<root>/<id>), and any older session folder that exists on disk still resolves to itself, so run history keeps working.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const SAFE_PROFILE = /^[A-Za-z0-9_-]{1,64}$/;

export interface WorkspaceResolver {
  /** Mark a connection (dashboard tab or CLI run) as an interactive session: its files go to the active profile's workspace. */
  register(id: string): void;
  /** Give a specialist Think Box its own folder, created now. */
  isolate(id: string): string;
  /** The directory for a session id. Throws on a malformed id. */
  dirFor(id: string): string;
  /** True for a registered session or an id whose folder exists on disk. */
  exists(id: string): boolean;
  /** The persistent workspace of a profile (created). */
  profileDir(profileId: string): string;
  /** Remove empty, UUID-named session folders left by earlier versions (never a folder with anything in it). Returns how many. */
  pruneEmpty(olderThanMs?: number): number;
}

export function createWorkspaceResolver(opts: { root: string; idRe: RegExp; activeProfile: () => string }): WorkspaceResolver {
  const root = path.resolve(opts.root);
  const interactive = new Set<string>();
  const isolated = new Set<string>();
  const check = (id: string): void => { if (!opts.idRe.test(id)) throw new Error('Invalid session id'); };
  const profileDir = (profileId: string): string => {
    const name = SAFE_PROFILE.test(profileId) ? profileId : `p-${crypto.createHash('sha1').update(profileId).digest('hex').slice(0, 12)}`;
    const dir = path.join(root, '_profiles', name);
    fs.mkdirSync(dir, { recursive: true });
    return dir;
  };
  return {
    register(id) { check(id); interactive.add(id); },
    isolate(id) { check(id); isolated.add(id); const dir = path.join(root, id); fs.mkdirSync(dir, { recursive: true }); return dir; },
    dirFor(id) {
      check(id);
      if (!isolated.has(id) && interactive.has(id)) return profileDir(opts.activeProfile());
      return path.join(root, id);
    },
    exists(id) { return opts.idRe.test(id) && (interactive.has(id) || isolated.has(id) || fs.existsSync(path.join(root, id))); },
    profileDir,
    pruneEmpty(olderThanMs = 60_000) {
      let removed = 0;
      let entries: fs.Dirent[] = [];
      try { entries = fs.readdirSync(root, { withFileTypes: true }); } catch { return 0; }
      for (const e of entries) {
        if (!e.isDirectory() || !opts.idRe.test(e.name)) continue;
        const dir = path.join(root, e.name);
        try {
          if (Date.now() - fs.statSync(dir).mtimeMs < olderThanMs || isolated.has(e.name) || fs.readdirSync(dir).length) continue;
          fs.rmdirSync(dir); removed += 1;
        } catch { /* in use or not empty: leave it */ }
      }
      return removed;
    },
  };
}
