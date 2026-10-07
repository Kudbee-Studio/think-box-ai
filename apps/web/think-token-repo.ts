// Think Tokens per repository: a lesson learned while the agent worked on a chosen repository carries a `repo:` tag and is recalled only in that repository.
// Tokens with no `repo:` tag (everything saved before this) are general and are recalled everywhere. Pure functions, no I/O.
import { createHash } from 'node:crypto';
export const REPO_TAG_PREFIX = 'repo:';
// The store's tag limits (LIMITS.tag, LIMITS.tags in think-token-store.ts, which imports this module).
const TAG_MAX = 32;
const TAGS_MAX = 8;

/** `repo:<owner>:<name>` lower-cased (the store's tag cleaner keeps only a-z 0-9 _ . : -, and ':' cannot appear in a GitHub name, so it is an unambiguous separator). Longer than a tag may be (32): cut, then `:` and a short hash of the full name. Null when there is no GitHub repository. */
export function repoTag(repo: string | null | undefined): string | null {
  const name = String(repo ?? '').trim().toLowerCase();
  if (!/^[\w.-]+\/[\w.-]+$/.test(name)) return null;
  const room = TAG_MAX - REPO_TAG_PREFIX.length; const flat = name.replace('/', ':');
  return REPO_TAG_PREFIX + (flat.length <= room ? flat : `${flat.slice(0, room - 7)}:${createHash('sha1').update(name).digest('hex').slice(0, 6)}`);
}

export const repoTagOf = (tags: readonly string[]): string | null => tags.find((t) => t.startsWith(REPO_TAG_PREFIX)) ?? null;

/** A token is in scope when it is general (no repo tag) or its repo tag is the one for the repository being worked on. With no repository chosen, repo-specific tokens stay out. */
export function inRepoScope(tags: readonly string[], current: string | null | undefined): boolean {
  const own = repoTagOf(tags);
  return own === null || own === (current ?? null);
}

/** Adds the repo tag to a draft's tags (kept within the 8-tag limit, repo tag last so it always survives). */
export function withRepoTag(tags: readonly string[], current: string | null | undefined): string[] {
  if (!current || repoTagOf(tags)) return [...tags];
  return [...tags.slice(0, TAGS_MAX - 1), current];
}
