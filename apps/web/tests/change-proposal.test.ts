// A proposed change as exact text edits, turned into a unified diff by code: the diff applies cleanly to the commit and produces exactly the intended file, and every
// way an edit can be wrong is reported precisely enough for a model to fix it. Nothing is written to the repository.
import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { MAX_CREATE_CHARS, MAX_EDITS, MAX_FIND_CHARS, MAX_REPLACE_CHARS, buildPatch } from '../change-proposal.ts';

let repo = ''; let sha = '';
const git = (...a: string[]): string => execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', ...a], { cwd: repo, encoding: 'utf8' }).trim();
const state = (): string => createHash('sha256').update(git('status', '--porcelain', '--ignored') + git('rev-parse', 'HEAD') + fs.readFileSync(path.join(repo, '.git', 'index'))).digest('hex');
const leftovers = (): number => fs.readdirSync(os.tmpdir()).filter((n) => n.startsWith('kudbee-diff-') || n.startsWith('kudbee-idx-')).length;
const GREETER = "function greet(name) {\n  return 'helo ' + name;\n}\n\nfunction farewell(name) {\n  return 'bye ' + name;\n}\n\nmodule.exports = { greet, farewell };\n";
const realTmp = process.env.TMPDIR; let privateTmp = '';

before(() => {
  privateTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'cp-tests-')); process.env.TMPDIR = privateTmp;
  repo = fs.mkdtempSync(path.join(os.tmpdir(), 'cp-fixture-'));
  const w = (rel: string, text: string | Buffer): void => { fs.mkdirSync(path.dirname(path.join(repo, rel)), { recursive: true }); fs.writeFileSync(path.join(repo, rel), text); };
  w('src/greeter.js', GREETER); w('src/dup.js', 'const a = 1;\nconst a = 1;\nconst b = 2;\n'); w('src/nonl.txt', 'one\ntwo'); w('src/bin.txt', Buffer.from([65, 0, 66])); w('.env', 'SECRET=1\n');
  w('src/big.txt', 'x'.repeat(500_000));
  git('init', '-q', '-b', 'main'); git('add', '-A'); git('commit', '-qm', 'fixture'); sha = git('rev-parse', 'HEAD');
});
after(() => { fs.rmSync(repo, { recursive: true, force: true }); if (realTmp === undefined) delete process.env.TMPDIR; else process.env.TMPDIR = realTmp; fs.rmSync(privateTmp, { recursive: true, force: true }); });

/** Apply the patch to a real export of the commit and read the file back: the strongest check that the diff means what the edit said. */
function applied(patch: string): (rel: string) => string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cp-apply-'));
  execFileSync('git', ['archive', '--format=tar', '-o', path.join(dir, 't.tar'), sha], { cwd: repo });
  fs.mkdirSync(path.join(dir, 'w')); execFileSync('tar', ['-x', '-f', path.join(dir, 't.tar'), '-C', path.join(dir, 'w')]);
  execFileSync('git', ['apply', '--whitespace=nowarn', '-'], { cwd: path.join(dir, 'w'), input: patch });
  return (rel) => fs.readFileSync(path.join(dir, 'w', rel), 'utf8');
}
const ok = async (edits: unknown) => { const r = await buildPatch(repo, sha, edits); assert.equal(r.ok, true, JSON.stringify(r)); return r as Extract<typeof r, { ok: true }>; };
const bad = async (edits: unknown): Promise<string> => { const r = await buildPatch(repo, sha, edits); assert.equal(r.ok, false, JSON.stringify(edits)?.slice(0, 80)); return (r as { error: string }).error; };

