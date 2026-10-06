// SIMULATE convoys: a patch worker (Mercury, faked here but calling the REAL governed propose_change) proposes exact text edits; the sandbox verifies the proposal on one
// pinned commit after a human approves that run; the result is built by code, so a model's words can never become the verdict. The fixture repository has a genuinely failing test.
import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { OPT_IN_TOOLS, TOOLS as REGISTRY, AGENT_PROFILES, newRunContext, runGovernedTool, type AgentHooks, type AgentRunResult } from '../agent.ts';
import { executeConvoy, type RunnerDeps } from '../convoy-runner.ts';
import { ConvoyStore } from '../convoy.ts';
import { evaluatePolicy, planConvoy } from '../mayor.ts';
import { RunStore, type RunRecord } from '../runs.ts';
import { probeSandbox, runScratch } from '../scratch-runner.ts';
import { lookupHooks } from './helpers/lookup-hooks.ts';

const realTmp = process.env.TMPDIR; let privateTmp = ''; let repo = ''; let sha = ''; const savedRoot = process.env.KUDBEE_REPO_ROOT;
const probe = await (async () => { privateTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'sim-tests-')); process.env.TMPDIR = privateTmp; return probeSandbox(); })();
const skip = probe.ok ? false : `no proven sandbox here: ${(probe as { reason: string }).reason}`;
const git = (...a: string[]): string => execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', ...a], { cwd: repo, encoding: 'utf8' }).trim();
const state = (): string => createHash('sha256').update(git('status', '--porcelain', '--ignored') + git('rev-parse', 'HEAD') + fs.readFileSync(path.join(repo, '.git', 'index'))).digest('hex');
const scratch = (): number => fs.readdirSync(os.tmpdir()).filter((n) => n.startsWith('kudbee-scratch-')).length;
const GREETER = "function greet(name) {\n  return 'helo ' + name;\n}\nmodule.exports = { greet };\n";
const FIX = [{ path: 'apps/web/src/greeter.js', find: "'helo '", replace: "'hello '" }];
const NOT_A_FIX = [{ path: 'apps/web/src/greeter.js', find: "'helo '", replace: "'hullo '" }];

before(() => {
  repo = fs.mkdtempSync(path.join(os.tmpdir(), 'sim-fixture-'));
  const w = (rel: string, text: string): void => { fs.mkdirSync(path.dirname(path.join(repo, rel)), { recursive: true }); fs.writeFileSync(path.join(repo, rel), text); };
  w('apps/web/package.json', JSON.stringify({ name: 'fixture', scripts: { test: 'node --test "tests/*.test.js"', lint: 'node -e "0"' } }));
  w('apps/web/src/greeter.js', GREETER);
  w('apps/web/tests/greeter.test.js', "const { test } = require('node:test'); const assert = require('node:assert'); const { greet } = require('../src/greeter.js');\ntest('greets', () => assert.equal(greet('x'), 'hello x'));\n");
  w('apps/web/.gitignore', 'node_modules\n'); fs.mkdirSync(path.join(repo, 'apps/web/node_modules'), { recursive: true });
  git('init', '-q', '-b', 'main'); git('add', '-A'); git('commit', '-qm', 'fixture: the greeting test fails'); sha = git('rev-parse', 'HEAD');
  process.env.KUDBEE_REPO_ROOT = repo;
});
after(async () => {
  await new Promise((r) => setTimeout(r, 500)); // the stores save asynchronously; let their last writes land before the directory goes
  if (savedRoot === undefined) delete process.env.KUDBEE_REPO_ROOT; else process.env.KUDBEE_REPO_ROOT = savedRoot;
  if (realTmp === undefined) delete process.env.TMPDIR; else process.env.TMPDIR = realTmp;
  fs.rmSync(repo, { recursive: true, force: true }); fs.rmSync(privateTmp, { recursive: true, force: true });
});

const TOOLS = ['list_files', 'read_file', 'repo_search', 'repo_read', 'propose_change', 'run_checks', 'live_lookup'];
type AgentScript = (goal: string, model: string, hooks: AgentHooks) => Promise<AgentRunResult>;
const done = (over: Partial<AgentRunResult> = {}): AgentRunResult => ({ success: true, result: 'done', steps: 2, tool_calls: 1, prompt_tokens: 100, completion_tokens: 40, tokens: 140, cost_usd: 0.0012, ...over });
/** A Mercury stand-in that makes real, governed propose_change calls. */
const proposing = (edits: unknown, summary = 'Fixes the typo in the greeting.'): AgentScript => async (_g, _m, hooks) => { await runGovernedTool('propose_change', { edits, summary }, hooks, newRunContext(), 1); return done({ result: summary }); };

