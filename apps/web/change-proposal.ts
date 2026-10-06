// A proposed change as EXACT TEXT EDITS, turned into a unified diff by code (Layer 4). A model asked to write a unified diff by hand gets line numbers and context wrong (a live
// run produced a corrupt patch); asked for "find this exact text, replace it with that", it can copy from what it read, and the diff is computed here from the real file at one
// commit. Nothing is written to the repository: files are read with `git show`, the diff is built in a temporary directory, and the result goes through the same patch policy
// and "does it apply" check as any patch (scratch-runner.ts). Used by the `propose_change` tool and by the SIMULATE convoy.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { checkRepoPath } from './repo-tools.ts';
import { patchProblem, reviewPatch, type PatchReview } from './scratch-runner.ts';

export const PROPOSE_CHANGE_TOOL = 'propose_change';
export const MAX_EDITS = 10;
export const MAX_FIND_CHARS = 4000;
export const MAX_REPLACE_CHARS = 8000;
export const MAX_CREATE_CHARS = 20_000;
const MAX_FILE_BYTES = 400_000;
const KEYS = new Set(['path', 'find', 'replace', 'create']);

export interface Edit { path: string; find?: string; replace?: string; create?: string }
export type Proposal = { ok: true; patch: string; files: string[]; flags: string[]; sha256: string; edits: number } | { ok: false; error: string };

const git = (cwd: string, args: string[]): Promise<{ code: number; out: Buffer }> =>
  new Promise((resolve) => {
    // stdin is closed, never written: git may exit before it would be read, and a write to a closed pipe is an EPIPE crash
    const child = spawn('git', args, { cwd, env: { PATH: '/usr/bin:/bin', GIT_CONFIG_NOSYSTEM: '1' }, stdio: ['ignore', 'pipe', 'pipe'] });
    const chunks: Buffer[] = [];
    child.stdout.on('data', (d: Buffer) => chunks.push(d)); child.stderr.on('data', (d: Buffer) => chunks.push(d));
    child.on('error', () => resolve({ code: 1, out: Buffer.from('git could not start') }));
    child.on('close', (code) => resolve({ code: code ?? 1, out: Buffer.concat(chunks) }));
  });

const occurrences = (text: string, needle: string): number => (needle ? text.split(needle).length - 1 : 0);
const lines = (text: string): string[] => { const l = text.split('\n'); if (l.at(-1) === '') l.pop(); return l; };

/** A new-file diff built by hand (git's no-index mode cannot diff against nothing). */
function newFileDiff(file: string, content: string): string {
  const body = lines(content);
  const noEol = content.length > 0 && !content.endsWith('\n');
  return `diff --git a/${file} b/${file}\nnew file mode 100644\n--- /dev/null\n+++ b/${file}\n@@ -0,0 +1,${body.length} @@\n${body.map((l) => `+${l}`).join('\n')}\n${noEol ? '\\ No newline at end of file\n' : ''}`;
}

/** The unified diff of `file` from `before` to `after`, with a/ and b/ paths, computed by git in a temporary directory. */
async function modifyDiff(file: string, before: string, after: string): Promise<string> {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-diff-'));
  try {
    for (const [side, text] of [['a', before], ['b', after]] as const) { const p = path.join(dir, side, file); fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, text); }
    const r = await git(dir, ['diff', '--no-index', '--no-prefix', '--no-color', '--no-ext-diff', '-U3', '--', `a/${file}`, `b/${file}`]);
    if (r.code !== 1) throw new Error(`could not compute the diff (git exit ${r.code})`);
    return r.out.toString('utf8');
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
}

