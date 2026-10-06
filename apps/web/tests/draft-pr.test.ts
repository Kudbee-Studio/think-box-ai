// Draft pull requests (slice 4): eligibility, the commit built without touching the work tree, and the push + `gh pr create --draft` flow, against a local checkout, a local BARE
// repository standing in for GitHub, and a fake `gh`. Nothing here reaches the network.
import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildPatch } from '../change-proposal.ts';
import type { ConvoyRecord } from '../convoy.ts';
import { buildCommit, defaultRun, draftPrConfig, draftPrEligibility, openDraftPr, prepareDraftPr, renderPrBody, scrub, type DraftPrConfig, type RunFn } from '../draft-pr.ts';

let root = ''; let checkout = ''; let bare = ''; let sha = ''; let patch = ''; let patchHash = '';
const realTmp = process.env.TMPDIR; let privateTmp = '';
const G = (cwd: string, ...a: string[]): string => execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', ...a], { cwd, encoding: 'utf8' }).trim();
const GREETER = "function greet(name) {\n  return 'helo ' + name;\n}\nmodule.exports = { greet };\n";
const REPO = 'Acme/widgets';

before(async () => {
  privateTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'dpr-tests-')); process.env.TMPDIR = privateTmp;
  root = fs.mkdtempSync(path.join(os.tmpdir(), 'dpr-root-')); checkout = path.join(root, 'checkout'); bare = path.join(root, 'remote.git'); fs.mkdirSync(checkout);
  fs.mkdirSync(path.join(checkout, 'apps/web/src'), { recursive: true }); fs.writeFileSync(path.join(checkout, 'apps/web/src/greeter.js'), GREETER); fs.writeFileSync(path.join(checkout, 'README.md'), '# x\n');
  G(checkout, 'init', '-q', '-b', 'main'); G(checkout, 'add', '-A'); G(checkout, 'commit', '-qm', 'base'); sha = G(checkout, 'rev-parse', 'HEAD');
  execFileSync('git', ['init', '-q', '--bare', '-b', 'main', bare]); G(checkout, 'push', '-q', bare, 'main:refs/heads/main');
  const p = await buildPatch(checkout, sha, [{ path: 'apps/web/src/greeter.js', find: "'helo '", replace: "'hello '" }]);
  assert.ok(p.ok); patch = p.patch; patchHash = p.sha256;
});
after(() => { fs.rmSync(root, { recursive: true, force: true }); if (realTmp === undefined) delete process.env.TMPDIR; else process.env.TMPDIR = realTmp; fs.rmSync(privateTmp, { recursive: true, force: true }); });

const cfg = (over: Partial<DraftPrConfig> = {}): DraftPrConfig => ({ enabled: true, repo: REPO, base: 'main', remoteUrl: bare, ...over });
const report = (over: Record<string, unknown> = {}) => ({ ref: 'HEAD', sha, patch_sha256: patchHash, files_touched: ['apps/web/src/greeter.js'], flags: [], sandbox: { tool: 'bwrap', version: '0.11', network: 'blocked' }, checks: [{ check: 'lint', passed: true, exit_code: 0 }, { check: 'test', passed: true, exit_code: 0, tests: { pass: 1, fail: 0 } }], verified: true, started_at: 'x', duration_ms: 1, ...over });
function convoy(over: Record<string, any> = {}): ConvoyRecord {
  const base: any = { id: '0123abcd-aaaa-bbbb-cccc-dddddddddddd', goal: "Fix the greeting typo\nin greeter.js\u0007", state: 'COMPLETED', outcome: 'success', plan: { think_mode: 'simulate' }, review: { state: 'accepted', decided_by: 'human' },
    simulation: { ref: 'HEAD', sha, proposed_by: 'mercury-2', summary: 'Fixes the typo.', patch, patch_sha256: patchHash, files: ['apps/web/src/greeter.js'], flags: [], checks_ran: true, verified: true, report: report(), rounds: [{ round: 1, outcome: 'test failed' }, { round: 2, outcome: 'verified' }], max_rounds: 2 }, events: [] };
  return { ...base, ...over, simulation: over.simulation === null ? undefined : { ...base.simulation, ...(over.simulation ?? {}) } } as ConvoyRecord;
}
/** git is real; gh is fake and records its calls. Every command is logged so the tests can assert on exactly what was run. */
function rig(gh: (args: string[], input?: string) => { code: number; out: string } = () => ({ code: 0, out: `https://github.com/${REPO}/pull/7\n` })) {
  const calls: Array<{ cmd: string; args: string[]; input?: string; net?: boolean }> = [];
  const run: RunFn = async (cmd, args, opts) => { calls.push({ cmd, args, input: opts?.input, net: opts?.net }); return cmd === 'gh' ? gh(args, opts?.input) : defaultRun(cmd, args, opts); };
  return { calls, run };
}
const state = (dir: string): string => createHash('sha256').update(G(dir, 'status', '--porcelain', '--ignored') + G(dir, 'rev-parse', 'HEAD') + G(dir, 'for-each-ref') + fs.readFileSync(path.join(dir, '.git', 'index'))).digest('hex');
const remoteBranches = (): string => G(bare, 'for-each-ref', '--format=%(refname) %(objectname)');
const prepared = async (c = convoy(), config = cfg()) => { const p = await prepareDraftPr(c, config, checkout); assert.equal(p.ok, true, JSON.stringify(p)); return p as Extract<typeof p, { ok: true }>; };

