import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { loadBaseline, scanHistory, scanText, scanTracked, withoutBaseline, writeBaseline } from '../secret-scan.ts';

const fakeKey = ['sk', 'live', 'abcdefghij1234567890wxyz'].join('-');
const fakePem = ['-----BEGIN', 'RSA PRIVATE KEY-----'].join(' ');

test('scanText finds keys, private keys and assigned secrets, with line numbers and a masked preview', () => {
  const found = scanText(`line one\nconst k = "${fakeKey}";\n${fakePem}\npassword = "hunter2hunter2"\n`, 'a.ts'); // secret-scan:ignore (deliberate fixture)
  assert.deepEqual(found.map((f) => [f.line, f.rule]), [[2, 'key'], [3, 'private-key'], [4, 'assigned-secret']]);
  assert.ok(found.every((f) => !f.preview.includes('abcdefghij1234567890wxyz') && !f.preview.includes('hunter2hunter2')), 'a finding never repeats the secret');
});

test('scanText leaves ordinary code, placeholders and marked lines alone', () => {
  const clean = `const token = process.env.TOKEN;\napikey = "<your key here>"\nconst x = "${fakeKey}"; // secret-scan:ignore\nconst s = 'password'`;
  assert.deepEqual(scanText(clean, 'b.ts'), []);
});

function repo(files: Record<string, string>): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'scan-'));
  const git = (...a: string[]) => execFileSync('git', a, { cwd: dir, stdio: 'pipe' });
  git('init', '-q'); git('config', 'user.email', 't@t'); git('config', 'user.name', 't');
  for (const [f, body] of Object.entries(files)) { fs.mkdirSync(path.dirname(path.join(dir, f)), { recursive: true }); fs.writeFileSync(path.join(dir, f), body); }
  git('add', '-A'); git('commit', '-qm', 'one');
  return dir;
}

test('scanTracked reads tracked files only and skips binaries', () => {
  const dir = repo({ 'src/a.ts': `export const k = "${fakeKey}";\n`, 'src/ok.ts': 'export const n = 1;\n', 'bin.dat': 'x\0y' });
  fs.writeFileSync(path.join(dir, 'untracked.env'), `KEY=${fakeKey}\n`);
  const found = scanTracked(dir);
  assert.deepEqual(found.map((f) => f.file), ['src/a.ts']);
});

test('scanHistory finds a secret that was committed and later removed', () => {
  const dir = repo({ 'a.ts': `const k = "${fakeKey}";\n` });
  fs.writeFileSync(path.join(dir, 'a.ts'), 'const k = process.env.K;\n');
  execFileSync('git', ['commit', '-qam', 'remove'], { cwd: dir });
  assert.equal(scanTracked(dir).length, 0, 'the working tree is clean');
  const hist = scanHistory(dir);
  assert.equal(hist.length, 1);
  assert.match(hist[0].commit ?? '', /^[0-9a-f]{8}$/);
});

test('ordinary identifiers are not secrets: skip_special_tokens, tokenId, a header name', () => {
  const text = `decode(x, skip_special_tokens=True)\n{ tokenId: 'token-tools-70aef020-e6b4-4544-9544-455873925d0c' }\nAPI_KEY_HEADER = "X-API-Key"`;
  assert.deepEqual(scanText(text, 'c.py'), []);
});

test('a baseline hides accepted findings, shows new ones, and holds hashes not secrets', () => {
  const dir = repo({ 'a.ts': `export const k = "${fakeKey}";\n` });
  assert.equal(writeBaseline(dir), 1);
  const raw = fs.readFileSync(path.join(dir, 'docs/security/secret-scan-baseline.json'), 'utf8');
  assert.ok(!raw.includes('abcdefghij1234567890wxyz'));
  const base = loadBaseline(dir);
  assert.deepEqual(withoutBaseline(scanTracked(dir), base), []);
  fs.writeFileSync(path.join(dir, 'b.ts'), `export const k2 = "${fakeKey.replace('live', 'new1')}";\n`);
  execFileSync('git', ['add', '-A'], { cwd: dir });
  assert.deepEqual(withoutBaseline(scanTracked(dir), base).map((f) => f.file), ['b.ts']);
});

test('a missing or broken baseline file means an empty baseline', () => {
  const dir = repo({ 'a.ts': 'x\n' });
  assert.equal(loadBaseline(dir).size, 0);
  fs.mkdirSync(path.join(dir, 'docs/security'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'docs/security/secret-scan-baseline.json'), '{not json');
  assert.equal(loadBaseline(dir).size, 0);
});
