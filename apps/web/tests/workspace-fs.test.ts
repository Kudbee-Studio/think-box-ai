// Unit tests for workspace-fs.ts: confined read/write/unlink, symlink refusal, size cap and the raw confinement helpers.
import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {
  readConfined, writeConfined, unlinkConfined, assertRealInside, assertRealInsideSync,
  isInside, WorkspacePathError, FileTooLargeError,
} from '../workspace-fs.ts';

const roots: string[] = [];
function tmpRoot(): string { const r = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-fs-')); roots.push(r); return r; }
after(() => { for (const r of roots) fs.rmSync(r, { recursive: true, force: true }); });

test('writeConfined then readConfined round-trips, creating directories on request', async () => {
  const root = tmpRoot();
  await writeConfined(root, path.join(root, 'nested', 'a.txt'), 'hello', { mkdirs: true });
  assert.equal((await readConfined(root, path.join(root, 'nested', 'a.txt'))).toString(), 'hello');
});

test('writeConfined truncates an existing file instead of appending', async () => {
  const root = tmpRoot();
  const file = path.join(root, 'a.txt');
  fs.writeFileSync(file, 'a much longer original value');
  await writeConfined(root, file, 'short');
  assert.equal(fs.readFileSync(file, 'utf8'), 'short');
});

test('readConfined enforces the byte cap', async () => {
  const root = tmpRoot();
  const file = path.join(root, 'big.txt');
  fs.writeFileSync(file, 'x'.repeat(50));
  await assert.rejects(() => readConfined(root, file, 10), FileTooLargeError);
});

test('readConfined refuses a directory', async () => {
  const root = tmpRoot();
  const dir = path.join(root, 'dir');
  fs.mkdirSync(dir);
  await assert.rejects(() => readConfined(root, dir), WorkspacePathError);
});

test('readConfined refuses a symlink that resolves outside the root', async () => {
  const root = tmpRoot();
  const outside = tmpRoot();
  const target = path.join(outside, 'secret.txt');
  fs.writeFileSync(target, 'secret');
  fs.symlinkSync(target, path.join(root, 'link.txt'));
  await assert.rejects(() => readConfined(root, path.join(root, 'link.txt')), WorkspacePathError);
});

test('writeConfined refuses to write through a symlink, even one that stays inside the root', async () => {
  const root = tmpRoot();
  fs.writeFileSync(path.join(root, 'real.txt'), 'real');
  fs.symlinkSync(path.join(root, 'real.txt'), path.join(root, 'alias.txt'));
  await assert.rejects(() => writeConfined(root, path.join(root, 'alias.txt'), 'x'), /Refusing to write through a symlink/);
  assert.equal(fs.readFileSync(path.join(root, 'real.txt'), 'utf8'), 'real');
});

test('writeConfined refuses a destination outside the root', async () => {
  const root = tmpRoot();
  await assert.rejects(() => writeConfined(root, path.join(root, '..', 'evil.txt'), 'x'), WorkspacePathError);
});

test('unlinkConfined removes a regular file', async () => {
  const root = tmpRoot();
  const file = path.join(root, 'gone.txt');
  fs.writeFileSync(file, 'x');
  await unlinkConfined(root, file);
  assert.equal(fs.existsSync(file), false);
});

test('unlinkConfined refuses a directory', async () => {
  const root = tmpRoot();
  const dir = path.join(root, 'dir');
  fs.mkdirSync(dir);
  await assert.rejects(() => unlinkConfined(root, dir), /Not a file/);
});

test('unlinkConfined removes a symlink itself and leaves its target', async () => {
  const root = tmpRoot();
  const target = path.join(root, 'target.txt');
  fs.writeFileSync(target, 'keep');
  const link = path.join(root, 'link.txt');
  fs.symlinkSync(target, link);
  await unlinkConfined(root, link);
  assert.equal(fs.existsSync(link), false);
  assert.equal(fs.readFileSync(target, 'utf8'), 'keep');
});

test('assertRealInside accepts an inside path and rejects an escape', async () => {
  const root = tmpRoot();
  const inside = path.join(root, 'x', 'y.txt');
  assert.equal(await assertRealInside(root, inside), await fs.promises.realpath(root));
  await assert.rejects(() => assertRealInside(root, path.join(root, '..', 'outside.txt')), WorkspacePathError);
});

test('assertRealInsideSync mirrors the async check', () => {
  const root = tmpRoot();
  assert.doesNotThrow(() => assertRealInsideSync(root, path.join(root, 'a.txt')));
  assert.throws(() => assertRealInsideSync(root, path.join(root, '..', 'outside.txt')), WorkspacePathError);
});

test('isInside is true only for the root or a descendant', () => {
  assert.equal(isInside('/a/b', '/a'), true);
  assert.equal(isInside('/a', '/a'), true);
  assert.equal(isInside('/ab', '/a'), false);
});
