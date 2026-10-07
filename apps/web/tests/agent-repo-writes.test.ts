// With "use for agent" on, the agent's file tools work inside the chosen repository: a fix is written where `git diff` shows it, and .git is off limits.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test } from 'node:test';
import { repoFilePath } from '../active-repo.ts';
import { listWorkspace } from '../agent.ts';

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-repo-writes-'));
after(() => fs.rmSync(root, { recursive: true, force: true }));

test('a relative path resolves inside the repository', () => {
  assert.equal(repoFilePath(root, 'src/cart.js'), path.join(root, 'src', 'cart.js'));
  assert.equal(repoFilePath(root, '/src/cart.js'), path.join(root, 'src', 'cart.js'));
});

test('parent paths and the .git folder are refused', () => {
  assert.throws(() => repoFilePath(root, '../x.js'), /Invalid workspace path/);
  assert.throws(() => repoFilePath(root, ''), /Invalid workspace path/);
  assert.throws(() => repoFilePath(root, '.git/config'), /\.git folder/);
  assert.throws(() => repoFilePath(root, 'src/.git/hooks/pre-commit'), /\.git folder/);
});

test('list_files skips .git and node_modules', async () => {
  fs.mkdirSync(path.join(root, '.git')); fs.writeFileSync(path.join(root, '.git', 'HEAD'), 'x');
  fs.mkdirSync(path.join(root, 'node_modules', 'm'), { recursive: true }); fs.writeFileSync(path.join(root, 'node_modules', 'm', 'i.js'), 'x');
  fs.mkdirSync(path.join(root, 'src')); fs.writeFileSync(path.join(root, 'src', 'a.js'), 'x');
  assert.deepEqual((await listWorkspace(root)).map((f) => f.path), ['src/a.js']);
});
