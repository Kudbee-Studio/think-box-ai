// Read-only repository tools for governed workers (Layer 4: tools glue).
// `repo_search` (literal text search) and `repo_read` (a window of numbered lines) let a worker look at the REAL repository and nothing else:
//   - confined to the repository root with symlink-safe reads (workspace-fs `readConfined`); symlinks are never followed while walking;
//   - secrets, `.env*`, keys, databases, `.git`, `node_modules` and the app's data/workspace folders are not searchable or readable;
//   - text files only, size and result caps, a time budget: a hostile or huge tree cannot make a search run away.
// Results are NORMALIZED EVIDENCE (path, line numbers, the exact line text, source, tool-call count, latency), the same shape of idea as `live_lookup`'s,
// and the grounding validator checks a worker's finding against this evidence. Nothing here writes, executes or fetches.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { readConfined } from './workspace-fs.ts';

export const REPO_TOOLS = ['repo_search', 'repo_read'] as const;

const LIMITS = { maxMatches: 40, maxFiles: 4000, maxFileBytes: 400_000, maxQuery: 120, maxLineChars: 240, readWindow: 200, defaultWindow: 120, deadlineMs: 6000 } as const;
const TEXT_EXT = new Set(['.ts', '.js', '.mjs', '.cjs', '.json', '.md', '.css', '.html', '.py', '.sh', '.yml', '.yaml', '.txt', '.toml']);
const EXCLUDED_DIRS = new Set(['.git', 'node_modules', 'data', 'workspaces', 'coverage', 'dist', '.cache', '.codeql', '__pycache__', '.venv', 'venv']);
/** Files a worker must never see, whatever their extension. */
const SECRET_FILE = /(^|\/)(\.env(\..*)?|\.local-token.*|local-token.*|id_(rsa|ed25519|ecdsa).*|.*\.(pem|key|p12|pfx|crt|db|sqlite|db-wal|db-shm|bak)|.*secret.*|.*credential.*|\.npmrc|\.netrc)$/i;

