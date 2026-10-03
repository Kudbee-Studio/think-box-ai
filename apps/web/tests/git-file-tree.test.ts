import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { GitRepoManager } from '../git-repo-manager.ts';

test('getFileTree skips a broken symlink and still lists every other entry', () => {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'tree-'));
  try {
    const dir = path.join(base, 'repo');
    fs.mkdirSync(dir);
    fs.writeFileSync(path.join(dir, 'a.txt'), 'a');
    fs.symlinkSync(path.join(base, 'does-not-exist'), path.join(dir, 'broken'));
    fs.writeFileSync(path.join(dir, 'z.txt'), 'z');
    const tree = new GitRepoManager(path.join(base, 'ws')).getFileTree(dir);
    const names = (tree.children ?? []).map((c) => c.name).sort();
    assert.deepEqual(names, ['a.txt', 'z.txt']);
  } finally {
    fs.rmSync(base, { recursive: true, force: true });
  }
});