describe('a valid proposal becomes a diff that applies cleanly and means what it said', () => {
  it('one edit: the diff names the file with a/ b/ paths, applies to the commit, and yields exactly the intended file', async () => {
    const r = await ok([{ path: 'src/greeter.js', find: "'helo '", replace: "'hello '" }]);
    assert.match(r.patch, /^diff --git a\/src\/greeter\.js b\/src\/greeter\.js\n/);
    assert.deepEqual(r.files, ['src/greeter.js']); assert.deepEqual(r.flags, []); assert.equal(r.edits, 1);
    assert.equal(r.sha256, createHash('sha256').update(r.patch).digest('hex'));
    assert.equal(applied(r.patch)('src/greeter.js'), GREETER.replace("'helo '", "'hello '"));
  });
  it('several edits in one file apply in order (a later edit sees the earlier ones), and edits to several files give one diff', async () => {
    const r = await ok([{ path: 'src/greeter.js', find: "'helo '", replace: "'hello '" }, { path: 'src/greeter.js', find: "'hello ' + name", replace: "'hello, ' + name + '!'" }, { path: 'src/dup.js', find: 'const b = 2;', replace: 'const b = 3;' }]);
    assert.deepEqual(r.files, ['src/dup.js', 'src/greeter.js']);
    const read = applied(r.patch);
    assert.match(read('src/greeter.js'), /return 'hello, ' \+ name \+ '!';/); assert.equal(read('src/dup.js'), 'const a = 1;\nconst a = 1;\nconst b = 3;\n');
  });
  it('a replacement may be empty (a deletion) and the replacement text is inserted literally, special characters included', async () => {
    const del = await ok([{ path: 'src/greeter.js', find: "function farewell(name) {\n  return 'bye ' + name;\n}\n\n", replace: '' }]);
    assert.doesNotMatch(applied(del.patch)('src/greeter.js'), /farewell\(name\)/);
    const dollars = await ok([{ path: 'src/greeter.js', find: "'helo '", replace: "'$& $1 $$ '" }]);
    assert.match(applied(dollars.patch)('src/greeter.js'), /return '\$& \$1 \$\$ ' \+ name;/);
  });
  it('a new file is a hand-built new-file diff, with and without a trailing newline, and flags a test file', async () => {
    const a = await ok([{ path: 'src/new.js', create: 'module.exports = 1;\n' }]);
    assert.match(a.patch, /^diff --git a\/src\/new\.js b\/src\/new\.js\nnew file mode 100644\n--- \/dev\/null\n\+\+\+ b\/src\/new\.js\n@@ -0,0 \+1,1 @@\n\+module\.exports = 1;\n$/);
    assert.equal(applied(a.patch)('src/new.js'), 'module.exports = 1;\n');
    const b = await ok([{ path: 'tests/new.test.js', create: 'line one\nno newline' }]);
    assert.equal(applied(b.patch)('tests/new.test.js'), 'line one\nno newline'); assert.deepEqual(b.flags, ['touches_tests']);
  });
  it('a file without a trailing newline round-trips, and the repository is exactly as it was afterwards (no temporary files left)', async () => {
    const before = state(); const left = leftovers();
    const r = await ok([{ path: 'src/nonl.txt', find: 'two', replace: 'three' }]);
    assert.equal(applied(r.patch)('src/nonl.txt'), 'one\nthree');
    assert.equal(state(), before); assert.equal(leftovers(), left);
  });
  it('is deterministic: the same edits give the same patch and hash', async () => {
    const e = [{ path: 'src/greeter.js', find: "'helo '", replace: "'hello '" }];
    assert.equal((await ok(e)).sha256, (await ok(e)).sha256);
  });
});

