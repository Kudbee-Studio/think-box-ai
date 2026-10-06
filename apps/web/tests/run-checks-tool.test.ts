// run_checks through the governed path (slice 2): opt-in only, validated before any prompt, a human's approval on EVERY call bound to the exact commit, abort, and the
// agent loop's claim guard with a scripted Mercury. The sandbox parts skip themselves when bubblewrap cannot be proven here.
import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { AGENT_PROFILES, OPT_IN_TOOLS, TOOLS, VERIFIER_ALLOWED_TOOLS, newRunContext, runGovernedTool, runToolAgent } from '../agent.ts';
import { probeSandbox } from '../scratch-runner.ts';
import { lookupHooks } from './helpers/lookup-hooks.ts';
import { call, say, startMockInception, type MockInception } from './helpers/mock-inception.ts';

// Each test file gets a private temporary directory (os.tmpdir() honours TMPDIR at call time), so counting scratch copies left behind cannot see another test file's runs.
const realTmp = process.env.TMPDIR;
const privateTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'run-checks-tests-'));
process.env.TMPDIR = privateTmp;
after(() => { if (realTmp === undefined) delete process.env.TMPDIR; else process.env.TMPDIR = realTmp; fs.rmSync(privateTmp, { recursive: true, force: true }); });

const probe = await probeSandbox();
const skip = probe.ok ? false : `no proven sandbox here: ${(probe as { reason: string }).reason}`;
let repo = ''; let mock: MockInception; const saved: Record<string, string | undefined> = {};
const git = (...a: string[]): string => execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', ...a], { cwd: repo, encoding: 'utf8' }).trim();
const pkg = (scripts: Record<string, string>): string => JSON.stringify({ name: 'fixture', scripts });
const leftovers = (): number => fs.readdirSync(os.tmpdir()).filter((n) => n.startsWith('kudbee-scratch-')).length;
const treeState = (): string => createHash('sha256').update(git('status', '--porcelain', '--ignored') + git('rev-parse', 'HEAD')).digest('hex');
const PROFILE = [...VERIFIER_ALLOWED_TOOLS];

before(async () => {
  repo = fs.mkdtempSync(path.join(os.tmpdir(), 'rc-fixture-'));
  fs.mkdirSync(path.join(repo, 'apps/web/node_modules'), { recursive: true });
  fs.writeFileSync(path.join(repo, 'apps/web/package.json'), pkg({ lint: 'node -e "console.log(\'lint ok\')"', 'typecheck:tsc': 'node -e "console.error(\'type error\'); process.exit(2)"', test: 'node --test "tests/*.test.js"' }));
  fs.mkdirSync(path.join(repo, 'apps/web/tests'), { recursive: true });
  fs.writeFileSync(path.join(repo, 'apps/web/tests/a.test.js'), "const { test } = require('node:test'); test('ok', () => {});\n");
  fs.writeFileSync(path.join(repo, 'apps/web/.gitignore'), 'node_modules\n');
  git('init', '-q', '-b', 'main'); git('add', '-A'); git('commit', '-qm', 'fixture');
  git('checkout', '-q', '-b', 'slow'); fs.writeFileSync(path.join(repo, 'apps/web/package.json'), pkg({ lint: 'node -e "setInterval(() => {}, 1000)"' })); git('commit', '-qam', 'slow'); git('checkout', '-q', 'main');
  mock = await startMockInception();
  for (const k of ['KUDBEE_REPO_ROOT', 'INCEPTION_BASE_URL', 'INCEPTION_API_KEY']) saved[k] = process.env[k];
  process.env.KUDBEE_REPO_ROOT = repo; process.env.INCEPTION_BASE_URL = mock.baseUrl; process.env.INCEPTION_API_KEY = 'test-key';
});
after(async () => {
  for (const [k, v] of Object.entries(saved)) { if (v === undefined) delete process.env[k]; else process.env[k] = v; }
  await mock.close(); fs.rmSync(repo, { recursive: true, force: true });
});

