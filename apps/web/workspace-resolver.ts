// Where an agent session's files live. A dashboard or CLI session used to get a brand-new folder on every connection, so a page reload showed an empty
// Files panel and left one empty folder per page load behind. Interactive sessions now share ONE persistent workspace per profile
// (<root>/_profiles/<profile>/), so files the agent creates and repositories you clone are still there after a reload or a restart. A specialist's
// isolated Think Box keeps its own folder (<root>/<id>), and any older session folder that exists on disk still resolves to itself, so run history keeps working.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const SAFE_PROFILE = /^[A-Za-z0-9_-]{1,64}$/;
/** Session and Think Box ids are server-made UUIDs; anything else never reaches a path. */
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

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

export function createWorkspaceResolver(opts: { root: string; activeProfile: () => string }): WorkspaceResolver {
  const root = path.resolve(opts.root);
  const interactive = new Set<string>();
  const isolated = new Set<string>();
  const check = (id: string): void => { if (!UUID.test(id)) throw new Error('Invalid session id'); };
  /** <root>/<id> for a valid id, confined to the root even if a regex were ever loosened. */
  const own = (id: string): string => { check(id); const dir = path.resolve(root, id); if (!dir.startsWith(root + path.sep)) throw new Error('Invalid session id'); return dir; };
  const profileDir = (profileId: string): string => {
    const name = SAFE_PROFILE.test(profileId) ? profileId : `p-${crypto.createHash('sha1').update(profileId).digest('hex').slice(0, 12)}`;
    const dir = path.join(root, '_profiles', name);
    fs.mkdirSync(dir, { recursive: true });
    return dir;
  };
  return {
    register(id) { check(id); interactive.add(id); },
    isolate(id) { const dir = own(id); isolated.add(id); fs.mkdirSync(dir, { recursive: true }); return dir; },
    dirFor(id) {
      if (!isolated.has(id) && interactive.has(id)) { check(id); return profileDir(opts.activeProfile()); }
      return own(id);
    },
    exists(id) { return UUID.test(id) && (interactive.has(id) || isolated.has(id) || fs.existsSync(own(id))); },
    profileDir,
    pruneEmpty(olderThanMs = 60_000) {
      let removed = 0;
      let entries: fs.Dirent[] = [];
      try { entries = fs.readdirSync(root, { withFileTypes: true }); } catch { return 0; }
      for (const e of entries) {
        if (!e.isDirectory() || !UUID.test(e.name)) continue;
        const dir = own(e.name);
        try {
          if (Date.now() - fs.statSync(dir).mtimeMs < olderThanMs || isolated.has(e.name) || fs.readdirSync(dir).length) continue;
          fs.rmdirSync(dir); removed += 1;
        } catch { /* in use or not empty: leave it */ }
      }
      return removed;
    },
  };
}