export function repoRoot(env: Record<string, string | undefined> = process.env): string {
  return path.resolve(env.KUDBEE_REPO_ROOT || path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..'));
}

export type RepoEvidence =
  | { tool: 'repo_search'; query: string; path: string; matches: Array<{ path: string; line: number; text: string }>; truncated: boolean; files_scanned: number; fetched_at: string; tool_calls: 1; latency_ms: number }
  | { tool: 'repo_read'; path: string; start: number; end: number; total_lines: number; lines: Array<{ n: number; text: string }>; fetched_at: string; tool_calls: 1; latency_ms: number };

export class RepoToolError extends Error {}

/** A repo-relative path, or the reason it is refused. Pure. */
export function checkRepoPath(raw: unknown, { allowDir = false }: { allowDir?: boolean } = {}): { ok: true; rel: string } | { ok: false; error: string } {
  if (typeof raw !== 'string' || !raw.trim()) return { ok: false, error: 'path must be a non-empty string' };
  if (raw.length > 300 || raw.includes('\0')) return { ok: false, error: 'path is not valid' };
  const normalized = raw.replaceAll('\\', '/').replace(/^\.\//, '');
  if (normalized.startsWith('/') || /^[A-Za-z]:/.test(normalized)) return { ok: false, error: 'path must be relative to the repository' };
  const parts = normalized.split('/').filter(Boolean);
  if (parts.includes('..')) return { ok: false, error: 'path must stay inside the repository' };
  if (parts.some((p) => EXCLUDED_DIRS.has(p))) return { ok: false, error: `path is in an excluded folder (${parts.find((p) => EXCLUDED_DIRS.has(p))})` };
  const rel = parts.join('/');
  if (SECRET_FILE.test(rel)) return { ok: false, error: 'this file is not available to workers (secrets, keys, databases)' };
  if (!allowDir && !TEXT_EXT.has(path.extname(rel).toLowerCase())) return { ok: false, error: `only text source files can be read (${[...TEXT_EXT].join(' ')})` };
  return { ok: true, rel };
}

export function validateRepoSearchArgs(raw: unknown): { ok: true; args: { query: string; path: string } } | { ok: false; error: string } {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return { ok: false, error: 'the tool request must be an object' };
  const r = raw as Record<string, unknown>;
  const extra = Object.keys(r).filter((k) => !['query', 'path'].includes(k));
  if (extra.length) return { ok: false, error: `unknown argument(s): ${extra.join(', ')}` };
  if (typeof r.query !== 'string' || r.query.trim().length < 2) return { ok: false, error: 'query must be a string of at least 2 characters' };
  if (r.query.length > LIMITS.maxQuery || /[\0\n\r]/.test(r.query)) return { ok: false, error: `query must be one line of at most ${LIMITS.maxQuery} characters` };
  let scope = '';
  if (r.path !== undefined && r.path !== null && r.path !== '' && r.path !== '.') {
    const p = checkRepoPath(r.path, { allowDir: true });
    if (!p.ok) return p;
    scope = p.rel;
  }
  return { ok: true, args: { query: r.query, path: scope } };
}

export function validateRepoReadArgs(raw: unknown): { ok: true; args: { path: string; start: number; end: number } } | { ok: false; error: string } {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return { ok: false, error: 'the tool request must be an object' };
  const r = raw as Record<string, unknown>;
  const extra = Object.keys(r).filter((k) => !['path', 'start', 'end'].includes(k));
  if (extra.length) return { ok: false, error: `unknown argument(s): ${extra.join(', ')}` };
  const p = checkRepoPath(r.path);
  if (!p.ok) return p;
  const int = (v: unknown, fallback: number): number | null => (v === undefined || v === null ? fallback : typeof v === 'number' && Number.isInteger(v) && v >= 1 && v <= 1_000_000 ? v : null);
  const start = int(r.start, 1);
  if (start === null) return { ok: false, error: 'start must be a whole number of 1 or more' };
  const end = int(r.end, start + LIMITS.defaultWindow - 1);
  if (end === null || end < start) return { ok: false, error: 'end must be a whole number not before start' };
  return { ok: true, args: { path: p.rel, start, end: Math.min(end, start + LIMITS.readWindow - 1) } };
}

const clip = (text: string): string => (text.length > LIMITS.maxLineChars ? `${text.slice(0, LIMITS.maxLineChars)}…` : text);
const looksBinary = (buf: Buffer): boolean => buf.subarray(0, 1024).includes(0);

async function readTextFile(root: string, rel: string): Promise<string | null> {
  const abs = path.join(root, rel);
  const st = await fs.promises.lstat(abs);
  if (!st.isFile() || st.size > LIMITS.maxFileBytes) return null;
  const buf = await readConfined(root, abs, LIMITS.maxFileBytes);
  return looksBinary(buf) ? null : buf.toString('utf8');
}

/** For a "not found" error: what the nearest existing folder above the missing path holds, so a model can correct a guessed name. Hidden entries, secrets and excluded folders are never listed. */
async function navigationHint(realRoot: string, rel: string): Promise<string> {
  const parts = rel.split('/').filter(Boolean);
  for (let n = parts.length - 1; n >= 0; n -= 1) {
    const dir = parts.slice(0, n).join('/');
    let entries: fs.Dirent[];
    try { entries = await fs.promises.readdir(path.join(realRoot, dir), { withFileTypes: true }); } catch { continue; }
    const names = entries.filter((e) => !e.isSymbolicLink() && !e.name.startsWith('.') && !SECRET_FILE.test(e.name) && (e.isDirectory() ? !EXCLUDED_DIRS.has(e.name) : TEXT_EXT.has(path.extname(e.name).toLowerCase())))
      .map((e) => (e.isDirectory() ? `${e.name}/` : e.name)).sort().slice(0, 12);
    return names.length ? ` In ${dir || 'the repository root'}: ${names.join(', ')}.` : '';
  }
  return '';
}

/** Literal, case-insensitive search of the repository's text files. Symlinks are skipped; the walk is bounded in files, matches and time. */
export async function repoSearch(args: { query: string; path: string }, root: string = repoRoot()): Promise<RepoEvidence> {
  const startedAt = Date.now();
  const needle = args.query.toLowerCase();
  const matches: Array<{ path: string; line: number; text: string }> = [];
  let scanned = 0; let truncated = false;
  const deadline = startedAt + LIMITS.deadlineMs;
  const realRoot = await fs.promises.realpath(root);
  const startRel = args.path;
  const walk = async (rel: string): Promise<void> => {
    if (truncated) return;
    const abs = path.join(realRoot, rel);
    let entries: fs.Dirent[];
    try { entries = await fs.promises.readdir(abs, { withFileTypes: true }); } catch { return; }
    entries.sort((a, b) => a.name.localeCompare(b.name));
    for (const e of entries) {
      if (truncated) return;
      if (e.isSymbolicLink()) continue;
      const childRel = rel ? `${rel}/${e.name}` : e.name;
      if (e.isDirectory()) { if (!EXCLUDED_DIRS.has(e.name)) await walk(childRel); continue; }
      if (!e.isFile() || SECRET_FILE.test(childRel) || !TEXT_EXT.has(path.extname(e.name).toLowerCase())) continue;
      if (scanned >= LIMITS.maxFiles || Date.now() > deadline) { truncated = true; return; }
      scanned += 1;
      let text: string | null;
      try { text = await readTextFile(realRoot, childRel); } catch { continue; }
      if (text === null || !text.toLowerCase().includes(needle)) continue;
      const lines = text.split('\n');
      for (let i = 0; i < lines.length; i += 1) {
        if (lines[i]!.toLowerCase().includes(needle)) {
          if (matches.length >= LIMITS.maxMatches) { truncated = true; return; }
          matches.push({ path: childRel, line: i + 1, text: clip(lines[i]!.replace(/\r$/, '')) });
        }
      }
    }
  };
  // The start path may be a file or a directory.
  let startIsFile = false;
  if (startRel) {
    const st = await fs.promises.lstat(path.join(realRoot, startRel)).catch(() => null);
    if (!st) throw new RepoToolError(`path not found: ${startRel}.${await navigationHint(realRoot, startRel)}`);
    if (st.isSymbolicLink()) throw new RepoToolError('refusing to follow a symlink');
    startIsFile = st.isFile();
  }
  if (startIsFile) {
    if (!TEXT_EXT.has(path.extname(startRel).toLowerCase())) throw new RepoToolError('only text source files can be searched');
    scanned = 1;
    const text = await readTextFile(realRoot, startRel);
    if (text !== null) text.split('\n').forEach((l, i) => { if (l.toLowerCase().includes(needle) && matches.length < LIMITS.maxMatches) matches.push({ path: startRel, line: i + 1, text: clip(l.replace(/\r$/, '')) }); });
  } else await walk(startRel);
  return { tool: 'repo_search', query: args.query, path: startRel, matches, truncated, files_scanned: scanned, fetched_at: new Date().toISOString(), tool_calls: 1, latency_ms: Date.now() - startedAt };
}

/** A window of numbered lines from one file. */
export async function repoRead(args: { path: string; start: number; end: number }, root: string = repoRoot()): Promise<RepoEvidence> {
  const startedAt = Date.now();
  const realRoot = await fs.promises.realpath(root);
  const st = await fs.promises.lstat(path.join(realRoot, args.path)).catch(() => null);
  if (!st) throw new RepoToolError(`file not found: ${args.path}.${await navigationHint(realRoot, args.path)}`);
  if (st.isSymbolicLink()) throw new RepoToolError('refusing to follow a symlink');
  if (!st.isFile()) throw new RepoToolError(`not a file: ${args.path}`);
  if (st.size > LIMITS.maxFileBytes) throw new RepoToolError(`file is larger than ${LIMITS.maxFileBytes} bytes`);
  const text = await readTextFile(realRoot, args.path);
  if (text === null) throw new RepoToolError('binary or unreadable file');
  const all = text.split('\n');
  if (args.start > all.length) throw new RepoToolError(`start ${args.start} is past the end of the file (${all.length} lines)`);
  const end = Math.min(args.end, all.length);
  const lines = all.slice(args.start - 1, end).map((t, i) => ({ n: args.start + i, text: clip(t.replace(/\r$/, '')) }));
  return { tool: 'repo_read', path: args.path, start: args.start, end, total_lines: all.length, lines, fetched_at: new Date().toISOString(), tool_calls: 1, latency_ms: Date.now() - startedAt };
}

/** The evidence as plain numbered lines, for a model to read. */
export function renderRepoEvidence(e: RepoEvidence): string {
  if (e.tool === 'repo_search') {
    const head = `Search for "${e.query}"${e.path ? ` in ${e.path}` : ' in the repository'}: ${e.matches.length} match(es)${e.truncated ? ' (more exist; the search was cut off)' : ''}, ${e.files_scanned} file(s) scanned.`;
    return e.matches.length ? `${head}\n${e.matches.map((m) => `${m.path}:${m.line}: ${m.text}`).join('\n')}` : `${head} NO MATCHES.`;
  }
  return `${e.path} lines ${e.start}-${e.end} of ${e.total_lines}:\n${e.lines.map((l) => `${l.n}: ${l.text}`).join('\n')}`;
}

/** Independent check, outside the model's tool loop: does this exact quote sit at this line of this file on disk right now? */
export async function verifyQuoteOnDisk(file: string, line: number, quote: string, root: string = repoRoot()): Promise<{ ok: boolean; reason?: string }> {
  const p = checkRepoPath(file);
  if (!p.ok) return { ok: false, reason: p.error };
  try {
    const ev = await repoRead({ path: p.rel, start: Math.max(1, line), end: line + 2 }, root);
    if (ev.tool !== 'repo_read') return { ok: false, reason: 'unexpected evidence' };
    const window = ev.lines.map((l) => l.text).join(' ');
    return normalize(window).includes(normalize(quote)) ? { ok: true } : { ok: false, reason: `the quote is not at ${p.rel}:${line} on disk` };
  } catch (err) {
    return { ok: false, reason: err instanceof Error ? err.message : String(err) };
  }
}

export const normalize = (s: string): string => s.replace(/\s+/g, ' ').trim().toLowerCase();