const go = (args: Record<string, unknown>, hooks: ReturnType<typeof lookupHooks>['hooks']) => runGovernedTool('run_checks', args, hooks, newRunContext(), 1);

describe('run_checks is opt-in and validated before any prompt', () => {
  it('is not offered by default, only the verifier profile names it, and a call outside an allowlist is rejected before any approval', async () => {
    assert.ok(OPT_IN_TOOLS.has('run_checks'));
    assert.deepEqual(VERIFIER_ALLOWED_TOOLS, ['repo_search', 'repo_read', 'run_checks']);
    assert.deepEqual(AGENT_PROFILES.verifier!.allowedTools, VERIFIER_ALLOWED_TOOLS);
    assert.ok(!['hermes', 'asclepius'].some((k) => AGENT_PROFILES[k]!.allowedTools.includes('run_checks')));
    for (const hooks of [lookupHooks(), lookupHooks({ allowedTools: ['repo_search', 'repo_read'] }), lookupHooks({ allowedTools: ['algorand'] })]) {
      const g = await go({ checks: ['lint'] }, hooks.hooks);
      assert.equal(g.output.ok, false);
      assert.match(String(g.output.error), /not available to this run \(repository tools are opt-in\)|not available to this agent profile/);
      assert.equal(hooks.approvals.length, 0, 'the gate was never reached');
    }
  });
  it('the tool definition names no command string: only check names, test files and an optional diff', () => {
    const def = TOOLS.find((t) => t.function.name === 'run_checks')!.function as { description: string; parameters: { properties: Record<string, any> } };
    assert.deepEqual(Object.keys(def.parameters.properties).sort(), ['checks', 'patch', 'ref', 'test_files']);
    assert.deepEqual(def.parameters.properties.checks.items.enum, ['lint', 'typecheck', 'tsc', 'test']);
    assert.match(def.description, /ONLY if the report says so/);
  });
  it('a patch that does not apply to the commit never reaches the prompt (the live run once asked a human to approve a corrupt patch)', async () => {
    const h = lookupHooks({ allowedTools: PROFILE });
    const g = await go({ checks: ['tsc'], patch: 'diff --git a/apps/web/package.json b/apps/web/package.json\n--- a/apps/web/package.json\n+++ b/apps/web/package.json\n@@ -1,4 +1,4 @@\n this line is not in the file\n' }, h.hooks);
    assert.equal(g.output.ok, false); assert.match(String(g.output.error), /^run_checks: the patch does not apply to [0-9a-f]{8}: /);
    assert.equal(h.approvals.length, 0);
  });
  it('a bad request is an error result with the reason, and no approval is asked', async () => {
    for (const [args, why] of [[{ checks: ['rm -rf /'] }, /unknown check/], [{}, /name at least one check/], [{ checks: ['lint'], patch: 'nope' }, /patch refused/], [{ checks: ['lint'], ref: 'no-such-ref' }, /is not a commit/], [{ checks: ['lint'], extra: 1 }, /unknown argument/]] as Array<[Record<string, unknown>, RegExp]>) {
      const h = lookupHooks({ allowedTools: PROFILE });
      const g = await go(args, h.hooks);
      assert.equal(g.output.ok, false); assert.match(String(g.output.error), why); assert.match(String(g.output.error), /^run_checks: /);
      assert.equal(h.approvals.length, 0);
    }
  });
});