describe('configuration and scrubbing', () => {
  it('is OFF unless KUDBEE_DRAFT_PR=on, defaults the base to main, and takes the remote from the configured repository', () => {
    assert.deepEqual(draftPrConfig({}), { enabled: false, repo: null, base: 'main', remoteUrl: null });
    assert.deepEqual(draftPrConfig({ KUDBEE_DRAFT_PR: 'on', KUDBEE_REPO: 'Kudbee-Studio/think-box-ai' }), { enabled: true, repo: 'Kudbee-Studio/think-box-ai', base: 'main', remoteUrl: 'https://github.com/Kudbee-Studio/think-box-ai.git' });
    for (const v of ['1', 'true', 'ON', 'yes', '']) assert.equal(draftPrConfig({ KUDBEE_DRAFT_PR: v, KUDBEE_REPO: REPO }).enabled, false, v);
    assert.equal(draftPrConfig({ KUDBEE_DRAFT_PR: 'on', KUDBEE_REPO: 'not a repo' }).repo, null);
    assert.equal(draftPrConfig({ KUDBEE_DRAFT_PR: 'on', KUDBEE_REPO: REPO, KUDBEE_PR_BASE: 'release/1.0' }).base, 'release/1.0');
    assert.equal(draftPrConfig({ KUDBEE_DRAFT_PR: 'on', KUDBEE_REPO: REPO, KUDBEE_PR_BASE: '--delete' }).base, 'main');
    assert.equal(draftPrConfig({ KUDBEE_DRAFT_PR: 'on', KUDBEE_REPO: REPO, KUDBEE_PR_REMOTE_URL: '/tmp/mirror.git' }).remoteUrl, '/tmp/mirror.git');
  });
  it('scrub removes the operator\'s tokens, GitHub token shapes and credentials embedded in URLs', () => {
    const env = { GH_TOKEN: 'abcdef123456SECRET', GITHUB_TOKEN: 'zzzzzzzz99999999' };
    const out = scrub('failed with abcdef123456SECRET and ghp_abcdefghijklmnopqrstuvwxyz0123 at https://user:pa55@github.com/x and github_pat_11ABCDEFG0123456789abcdefghij and zzzzzzzz99999999', env);
    assert.doesNotMatch(out, /abcdef123456SECRET|ghp_abcdef|pa55|github_pat_11|zzzzzzzz99999999/); assert.match(out, /https:\/\/\*\*\*@github\.com\/x/);
    assert.equal(scrub('nothing secret here', {}), 'nothing secret here');
  });
});

