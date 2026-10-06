// Read-only repository tools: what a worker can see of the repo, and everything it must not be able to see.
import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { checkRepoPath, normalize, renderRepoEvidence, repoRead, repoSearch, validateRepoReadArgs, validateRepoSearchArgs, verifyQuoteOnDisk } from '../repo-tools.ts';

let root = ''; let outside = '';
const write = (rel: string, text: string | Buffer) => { fs.mkdirSync(path.dirname(path.join(root, rel)), { recursive: true }); fs.writeFileSync(path.join(root, rel), text); };

before(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), 'repo-tools-'));
  outside = fs.mkdtempSync(path.join(os.tmpdir(), 'repo-outside-'));
  fs.writeFileSync(path.join(outside, 'stolen.ts'), 'export const SECRET_OUTSIDE = 1;\n');
  write('src/alpha.ts', 'export function alpha(x: number): number {\n  return x + 1; // alpha(1) [x]\n}\nexport function beta() {}\n');
  write('src/beta.ts', 'import { alpha } from "./alpha.ts";\nexport const Z = alpha(2);\n');
  write('tests/alpha.test.ts', 'import { alpha } from "../src/alpha.ts";\ntest("alpha", () => alpha(1));\n');
  write('README.md', '# Title\nSee alpha.\n');
  write('.env', 'API_KEY=supersecret\n');
  write('config/credentials.json', '{"token":"supersecret"}\n');
  write('node_modules/pkg/index.js', 'alpha();\n');
  write('.git/config', '[core]\nalpha\n');
  write('data/runs.json', '{"alpha":1}\n');
  write('assets/blob.ts', Buffer.concat([Buffer.from('alpha'), Buffer.from([0, 1, 2, 3])]));
  write('big.ts', `alpha\n${'x'.repeat(450_000)}`);
  fs.symlinkSync(path.join(outside, 'stolen.ts'), path.join(root, 'src/link.ts'));
  fs.symlinkSync(outside, path.join(root, 'linkdir'));
});
after(() => { fs.rmSync(root, { recursive: true, force: true }); fs.rmSync(outside, { recursive: true, force: true }); });

describe('checkRepoPath', () => {
  it('accepts normal repo-relative source paths', () => {
    for (const p of ['src/alpha.ts', './src/alpha.ts', 'README.md', 'apps\\web\\x.ts']) assert.equal(checkRepoPath(p).ok, true, p);
    assert.deepEqual(checkRepoPath('./src//alpha.ts'), { ok: true, rel: 'src/alpha.ts' });
  });
  it('refuses escapes, absolute paths, excluded folders, secrets and non-text files', () => {
    const bad = ['', '   ', '../x.ts', 'src/../../x.ts', '/etc/passwd', 'C:/x.ts', 'src/a\0.ts', 'x'.repeat(301), 'node_modules/a/index.js', '.git/config', 'data/runs.json', 'workspaces/s/x.ts', '.env', '.env.local', 'config/credentials.json', 'keys/id_rsa.pub.ts', 'server.pem', 'app.db', 'src/blob.png', 'noext'];
    for (const p of bad) assert.equal(checkRepoPath(p).ok, false, JSON.stringify(p));
    for (const p of [null, undefined, 5, {}, []]) assert.equal(checkRepoPath(p).ok, false);
  });
  it('allows a directory only when asked', () => {
    assert.equal(checkRepoPath('src').ok, false);
    assert.deepEqual(checkRepoPath('src', { allowDir: true }), { ok: true, rel: 'src' });
  });
});

describe('argument validation', () => {
  it('search: strict keys, a real query, one line', () => {
    assert.deepEqual(validateRepoSearchArgs({ query: 'alpha' }), { ok: true, args: { query: 'alpha', path: '' } });
    assert.deepEqual(validateRepoSearchArgs({ query: 'alpha', path: 'tests' }), { ok: true, args: { query: 'alpha', path: 'tests' } });
    for (const bad of [null, [], 'alpha', {}, { query: 'a' }, { query: 'x'.repeat(121) }, { query: 'a\nb' }, { query: 'alpha', extra: 1 }, { query: 'alpha', path: '../x' }, { query: 'alpha', path: '.env' }, { query: 'alpha', path: 'node_modules' }]) assert.equal(validateRepoSearchArgs(bad).ok, false, JSON.stringify(bad));
  });
  it('read: strict keys, whole-number line range, capped window', () => {
    assert.deepEqual(validateRepoReadArgs({ path: 'src/alpha.ts' }), { ok: true, args: { path: 'src/alpha.ts', start: 1, end: 120 } });
    assert.deepEqual(validateRepoReadArgs({ path: 'src/alpha.ts', start: 10, end: 5000 }), { ok: true, args: { path: 'src/alpha.ts', start: 10, end: 209 } });
    for (const bad of [{}, { path: 'src/alpha.ts', start: 0 }, { path: 'src/alpha.ts', start: 1.5 }, { path: 'src/alpha.ts', start: 5, end: 2 }, { path: 'src/alpha.ts', start: '1' }, { path: '.env' }, { path: 'src/alpha.ts', lines: 3 }]) assert.equal(validateRepoReadArgs(bad).ok, false, JSON.stringify(bad));
  });
});

