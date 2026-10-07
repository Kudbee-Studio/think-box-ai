// Which repository the agent works on. The Files panel can hold several cloned repositories (<profile workspace>/repositories/<name>); the one marked "Use for
// agent" becomes the repository root for the agent's repository tools, SIMULATE and its checks (KUDBEE_REPO_ROOT), and the GitHub owner/name its lookups use. The
// choice is saved per profile. Nothing outside <profile workspace>/repositories/ can be chosen, and a clone must be a real directory with a .git.
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { repoTag } from './think-token-repo.ts';
import { parseRepo } from './repo-context.ts';

const NAME = /^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$/;

export class ActiveRepoError extends Error {}
export interface ActiveRepo { name: string; root: string; /** owner/name when the clone's origin is a GitHub repository. */ repo: string | null }

export class ActiveRepoManager {
  private readonly bootRoot: string | undefined;
  private readonly bootRepo: string | undefined;
  private readonly opts: { file: string; profileDir: (profileId: string) => string; env?: Record<string, string | undefined> };
  constructor(opts: { file: string; profileDir: (profileId: string) => string; env?: Record<string, string | undefined> }) {
    this.opts = opts;
    const env = opts.env ?? process.env;
    this.bootRoot = env.KUDBEE_REPO_ROOT; this.bootRepo = env.KUDBEE_REPO;
  }

  private env(): Record<string, string | undefined> { return this.opts.env ?? process.env; }
  private base(profileId: string): string { return path.resolve(this.opts.profileDir(profileId), 'repositories'); }
  private read(): Record<string, string> {
    try { const d = JSON.parse(fs.readFileSync(this.opts.file, 'utf8')) as unknown; return d && typeof d === 'object' && !Array.isArray(d) ? d as Record<string, string> : {}; } catch { return {}; }
  }
  private write(d: Record<string, string>): void {
    fs.mkdirSync(path.dirname(this.opts.file), { recursive: true });
    const tmp = `${this.opts.file}.${process.pid}.tmp`; fs.writeFileSync(tmp, JSON.stringify(d, null, 2)); fs.renameSync(tmp, this.opts.file);
  }

  /** The directory of a cloned repository, or why it cannot be used. */
  private resolve(profileId: string, name: unknown): ActiveRepo {
    if (typeof name !== 'string' || !NAME.test(name)) throw new ActiveRepoError('Not a valid repository name');
    const base = this.base(profileId); const dir = path.resolve(base, name);
    if (!dir.startsWith(base + path.sep)) throw new ActiveRepoError('Not a valid repository name');
    let st: fs.Stats; try { st = fs.lstatSync(dir); } catch { throw new ActiveRepoError(`No cloned repository named ${name} in this profile's workspace`); }
    if (!st.isDirectory() || st.isSymbolicLink()) throw new ActiveRepoError(`${name} is not a plain directory`);
    if (!fs.existsSync(path.join(dir, '.git'))) throw new ActiveRepoError(`${name} is not a git repository`);
    let repo: string | null = null;
    try { repo = parseRepo(execFileSync('git', ['remote', 'get-url', 'origin'], { cwd: dir, encoding: 'utf8', timeout: 3000, stdio: ['ignore', 'pipe', 'ignore'] })); } catch { /* no origin: lookups stay off */ }
    return { name, root: dir, repo };
  }

  /** The cloned repositories of a profile that can be chosen. */
  list(profileId: string): string[] {
    try { return fs.readdirSync(this.base(profileId)).filter((n) => { try { this.resolve(profileId, n); return true; } catch { return false; } }).sort(); } catch { return []; }
  }

  /** The profile's chosen repository, if it is still there. */
  active(profileId: string): ActiveRepo | null {
    const name = this.read()[profileId];
    if (!name) return null;
    try { return this.resolve(profileId, name); } catch { return null; }
  }

  /** The Think Token scope tag of the chosen repository (think-token-repo.ts), or null when none is chosen or it has no GitHub address. */
  tag(profileId: string): string | null { return repoTag(this.active(profileId)?.repo); }

  /** Point the agent at a repository (saved per profile) and apply it now. */
  set(profileId: string, name: unknown): ActiveRepo {
    const found = this.resolve(profileId, name);
    this.write({ ...this.read(), [profileId]: found.name });
    this.apply(profileId);
    return found;
  }

  clear(profileId: string): void {
    const d = this.read(); delete d[profileId]; this.write(d); this.apply(profileId);
  }

  /** Make the process environment match the profile's choice: the clone, or the checkout the server runs in. Called at startup, on a profile switch and after set/clear. */
  apply(profileId: string): ActiveRepo | null {
    const env = this.env(); const a = this.active(profileId);
    if (a) { env.KUDBEE_REPO_ROOT = a.root; delete env.KUDBEE_REPO; return a; }
    if (this.bootRoot === undefined) delete env.KUDBEE_REPO_ROOT; else env.KUDBEE_REPO_ROOT = this.bootRoot;
    if (this.bootRepo === undefined) delete env.KUDBEE_REPO; else env.KUDBEE_REPO = this.bootRepo;
    return null;
  }
}

/** A path the agent's file tools may use inside a chosen repository: relative, no "..", never the .git folder (any letter case, and not through a symlink). */
export function repoFilePath(root: string, relativePath: string): string {
  const base = path.resolve(root);
  const normalized = relativePath.replaceAll('\\', '/').replace(/^\/+/, '');
  const parts = normalized.split('/');
  if (!normalized || parts.some((part) => part === '..')) throw new Error('Invalid workspace path');
  const isGit = (segments: string[]): boolean => segments.some((part) => part.toLowerCase() === '.git');
  if (isGit(parts)) throw new Error('The .git folder is not available to the agent');
  const abs = path.resolve(base, normalized);
  if (abs !== base && !abs.startsWith(`${base}${path.sep}`)) throw new Error('Path escapes workspace');
  try {
    const real = path.relative(fs.realpathSync(base), fs.realpathSync(abs));
    if (isGit(real.split(path.sep))) throw new Error('The .git folder is not available to the agent');
  } catch (err) { if ((err as NodeJS.ErrnoException).code !== 'ENOENT') throw err; }
  return abs;
}