describe('eligibility: a human may turn a verified, accepted proposal into a draft, and nothing else', () => {
  const refuse = (c: ConvoyRecord, why: RegExp, config = cfg()) => { const r = draftPrEligibility(c, config); assert.equal(r.ok, false); assert.match((r as any).error, why); };
  it('accepts a verified SIMULATE convoy whose review a human accepted', () => { assert.deepEqual(draftPrEligibility(convoy(), cfg()), { ok: true }); });
  it('refuses when off, without a repository, for a convoy that is not a SIMULATE proposal, did not succeed, or is not verified by a report for its own commit', () => {
    refuse(convoy(), /draft pull requests are off/, cfg({ enabled: false })); refuse(convoy(), /no repository is configured/, cfg({ repo: null })); refuse(convoy(), /no repository is configured/, cfg({ remoteUrl: null }));
    refuse(convoy({ plan: { think_mode: 'observe' } }), /only a SIMULATE convoy/); refuse(convoy({ simulation: null }), /only a SIMULATE convoy/);
    refuse(convoy({ state: 'PARTIAL', outcome: 'partial' }), /did not end in a verified success/); refuse(convoy({ outcome: 'failed' }), /did not end in a verified success/);
    refuse(convoy({ simulation: { verified: false } }), /not verified by a sandbox report/); refuse(convoy({ simulation: { checks_ran: false } }), /not verified by a sandbox report/); refuse(convoy({ simulation: { report: null } }), /not verified by a sandbox report/);
    refuse(convoy({ simulation: { report: report({ verified: false }) } }), /not verified by a sandbox report/); refuse(convoy({ simulation: { report: report({ sha: 'b'.repeat(40) }) } }), /not verified by a sandbox report for its own commit/);
  });
  it('refuses a patch that is not the one that was verified (any change to the recorded patch breaks its hash)', () => {
    refuse(convoy({ simulation: { patch: `${patch}\n+sneaky\n` } }), /does not match the hash that was verified/);
    refuse(convoy({ simulation: { report: report({ patch_sha256: 'c'.repeat(64) }) } }), /does not match the hash that was verified/);
  });
  it('needs a human to have accepted the review: pending, rejected, not required and absent are all refused; and a convoy already opened is not opened twice', () => {
    for (const review of [{ state: 'pending' }, { state: 'rejected' }, { state: 'not_required' }, undefined]) refuse(convoy({ review }), /a human must accept the convoy's outcome first/);
    refuse(convoy({ draft_pr: { state: 'opened', url: `https://github.com/${REPO}/pull/3` } }), /already opened: https:\/\/github\.com\/Acme\/widgets\/pull\/3/);
    assert.equal(draftPrEligibility(convoy({ draft_pr: { state: 'branch_pushed' } }), cfg()).ok, true, 'a pushed branch without its pull request may be finished');
  });
});

describe('prepareDraftPr: everything decided before the human is asked', () => {
  it('builds the branch, title, body and approval text; the patch is not in the approval request', async () => {
    const p = await prepared();
    assert.equal(p.branch, `kudbee/sim-0123abcd-${patchHash.slice(0, 8)}`); assert.equal(p.title, 'kudbEE: Fix the greeting typo in greeter.js');
    assert.match(p.reason, new RegExp(`^Open a DRAFT pull request on ${REPO} \\(base main, new branch ${p.branch}\\) from SIMULATE convoy 0123abcd: patch ${patchHash.slice(0, 12)} touching 1 file\\(s\\): apps/web/src/greeter\\.js\\. The sandbox verified it and a human accepted the review\\. This pushes one new branch using this machine's existing git and gh logins, and creates a draft\\. It never merges, never force-pushes, never marks a pull request ready\\.$`));
    assert.deepEqual(p.display, { repo: REPO, base: 'main', branch: p.branch, convoy: '0123abcd', base_commit: sha, patch_sha256: patchHash, files: ['apps/web/src/greeter.js'], flags: [], draft: true, resume: false, title: p.title });
    assert.equal(JSON.stringify(p.display).includes('diff --git'), false);
  });
  it('a flagged patch is allowed but the approval says WARNING with what each flag means', async () => {
    const p = await prepared(convoy({ simulation: { flags: ['touches_tests', 'harness_detection'] } }));
    assert.match(p.reason, /WARNING: touches_tests \(the patch edits tests, which are what judge it\); harness_detection \(the source change refers to tests or detects the test harness/);
  });
  it('the PR body states the verdict as the report\'s, labels the model\'s summary as its words, lists the checks, rounds and flags, and does not contain the patch', async () => {
    const body = renderPrBody(convoy({ simulation: { flags: ['touches_tests'] } }));
    assert.match(body, /^> A DRAFT opened from a kudbEE SIMULATE convoy after a human accepted its review\. It is not merged and not marked ready/);
    assert.match(body, /\*\*The model's summary \(its words, not a verdict\):\*\* Fixes the typo\./); assert.match(body, /\(The verdict comes from the sandbox report, not from the model\.\)/);
    assert.match(body, /\| lint \| passed \| *\|\n\| test \| passed \| 1 passed, 0 failed \|/); assert.match(body, /\*\*Rounds:\*\* 1: test failed; 2: verified\./);
    assert.match(body, /\*\*Flags for the reviewer:\*\* `touches_tests` \(the patch edits tests/); assert.match(body, /not proof the change is correct/);
    assert.match(body, new RegExp(`\\*\\*Base commit:\\*\\* \`${sha.slice(0, 12)}\``)); assert.doesNotMatch(body, /diff --git|\+  return/);
  });
  it('refuses a recorded patch the policy now refuses, or that no longer applies to the pinned commit', async () => {
    const evil = 'diff --git a/.env b/.env\nnew file mode 100644\n--- /dev/null\n+++ b/.env\n@@ -0,0 +1 @@\n+SECRET=1\n';
    const eh = createHash('sha256').update(evil).digest('hex');
    const r1 = await prepareDraftPr(convoy({ simulation: { patch: evil, patch_sha256: eh, report: report({ patch_sha256: eh }) } }), cfg(), checkout) as any;
    assert.equal(r1.ok, false); assert.match(r1.error, /the recorded patch is refused now: \.env: /);
    const stale = patch.replace("-  return 'helo ' + name;", "-  return 'something else ' + name;"); const sh = createHash('sha256').update(stale).digest('hex');
    const r2 = await prepareDraftPr(convoy({ simulation: { patch: stale, patch_sha256: sh, report: report({ patch_sha256: sh }) } }), cfg(), checkout) as any;
    assert.equal(r2.ok, false); assert.match(r2.error, new RegExp(`the recorded patch no longer applies to ${sha.slice(0, 8)}`));
  });
  it('a pushed branch without its pull request is a resume, and the approval says the branch is already pushed', async () => {
    const p = await prepared(convoy({ draft_pr: { state: 'branch_pushed', branch: `kudbee/sim-0123abcd-${patchHash.slice(0, 8)}`, commit: 'd'.repeat(40) } }));
    assert.deepEqual(p.resume, { branch: p.branch, commit: 'd'.repeat(40) }); assert.match(p.reason, /^Finish opening a DRAFT pull request/); assert.match(p.reason, /The branch is already pushed; this creates the draft pull request\./);
  });
});

describe('buildCommit: one commit on the base, built without touching the work tree', () => {
  it('has the base as its only parent, a tree equal to the base with the patch applied, a fixed agent identity, and leaves refs, index and work tree exactly as they were', async () => {
    const before = state(checkout);
    const built = await buildCommit(checkout, sha, patch, 'kudbEE: fix\n\nbody'); assert.equal(built.ok, true, JSON.stringify(built));
    const commit = (built as { commit: string }).commit;
    assert.equal(G(checkout, 'rev-list', '--parents', '-n', '1', commit), `${commit} ${sha}`);
    assert.match(G(checkout, 'show', `${commit}:apps/web/src/greeter.js`), /return 'hello ' \+ name;/); assert.equal(G(checkout, 'show', `${commit}:README.md`), '# x');
    assert.equal(G(checkout, 'diff', '--stat', sha, commit).split('\n').length, 2, 'exactly one file differs');
    assert.equal(G(checkout, 'log', '-1', '--format=%an <%ae> | %cn <%ce> | %s', commit), 'kudbEE agent (draft) <kudbee-agent@users.noreply.github.com> | kudbEE agent (draft) <kudbee-agent@users.noreply.github.com> | kudbEE: fix');
    assert.equal(state(checkout), before, 'no ref, no index, no work-tree file changed'); assert.equal(fs.readFileSync(path.join(checkout, 'apps/web/src/greeter.js'), 'utf8'), GREETER);
    assert.equal(fs.readdirSync(os.tmpdir()).filter((n) => n.startsWith('kudbee-pr-')).length, 0, 'the temporary index is removed');
  });
  it('says why when the patch does not apply or the base is unknown', async () => {
    assert.match(((await buildCommit(checkout, sha, patch.replace("-  return 'helo '", "-  return 'x'"), 'm')) as any).error, /the patch does not apply to the base commit/);
    assert.match(((await buildCommit(checkout, 'f'.repeat(40), patch, 'm')) as any).error, /could not read the base commit/);
  });
});

describe('openDraftPr: push one new branch, create the draft, and nothing else', () => {
  it('pushes exactly one new branch (no force) to the remote, leaves its base untouched and the checkout untouched, and creates the PR with --draft, hard-coded', async () => {
    const p = await prepared(); const before = state(checkout); const remoteBefore = remoteBranches(); const r = rig();
    const res = await openDraftPr(p, checkout, r.run);
    assert.equal(res.ok, true, JSON.stringify(res)); assert.equal(res.state, 'opened'); assert.equal(res.url, `https://github.com/${REPO}/pull/7`); assert.equal(res.number, 7); assert.equal(res.branch, p.branch);
    const after = remoteBranches().split('\n');
    assert.equal(after.length, 2); assert.ok(after.includes(`refs/heads/main ${sha}`), 'the remote base is exactly as it was'); assert.ok(after.includes(`refs/heads/${p.branch} ${res.commit}`));
    assert.equal(G(bare, 'rev-list', '--parents', '-n', '1', res.commit!), `${res.commit} ${sha}`);
    assert.equal(state(checkout), before, 'the checkout is untouched'); assert.equal(remoteBefore.split('\n').length, 1);
    const push = r.calls.find((c) => c.cmd === 'git' && c.args[0] === 'push')!;
    assert.deepEqual(push.args, ['push', bare, `${res.commit}:refs/heads/${p.branch}`]); assert.ok(push.net);
    for (const c of r.calls) for (const a of c.args) assert.ok(!/^(-f|--force|--force-with-lease|--mirror|--delete|\+.*)$/.test(a), `no force or delete: ${a}`);
    const gh = r.calls.filter((c) => c.cmd === 'gh'); assert.equal(gh.length, 1);
    assert.deepEqual(gh[0]!.args, ['pr', 'create', '--repo', REPO, '--draft', '--base', 'main', '--head', p.branch, '--title', 'kudbEE: Fix the greeting typo in greeter.js', '--body-file', '-']);
    assert.equal(gh[0]!.input, p.body);
    assert.ok(r.calls.every((c) => c.cmd === 'git' || (c.cmd === 'gh' && c.args[0] === 'pr' && c.args[1] === 'create')), 'only git and `gh pr create` were ever run');
    assert.ok(!r.calls.some((c) => c.args.some((a) => /merge|ready|--web|--no-draft/.test(a))));
    assert.deepEqual(res.steps.map((s) => [s.step, s.ok]), [['ls-remote', true], ['commit', true], ['push', true], ['gh pr create', true]]);
    G(bare, 'update-ref', '-d', `refs/heads/${p.branch}`);
  });

  it('refuses without pushing or calling gh when the remote base is not the commit the proposal was made on (it would publish unpublished history)', async () => {
    const other = fs.mkdtempSync(path.join(root, 'other-')); G(other, 'clone', '-q', bare, '.'); fs.writeFileSync(path.join(other, 'later.txt'), 'x'); G(other, 'add', '-A'); G(other, 'commit', '-qm', 'later'); G(other, 'push', '-q', 'origin', 'main');
    try {
      const r = rig(); const res = await openDraftPr(await prepared(), checkout, r.run);
      assert.equal(res.ok, false); assert.match(res.error!, new RegExp(`made on ${sha.slice(0, 8)} but ${REPO}'s main is at [0-9a-f]{8}.*unpublished history`));
      assert.ok(!r.calls.some((c) => c.args[0] === 'push' || c.cmd === 'gh'), 'nothing was pushed and gh was not called');
    } finally { G(bare, 'update-ref', 'refs/heads/main', sha); fs.rmSync(other, { recursive: true, force: true }); }
  });

  it('refuses when the branch already exists, when the remote cannot be read, and when the push is rejected; gh is never called after a failure before the push', async () => {
    const p = await prepared(); G(checkout, 'push', '-q', bare, `${sha}:refs/heads/${p.branch}`);
    try { const r = rig(); const res = await openDraftPr(p, checkout, r.run); assert.equal(res.ok, false); assert.match(res.error!, /already exists on the remote; nothing was changed/); assert.ok(!r.calls.some((c) => c.args[0] === 'push' || c.cmd === 'gh')); } finally { G(bare, 'update-ref', '-d', `refs/heads/${p.branch}`); }
    const r2 = rig(); const noRemote = await openDraftPr({ ...p, cfg: { ...p.cfg, remoteUrl: path.join(root, 'no-such-remote.git') } }, checkout, r2.run);
    assert.equal(noRemote.ok, false); assert.match(noRemote.error!, /could not read the remote/); assert.ok(!r2.calls.some((c) => c.cmd === 'gh'));
    const hook = path.join(bare, 'hooks', 'pre-receive'); fs.writeFileSync(hook, '#!/bin/sh\necho "rejected by policy" >&2\nexit 1\n', { mode: 0o755 });
    try { const r3 = rig(); const res = await openDraftPr(p, checkout, r3.run); assert.equal(res.ok, false); assert.match(res.error!, /the push failed: .*rejected/s); assert.ok(!r3.calls.some((c) => c.cmd === 'gh'), 'no pull request after a failed push'); assert.equal(remoteBranches().split('\n').length, 1); } finally { fs.rmSync(hook, { force: true }); }
  });

  it('a gh failure AFTER the push says so, and the retry only creates the pull request (no second push); a retry on a changed branch refuses', async () => {
    let n = 0; const p = await prepared();
    const flaky = rig(() => (++n === 1 ? { code: 1, out: 'GraphQL: rate limited' } : { code: 0, out: `https://github.com/${REPO}/pull/9\n` }));
    const first = await openDraftPr(p, checkout, flaky.run);
    assert.equal(first.ok, false); assert.equal(first.state, 'branch_pushed'); assert.match(first.error!, /the branch is pushed but the draft pull request was not created: GraphQL: rate limited/);
    assert.equal(remoteBranches().split('\n').length, 2);
    const resumed = await prepared(convoy({ draft_pr: { state: 'branch_pushed', branch: first.branch, commit: first.commit } }));
    const second = rig(() => ({ code: 0, out: `https://github.com/${REPO}/pull/9\n` }));
    const done = await openDraftPr(resumed, checkout, second.run);
    assert.equal(done.ok, true); assert.equal(done.url, `https://github.com/${REPO}/pull/9`); assert.equal(done.commit, first.commit);
    assert.ok(!second.calls.some((c) => c.args[0] === 'push'), 'the retry does not push again'); assert.equal(second.calls.filter((c) => c.cmd === 'gh').length, 1);
    const wrong = await openDraftPr({ ...resumed, resume: { branch: resumed.branch, commit: 'e'.repeat(40) } }, checkout, rig().run);
    assert.equal(wrong.ok, false); assert.match(wrong.error!, /is not the commit this convoy pushed.*nothing was changed/);
    G(bare, 'update-ref', '-d', `refs/heads/${p.branch}`);
  });

  it('only a pull-request URL of the configured repository counts as success; anything else is a failure after the push, with tokens scrubbed from the error', async () => {
    const p = await prepared();
    for (const out of ['https://github.com/Other/repo/pull/3\n', 'created!\n', `https://github.com/${REPO}/issues/3\n`]) {
      const res = await openDraftPr(p, checkout, rig(() => ({ code: 0, out })).run);
      assert.equal(res.ok, false, out); assert.equal(res.state, 'branch_pushed');
      G(bare, 'update-ref', '-d', `refs/heads/${p.branch}`);
    }
    process.env.GH_TOKEN = 'ghp_abcdefghijklmnopqrstuvwxyz0123';
    try {
      const res = await openDraftPr(p, checkout, rig(() => ({ code: 1, out: 'auth failed for ghp_abcdefghijklmnopqrstuvwxyz0123' })).run);
      assert.equal(res.ok, false); assert.doesNotMatch(JSON.stringify(res), /ghp_abcdefghijklmnopqrstuvwxyz0123/);
    } finally { delete process.env.GH_TOKEN; G(bare, 'update-ref', '-d', `refs/heads/${p.branch}`); }
  });
});
