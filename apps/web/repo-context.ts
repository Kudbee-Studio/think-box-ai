// The repository this Agent OS belongs to, so the planner never has to guess a GitHub owner/name (it once guessed "kudbEE/kudbEE" and got a 404).
// KUDBEE_REPO=owner/name wins; otherwise it is read from the git remote of the checkout. Pure parsing here; the caller does the one `git remote get-url`.
import { execFileSync } from 'node:child_process';

/** owner/name from an https or ssh GitHub remote URL, or a bare owner/name. null if it is not recognizable. */
export function parseRepo(text: string | undefined | null): string | null {
  const t = (text ?? '').trim();
  if (!t) return null;
  const m = /^(?:https?:\/\/(?:[^@/]+@)?github\.com\/|git@github\.com:|ssh:\/\/git@github\.com\/)?([A-Za-z0-9][A-Za-z0-9-]{0,38})\/([A-Za-z0-9._-]{1,100}?)(?:\.git)?\/?$/.exec(t);
  return m ? `${m[1]}/${m[2]}` : null;
}

export function detectRepo(env: Record<string, string | undefined> = process.env, cwd: string = process.cwd()): string | null {
  const fromEnv = parseRepo(env.KUDBEE_REPO);
  if (fromEnv) return fromEnv;
  try {
    return parseRepo(execFileSync('git', ['remote', 'get-url', 'origin'], { cwd, encoding: 'utf8', timeout: 2000, stdio: ['ignore', 'pipe', 'ignore'] }));
  } catch {
    return null;
  }
}

export function repoContextLine(repo: string | null): string {
  return repo
    ? `KNOWN REPOSITORY: this project's GitHub repository is ${repo} (https://github.com/${repo}; API https://api.github.com/repos/${repo}). Use exactly this owner and name in GitHub URLs; never guess a different one.`
    : '';
}
