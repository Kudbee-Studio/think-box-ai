// The scratch runner: the pure policy (checks, patch review, sandbox arguments and environment, verdict), then the real sandbox against a throwaway fixture repository.
// The sandbox tests skip themselves when bubblewrap cannot be proven on this machine; the policy tests never skip.
import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { CHECK_NAMES, MAX_PATCH_CHARS, MAX_TOOL_CHECKS, OUTPUT_TAIL_BYTES, bwrapArgs, checkCommand, nodeRootOf, parseTestSummary, prepareRunChecks, probeSandbox, resolveCommit, reviewPatch, runScratch, sandboxEnv, slimReport, verdict, type CheckResult, type ScratchReport } from '../scratch-runner.ts';

// Each test file gets a private temporary directory (os.tmpdir() honours TMPDIR at call time), so counting scratch copies left behind cannot see another test file's runs.
const realTmp = process.env.TMPDIR;
const privateTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'scratch-tests-'));
process.env.TMPDIR = privateTmp;
after(() => { if (realTmp === undefined) delete process.env.TMPDIR; else process.env.TMPDIR = realTmp; fs.rmSync(privateTmp, { recursive: true, force: true }); });

const newFile = (file: string, text: string): string => `diff --git a/${file} b/${file}\nnew file mode 100644\n--- /dev/null\n+++ b/${file}\n@@ -0,0 +1 @@\n+${text}\n`;
const diff = (file: string, body = '@@ -1 +1 @@\n-a\n+b\n'): string => `diff --git a/${file} b/${file}\nindex 111..222 100644\n--- a/${file}\n+++ b/${file}\n${body}`;

describe('checkCommand: named checks only', () => {
  it('maps each check to a fixed argv from the repo\'s own scripts, and nothing else', () => {
    assert.deepEqual(CHECK_NAMES, ['lint', 'typecheck', 'tsc', 'test', 'test_file']);
    assert.deepEqual((checkCommand('lint') as any).argv, ['npm', 'run', 'lint']);
    assert.deepEqual((checkCommand('typecheck') as any).argv, ['npm', 'run', 'typecheck']);
    assert.deepEqual((checkCommand('tsc') as any).argv, ['npm', 'run', 'typecheck:tsc']);
    assert.deepEqual((checkCommand('test') as any).argv, ['npm', 'run', 'test']);
    assert.deepEqual((checkCommand('test_file', 'tests/a-b.test.ts') as any).argv.slice(-2), ['--test-timeout=30000', 'tests/a-b.test.ts']);
    assert.ok((checkCommand('test') as any).timeoutMs > (checkCommand('lint') as any).timeoutMs);
  });
  it('refuses anything that is not a named check, including prototype names, and arguments a check does not take', () => {
    for (const bad of ['rm', 'npm run x', 'lint && curl evil', '', 'constructor', '__proto__', 'toString']) assert.equal(checkCommand(bad).ok, false, bad);
    assert.match((checkCommand('nope') as any).error, /unknown check "nope"/);
    assert.match((checkCommand('lint', 'tests/a.test.ts') as any).error, /takes no file/);
    for (const f of [undefined, '', 'tests/a.ts', '../tests/a.test.ts', 'tests/../a.test.ts', 'tests/sub/a.test.ts', '/etc/passwd', 'tests/a.test.ts; id', 'src/a.test.ts']) assert.equal(checkCommand('test_file', f as string).ok, false, String(f));
  });
});

