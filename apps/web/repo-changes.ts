// What the agent changed in the repository chosen with "use for agent": the changed files, a bounded diff per file, and undo. Plain git, no index changes.
import { execFile } from 'node:child_process';
import { repoFilePath } from './active-repo.ts';

export interface RepoChange { path: string; status: 'modified' | 'added' | 'deleted' | 'renamed' | 'untracked' }
const MAX_FILES = 200;
const MAX_DIFF = 60_000;

function git(root: string, args: string[]): Promise<{ stdout: string; code: number }> {
  return new Promise((resolve, reject) => {
    execFile('git', args, { cwd: root, encoding: 'utf8', timeout: 15000, maxBuffer: 4 * 1024 * 1024 }, (err, stdout) => {
      if (!err) return resolve({ stdout, code: 0 });
      const code = (err as NodeJS.ErrnoException & { code?: number | string }).code;
      if (typeof code === 'number') return resolve({ stdout: String(stdout ?? ''), code }); // `git diff --no-index` exits 1 when files differ
      reject(err);
    });
  });
}

function statusOf(xy: string): RepoChange['status'] {
  if (xy === '??') return 'untracked';
  if (xy.includes('D')) return 'deleted';
  if (xy.includes('R')) return 'renamed';
  if (xy.includes('A')) return 'added';
  return 'modified';
}

/** The changed files, newest-style order as git reports them (path order). Renames report the new path. */
export async function listChanges(root: string): Promise<{ files: RepoChange[]; truncated: boolean }> {
  const { stdout } = await git(root, ['status', '--porcelain=v1', '-z', '-uall']);
  const parts = stdout.split('\0').filter(Boolean);
  const files: RepoChange[] = [];
  for (let i = 0; i < parts.length; i++) {
    const entry = parts[i]!; const xy = entry.slice(0, 2); const file = entry.slice(3);
    if (xy.includes('R') || xy.includes('C')) i++; // the next field is the old path
    files.push({ path: file, status: statusOf(xy) });
  }
  return { files: files.slice(0, MAX_FILES), truncated: files.length > MAX_FILES };
}

/** The diff of one changed file against the last commit; a new file is shown as all added lines. */
export async function diffOf(root: string, relativePath: string): Promise<{ diff: string; truncated: boolean }> {
  repoFilePath(root, relativePath);
  const known = (await listChanges(root)).files.find((f) => f.path === relativePath);
  if (!known) throw new Error('That file has no changes');
  const out = known.status === 'untracked'
    ? await git(root, ['diff', '--no-index', '--no-color', '--', '/dev/null', relativePath])
    : await git(root, ['diff', 'HEAD', '--no-color', '--', relativePath]);
  return { diff: out.stdout.slice(0, MAX_DIFF), truncated: out.stdout.length > MAX_DIFF };
}

/** Put one file, or every changed file, back to the last commit. New files are deleted; ignored files are left alone. */
export async function undoChanges(root: string, relativePath?: string): Promise<{ restored: number }> {
  if (relativePath !== undefined) {
    repoFilePath(root, relativePath);
    const known = (await listChanges(root)).files.find((f) => f.path === relativePath);
    if (!known) throw new Error('That file has no changes');
    if (known.status === 'untracked') await git(root, ['clean', '-fq', '--', relativePath]);
    else if (known.status === 'added') await git(root, ['rm', '-fq', '--', relativePath]);
    else await git(root, ['checkout', 'HEAD', '--', relativePath]);
    return { restored: 1 };
  }
  const { files } = await listChanges(root);
  await git(root, ['reset', '-q']);
  await git(root, ['checkout', 'HEAD', '--', '.']);
  await git(root, ['clean', '-fdq']);
  return { restored: files.length };
}
