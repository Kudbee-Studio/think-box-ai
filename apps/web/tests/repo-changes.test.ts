// Review changes: the files the agent changed in the chosen repository, a bounded diff per file, and undo, all with plain git on a real repository.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, beforeEach, test } from 'node:test';
import { diffOf, listChanges, undoChanges } from '../repo-changes.ts';

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-changes-'));
after(() => fs.rmSync(root, { recursive: true, force: true }));
const git = (...a: string[]): string => execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', ...a], { cwd: root, encoding: 'utf8' });
const put = (rel: string, text: string): void => { fs.mkdirSync(path.dirname(path.join(root, rel)), { recursive: true }); fs.writeFileSync(path.join(root, rel), text); };

beforeEach(() => {
  fs.rmSync(root, { recursive: true, force: true }); fs.mkdirSync(root);
  git('init', '-q', '-b', 'main'); put('src/a.js', 'one\n'); put('src/b.js', 'two\n'); put('.gitignore', 'ignored.log\n');
  git('add', '-A'); git('commit', '-qm', 'base');
});

test('a clean repository has no changes', async () => {
  assert.deepEqual(await listChanges(root), { files: [], truncated: false });
});

test('modified, deleted and new files are listed with their kind; ignored files are not', async () => {
  put('src/a.js', 'ONE\n'); fs.rmSync(path.join(root, 'src/b.js')); put('new/c.js', 'x\n'); put('ignored.log', 'noise');
  const { files } = await listChanges(root);
  assert.deepEqual(files.map((f) => `${f.status}:${f.path}`).sort(), ['deleted:src/b.js', 'modified:src/a.js', 'untracked:new/c.js']);
});

test('the diff of a changed file shows the change; a new file shows as added lines; an unchanged file is refused', async () => {
  put('src/a.js', 'ONE\n'); put('new/c.js', 'hello\n');
  assert.match((await diffOf(root, 'src/a.js')).diff, /-one\n\+ONE/);
  assert.match((await diffOf(root, 'new/c.js')).diff, /\+hello/);
  await assert.rejects(diffOf(root, 'src/b.js'), /no changes/);
  await assert.rejects(diffOf(root, '../x'), /Invalid workspace path/);
  await assert.rejects(diffOf(root, '.git/config'), /\.git folder/);
});

test('a very large diff is cut and says so', async () => {
  put('src/a.js', `${'line\n'.repeat(30000)}`);
  const d = await diffOf(root, 'src/a.js');
  assert.equal(d.truncated, true); assert.ok(d.diff.length <= 60000);
});

test('undo of one file restores a modified file, removes a new file, and leaves the others', async () => {
  put('src/a.js', 'ONE\n'); put('new/c.js', 'x\n'); fs.rmSync(path.join(root, 'src/b.js'));
  await undoChanges(root, 'src/a.js'); assert.equal(fs.readFileSync(path.join(root, 'src/a.js'), 'utf8'), 'one\n');
  await undoChanges(root, 'new/c.js'); assert.equal(fs.existsSync(path.join(root, 'new/c.js')), false);
  assert.deepEqual((await listChanges(root)).files.map((f) => f.path), ['src/b.js']);
  await undoChanges(root, 'src/b.js'); assert.equal(fs.readFileSync(path.join(root, 'src/b.js'), 'utf8'), 'two\n');
  await assert.rejects(undoChanges(root, 'src/a.js'), /no changes/);
});

test('undo all restores everything but keeps ignored files', async () => {
  put('src/a.js', 'ONE\n'); put('new/c.js', 'x\n'); fs.rmSync(path.join(root, 'src/b.js')); put('ignored.log', 'keep');
  const r = await undoChanges(root);
  assert.equal(r.restored, 3);
  assert.deepEqual((await listChanges(root)).files, []);
  assert.equal(fs.readFileSync(path.join(root, 'ignored.log'), 'utf8'), 'keep');
});

test('a staged change is undone too', async () => {
  put('src/a.js', 'ONE\n'); git('add', 'src/a.js');
  await undoChanges(root, 'src/a.js');
  assert.equal(fs.readFileSync(path.join(root, 'src/a.js'), 'utf8'), 'one\n');
});

test('a new file the agent already staged is removed by undo', async () => {
  put('new/d.js', 'x\n'); git('add', 'new/d.js');
  assert.equal((await listChanges(root)).files[0]?.status, 'added');
  await undoChanges(root, 'new/d.js');
  assert.equal(fs.existsSync(path.join(root, 'new/d.js')), false);
});
