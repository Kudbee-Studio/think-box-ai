// The scratch runner: the pure policy (checks, patch review, sandbox arguments and environment, verdict), then the real sandbox against a throwaway fixture repository.
// The sandbox tests skip themselves when bubblewrap cannot be proven on this machine; the policy tests never skip.
import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { CHECK_NAMES, MAX_PATCH_CHARS, OUTPUT_TAIL_BYTES, bwrapArgs, checkCommand, nodeRootOf, parseTestSummary, probeSandbox, reviewPatch, runScratch, sandboxEnv, verdict, type CheckResult } from '../scratch-runner.ts';

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
