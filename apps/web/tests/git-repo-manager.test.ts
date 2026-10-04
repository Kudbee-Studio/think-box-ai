// Unit tests for git-repo-manager.ts: URL/branch/depth validation, confinement, file tree, read/write, status and delete.
// No test reaches the network: the clone path that would contact github.com is exercised only through its validation and
// the "already exists" branch, and the git subprocess failures are the real, local "not a repository" errors.
import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { GitRepoManager, GitInputError, GITHUB_HTTPS_URL, SAFE_BRANCH } from '../git-repo-manager.ts';

const roots: string[] = [];
function baseDir(): string { const r = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-git-')); roots.push(r); return r; }
after(() => { for (const r of roots) fs.rmSync(r, { recursive: true, force: true }); });

test('constructor creates the base directory', () => {
  const base = path.join(baseDir(), 'deep', 'workspaces');
  new GitRepoManager(base);
  assert.equal(fs.existsSync(base), true);
});

test('cloneRepository rejects a URL that is not a public github https repo', async () => {
  const m = new GitRepoManager(baseDir());
  for (const url of ['http://github.com/o/r', 'https://gitlab.com/o/r', 'git@github.com:o/r.git', 'https://github.com/o/r/extra']) {
    await assert.rejects(() => m.cloneRepository({ url }), GitInputError);
  }
});

test('cloneRepository rejects an invalid branch and an out-of-range depth', async () => {
  const m = new GitRepoManager(baseDir());
  await assert.rejects(() => m.cloneRepository({ url: 'https://github.com/o/r', branch: '-x' }), GitInputError);
  await assert.rejects(() => m.cloneRepository({ url: 'https://github.com/o/r', depth: 0 }), GitInputError);
  await assert.rejects(() => m.cloneRepository({ url: 'https://github.com/o/r', depth: 5000 }), GitInputError);
});

test('cloneRepository on an existing local path syncs (fails gracefully off-repo), counts files and reports idle', async () => {
  const base = baseDir();
  const m = new GitRepoManager(base);
  const local = path.join(base, 'repo');
  fs.mkdirSync(local, { recursive: true });
  fs.writeFileSync(path.join(local, 'a.txt'), 'a');
  fs.mkdirSync(path.join(local, 'sub'));
  fs.writeFileSync(path.join(local, 'sub', 'b.txt'), 'b');
  const state = await m.cloneRepository({ url: 'https://github.com/owner/repo' });
  assert.equal(state.name, 'repo');
  assert.equal(state.status, 'idle');
  assert.equal(state.fileCount, 2);
  assert.equal(m.getRepositoryInfo('repo')?.url, 'https://github.com/owner/repo');
  assert.equal(m.listRepositories().length, 1);
});

test('resolveInside accepts an inside path and refuses absolute, .. and symlink escapes', () => {
  const base = baseDir();
  const m = new GitRepoManager(base);
  fs.writeFileSync(path.join(base, 'ok.txt'), 'ok');
  assert.equal(m.resolveInside('ok.txt'), path.join(fs.realpathSync(base), 'ok.txt'));

  const outside = baseDir();
  fs.writeFileSync(path.join(outside, 'secret.txt'), 's');
  fs.symlinkSync(outside, path.join(base, 'escape'));
  assert.throws(() => m.resolveInside(path.join(outside, 'secret.txt')), GitInputError);
  assert.throws(() => m.resolveInside('../outside.txt'), GitInputError);
  assert.throws(() => m.resolveInside('escape/secret.txt'), GitInputError);
});

test('readFile reads inside the workspace and reports a missing file', () => {
  const base = baseDir();
  const m = new GitRepoManager(base);
  fs.writeFileSync(path.join(base, 'r.txt'), 'content');
  assert.equal(m.readFile('r.txt'), 'content');
  assert.throws(() => m.readFile('missing.txt'), /Failed to read file/);
});

test('writeFile creates parent directories and refuses to escape', () => {
  const base = baseDir();
  const m = new GitRepoManager(base);
  const written = m.writeFile(path.join('nested', 'w.txt'), 'hi');
  assert.equal(fs.readFileSync(written, 'utf8'), 'hi');
  assert.throws(() => m.writeFile('../escape.txt', 'x'), GitInputError);
});

test('getFileTree lists files and directories, skips hidden entries and broken symlinks, and honours maxDepth', () => {
  const base = baseDir();
  const m = new GitRepoManager(base);
  fs.mkdirSync(path.join(base, 'src'));
  fs.writeFileSync(path.join(base, 'src', 'index.ts'), 'x');
  fs.writeFileSync(path.join(base, 'README.md'), 'r');
  fs.writeFileSync(path.join(base, '.hidden'), 'h');
  fs.symlinkSync(path.join(base, 'does-not-exist'), path.join(base, 'broken'));

  const tree = m.getFileTree(base);
  const names = (tree.children ?? []).map((c) => c.name);
  assert.ok(names.includes('src'));
  assert.ok(names.includes('README.md'));
  assert.equal(names.includes('.hidden'), false);
  assert.equal(names.includes('broken'), false);
  const src = tree.children!.find((c) => c.name === 'src')!;
  assert.equal(src.type, 'directory');
  assert.equal(src.children![0].name, 'index.ts');

  const shallow = m.getFileTree(base, 1);
  const shallowSrc = shallow.children!.find((c) => c.name === 'src')!;
  assert.deepEqual(shallowSrc.children, []);
});

test('getFileTree refuses a path outside the workspace', () => {
  const base = baseDir();
  const m = new GitRepoManager(base);
  assert.throws(() => m.getFileTree(path.join(base, '..', 'elsewhere')), GitInputError);
});

test('getRepositoryStatus reports an error for a directory that is not a repository', () => {
  const base = baseDir();
  const m = new GitRepoManager(base);
  fs.mkdirSync(path.join(base, 'plain'));
  const status = m.getRepositoryStatus(path.join(base, 'plain'));
  assert.equal(status.isDirty, false);
  assert.deepEqual(status.changes, []);
  assert.equal(typeof status.error, 'string');
});

test('deleteRepository removes a known repository and reports an unknown one', async () => {
  const base = baseDir();
  const m = new GitRepoManager(base);
  const local = path.join(base, 'repo');
  fs.mkdirSync(local, { recursive: true });
  await m.cloneRepository({ url: 'https://github.com/owner/repo' });
  assert.equal(m.deleteRepository('missing'), false);
  assert.equal(m.deleteRepository('repo'), true);
  assert.equal(fs.existsSync(local), false);
  assert.equal(m.getRepositoryInfo('repo'), undefined);
});

test('the URL and branch patterns match only what git is allowed to receive', () => {
  assert.equal(GITHUB_HTTPS_URL.test('https://github.com/owner/repo'), true);
  assert.equal(GITHUB_HTTPS_URL.test('https://github.com/owner/repo.git'), true);
  assert.equal(GITHUB_HTTPS_URL.test('https://github.com/owner/repo; rm -rf /'), false);
  assert.equal(SAFE_BRANCH.test('feature/x-1'), true);
  assert.equal(SAFE_BRANCH.test('bad branch'), false);
});