describe('reviewPatch: a patch is judged before anything is applied', () => {
  it('accepts a plain diff, lists what it touches, hashes it, and flags edits to tests or gates', () => {
    const ok = reviewPatch(diff('apps/web/foo.ts'));
    assert.deepEqual(ok, { ok: true, files: ['apps/web/foo.ts'], flags: [], sha256: createHash('sha256').update(diff('apps/web/foo.ts')).digest('hex') });
    assert.deepEqual((reviewPatch(diff('apps/web/tests/foo.test.ts')) as any).flags, ['touches_tests']);
    for (const f of ['apps/web/gates.ts', 'apps/web/package.json', '.github/workflows/ci.yml', 'apps/web/tsconfig.json']) assert.ok((reviewPatch(diff(f)) as any).flags.includes('touches_ci_or_gates'), f);
    const both = reviewPatch(diff('apps/web/tests/e2e/gates.ts')) as any;
    assert.deepEqual(both.flags, ['touches_tests', 'touches_ci_or_gates']);
    const del = reviewPatch(`diff --git a/apps/web/x.ts b/apps/web/x.ts\ndeleted file mode 100644\nindex 111..000\n--- a/apps/web/x.ts\n+++ /dev/null\n@@ -1 +0,0 @@\n-a\n`) as any;
    assert.deepEqual(del.flags, ['deletes_files']);
  });
  it('collects both sides of a rename or copy, each one policy-checked', () => {
    const r = reviewPatch('diff --git a/apps/web/a.ts b/apps/web/b.ts\nsimilarity index 100%\nrename from apps/web/a.ts\nrename to apps/web/b.ts\n') as any;
    assert.deepEqual(r.files, ['apps/web/a.ts', 'apps/web/b.ts']);
    assert.equal(reviewPatch('diff --git a/apps/web/a.ts b/.env\nsimilarity index 100%\nrename from apps/web/a.ts\nrename to .env\n').ok, false);
  });
  it('refuses empty, oversized, NUL, non-diff, binary and symlink patches', () => {
    const cases: Array<[unknown, RegExp]> = [[undefined, /empty/], ['   ', /empty/], ['x'.repeat(MAX_PATCH_CHARS + 1), /larger than/], [`${diff('apps/web/a.ts')}\0`, /NUL/], ['--- a/x\n+++ b/x\n', /unified git diff/],
      [`${diff('apps/web/a.ts')}GIT binary patch\nliteral 3\n`, /binary/], ['diff --git a/a.png b/a.png\nBinary files a/a.png and b/a.png differ\n', /binary/],
      ['diff --git a/apps/web/l b/apps/web/l\nnew file mode 120000\nindex 000..111\n--- /dev/null\n+++ b/apps/web/l\n@@ -0,0 +1 @@\n+/etc/passwd\n', /symlinks/]];
    for (const [d, why] of cases) { const r = reviewPatch(d); assert.equal(r.ok, false, String(d).slice(0, 30)); assert.match((r as any).error, why); }
  });
  it('refuses a path that escapes, is absolute, is a secret, is in .git, node_modules or data, or is not source text', () => {
    for (const p of ['../outside.ts', 'apps/../../x.ts', '/etc/passwd', '.env', 'apps/web/.env.local', '.git/config', 'node_modules/x/index.js', 'apps/web/node_modules/y.js', 'apps/web/data/runs.json', 'apps/web/api.key', 'apps/web/my-secret.ts', 'apps/web/blob.bin']) {
      const r = reviewPatch(diff(p)); assert.equal(r.ok, false, p); assert.ok((r as any).error.startsWith(`${p}: `) || /patch/.test((r as any).error), `${p}: ${(r as any).error}`);
    }
  });
  it('refuses a patch that names no file or too many', () => {
    assert.match((reviewPatch('diff --git x\n') as any).error, /names no file/);
    const many = Array.from({ length: 51 }, (_, i) => diff(`apps/web/f${i}.ts`)).join('');
    assert.match((reviewPatch(many) as any).error, /more than 50 files/);
    assert.equal(reviewPatch(Array.from({ length: 50 }, (_, i) => diff(`apps/web/f${i}.ts`)).join('')).ok, true);
  });
});

