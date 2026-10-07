// The sandbox runs the repository's own checks for repositories that are not shaped like ours: an npm project at the ROOT, with or without dependencies, defining only some of
// the named scripts. The planner offers only the checks that exist, so what a human approves is what runs. The sandbox tests skip when bubblewrap cannot be proven here.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, describe, it } from 'node:test';
import { planConvoy, type PlanInput } from '../mayor.ts';
import { definedChecks, probeSandbox, projectOf, runScratch } from '../scratch-runner.ts';

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'scratch-generic-'));
after(() => fs.rmSync(tmp, { recursive: true, force: true }));
const git = (cwd: string, ...a: string[]): string => execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', ...a], { cwd, encoding: 'utf8' }).trim();
function repo(name: string, files: Record<string, string>): { dir: string; sha: string } {
  const dir = path.join(tmp, name);
  for (const [f, c] of Object.entries(files)) { fs.mkdirSync(path.dirname(path.join(dir, f)), { recursive: true }); fs.writeFileSync(path.join(dir, f), c); }
  git(dir, 'init', '-q', '-b', 'main'); git(dir, 'add', '-A'); git(dir, 'commit', '-qm', 'one');
  return { dir, sha: git(dir, 'rev-parse', 'HEAD') };
}
const SRC = 'function add(a, b) {\n  return a - b;\n}\nmodule.exports = { add };\n';
const TEST = "const { test } = require('node:test'); const assert = require('node:assert');\nconst { add } = require('../src/add.js');\ntest('add', () => { assert.equal(add(2, 3), 5); });\n";
const FIX = 'diff --git a/src/add.js b/src/add.js\n--- a/src/add.js\n+++ b/src/add.js\n@@ -1,3 +1,3 @@\n function add(a, b) {\n-  return a - b;\n+  return a + b;\n }\n';

describe('which project and which checks', () => {
  it('finds the npm project at the root or in apps/web, its scripts and whether it declares dependencies', () => {
    const root = repo('root-proj', { 'package.json': JSON.stringify({ scripts: { test: 'node --test tests/*.test.js', lint: 'x' }, devDependencies: { left: '1' } }) });
    assert.deepEqual(projectOf(root.dir), { cwdRel: '.', scripts: ['test', 'lint'], hasDeps: true });
    const web = repo('web-proj', { 'apps/web/package.json': JSON.stringify({ scripts: { test: 't', typecheck: 'x', 'typecheck:tsc': 'y', lint: 'z' } }), 'package.json': '{}' });
    assert.deepEqual(projectOf(web.dir), { cwdRel: 'apps/web', scripts: ['test', 'typecheck', 'typecheck:tsc', 'lint'], hasDeps: false }, 'apps/web wins, as in this repository');
    assert.equal(projectOf(path.join(tmp, 'nope')), null);
    const none = repo('no-pkg', { 'a.txt': 'x' }); assert.equal(projectOf(none.dir), null);
  });
  it('definedChecks lists only the named checks whose npm script exists (tsc is the script typecheck:tsc)', () => {
    assert.deepEqual(definedChecks(path.join(tmp, 'root-proj')), ['lint', 'test']);
    assert.deepEqual(definedChecks(path.join(tmp, 'web-proj')), ['lint', 'typecheck', 'tsc', 'test']);
    assert.deepEqual(definedChecks(path.join(tmp, 'no-pkg')), []);
  });
});

const input = (over: Partial<PlanInput> = {}): PlanInput => ({ goal: 'Fix it', mode: 'simulate', lookupModel: null, agentModel: 'mercury-2', isLocalModel: () => false, availableTools: ['repo_search', 'repo_read', 'propose_change', 'run_checks'], costOf: () => ({ usd: null, basis: 'none' }), now: 1, ...over });
describe('the SIMULATE plan offers the checks the repository has', () => {
  it('uses the repository\'s checks, and this project\'s four when none are given', () => {
    const p = planConvoy(input({ repoChecks: ['test'] })); assert.ok(p.ok); assert.deepEqual(p.plan.simulation?.checks, ['test']);
    assert.match(p.plan.workers.find((w) => w.id === 'checks-1')!.purpose, /\(test\)/);
    const d = planConvoy(input()); assert.ok(d.ok); assert.deepEqual(d.plan.simulation?.checks, ['lint', 'typecheck', 'tsc', 'test']);
  });
  it('is blocked with a plain reason when the repository defines no check', () => {
    const p = planConvoy(input({ repoChecks: [] }));
    assert.ok(p.ok); assert.ok(p.plan.blocked_reasons.some((b) => /defines no check the sandbox can run/.test(b)), JSON.stringify(p.plan.blocked_reasons));
  });
});

const probe = await probeSandbox();
const skip = probe.ok ? false : `no proven sandbox here: ${(probe as { reason: string }).reason}`;
describe('the sandbox on a repository with an npm project at its root', () => {
  it('runs the test check on a zero-dependency root project: the seeded bug fails, the patched copy passes', { skip }, async () => {
    const r = repo('zero-dep', { 'package.json': JSON.stringify({ scripts: { test: 'node --test tests/*.test.js' } }), 'src/add.js': SRC, 'tests/add.test.js': TEST });
    const before = await runScratch({ repoRoot: r.dir, ref: r.sha, checks: [{ check: 'test' }] });
    assert.equal(before.verified, false); assert.equal(before.checks[0]!.passed, false);
    const after = await runScratch({ repoRoot: r.dir, ref: r.sha, patch: FIX, checks: [{ check: 'test' }] });
    assert.equal(after.verified, true); assert.deepEqual(after.files_touched, ['src/add.js']); assert.equal(after.checks[0]!.tests?.pass, 1);
    assert.equal(git(r.dir, 'status', '--porcelain'), '', 'the repository itself is untouched');
  });
  it('refuses, saying why, a project that declares dependencies but has none installed (the sandbox has no network)', { skip }, async () => {
    const r = repo('needs-deps', { 'package.json': JSON.stringify({ scripts: { test: 'node --test tests/*.test.js' }, dependencies: { left: '1.0.0' } }), 'src/add.js': SRC, 'tests/add.test.js': TEST });
    await assert.rejects(runScratch({ repoRoot: r.dir, ref: r.sha, checks: [{ check: 'test' }] }), /dependencies are not installed in the repository root.*no network to install them/);
  });
  it('refuses a repository with no package.json, and still runs this repository\'s apps/web layout', { skip }, async () => {
    const none = repo('plain', { 'a.txt': 'x' });
    await assert.rejects(runScratch({ repoRoot: none.dir, ref: none.sha, checks: [{ check: 'test' }] }), /no package\.json/);
    const web = repo('web', { 'apps/web/package.json': JSON.stringify({ scripts: { test: 'node --test tests/*.test.js' } }), 'apps/web/src/add.js': SRC, 'apps/web/tests/add.test.js': TEST });
    const patch = FIX.replaceAll('src/add.js', 'apps/web/src/add.js');
    const ok = await runScratch({ repoRoot: web.dir, ref: web.sha, patch, checks: [{ check: 'test' }] });
    assert.equal(ok.verified, true);
  });
});