describe('repoSearch', () => {
  it('finds literal text with numbered lines, newest-safe order, and records its own evidence', async () => {
    const e = await repoSearch({ query: 'alpha', path: '' }, root);
    assert.equal(e.tool, 'repo_search');
    if (e.tool !== 'repo_search') return;
    const where = e.matches.map((m) => `${m.path}:${m.line}`);
    assert.ok(where.includes('src/alpha.ts:1') && where.includes('tests/alpha.test.ts:1') && where.includes('README.md:2'));
    assert.deepEqual(e.matches.find((m) => m.path === 'src/alpha.ts' && m.line === 2)?.text, '  return x + 1; // alpha(1) [x]');
    assert.equal(e.tool_calls, 1);
    assert.ok(Number.isFinite(e.latency_ms) && e.fetched_at);
  });
  it('treats regex characters as literal text', async () => {
    const e = await repoSearch({ query: 'alpha(1) [x]', path: '' }, root);
    if (e.tool !== 'repo_search') return;
    assert.deepEqual(e.matches.map((m) => `${m.path}:${m.line}`), ['src/alpha.ts:2']);
    assert.equal((await repoSearch({ query: '.*', path: '' }, root) as any).matches.length, 0);
  });
  it('never returns secrets, excluded folders, symlink targets, binaries or oversized files', async () => {
    const all = JSON.stringify(await repoSearch({ query: 'alpha', path: '' }, root));
    for (const hidden of ['supersecret', 'node_modules', '.git/', 'data/runs.json', 'SECRET_OUTSIDE', 'blob.ts', 'big.ts', 'link.ts', 'linkdir']) assert.ok(!all.includes(hidden), hidden);
    assert.equal(((await repoSearch({ query: 'SECRET_OUTSIDE', path: '' }, root)) as any).matches.length, 0);
    assert.equal(((await repoSearch({ query: 'supersecret', path: '' }, root)) as any).matches.length, 0);
  });
  it('scopes to a folder or a file, and a zero-hit search is evidence of absence (no matches, not truncated)', async () => {
    const tests = await repoSearch({ query: 'beta', path: 'tests' }, root);
    if (tests.tool !== 'repo_search') return;
    assert.deepEqual({ n: tests.matches.length, truncated: tests.truncated }, { n: 0, truncated: false });
    assert.ok(tests.files_scanned >= 1);
    const one = await repoSearch({ query: 'alpha', path: 'src/alpha.ts' }, root);
    if (one.tool === 'repo_search') assert.ok(one.matches.every((m) => m.path === 'src/alpha.ts'));
    assert.match(renderRepoEvidence(tests), /NO MATCHES/);
  });
  it('refuses a symlinked start path and a missing one', async () => {
    await assert.rejects(repoSearch({ query: 'alpha', path: 'linkdir' }, root), /symlink/);
    await assert.rejects(repoSearch({ query: 'alpha', path: 'nope' }, root), /not found/);
  });
  it('caps the number of matches and says it was cut off', async () => {
    write('many/m.ts', Array.from({ length: 80 }, () => 'needle').join('\n'));
    const e = await repoSearch({ query: 'needle', path: 'many' }, root);
    if (e.tool !== 'repo_search') return;
    assert.equal(e.matches.length, 40);
    assert.equal(e.truncated, true);
  });
});

