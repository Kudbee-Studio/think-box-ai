import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { lockDataDir, looseEntries } from '../data-permissions.ts';

function dataDir(): string {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'data-'));
  fs.chmodSync(d, 0o755);
  fs.mkdirSync(path.join(d, 'profiles'), { mode: 0o755 });
  fs.writeFileSync(path.join(d, 'runs.json'), '[]', { mode: 0o644 });
  fs.writeFileSync(path.join(d, 'profiles', 'p.json'), '{}', { mode: 0o644 });
  return d;
}
const mode = (p: string) => fs.statSync(p).mode & 0o777;

test('lockDataDir makes the folder and everything in it private to the owner', () => {
  const d = dataDir();
  assert.equal(looseEntries(d).length, 4);
  assert.equal(lockDataDir(d), 4);
  assert.equal(mode(d), 0o700);
  assert.equal(mode(path.join(d, 'profiles')), 0o700);
  assert.equal(mode(path.join(d, 'runs.json')), 0o600);
  assert.equal(mode(path.join(d, 'profiles', 'p.json')), 0o600);
  assert.deepEqual(looseEntries(d), []);
});

test('lockDataDir is idempotent and does not follow symlinks out of the folder', () => {
  const d = dataDir();
  const outside = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'out-')), 'keep.txt');
  fs.writeFileSync(outside, 'x', { mode: 0o644 });
  fs.symlinkSync(outside, path.join(d, 'link'));
  lockDataDir(d);
  assert.equal(lockDataDir(d), 0);
  assert.equal(mode(outside), 0o644);
});

test('a missing folder is not an error', () => assert.equal(lockDataDir('/nonexistent/kudbee-x'), 0));

test('secureDataDir creates a missing folder privately and sets the umask so later files are private', async () => {
  const { secureDataDir } = await import('../data-permissions.ts');
  const before = process.umask();
  try {
    const d = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'sec-')), 'fresh');
    secureDataDir(d);
    assert.equal(mode(d), 0o700);
    fs.writeFileSync(path.join(d, 'later.db'), 'x');
    assert.equal(mode(path.join(d, 'later.db')), 0o600);
  } finally { process.umask(before); }
});