function harness(over: { approve?: boolean; checks?: string[]; planTweak?: (p: any) => void } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sim-run-'));
  const store = new ConvoyStore(path.join(dir, 'c.json')); const runStore = new RunStore(path.join(dir, 'r.json'));
  const planned = planConvoy({ goal: 'Fix the typo in the greeting so the greeting test passes', mode: 'simulate', lookupModel: null, agentModel: 'mercury-2', isLocalModel: (m) => !m.startsWith('mercury'), availableTools: TOOLS, now: 1, costOf: () => ({ usd: 0.01, basis: 'test' }) });
  assert.ok(planned.ok, JSON.stringify(planned));
  const plan = (planned as any).plan; plan.simulation.checks = over.checks ?? ['test']; over.planTweak?.(plan);
  const c = store.create(plan.goal, plan, evaluatePolicy(plan));
  store.submit(c.id); store.decide(c.id, 'approve', 'human');
  const approvals: Array<{ tool: string; reason: string; args: Record<string, unknown> }> = []; const broadcasts: any[] = []; const ac = new AbortController();
  const deps = (agent: AgentScript): RunnerDeps => ({
    store, runStore, repo: null, isLocalModel: (m) => !m.startsWith('mercury'), chat: { modelCapabilities: async () => [], chatOnce: async () => { throw new Error('no local model here'); } },
    newChildRun: (g, runId, model, convoyId, workerId) => runStore.create({ id: runId, session_id: 's', goal: g, model, provider: model === 'sandbox' ? 'sandbox' : 'inception', status: 'running', started_at: Date.now(), steps: [], current_step: 0, tool_calls: 0, prompt_tokens: 0, completion_tokens: 0, cost_usd: 0, approvals: { approved: 0, denied: 0 }, files: [], jobId: convoyId, specialistId: workerId } as RunRecord),
    hooksFor: (_r, signal, allowedTools) => ({ ...lookupHooks({ signal, requestApproval: async (tool, args, reason) => { approvals.push({ tool, reason, args }); return over.approve ?? true; } }).hooks, allowedTools }),
    runAgent: (g, m, h) => agent(g, m, h), runSpecialists: async () => ({}), broadcast: (m) => broadcasts.push(m), signal: ac.signal,
  });
  return { store, runStore, c, deps, approvals, broadcasts, ac };
}

describe('the plan is what the runner executes', () => {
  it('the planned simulation block is frozen into the approved convoy', () => {
    const h = harness();
    assert.equal(h.c.plan.think_mode, 'simulate'); assert.deepEqual(h.c.workers.map((w) => [w.id, w.kind, w.status]), [['patch-1', 'patch', 'pending'], ['checks-1', 'checks', 'pending']]);
    assert.equal(h.c.plan.simulation?.ref, 'HEAD');
  });
  it('a plan with no simulation block or no model does not run', async () => {
    const h = harness({ planTweak: (p) => { delete p.simulation; } });
    const c = await executeConvoy(h.deps(proposing(FIX)), h.c.id);
    assert.equal(c.state, 'FAILED'); assert.match(c.error ?? '', /simulate_plan/);
  });
});