/** Builds the patch for these edits against the files as they are at `sha`, or says exactly what is wrong with an edit so a model can correct it. */
export async function buildPatch(repoRoot: string, sha: string, raw: unknown): Promise<Proposal> {
  if (!Array.isArray(raw) || !raw.length) return { ok: false, error: 'edits must be a non-empty list' };
  if (raw.length > MAX_EDITS) return { ok: false, error: `at most ${MAX_EDITS} edits per proposal` };
  const edits: Edit[] = [];
  for (const [i, e] of raw.entries()) {
    const at = `edit ${i + 1}`;
    if (!e || typeof e !== 'object' || Array.isArray(e)) return { ok: false, error: `${at}: must be an object` };
    const extra = Object.keys(e).filter((k) => !KEYS.has(k));
    if (extra.length) return { ok: false, error: `${at}: unknown field(s) ${extra.join(', ')} (use path, find, replace, or path and create)` };
    const r = e as Record<string, unknown>;
    const p = checkRepoPath(r.path);
    if (!p.ok) return { ok: false, error: `${at}: ${p.error}` };
    if (r.create !== undefined) {
      if (r.find !== undefined || r.replace !== undefined) return { ok: false, error: `${at}: a new file takes only path and create` };
      if (typeof r.create !== 'string' || !r.create.length || r.create.length > MAX_CREATE_CHARS) return { ok: false, error: `${at}: create must be text of 1 to ${MAX_CREATE_CHARS} characters` };
      edits.push({ path: p.rel, create: r.create });
    } else {
      if (typeof r.find !== 'string' || !r.find.length || r.find.length > MAX_FIND_CHARS) return { ok: false, error: `${at}: find must be text of 1 to ${MAX_FIND_CHARS} characters, copied exactly from the file` };
      if (typeof r.replace !== 'string' || r.replace.length > MAX_REPLACE_CHARS) return { ok: false, error: `${at}: replace must be text of at most ${MAX_REPLACE_CHARS} characters (empty deletes the found text)` };
      edits.push({ path: p.rel, find: r.find, replace: r.replace });
    }
  }
  const order = [...new Set(edits.map((e) => e.path))];
  const diffs: string[] = [];
  for (const file of order) {
    const mine = edits.filter((e) => e.path === file);
    if (mine.some((e) => e.create !== undefined)) {
      if (mine.length > 1) return { ok: false, error: `${file}: a new file takes exactly one edit` };
      if ((await git(repoRoot, ['cat-file', '-e', `${sha}:${file}`])).code === 0) return { ok: false, error: `${file} already exists at this commit: edit it with find and replace instead of create` };
      diffs.push(newFileDiff(file, mine[0]!.create!));
      continue;
    }
    const shown = await git(repoRoot, ['show', `${sha}:${file}`]);
    if (shown.code !== 0) return { ok: false, error: `${file} does not exist at this commit (to add a file use path and create)` };
    if (shown.out.length > MAX_FILE_BYTES || shown.out.includes(0)) return { ok: false, error: `${file} is too large or not text` };
    const before = shown.out.toString('utf8');
    let after = before;
    for (const [i, e] of mine.entries()) {
      const n = occurrences(after, e.find!);
      const label = `${file}, edit ${i + 1} of ${mine.length} in this file`;
      if (n === 0) return { ok: false, error: `${label}: the text to find is not in the file${i ? ' (after your earlier edits to it)' : ''}. Copy it exactly from the file content, without the line-number prefixes repo_read adds` };
      if (n > 1) return { ok: false, error: `${label}: the text to find occurs ${n} times; include more surrounding lines so it matches exactly once` };
      after = after.replace(e.find!, () => e.replace!);
    }
    if (after === before) return { ok: false, error: `${file}: the edits change nothing` };
    diffs.push(await modifyDiff(file, before, after));
  }
  const patch = diffs.join('');
  const review = reviewPatch(patch);
  if (!review.ok) return { ok: false, error: `the proposal is refused: ${review.error}` };
  const bad = await patchProblem(repoRoot, sha, patch);
  if (bad) return { ok: false, error: `the proposal does not apply to ${sha.slice(0, 8)}: ${bad}` };
  const ok = review as Extract<PatchReview, { ok: true }>;
  return { ok: true, patch, files: ok.files, flags: ok.flags, sha256: ok.sha256, edits: edits.length };
}