describe('every call asks a human, bound to the exact commit', () => {
  it('asks on each call (nothing is remembered), shows commit, checks, patch files and flags, and carries a preview, not the whole patch', { skip }, async () => {
    const h = lookupHooks({ allowedTools: PROFILE });
    const main = git('rev-parse', 'main');
    const first = await go({ ref: 'main', checks: ['lint'] }, h.hooks);
    const second = await go({ ref: 'main', checks: ['lint'] }, h.hooks);
    assert.equal(first.output.ok, true); assert.equal(second.output.ok, true);
    assert.equal(h.approvals.length, 2, 'a second identical call asks again');
    assert.match(h.approvals[0]!.reason, new RegExp(`^Run sandboxed checks \\(lint\\) on commit ${main.slice(0, 12)} \\(ref main\\)\\. No patch`));
    assert.equal(first.approval, 'approved'); assert.match(String(first.reason), /no network and no credentials/);
    const ev = h.events.filter((e) => e.kind === 'tool') as Array<{ approval?: string; approval_reason?: string; args: Record<string, unknown> }>;
    assert.deepEqual(ev.map((e) => e.approval), ['approved', 'approved']);
    assert.match(String(ev[0]!.approval_reason), /^Run sandboxed checks/);
    assert.equal(ev[0]!.args.ref, main, 'the event records the pinned sha, not the branch name');
  });

  it('the approval request carries the patch hash, files, flags and a preview, never the full patch', { skip }, async () => {
    const seen: Array<Record<string, unknown>> = [];
    const h = lookupHooks({ allowedTools: PROFILE, requestApproval: async (_t, a) => { seen.push(a); return false; } });
    const patch = `diff --git a/apps/web/tests/new.test.js b/apps/web/tests/new.test.js\nnew file mode 100644\n--- /dev/null\n+++ b/apps/web/tests/new.test.js\n@@ -0,0 +1 @@\n+${'y'.repeat(5000)}\n`;
    await go({ checks: ['test'], patch }, h.hooks);
    assert.equal(seen.length, 1);
    assert.equal(seen[0]!.patch, undefined); assert.equal(seen[0]!.patch_sha256, createHash('sha256').update(patch).digest('hex'));
    assert.deepEqual(seen[0]!.patch_files, ['apps/web/tests/new.test.js']); assert.deepEqual(seen[0]!.patch_flags, ['touches_tests']);
    assert.ok(String(seen[0]!.patch_preview).length < 1700);
  });

  it('a denial is a failure with no run: no report, no scratch copy, and the real tree untouched', { skip }, async () => {
    const left = leftovers(); const before = treeState();
    const h = lookupHooks({ allowedTools: PROFILE }, false);
    const g = await go({ checks: ['lint'] }, h.hooks);
    assert.equal(g.output.ok, false); assert.match(String(g.output.error), /Denied by human reviewer \(Run sandboxed checks/);
    assert.equal(g.approval, 'denied'); assert.equal(g.output.report, undefined);
    assert.equal(h.approvals.length, 1); assert.equal(leftovers(), left); assert.equal(treeState(), before);
  });

  it('what is approved is what runs: a branch that moves while the approval is pending does not change the commit', { skip }, async () => {
    const approvedSha = git('rev-parse', 'main');
    const h = lookupHooks({ allowedTools: PROFILE, requestApproval: async () => {
      // while the human decides, the branch moves to a commit whose lint fails
      fs.writeFileSync(path.join(repo, 'apps/web/package.json'), pkg({ lint: 'node -e "process.exit(3)"', test: 'node -e "0"' }));
      git('commit', '-qam', 'breaks lint');
      return true;
    } });
    try {
      const g = await go({ ref: 'main', checks: ['lint'] }, h.hooks);
      assert.notEqual(git('rev-parse', 'main'), approvedSha, 'the branch really moved');
      assert.equal(g.output.ok, true);
      assert.equal((g.output.report as any).sha, approvedSha, 'the report is for the approved commit');
      assert.equal(g.output.verified, true, 'and that commit\'s lint passes');
    } finally { git('reset', '-q', '--hard', approvedSha); }
  });

  it('runs a verified change end to end and returns a slim report the model can read', { skip }, async () => {
    const before = treeState();
    const h = lookupHooks({ allowedTools: PROFILE });
    const g = await go({ checks: ['lint', 'test'] }, h.hooks);
    assert.equal(g.output.ok, true); assert.equal(g.output.verified, true);
    const r = g.output.report as any;
    assert.deepEqual(r.checks.map((c: any) => [c.check, c.passed]), [['lint', true], ['test', true]]);
    assert.equal(r.sandbox.network, 'blocked'); assert.deepEqual(r.checks[1].tests, { pass: 1, fail: 0 });
    assert.equal(treeState(), before);
  });

  it('an operator stop during the run ends it and the call rethrows (the run was aborted)', { skip }, async () => {
    const ac = new AbortController();
    const h = lookupHooks({ allowedTools: PROFILE, signal: ac.signal, requestApproval: async () => { setTimeout(() => ac.abort(), 700); return true; } });
    const left = leftovers(); const t0 = Date.now();
    await assert.rejects(go({ ref: 'slow', checks: ['lint'] }, h.hooks), /abort/i);
    assert.ok(Date.now() - t0 < 10_000); assert.equal(leftovers(), left);
  });
});

describe('the agent loop: what a model may say about a report is decided in code', () => {
  const run = (goal: string, hooks: ReturnType<typeof lookupHooks>['hooks']) => runToolAgent(goal, 'mercury-2', 6, 0, [], { ...hooks, apiBaseUrl: mock.baseUrl });
  it('the verifier profile is offered the tool; a default run is not', async () => {
    mock.script([say('ok')]); await run('hello', lookupHooks({ allowedTools: PROFILE }).hooks);
    assert.ok((mock.requests.at(-1)!.tools as Array<{ function: { name: string } }>).some((t) => t.function.name === 'run_checks'));
    mock.script([say('ok')]); await run('hello', lookupHooks().hooks);
    assert.ok(!(mock.requests.at(-1)!.tools as Array<{ function: { name: string } }>).some((t) => t.function.name === 'run_checks'));
  });
  it('"all checks pass, verified" after a FAILED tsc run is replaced by what the report says, and the approval was asked once', { skip }, async () => {
    const h = lookupHooks({ allowedTools: PROFILE });
    mock.script([call('run_checks', { checks: ['lint', 'tsc'] }), say('All checks pass. The change is verified and safe to merge.')]);
    const r = await run('verify main', h.hooks);
    assert.equal(r.success, true);
    assert.match(String(r.result), /^FLAGGED: my answer claimed more than the check report supports/);
    assert.match(String(r.result), /tsc FAILED \(exit 2\)/); assert.match(String(r.result), /verified: NO/);
    assert.ok(r.evidence_conflicts?.some((c) => /not verified/.test(c)));
    assert.equal(h.approvals.length, 1);
  });
  it('an honest answer passes through untouched', { skip }, async () => {
    mock.script([call('run_checks', { checks: ['lint'] }), say('Lint passed and the report says verified. Nothing else was run, so this says nothing about typecheck or the tests.')]);
    const r = await run('verify lint', lookupHooks({ allowedTools: PROFILE }).hooks);
    assert.match(String(r.result), /^Lint passed and the report says verified/); assert.equal(r.evidence_conflicts, undefined);
  });
  it('a denied approval leaves no report, so any claim of success is refused', { skip }, async () => {
    mock.script([call('run_checks', { checks: ['lint'] }), say('Everything passed, it is verified.')]);
    const r = await run('verify', lookupHooks({ allowedTools: PROFILE }, false).hooks);
    assert.match(String(r.result), /^FLAGGED: .*no check was run.*What the report says: no check was run/s);
  });
  it('claiming a pass without ever calling the tool is refused for the verifier, and not policed for a default run', async () => {
    mock.script([say('The tests pass.')]);
    const v = await run('do the tests pass?', lookupHooks({ allowedTools: PROFILE }).hooks);
    assert.match(String(v.result), /^FLAGGED: .*tests passes, but that check was not run/);
    mock.script([say('All checks pass.')]);
    const d = await run('chat', lookupHooks().hooks);
    assert.equal(d.result, 'All checks pass.');
  });
});