describe('a verified proposal', () => {
  it('the meaningful baseline: the fixture\'s test really fails on the commit as it is', { skip }, async () => {
    const r = await runScratch({ repoRoot: repo, ref: 'main', checks: [{ check: 'test' }] });
    assert.equal(r.verified, false); assert.deepEqual(r.checks[0]!.tests, { pass: 0, fail: 1 });
  });

  it('proposes exact edits, a human approves the run, the sandbox verifies, and the RESULT IS BUILT BY CODE; the working tree is untouched and the convoy is pinned to one commit', { skip }, async () => {
    const before = state(); const left = scratch();
    const h = harness();
    const c = await executeConvoy(h.deps(proposing(FIX)), h.c.id);
    assert.equal(c.state, 'COMPLETED'); assert.equal(c.outcome, 'success');
    assert.deepEqual(c.workers.map((w) => [w.id, w.status, Boolean(w.failure)]), [['patch-1', 'completed', false], ['checks-1', 'completed', false]]);
    const s = c.simulation!;
    assert.equal(s.verified, true); assert.equal(s.checks_ran, true); assert.equal(s.sha, sha); assert.equal(s.proposed_by, 'mercury-2');
    assert.deepEqual(s.files, ['apps/web/src/greeter.js']); assert.deepEqual(s.flags, []);
    assert.match(s.patch, /^diff --git a\/apps\/web\/src\/greeter\.js b\/apps\/web\/src\/greeter\.js\n/); assert.equal(s.patch_sha256, createHash('sha256').update(s.patch).digest('hex'));
    assert.equal(s.summary, 'Fixes the typo in the greeting.');
    assert.equal((s.report as any).sha, sha); assert.equal((s.report as any).verified, true);
    // one human approval for the run, naming the exact commit, the check and the patch
    assert.equal(h.approvals.length, 1); assert.equal(h.approvals[0]!.tool, 'run_checks');
    assert.match(h.approvals[0]!.reason, new RegExp(`on commit ${sha.slice(0, 12)}`)); assert.match(h.approvals[0]!.reason, new RegExp(`Patch ${s.patch_sha256.slice(0, 12)} touches 1 file\\(s\\): apps/web/src/greeter\\.js`));
    assert.equal(h.approvals[0]!.args.patch, undefined, 'the approval request carries a preview, not the patch');
    // the answer is code: it states the verdict from the report
    assert.match(c.final_answer!, /^Proposed change by mercury-2 on commit [0-9a-f]{8}, 1 file\(s\): apps\/web\/src\/greeter\.js\./);
    assert.match(c.final_answer!, /Sandbox verification: commit [0-9a-f]{8} with patch [0-9a-f]{8}: test passed \(1 passed, 0 failed\); verified: yes\./);
    assert.match(c.final_answer!, /NOT applied to your working tree and nothing was pushed/);
    assert.equal(c.run_ids.length, 2); assert.ok(Math.abs(c.cost_usd - 0.0012) < 1e-9, `cost ${c.cost_usd}`);
    assert.equal(h.runStore.get(c.run_ids[1]!)?.provider, 'sandbox'); assert.equal(h.runStore.get(c.run_ids[0]!)?.jobId, c.id);
    assert.equal(state(), before, 'the repository is exactly as it was'); assert.equal(scratch(), left);
    assert.match(fs.readFileSync(path.join(repo, 'apps/web/src/greeter.js'), 'utf8'), /'helo '/, 'the real file still has the typo');
  });
});