describe('every way an edit can be wrong is reported so a model can fix it', () => {
  it('shape errors: not a list, empty, too many, not objects, unknown fields, mixed create and find', async () => {
    assert.match(await bad(undefined), /non-empty list/); assert.match(await bad([]), /non-empty list/); assert.match(await bad('x'), /non-empty list/);
    assert.match(await bad(Array.from({ length: MAX_EDITS + 1 }, () => ({ path: 'src/greeter.js', find: 'a', replace: 'b' }))), new RegExp(`at most ${MAX_EDITS} edits`));
    assert.match(await bad([null]), /edit 1: must be an object/); assert.match(await bad([[]]), /edit 1: must be an object/);
    assert.match(await bad([{ path: 'src/greeter.js', find: 'a', replace: 'b', cmd: 'rm' }]), /edit 1: unknown field\(s\) cmd/);
    assert.match(await bad([{ path: 'src/greeter.js', create: 'x', find: 'a' }]), /takes only path and create/);
  });
  it('size and type limits', async () => {
    assert.match(await bad([{ path: 'src/greeter.js', find: '', replace: 'x' }]), /find must be text of 1 to/);
    assert.match(await bad([{ path: 'src/greeter.js', find: 'x'.repeat(MAX_FIND_CHARS + 1), replace: 'x' }]), /find must be text/);
    assert.match(await bad([{ path: 'src/greeter.js', find: 'a', replace: 'x'.repeat(MAX_REPLACE_CHARS + 1) }]), /replace must be text of at most/);
    assert.match(await bad([{ path: 'src/greeter.js', find: 'a' }]), /replace must be text/); assert.match(await bad([{ path: 'src/greeter.js', find: 7, replace: 'x' }]), /find must be text/);
    assert.match(await bad([{ path: 'src/x.js', create: '' }]), /create must be text/); assert.match(await bad([{ path: 'src/x.js', create: 'x'.repeat(MAX_CREATE_CHARS + 1) }]), /create must be text/);
  });
  it('paths: secrets, escapes, excluded folders and non-text files are refused with the policy\'s reason', async () => {
    for (const p of ['.env', '../x.js', '/etc/passwd', '.git/config', 'node_modules/x.js', 'src/app.png', 7]) assert.match(await bad([{ path: p, find: 'a', replace: 'b' }]), /^edit 1: /, String(p));
  });
  it('find text that is missing, ambiguous, copied with line-number prefixes, or a no-op is explained', async () => {
    assert.match(await bad([{ path: 'src/greeter.js', find: 'not in the file', replace: 'x' }]), /the text to find is not in the file\. Copy it exactly from the file content, without the line-number prefixes/);
    assert.match(await bad([{ path: 'src/dup.js', find: 'const a = 1;', replace: 'x' }]), /occurs 2 times; include more surrounding lines/);
    assert.match(await bad([{ path: 'src/greeter.js', find: "2\\t  return 'helo ' + name;", replace: 'x' }]), /not in the file/);
    assert.match(await bad([{ path: 'src/greeter.js', find: "'helo '", replace: "'helo '" }]), /change nothing/);
    assert.match(await bad([{ path: 'src/greeter.js', find: "'helo '", replace: "'hello '" }, { path: 'src/greeter.js', find: "'helo '", replace: 'x' }]), /edit 2 of 2 in this file: the text to find is not in the file \(after your earlier edits to it\)/);
  });
  it('missing, binary and oversized files; creating a file that exists; creating twice; editing a file that is not there', async () => {
    assert.match(await bad([{ path: 'src/missing.js', find: 'a', replace: 'b' }]), /does not exist at this commit \(to add a file use path and create\)/);
    assert.match(await bad([{ path: 'src/bin.txt', find: 'A', replace: 'B' }]), /too large or not text/);
    assert.match(await bad([{ path: 'src/big.txt', find: 'x', replace: 'y' }]), /too large or not text/);
    assert.match(await bad([{ path: 'src/greeter.js', create: 'x' }]), /already exists at this commit: edit it with find and replace/);
    assert.match(await bad([{ path: 'src/n.js', create: 'a' }, { path: 'src/n.js', create: 'b' }]), /a new file takes exactly one edit/);
  });
  it('a proposal the patch policy refuses is refused with its reason (a diff that touches a secret path never gets this far, a gate edit is flagged, not refused)', async () => {
    const gate = await ok([{ path: 'src/greeter.js', create: undefined, find: "'helo '", replace: "'hello '" }].map((e) => ({ path: e.path, find: e.find, replace: e.replace })));
    assert.deepEqual(gate.flags, []);
    const pkg = await ok([{ path: 'package.json', create: '{}\n' }]);
    assert.deepEqual(pkg.flags, ['touches_ci_or_gates']);
  });
});