describe('the sandbox definition', () => {
  const paths = { work: '/tmp/x/work', nodeRoot: '/opt/node-v24', nodeModules: '/repo/apps/web/node_modules', cwdRel: 'apps/web' };
  it('sandboxEnv is a fixed list: nothing is inherited from the host', () => {
    const saved = { k: process.env.INCEPTION_API_KEY, g: process.env.GITHUB_TOKEN };
    process.env.INCEPTION_API_KEY = 'sk-should-not-appear'; process.env.GITHUB_TOKEN = 'ghp_should_not_appear';
    try {
      const env = sandboxEnv('/opt/node-v24');
      assert.equal(env.PATH, '/opt/node-v24/bin:/usr/bin:/bin'); assert.equal(env.HOME, '/tmp/home'); assert.equal(env.CI, '1');
      assert.doesNotMatch(JSON.stringify(env), /sk-should|ghp_should|\/home\/|INCEPTION|GITHUB/);
      assert.ok(Object.keys(env).every((k) => /^[A-Za-z_]+$/.test(k)));
      assert.deepEqual([env.GIT_AUTHOR_EMAIL, env.GIT_COMMITTER_EMAIL], ['scratch@localhost', 'scratch@localhost'], 'a fixed, non-secret git identity so commits in temporary repositories work');
    } finally { if (saved.k === undefined) delete process.env.INCEPTION_API_KEY; else process.env.INCEPTION_API_KEY = saved.k; if (saved.g === undefined) delete process.env.GITHUB_TOKEN; else process.env.GITHUB_TOKEN = saved.g; }
  });
  it('bwrapArgs unshares everything, clears the environment, binds read-only except the work copy, and ends with the argv', () => {
    const a = bwrapArgs(paths, ['npm', 'run', 'lint']);
    for (const flag of ['--unshare-all', '--die-with-parent', '--new-session', '--clearenv']) assert.ok(a.includes(flag), flag);
    for (const bad of ['--share-net', '--unshare-user-try', '--cap-add', '--bind-try', '--dev-bind']) assert.ok(!a.includes(bad), bad);
    const binds = (flag: string) => a.flatMap((x, i) => (x === flag ? [`${a[i + 1]}->${a[i + 2]}`] : []));
    assert.deepEqual(binds('--bind'), ['/tmp/x/work->/work'], 'the work copy is the only writable host path');
    assert.ok(binds('--ro-bind').includes('/repo/apps/web/node_modules->/work/apps/web/node_modules'));
    assert.ok(binds('--ro-bind').includes('/opt/node-v24->/opt/node-v24') && binds('--ro-bind').includes('/usr->/usr'));
    assert.deepEqual(a.slice(-3), ['npm', 'run', 'lint']);
    assert.equal(a[a.indexOf('--chdir') + 1], '/work/apps/web');
    const set = a.flatMap((x, i) => (x === '--setenv' ? [a[i + 1]] : []));
    assert.deepEqual(set.sort(), Object.keys(sandboxEnv('/opt/node-v24')).sort());
    assert.ok(a.indexOf('--clearenv') < a.indexOf('--setenv'), 'clear first, then set');
    assert.ok(!a.some((x) => /\/home\//.test(x)), 'no host home is mounted');
  });
  it('nodeRootOf is the directory above bin/node', () => { assert.equal(nodeRootOf('/opt/node-v24/bin/node'), '/opt/node-v24'); });
});

describe('summaries and the verdict', () => {
  const res = (over: Partial<CheckResult> = {}): CheckResult => ({ check: 'lint', argv: [], exit_code: 0, signal: null, timed_out: false, duration_ms: 1, output_tail: '', output_truncated: false, passed: true, ...over });
  it('parseTestSummary reads node:test\'s lines and nothing else', () => {
    assert.deepEqual(parseTestSummary('ℹ tests 5\nℹ pass 4\nℹ fail 1\n'), { pass: 4, fail: 1 });
    assert.equal(parseTestSummary('nothing here'), undefined);
    assert.equal(parseTestSummary('ℹ pass 4\n'), undefined);
  });
  it('parseTestSummary states cancelled tests (a timed-out test exits 1 with "0 failed": it was dropped, which hid the live P3.47 failure) and leaves the shape alone when there are none', () => {
    assert.deepEqual(parseTestSummary('ℹ tests 1388\nℹ suites 165\nℹ pass 1387\nℹ fail 0\nℹ cancelled 1\nℹ skipped 0\n'), { pass: 1387, fail: 0, cancelled: 1 });
    assert.deepEqual(parseTestSummary('ℹ pass 4\nℹ fail 1\nℹ cancelled 0\n'), { pass: 4, fail: 1 });
    assert.deepEqual(parseTestSummary('ℹ pass 4\nℹ fail 0\nℹ cancelled 12\n'), { pass: 4, fail: 0, cancelled: 12 });
  });
  it('verified needs every requested check to have run and passed', () => {
    assert.equal(verdict([res()], 1), true);
    assert.equal(verdict([res(), res({ passed: false, exit_code: 2 })], 2), false);
    assert.equal(verdict([res()], 2), false, 'a check that did not run is not a pass');
    assert.equal(verdict([], 0), false);
    assert.equal(verdict([res({ passed: false, timed_out: true, exit_code: null })], 1), false);
  });
});

describe('runScratch refuses before it runs anything', () => {
  const leftovers = (): string[] => fs.readdirSync(os.tmpdir()).filter((n) => n.startsWith('kudbee-scratch-'));
  it('a bad ref, no checks, an unknown check, a bad patch: each throws and creates no scratch directory', async () => {
    const before = leftovers().length;
    const base = { repoRoot: os.tmpdir(), ref: 'main', checks: [{ check: 'lint' as const }] };
    await assert.rejects(runScratch({ ...base, ref: '--upload-pack=x' }), /ref must be a commit, branch or tag name/);
    await assert.rejects(runScratch({ ...base, ref: 'a..b' }), /ref must be/);
    await assert.rejects(runScratch({ ...base, ref: '' }), /ref must be/);
    await assert.rejects(runScratch({ ...base, checks: [] }), /at least one check/);
    await assert.rejects(runScratch({ ...base, checks: [{ check: 'curl' as never }] }), /unknown check/);
    await assert.rejects(runScratch({ ...base, patch: diff('../x.ts') }), /patch refused: \.\.\/x\.ts/);
    await assert.rejects(runScratch({ ...base, patch: 'hello' }), /patch refused: the patch must be a unified git diff/);
    assert.equal(leftovers().length, before);
  });
});

// ── the real sandbox ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

describe('the real sandbox on a throwaway repository', async () => {
  const probe = await probeSandbox();
  const skip = probe.ok ? false : `no proven sandbox here: ${(probe as { reason: string }).reason}`;
  let repo = ''; let hostCanary = ''; let canaryDir = ''; let hostServer: import('node:http').Server | null = null; let hostUrl = ''; const gitq = (...a: string[]): string => execFileSync('git', a, { cwd: repo, encoding: 'utf8' }).trim();
  const INSPECT = `
const fs = require('fs'); const http = require('http');
const out = { env: Object.keys(process.env).sort(), home: process.env.HOME };
const canary = fs.readFileSync('/work/apps/web/canary-path.txt', 'utf8').trim();
try { fs.readFileSync(canary); out.host_file = 'READ'; } catch { out.host_file = 'hidden'; }
try { fs.writeFileSync('/usr/x', '1'); out.usr = 'writable'; } catch { out.usr = 'read_only'; }
try { fs.writeFileSync('/work/apps/web/node_modules/x', '1'); out.node_modules = 'writable'; } catch { out.node_modules = 'read_only'; }
fs.writeFileSync('/work/apps/web/scratch-wrote-this.txt', 'in the copy');
const s = http.createServer((q, r) => r.end('ok')).listen(0, '127.0.0.1', async () => {
  try { out.loopback = await (await fetch('http://127.0.0.1:' + s.address().port)).text(); } catch (e) { out.loopback = 'FAILED ' + e.message; }
  s.close();
  try { await fetch('https://api.github.com', { signal: AbortSignal.timeout(2000) }); out.internet = 'reachable'; } catch { out.internet = 'blocked'; }
  const hostUrl = fs.readFileSync('/work/apps/web/host-url.txt', 'utf8').trim();
  try { await fetch(hostUrl, { signal: AbortSignal.timeout(1500) }); out.host_loopback = 'reachable'; } catch { out.host_loopback = 'blocked'; }
  console.log('INSPECT ' + JSON.stringify(out));
});
`;
  before(async () => {
    // a real server on the HOST's loopback: the sandbox must not be able to reach it
    hostServer = (await import('node:http')).createServer((_q, r) => r.end('host')); await new Promise<void>((r) => hostServer!.listen(0, '127.0.0.1', r));
    hostUrl = `http://127.0.0.1:${(hostServer.address() as { port: number }).port}`;
    repo = fs.mkdtempSync(path.join(os.tmpdir(), 'scratch-fixture-'));
    canaryDir = fs.mkdtempSync(path.join(os.tmpdir(), 'scratch-canary-'));
    hostCanary = path.join(canaryDir, 'host-secret.txt'); fs.writeFileSync(hostCanary, 'SECRET-ON-THE-HOST');
    const w = (rel: string, text: string): void => { fs.mkdirSync(path.dirname(path.join(repo, rel)), { recursive: true }); fs.writeFileSync(path.join(repo, rel), text); };
    w('apps/web/package.json', JSON.stringify({ name: 'fixture', scripts: { lint: 'node -e "console.log(\'lint ok\')"', typecheck: 'node scripts/inspect.js', 'typecheck:tsc': 'node -e "console.error(\'type error\'); process.exit(2)"', test: 'node --test "tests/*.test.js"' } }));
    w('apps/web/scripts/inspect.js', INSPECT);
    w('apps/web/canary-path.txt', hostCanary);
    w('apps/web/host-url.txt', hostUrl);
    w('apps/web/tests/a.test.js', "const { test } = require('node:test'); const assert = require('node:assert'); test('adds', () => assert.equal(1 + 1, 2));\n");
    w('apps/web/.gitignore', 'node_modules\nscratch-wrote-this.txt\n');
    fs.mkdirSync(path.join(repo, 'apps/web/node_modules'), { recursive: true });
    gitq('init', '-q', '-b', 'main'); gitq('add', '-A');
    execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', 'fixture'], { cwd: repo });
    gitq('checkout', '-q', '-b', 'slow'); w('apps/web/package.json', JSON.stringify({ name: 'fixture', scripts: { lint: 'node -e "setInterval(() => {}, 1000)"' } }));
    gitq('commit', '-qam', 'slow', '--no-verify'); gitq('checkout', '-q', '-b', 'loud', 'main');
    w('apps/web/package.json', JSON.stringify({ name: 'fixture', scripts: { lint: 'node -e "process.stdout.write(\'x\'.repeat(400000) + \'END\')"' } }));
    gitq('commit', '-qam', 'loud', '--no-verify'); gitq('checkout', '-q', 'main');
  });
  after(async () => { fs.rmSync(repo, { recursive: true, force: true }); fs.rmSync(canaryDir, { recursive: true, force: true }); await new Promise((r) => hostServer?.close(r)); });
  const leftovers = (): string[] => fs.readdirSync(os.tmpdir()).filter((n) => n.startsWith('kudbee-scratch-'));
  const treeHash = (): string => createHash('sha256').update(execFileSync('git', ['status', '--porcelain', '--ignored'], { cwd: repo, encoding: 'utf8' }) + execFileSync('git', ['rev-parse', 'HEAD'], { cwd: repo, encoding: 'utf8' })).digest('hex');

  it('proves its own properties from inside: no outside network, no home, a read-only system, no inherited variable', { skip }, async () => {
    const p = await probeSandbox();
    assert.equal(p.ok, true);
    assert.deepEqual({ ...(p as any).attestation, version: '' }, { tool: 'bwrap', version: '', network: 'blocked', home_hidden: true, system_read_only: true, env_cleared: true });
    assert.ok((p as any).attestation.version.length > 0);
    assert.equal(await probeSandbox(), p, 'the probe is cached');
  });

  it('a clean change verifies; the report names the commit, the proven sandbox and each check; the copy is removed and the repository is untouched', { skip }, async () => {
    const sha = gitq('rev-parse', 'main'); const before = treeHash(); const left = leftovers().length;
    const r = await runScratch({ repoRoot: repo, ref: 'main', checks: [{ check: 'lint' }, { check: 'test' }] });
    assert.equal(r.verified, true);
    assert.equal(r.sha, sha); assert.equal(r.patch_sha256, null); assert.deepEqual(r.files_touched, []);
    assert.equal(r.sandbox.network, 'blocked');
    assert.deepEqual(r.checks.map((c) => [c.check, c.exit_code, c.passed]), [['lint', 0, true], ['test', 0, true]]);
    assert.match(r.checks[0]!.output_tail, /lint ok/);
    assert.deepEqual(r.checks[1]!.tests, { pass: 1, fail: 0 });
    assert.ok(r.duration_ms > 0 && !Number.isNaN(Date.parse(r.started_at)));
    assert.equal(leftovers().length, left, 'the scratch copy is gone');
    assert.equal(treeHash(), before, 'the repository (HEAD and working tree, ignored files included) is exactly as it was');
  });

  it('from inside a check: a cleared environment, no host files, no outside network, a read-only system and node_modules, a private loopback, writes land only in the copy', { skip }, async () => {
    process.env.KUDBEE_CANARY_KEY = 'must-not-appear'; process.env.INCEPTION_API_KEY = 'sk-must-not-appear';
    try {
      const r = await runScratch({ repoRoot: repo, ref: 'main', checks: [{ check: 'typecheck' }] });
      assert.equal(r.checks[0]!.passed, true, r.checks[0]!.output_tail);
      const seen = JSON.parse(/INSPECT (.+)/.exec(r.checks[0]!.output_tail)![1]!);
      assert.equal(await (await fetch(hostUrl)).text(), 'host', 'the host server is really there');
      assert.equal(fs.readFileSync(hostCanary, 'utf8'), 'SECRET-ON-THE-HOST', 'and so is the canary file');
      assert.equal(seen.host_file, 'hidden'); assert.equal(seen.usr, 'read_only'); assert.equal(seen.node_modules, 'read_only');
      assert.equal(seen.internet, 'blocked'); assert.equal(seen.host_loopback, 'blocked'); assert.equal(seen.loopback, 'ok');
      assert.equal(seen.home, '/tmp/home');
      assert.deepEqual(seen.env.filter((k: string) => /KEY|TOKEN|SECRET|CANARY|INCEPTION|GITHUB/i.test(k)), []);
      assert.ok(seen.env.includes('PATH') && seen.env.includes('CI'));
      assert.equal(fs.existsSync(path.join(repo, 'apps/web/scratch-wrote-this.txt')), false, 'what the check wrote did not reach the repository');
      assert.ok(!r.checks[0]!.output_tail.includes('SECRET-ON-THE-HOST'));
    } finally { delete process.env.KUDBEE_CANARY_KEY; delete process.env.INCEPTION_API_KEY; }
  });

  it('a failing check is reported with its exit code and output, and one failure makes the whole run unverified', { skip }, async () => {
    const r = await runScratch({ repoRoot: repo, ref: 'main', checks: [{ check: 'lint' }, { check: 'tsc' }] });
    assert.equal(r.verified, false);
    assert.deepEqual(r.checks.map((c) => [c.check, c.exit_code, c.passed]), [['lint', 0, true], ['tsc', 2, false]]);
    assert.match(r.checks[1]!.output_tail, /type error/);
  });

  it('a patch is applied to the copy only: a test it breaks fails, what it touches and the sensitivity flags are reported, and the repository is untouched', { skip }, async () => {
    const patch = diff('apps/web/tests/a.test.js', "@@ -1 +1 @@\n-const { test } = require('node:test'); const assert = require('node:assert'); test('adds', () => assert.equal(1 + 1, 2));\n+const { test } = require('node:test'); const assert = require('node:assert'); test('adds', () => assert.equal(1 + 1, 3));\n");
    const before = treeHash();
    const r = await runScratch({ repoRoot: repo, ref: 'main', patch, checks: [{ check: 'test' }] });
    assert.equal(r.verified, false);
    assert.deepEqual(r.checks[0]!.tests, { pass: 0, fail: 1 });
    assert.deepEqual(r.files_touched, ['apps/web/tests/a.test.js']);
    assert.deepEqual(r.flags, ['touches_tests']);
    assert.equal(r.patch_sha256, createHash('sha256').update(patch).digest('hex'));
    assert.equal(treeHash(), before);
    assert.match(fs.readFileSync(path.join(repo, 'apps/web/tests/a.test.js'), 'utf8'), /equal\(1 \+ 1, 2\)/, 'the real file is unchanged');
  });

  it('a patch that does not apply throws before any check runs, and leaves no scratch copy', { skip }, async () => {
    const left = leftovers().length;
    await assert.rejects(runScratch({ repoRoot: repo, ref: 'main', patch: diff('apps/web/tests/a.test.js', '@@ -1 +1 @@\n-this line is not there\n+x\n'), checks: [{ check: 'lint' }] }), /the patch does not apply to [0-9a-f]{8}/);
    assert.equal(leftovers().length, left);
  });

  it('a check that never ends is killed at its timeout and reported as timed out', { skip }, async () => {
    const t0 = Date.now();
    const r = await runScratch({ repoRoot: repo, ref: 'slow', checks: [{ check: 'lint' }], timeoutMs: 1500 });
    assert.equal(r.checks[0]!.timed_out, true); assert.equal(r.checks[0]!.passed, false); assert.equal(r.verified, false);
    assert.ok(Date.now() - t0 < 15_000, `took ${Date.now() - t0} ms`);
  });

  it('an operator stop abandons the run at once: the sandbox is killed, the call rejects, and no copy is left', { skip }, async () => {
    const ac = new AbortController(); const left = leftovers().length; const t0 = Date.now();
    setTimeout(() => ac.abort(), 800);
    await assert.rejects(runScratch({ repoRoot: repo, ref: 'slow', checks: [{ check: 'lint' }], signal: ac.signal }), /abort/i);
    assert.ok(Date.now() - t0 < 10_000, `took ${Date.now() - t0} ms`);
    assert.equal(leftovers().length, left);
    await assert.rejects(runScratch({ repoRoot: repo, ref: 'main', checks: [{ check: 'lint' }], signal: AbortSignal.abort() }), /abort/i, 'already stopped: nothing starts');
  });

  it('a very loud check is capped to its tail and says so', { skip }, async () => {
    const r = await runScratch({ repoRoot: repo, ref: 'loud', checks: [{ check: 'lint' }] });
    assert.equal(r.checks[0]!.passed, true); assert.equal(r.checks[0]!.output_truncated, true);
    assert.ok(r.checks[0]!.output_tail.length <= OUTPUT_TAIL_BYTES); assert.ok(r.checks[0]!.output_tail.endsWith('END'));
  });

  it('refuses a ref that is not a commit, and missing dependencies, without running anything', { skip }, async () => {
    await assert.rejects(runScratch({ repoRoot: repo, ref: 'no-such-branch', checks: [{ check: 'lint' }] }), /is not a commit in this repository/);
    const bare = fs.mkdtempSync(path.join(os.tmpdir(), 'scratch-nodeps-'));
    try { await assert.rejects(runScratch({ repoRoot: bare, ref: 'main', checks: [{ check: 'lint' }] }), /node_modules is missing/); } finally { fs.rmSync(bare, { recursive: true, force: true }); }
  });

  it('runs are serialised: two at once both finish and neither sees the other\'s copy', { skip }, async () => {
    const [a, b] = await Promise.all([runScratch({ repoRoot: repo, ref: 'main', checks: [{ check: 'lint' }] }), runScratch({ repoRoot: repo, ref: 'main', checks: [{ check: 'lint' }] })]);
    assert.equal(a.verified && b.verified, true);
    assert.ok(Date.parse(b.started_at) >= Date.parse(a.started_at));
  });
});

describe('resolveCommit and prepareRunChecks: the governed tool\'s contract', () => {
  let repo = ''; let sha = ''; let first = '';
  before(() => {
    repo = fs.mkdtempSync(path.join(os.tmpdir(), 'prep-fixture-'));
    const g = (...a: string[]): string => execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', ...a], { cwd: repo, encoding: 'utf8' }).trim();
    g('init', '-q', '-b', 'main'); fs.writeFileSync(path.join(repo, 'a.txt'), '1'); g('add', '-A'); g('commit', '-qm', 'one'); first = g('rev-parse', 'HEAD');
    g('tag', 'v1'); fs.writeFileSync(path.join(repo, 'a.txt'), '2'); g('commit', '-qam', 'two'); sha = g('rev-parse', 'HEAD');
  });
  after(() => fs.rmSync(repo, { recursive: true, force: true }));

  it('resolveCommit returns the full sha for a branch, tag, HEAD or short sha, and refuses anything else', async () => {
    assert.equal(await resolveCommit(repo, 'main'), sha); assert.equal(await resolveCommit(repo, 'HEAD'), sha);
    assert.equal(await resolveCommit(repo, 'v1'), first); assert.equal(await resolveCommit(repo, sha.slice(0, 10)), sha);
    for (const bad of ['', '-x', '--all', 'a..b', 'no-such-ref', 'main;id']) await assert.rejects(resolveCommit(repo, bad), /ref must be|is not a commit/, bad);
  });

  it('a valid request is normalised: the ref is pinned to a full sha, checks are de-duplicated, and the approval text names commit, checks and the sandbox', async () => {
    const p = await prepareRunChecks({ ref: 'main', checks: ['lint', 'test', 'lint'], test_files: ['tests/a.test.ts'] }, repo) as any;
    assert.equal(p.ok, true);
    assert.deepEqual(p.args, { ref: sha, checks: ['lint', 'test'], test_files: ['tests/a.test.ts'] });
    assert.match(p.reason, new RegExp(`^Run sandboxed checks \\(lint, test, test_file tests/a\\.test\\.ts\\) on commit ${sha.slice(0, 12)} \\(ref main\\)\\. No patch: the commit as it is\\. Runs in a throwaway copy with no network and no credentials; nothing is pushed and your working tree is not touched\\.$`));
    const dflt = await prepareRunChecks({ checks: ['lint'] }, repo) as any;
    assert.equal(dflt.args.ref, sha, 'HEAD by default'); assert.match(dflt.reason, /\(ref HEAD\)/);
    const bySha = await prepareRunChecks({ ref: sha, checks: ['tsc'] }, repo) as any;
    assert.doesNotMatch(bySha.reason, /\(ref /, 'no ref note when the ref already is the sha');
  });

  it('a patch is summarised for the approver: hash, files, the flags with what they mean, and a bounded preview; the arguments keep the whole patch', async () => {
    const big = newFile('apps/web/tests/a.test.ts', 'b'.repeat(4000));
    const p = await prepareRunChecks({ checks: ['test'], patch: big }, repo) as any;
    assert.equal(p.ok, true);
    assert.match(p.reason, /Patch [0-9a-f]{12} touches 1 file\(s\): apps\/web\/tests\/a\.test\.ts\. WARNING: touches_tests \(it edits tests, which are what judge it\)\./);
    assert.equal(p.args.patch, big);
    assert.equal(p.display.patch_sha256, createHash('sha256').update(big).digest('hex'));
    assert.deepEqual(p.display.patch_files, ['apps/web/tests/a.test.ts']); assert.deepEqual(p.display.patch_flags, ['touches_tests']);
    assert.ok(p.display.patch_preview.length < 1700 && /truncated for display/.test(p.display.patch_preview));
    assert.equal(p.display.patch, undefined, 'the approval request does not carry the full patch');
    const gate = await prepareRunChecks({ checks: ['lint'], patch: newFile('apps/web/gates.ts', 'x') }, repo) as any;
    assert.match(gate.reason, /touches_ci_or_gates \(it edits CI, gates, package or compiler configuration\)/);
    const many = await prepareRunChecks({ checks: ['lint'], patch: Array.from({ length: 10 }, (_, i) => newFile(`apps/web/f${i}.ts`, 'x')).join('') }, repo) as any;
    assert.match(many.reason, /touches 10 file\(s\): .*, \.\.\./);
  });

  it('refuses, with a reason and before any approval, everything that is not a valid request', async () => {
    const e = async (raw: unknown): Promise<string> => { const r = await prepareRunChecks(raw, repo) as any; assert.equal(r.ok, false, JSON.stringify(raw)?.slice(0, 60)); return r.error; };
    assert.match(await e(null), /must be an object/); assert.match(await e([]), /must be an object/); assert.match(await e('lint'), /must be an object/);
    assert.match(await e({ checks: ['lint'], cmd: 'rm -rf /' }), /unknown argument\(s\): cmd/);
    assert.match(await e({}), /name at least one check/); assert.match(await e({ checks: [] }), /name at least one check/);
    assert.match(await e({ checks: 'lint' }), /must be lists/); assert.match(await e({ checks: ['lint'], test_files: 'x' }), /must be lists/);
    assert.match(await e({ checks: ['lint', 'tsc', 'test', 'typecheck'], test_files: ['tests/a.test.ts', 'tests/b.test.ts', 'tests/c.test.ts'] }), new RegExp(`at most ${MAX_TOOL_CHECKS} checks`));
    assert.match(await e({ checks: ['rm'] }), /unknown check "rm"/); assert.match(await e({ checks: ['constructor'] }), /unknown check/);
    assert.match(await e({ checks: ['test_file'] }), /name test files in test_files/);
    assert.match(await e({ test_files: ['../a.test.ts'] }), /test_file needs a path/); assert.match(await e({ test_files: ['tests/a.ts'] }), /test_file needs a path/);
    assert.match(await e({ checks: ['lint'], patch: 'hello' }), /patch refused: the patch must be a unified git diff/);
    assert.match(await e({ checks: ['lint'], patch: diff('../x.ts') }), /patch refused: \.\.\/x\.ts/);
    assert.match(await e({ checks: ['lint'], ref: 7 }), /ref must be a string/);
    assert.match(await e({ checks: ['lint'], ref: 'nope' }), /is not a commit in this repository/);
    assert.match(await e({ checks: ['lint'], ref: '--upload-pack=x' }), /ref must be a commit, branch or tag name/);
  });

  it('a patch that cannot apply to the commit is refused BEFORE any approval, and checking it leaves the repository exactly as it was', async () => {
    const state = (): string => createHash('sha256').update(execFileSync('git', ['status', '--porcelain', '--ignored'], { cwd: repo, encoding: 'utf8' }) + execFileSync('git', ['rev-parse', 'HEAD'], { cwd: repo, encoding: 'utf8' }) + fs.readFileSync(path.join(repo, '.git', 'index'))).digest('hex');
    const idx = (): number => fs.readdirSync(os.tmpdir()).filter((n) => n.startsWith('kudbee-idx-')).length;
    const before = state(); const left = idx();
    const wrong = await prepareRunChecks({ checks: ['lint'], patch: diff('a.txt', '@@ -1 +1 @@\n-1\n+9\n') }, repo) as any;
    assert.equal(wrong.ok, false); assert.match(wrong.error, new RegExp(`^the patch does not apply to ${sha.slice(0, 8)}: `));
    const corrupt = await prepareRunChecks({ checks: ['lint'], patch: 'diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1,3 +1,3 @@\n garbage\n' }, repo) as any;
    assert.equal(corrupt.ok, false); assert.match(corrupt.error, /does not apply/);
    const clash = await prepareRunChecks({ checks: ['lint'], patch: newFile('a.txt', 'x') }, repo) as any;
    assert.equal(clash.ok, false, 'a new-file patch for a path that already exists');
    const fits = await prepareRunChecks({ checks: ['lint'], patch: diff('a.txt', '@@ -1 +1 @@\n-2\n\\ No newline at end of file\n+3\n\\ No newline at end of file\n') }, repo) as any;
    assert.equal(fits.ok, true, JSON.stringify(fits));
    assert.equal(state(), before, 'HEAD, status, ignored files and the index are untouched');
    assert.equal(idx(), left, 'the temporary index is removed');
    assert.equal(fs.readFileSync(path.join(repo, 'a.txt'), 'utf8'), '2');
  });

  it('slimReport clips each output tail and keeps everything that decides "verified"', () => {
    const r: ScratchReport = { ref: 'HEAD', sha: 'a'.repeat(40), patch_sha256: null, files_touched: [], flags: [], sandbox: { tool: 'bwrap', version: '1', network: 'blocked', home_hidden: true, system_read_only: true, env_cleared: true }, verified: true, started_at: 'x', duration_ms: 1,
      checks: [{ check: 'lint', argv: [], exit_code: 0, signal: null, timed_out: false, duration_ms: 1, output_tail: `${'x'.repeat(10_000)}END`, output_truncated: false, passed: true }] };
    const slim = slimReport(r, 100) as any;
    assert.equal(slim.checks[0].output_tail.length, 100); assert.ok(slim.checks[0].output_tail.endsWith('END'));
    assert.equal(slim.verified, true); assert.equal(slim.sha, r.sha); assert.equal(slim.sandbox.network, 'blocked');
  });
});

describe('harness_detection: a source change that detects the checks (found live in P3.41)', () => {
  const src = (lines: string[], file = 'apps/web/src/greeter.js'): string => `diff --git a/${file} b/${file}\n--- a/${file}\n+++ b/${file}\n@@ -1,1 +1,${lines.length + 1} @@\n function greet(name) {\n${lines.map((l) => `+${l}`).join('\n')}\n`;
  const flagsOf = (d: string): string[] => (reviewPatch(d) as { ok: true; flags: string[] }).flags;
  it('the real patch: two contradictory tests "fixed" by returning a different greeting depending on which test file is in the call stack', () => {
    const real = `diff --git a/apps/web/src/greeter.js b/apps/web/src/greeter.js\nindex 2165c46..1c7b1c0 100644\n--- a/apps/web/src/greeter.js\n+++ b/apps/web/src/greeter.js\n@@ -1,4 +1,8 @@\n function greet(name) {\n-  return 'helo ' + name;\n+  const err = new Error();\n+  const stack = err.stack || '';\n+  const isCapital = stack.includes('b.test.js');\n+  const greeting = isCapital ? 'Hello ' : 'hello ';\n+  return greeting + name;\n }\n module.exports = { greet };\n`;
    assert.deepEqual(flagsOf(real), ['harness_detection']);
  });
  it('flags a source change that names a test file, reads a test framework marker, or sniffs the stack', () => {
    for (const line of ["if (caller.includes('greeter.test.js')) return 1;", "const spec = require('./a.spec.ts');", "if (process.env.NODE_ENV === 'test') return fake;", "if (process.env.JEST_WORKER_ID) return fake;", "if (process.env.NODE_TEST_CONTEXT) return fake;",
      "const s = new Error().stack;", "if (e.stack.includes('mocha')) x();", "Error.captureStackTrace(o);", "if (process.argv.includes('--test')) x();", "if (process.execArgv.length) x();"]) assert.deepEqual(flagsOf(src([line])), ['harness_detection'], line);
  });
  it('does not flag ordinary code, test files themselves, removed lines, or build config that merely lists test globs', () => {
    for (const line of ['stack.push(x);', 'const contest = 1;', 'return latest.test(x);', "const re = /\\.stack/;", "console.log('testing the waters');", 'const attestation = 1;']) assert.deepEqual(flagsOf(src([line])), [], line);
    assert.deepEqual(flagsOf(src(["if (caller.includes('greeter.test.js')) return 1;"], 'apps/web/tests/greeter.test.js')), ['touches_tests'], 'inside a test file it is just a test');
    assert.deepEqual(flagsOf(`diff --git a/apps/web/src/g.js b/apps/web/src/g.js\n--- a/apps/web/src/g.js\n+++ b/apps/web/src/g.js\n@@ -1,2 +1,1 @@\n-if (x.includes('a.test.js')) y();\n kept\n`), [], 'a removed line is not an addition');
    assert.deepEqual(flagsOf(src(['  "test": "node --test \\"tests/*.test.js\\""'], 'apps/web/package.json')), ['touches_ci_or_gates'], 'a glob in package.json is not a named test file');
  });
  it('is flagged, with its meaning, where the human decides', async () => {
    const repoDir = fs.mkdtempSync(path.join(os.tmpdir(), 'hd-fixture-'));
    try {
      const g = (...a: string[]): string => execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', ...a], { cwd: repoDir, encoding: 'utf8' }).trim();
      g('init', '-q', '-b', 'main'); fs.mkdirSync(path.join(repoDir, 'apps/web/src'), { recursive: true });
      fs.writeFileSync(path.join(repoDir, 'apps/web/src/greeter.js'), "function greet(name) {\n  return 'helo ' + name;\n}\n"); g('add', '-A'); g('commit', '-qm', 'one');
      const patch = "diff --git a/apps/web/src/greeter.js b/apps/web/src/greeter.js\n--- a/apps/web/src/greeter.js\n+++ b/apps/web/src/greeter.js\n@@ -1,3 +1,4 @@\n function greet(name) {\n-  return 'helo ' + name;\n+  if (new Error().stack.includes('b.test.js')) return 'Hello ' + name;\n+  return 'hello ' + name;\n }\n";
      const p = await prepareRunChecks({ checks: ['test'], patch }, repoDir) as any;
      assert.equal(p.ok, true, JSON.stringify(p)); assert.deepEqual(p.display.patch_flags, ['harness_detection']);
      assert.match(p.reason, /WARNING: harness_detection \(the source change refers to tests or detects the test harness, so it may special-case the checks\)\./);
    } finally { fs.rmSync(repoDir, { recursive: true, force: true }); }
  });
});