describe('what is NOT a verified proposal', () => {
  it('a proposal that does not fix the problem is PARTIAL: the sandbox says verified: NO, and the model\'s claim that all tests pass changes nothing', { skip }, async () => {
    const h = harness();
    const c = await executeConvoy(h.deps(proposing(NOT_A_FIX, 'All tests pass now and the change is verified.')), h.c.id);
    assert.equal(c.state, 'PARTIAL'); assert.equal(c.outcome, 'partial');
    assert.equal(c.simulation!.verified, false); assert.equal(c.simulation!.checks_ran, true);
    assert.match(c.final_answer!, /Its summary: All tests pass now and the change is verified\./, 'the model\'s words are shown as its summary');
    assert.match(c.final_answer!, /Sandbox verification: .*test FAILED \(exit 1\) \(0 passed, 1 failed\); verified: NO\./, 'the verdict is the report\'s');
  });
  it('a denied run is PARTIAL with the proposal kept and the checks marked as not run', { skip }, async () => {
    const h = harness({ approve: false });
    const c = await executeConvoy(h.deps(proposing(FIX)), h.c.id);
    assert.equal(c.state, 'PARTIAL');
    assert.equal(c.simulation!.checks_ran, false); assert.equal(c.simulation!.verified, null); assert.equal(c.simulation!.report, null);
    assert.equal(c.workers[1]!.status, 'failed'); assert.equal(c.workers[1]!.failure?.kind, 'tool_denied');
    assert.match(c.final_answer!, /NOT VERIFIED: the checks were not run \(a human denied the run\)\./); assert.equal(c.simulation!.note, 'a human denied the run');
    assert.ok(c.simulation!.patch.length > 0);
    assert.equal(h.approvals.length, 1);
  });
  it('a proposal that edits the TEST can verify, and says so loudly: flagged in the run prompt, in the record and in the answer', { skip }, async () => {
    const h = harness();
    const c = await executeConvoy(h.deps(proposing([{ path: 'apps/web/tests/greeter.test.js', find: "'hello x'", replace: "'helo x'" }], 'Update the expected greeting in the test.')), h.c.id);
    assert.equal(c.simulation!.verified, true, 'weakening the test makes it pass');
    assert.deepEqual(c.simulation!.files, ['apps/web/tests/greeter.test.js']); assert.deepEqual(c.simulation!.flags, ['touches_tests']);
    assert.match(h.approvals[0]!.reason, /WARNING: touches_tests \(it edits tests, which are what judge it\)/);
    assert.match(c.final_answer!, /Flags: touches_tests \(the proposal edits tests, which are what judge it\)\./);
    assert.match(c.final_answer!, /verified: yes/, 'the verdict is still the report\'s: the flag is what tells the reader it proves less');
  });
  it('no proposal at all is FAILED, the checks worker is skipped, and a model that claims it fixed things in words is not believed', async () => {
    const h = harness();
    const c = await executeConvoy(h.deps(async () => done({ result: 'I fixed the typo; everything passes.' })), h.c.id);
    assert.equal(c.state, 'FAILED'); assert.equal(c.outcome, 'failed'); assert.match(c.error ?? '', /^no_patch: /);
    assert.deepEqual(c.workers.map((w) => [w.status, w.failure?.kind]), [['failed', 'no_patch'], ['skipped', 'not_run']]);
    assert.equal(c.final_answer, undefined); assert.equal(c.simulation, undefined); assert.equal(h.approvals.length, 0, 'nothing was asked of the human');
  });
  it('a proposal the code rejects (find text not in the file) never becomes a patch; a later valid one does', async () => {
    const h = harness({ checks: ['lint'] });
    const agent: AgentScript = async (_g, _m, hooks) => {
      const bad = await runGovernedTool('propose_change', { edits: [{ path: 'apps/web/src/greeter.js', find: 'text that is not there', replace: 'x' }] }, hooks, newRunContext(), 1);
      assert.equal(bad.output.ok, false); assert.match(String(bad.output.error), /the text to find is not in the file/);
      await runGovernedTool('propose_change', { edits: FIX, summary: 'second try' }, hooks, newRunContext(), 2);
      return done();
    };
    const only = await executeConvoy(h.deps(async (g, m, hooks) => { await runGovernedTool('propose_change', { edits: [{ path: 'apps/web/src/greeter.js', find: 'nope', replace: 'x' }] }, hooks, newRunContext(), 1); return done(); }), h.c.id);
    assert.equal(only.state, 'FAILED'); assert.match(only.error ?? '', /^no_patch: /);
    if (!skip) { const h2 = harness({ checks: ['lint'] }); const c = await executeConvoy(h2.deps(agent), h2.c.id); assert.equal(c.simulation?.summary, 'second try'); assert.equal(c.simulation?.verified, true, 'the last VALID proposal is the one verified'); }
  });
  it('a worker agent that fails or is stopped fails the convoy with its reason and runs nothing in the sandbox', async () => {
    const h = harness();
    const c = await executeConvoy(h.deps(async () => done({ success: false, error: 'Inception API HTTP 402' })), h.c.id);
    assert.equal(c.state, 'FAILED'); assert.match(c.error ?? '', /^agent_failed: Inception API HTTP 402/); assert.equal(c.workers[1]!.status, 'skipped'); assert.equal(h.approvals.length, 0);
    const h2 = harness();
    const stopped = await executeConvoy(h2.deps(async () => done({ success: false, stopped: true, error: 'Stopped by user' })), h2.c.id);
    assert.match(stopped.error ?? '', /^stopped: /);
    const h3 = harness();
    const crashed = await executeConvoy(h3.deps(async () => { throw new Error('boom'); }), h3.c.id);
    assert.match(crashed.error ?? '', /^error: boom/);
  });
  it('an unresolvable commit fails the convoy before any model is called', async () => {
    let called = false;
    const h = harness({ planTweak: (p) => { p.simulation.ref = 'no-such-ref'; } });
    const c = await executeConvoy(h.deps(async () => { called = true; return done(); }), h.c.id);
    assert.equal(called, false); assert.equal(c.state, 'FAILED'); assert.match(c.error ?? '', /^ref: .*not a commit/);
    assert.deepEqual(c.workers.map((w) => w.status), ['failed', 'skipped']);
  });
});