describe('repoRead', () => {
  it('returns numbered lines for a window and the file length', async () => {
    const e = await repoRead({ path: 'src/alpha.ts', start: 2, end: 3 }, root);
    if (e.tool !== 'repo_read') return;
    assert.deepEqual({ start: e.start, end: e.end, total: e.total_lines }, { start: 2, end: 3, total: 5 });
    assert.deepEqual(e.lines, [{ n: 2, text: '  return x + 1; // alpha(1) [x]' }, { n: 3, text: '}' }]);
    assert.match(renderRepoEvidence(e), /^src\/alpha\.ts lines 2-3 of 5:\n2: {3}return/);
  });
  it('clamps the end to the file and refuses a start past it', async () => {
    const e = await repoRead({ path: 'src/beta.ts', start: 1, end: 100 }, root);
    if (e.tool === 'repo_read') assert.equal(e.end, 3);
    await assert.rejects(repoRead({ path: 'src/beta.ts', start: 99, end: 100 }, root), /past the end/);
  });
  it('refuses symlinks, directories, missing, binary and oversized files', async () => {
    await assert.rejects(repoRead({ path: 'src/link.ts', start: 1, end: 2 }, root), /symlink/);
    await assert.rejects(repoRead({ path: 'src', start: 1, end: 2 }, root), /not a file|not found/);
    await assert.rejects(repoRead({ path: 'src/missing.ts', start: 1, end: 2 }, root), /not found/);
    await assert.rejects(repoRead({ path: 'assets/blob.ts', start: 1, end: 2 }, root), /binary/);
    await assert.rejects(repoRead({ path: 'big.ts', start: 1, end: 2 }, root), /larger than/);
  });
});

describe('verifyQuoteOnDisk', () => {
  it('confirms a quote at its line (whitespace-insensitive) and rejects a wrong line, a fake quote and a forbidden path', async () => {
    assert.deepEqual(await verifyQuoteOnDisk('src/alpha.ts', 1, 'export function alpha(x: number)', root), { ok: true });
    assert.deepEqual(await verifyQuoteOnDisk('src/alpha.ts', 2, 'return   x + 1', root), { ok: true });
    assert.equal((await verifyQuoteOnDisk('src/alpha.ts', 50, 'export function alpha', root)).ok, false);
    assert.match((await verifyQuoteOnDisk('src/alpha.ts', 1, 'export function gamma', root)).reason!, /not at src\/alpha\.ts:1/);
    assert.equal((await verifyQuoteOnDisk('.env', 1, 'API_KEY', root)).ok, false);
    assert.equal((await verifyQuoteOnDisk('../x.ts', 1, 'x', root)).ok, false);
  });
  it('normalize collapses whitespace and case', () => assert.equal(normalize('  A\n  b\tC '), 'a b c'));
});

describe('"not found" errors name what does exist (P3.34)', () => {
  it('a guessed folder gets the real ones; hidden entries, secrets and excluded folders are never listed', async () => {
    const err = await repoSearch({ query: 'alpha', path: 'test' }, root).then(() => '', (e: Error) => e.message);
    assert.match(err, /^path not found: test\. In the repository root: /);
    const listed = err.split('In the repository root: ')[1]!;
    for (const shown of ['src/', 'tests/', 'README.md', 'config/']) assert.ok(listed.includes(shown), `${shown} in ${listed}`);
    for (const hidden of ['.env', '.git', 'node_modules', 'data/', 'credentials']) assert.ok(!listed.includes(hidden), `${hidden} must not be listed: ${listed}`);
  });
  it('a missing file lists its nearest existing folder, and a missing folder falls back to the root', async () => {
    assert.match(await repoRead({ path: 'src/alpa.ts', start: 1, end: 3 }, root).then(() => '', (e: Error) => e.message), /^file not found: src\/alpa\.ts\. In src: alpha\.ts, beta\.ts\.$/);
    assert.match(await repoRead({ path: 'nodir/deep/x.ts', start: 1, end: 3 }, root).then(() => '', (e: Error) => e.message), /^file not found: nodir\/deep\/x\.ts\. In the repository root: /);
  });
  it('lists at most twelve entries and says nothing when the folder is empty', async () => {
    for (let i = 0; i < 15; i += 1) write(`many/f${String(i).padStart(2, '0')}.ts`, 'x\n');
    fs.mkdirSync(path.join(root, 'empty'), { recursive: true });
    const err = await repoRead({ path: 'many/zz.ts', start: 1, end: 2 }, root).then(() => '', (e: Error) => e.message);
    assert.equal(err.split('In many: ')[1]!.split(', ').length, 12);
    assert.equal(await repoRead({ path: 'empty/zz.ts', start: 1, end: 2 }, root).then(() => '', (e: Error) => e.message), 'file not found: empty/zz.ts.');
  });
});