describe('the convoy is pinned to one commit', () => {
  it('the proposal is built against the pinned commit even if the branch moved BEFORE the worker proposed (an unpinned proposal would not find its text)', { skip }, async () => {
    const h = harness();
    const agent: AgentScript = async (g, m, hooks) => {
      fs.writeFileSync(path.join(repo, 'apps/web/src/greeter.js'), "function greet(name) {\n  return 'changed ' + name;\n}\nmodule.exports = { greet };\n"); git('commit', '-qam', 'moved before the proposal');
      return proposing(FIX)(g, m, hooks);
    };
    try {
      const c = await executeConvoy(h.deps(agent), h.c.id);
      assert.equal(c.state, 'COMPLETED', JSON.stringify(c.workers.map((w) => w.failure))); assert.equal(c.simulation!.sha, sha); assert.equal(c.simulation!.verified, true);
    } finally { git('reset', '-q', '--hard', sha); }
  });

  it('a branch that moves after the proposal does not change what is verified: the report is for the pinned commit', { skip }, async () => {
    const h = harness();
    const agent: AgentScript = async (g, m, hooks) => {
      const r = await proposing(FIX)(g, m, hooks);
      // the branch moves AFTER the proposal was built: an unrelated commit
      fs.writeFileSync(path.join(repo, 'apps/web/unrelated.txt'), 'later\n'); git('add', '-A'); git('commit', '-qm', 'later');
      return r;
    };
    try {
      const c = await executeConvoy(h.deps(agent), h.c.id);
      assert.notEqual(git('rev-parse', 'HEAD'), sha, 'HEAD really moved');
      assert.equal(c.simulation!.sha, sha); assert.equal((c.simulation!.report as any).sha, sha); assert.equal(c.simulation!.verified, true);
    } finally { git('reset', '-q', '--hard', sha); }
  });
});

describe('propose_change through the governed path', () => {
  const propose = (args: Record<string, unknown>, hooks: ReturnType<typeof lookupHooks>) => runGovernedTool('propose_change', args, hooks.hooks, newRunContext(), 1);
  it('is opt-in: not offered by default, in no profile, and a call outside an allowlist is rejected', async () => {
    assert.ok(OPT_IN_TOOLS.has('propose_change')); assert.ok(REGISTRY.some((t) => t.function.name === 'propose_change'));
    assert.ok(!Object.values(AGENT_PROFILES).some((p) => p.allowedTools.includes('propose_change')));
    const h = lookupHooks(); const g = await propose({ edits: FIX }, h);
    assert.equal(g.output.ok, false); assert.match(String(g.output.error), /not available to this run \(repository tools are opt-in\)/); assert.equal(h.approvals.length, 0);
  });
  it('returns the patch built by code, never asks for approval (it writes and runs nothing), and clips the summary', async () => {
    const h = lookupHooks({ allowedTools: ['propose_change'] });
    const g = await propose({ edits: FIX, summary: 's'.repeat(900) }, h);
    assert.equal(g.output.ok, true); assert.equal(g.output.ref, sha); assert.deepEqual(g.output.files, ['apps/web/src/greeter.js']); assert.deepEqual(g.output.flags, []); assert.equal(g.output.edits, 1);
    assert.match(String(g.output.patch), /^diff --git a\/apps\/web\/src\/greeter\.js/); assert.ok(String(g.output.summary).length < 450 && String(g.output.summary).length < 900, 'the 900-character summary is clipped');
    assert.match(String(g.output.note), /Proposed only: nothing was written or run/);
    assert.equal(h.approvals.length, 0); assert.equal(g.approval, undefined);
  });
  it('unknown arguments and bad edits are error results a model can read and fix', async () => {
    const h = lookupHooks({ allowedTools: ['propose_change'] });
    const a = await propose({ edits: FIX, cmd: 'rm -rf /' }, h); assert.match(String(a.output.error), /^propose_change: unknown argument\(s\): cmd/);
    const b = await propose({ edits: [{ path: 'apps/web/src/greeter.js', find: 'nope', replace: 'x' }] }, h); assert.match(String(b.output.error), /^propose_change: .*the text to find is not in the file/);
    const c = await propose({ edits: [{ path: '.env', find: 'a', replace: 'b' }] }, h); assert.match(String(c.output.error), /^propose_change: edit 1: /);
    const d = await propose({}, h); assert.match(String(d.output.error), /non-empty list/);
  });
  it('builds against the convoy\'s pinned commit, not whatever HEAD has become', async () => {
    fs.writeFileSync(path.join(repo, 'apps/web/src/greeter.js'), "function greet(name) {\n  return 'changed ' + name;\n}\nmodule.exports = { greet };\n"); git('commit', '-qam', 'head moves');
    try {
      const pinned = await propose({ edits: FIX }, lookupHooks({ allowedTools: ['propose_change'], scratchRef: sha }));
      assert.equal(pinned.output.ok, true, JSON.stringify(pinned.output)); assert.equal(pinned.output.ref, sha);
      const moved = await propose({ edits: FIX }, lookupHooks({ allowedTools: ['propose_change'] }));
      assert.equal(moved.output.ok, false); assert.match(String(moved.output.error), /the text to find is not in the file/);
    } finally { git('reset', '-q', '--hard', sha); }
  });
});

