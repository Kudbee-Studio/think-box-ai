// A draft pull request from what the agent changed: off unless enabled, only from a clone at the base tip, a human approves first, one new branch is pushed, the clone is untouched.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, beforeEach, test } from 'node:test';
import { openAgentDraftPr, type AgentPrDeps } from '../agent-pr.ts';
import { defaultRun, type RunFn } from '../draft-pr.ts';

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-agent-pr-test-'));
after(() => fs.rmSync(tmp, { recursive: true, force: true }));
const g = (cwd: string, ...a: string[]): string => execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', ...a], { cwd, encoding: 'utf8' }).trim();
let remote = ''; let clone = '';
const ENV = (): Record<string, string> => ({ KUDBEE_DRAFT_PR: 'on', KUDBEE_REPO: 'acme/demo', KUDBEE_PR_REMOTE_URL: remote });
let asked: Array<{ args: Record<string, unknown>; reason: string }> = []; let ghCalls: string[][] = [];
const run: RunFn = async (cmd, args, opts) => {
  if (cmd === 'gh') { ghCalls.push(args); return { code: 0, out: 'https://github.com/acme/demo/pull/7\n' }; }
  return defaultRun(cmd, args, opts);
};
const deps = (over: Partial<AgentPrDeps> = {}): AgentPrDeps => ({ root: clone, env: ENV(), run, approve: async (_t, args, reason) => { asked.push({ args, reason }); return true; }, now: () => new Date('2026-10-07T12:00:00Z'), ...over });

beforeEach(() => {
  fs.rmSync(tmp, { recursive: true, force: true }); fs.mkdirSync(tmp);
  const seed = path.join(tmp, 'seed'); fs.mkdirSync(seed); g(seed, 'init', '-q', '-b', 'main'); fs.writeFileSync(path.join(seed, 'a.txt'), 'one\n'); g(seed, 'add', '-A'); g(seed, 'commit', '-qm', 'base');
  remote = path.join(tmp, 'remote.git'); g(tmp, 'clone', '-q', '--bare', seed, remote);
  clone = path.join(tmp, 'clone'); g(tmp, 'clone', '-q', remote, clone);
  fs.writeFileSync(path.join(clone, 'a.txt'), 'ONE\n'); fs.writeFileSync(path.join(clone, 'new.txt'), 'x\n');
  asked = []; ghCalls = [];
});

test('off unless KUDBEE_DRAFT_PR=on: nothing is asked or pushed', async () => {
  const r = await openAgentDraftPr(deps({ env: { ...ENV(), KUDBEE_DRAFT_PR: 'off' } }));
  assert.equal(r.ok, false); assert.match((r as { error: string }).error, /off/); assert.equal(asked.length, 0);
});

test('needs a chosen repository, a GitHub address and some changes', async () => {
  assert.match(((await openAgentDraftPr(deps({ root: undefined }))) as { error: string }).error, /Choose a repository/);
  const { KUDBEE_REPO: _omit, ...noRepo } = ENV();
  assert.match(((await openAgentDraftPr(deps({ env: noRepo }))) as { error: string }).error, /no GitHub address/);
  g(clone, 'checkout', '-q', '.'); fs.rmSync(path.join(clone, 'new.txt'));
  assert.match(((await openAgentDraftPr(deps())) as { error: string }).error, /no changes/);
});

test('approved: one new branch is pushed with the changed and new files, a draft PR is created, the clone is untouched', async () => {
  const r = await openAgentDraftPr(deps());
  assert.deepEqual(r, { ok: true, url: 'https://github.com/acme/demo/pull/7', branch: 'kudbee/fix-20261007-120000', files: 2 });
  assert.equal(asked.length, 1); assert.deepEqual(asked[0]!.args.files, ['changed a.txt', 'new new.txt']); assert.equal(asked[0]!.args.repository, 'acme/demo');
  const pushed = g(remote, 'show', 'kudbee/fix-20261007-120000:a.txt'); assert.equal(pushed, 'ONE');
  assert.equal(g(remote, 'show', 'kudbee/fix-20261007-120000:new.txt'), 'x');
  assert.equal(g(remote, 'rev-parse', 'main'), g(clone, 'rev-parse', 'HEAD'));
  assert.deepEqual(ghCalls[0]!.slice(0, 7), ['pr', 'create', '--repo', 'acme/demo', '--draft', '--base', 'main']); assert.ok(!ghCalls[0]!.includes('--web'));
  assert.equal(g(clone, 'status', '--porcelain').split('\n').length, 2); assert.equal(g(clone, 'branch', '--show-current'), 'main');
});

test('not approved: nothing is pushed and no PR is created', async () => {
  const r = await openAgentDraftPr(deps({ approve: async () => false }));
  assert.equal(r.ok, false); assert.match((r as { error: string }).error, /Not approved/);
  assert.equal(g(remote, 'branch', '--list', 'kudbee/*'), ''); assert.equal(ghCalls.length, 0);
});

test('a clone behind the base branch is refused, so unpublished history is never pushed', async () => {
  const other = path.join(tmp, 'other'); g(tmp, 'clone', '-q', remote, other); fs.writeFileSync(path.join(other, 'z.txt'), 'z'); g(other, 'add', '-A'); g(other, 'commit', '-qm', 'later'); g(other, 'push', '-q', 'origin', 'main');
  const r = await openAgentDraftPr(deps());
  assert.equal(r.ok, false); assert.match((r as { error: string }).error, /pull the latest/); assert.equal(asked.length, 0);
});

test('a push that works but a PR that fails says the branch is pushed; an unreadable remote is reported', async () => {
  const badGh: RunFn = async (cmd, args, opts) => cmd === 'gh' ? { code: 1, out: 'GraphQL: nope ghp_abcdefghijklmnopqrstuvwxyz0123' } : defaultRun(cmd, args, opts);
  const r = await openAgentDraftPr(deps({ run: badGh }));
  assert.equal(r.ok, false); assert.match((r as { error: string }).error, /is pushed but the draft pull request was not created/); assert.ok(!(r as { error: string }).error.includes('ghp_'));
  assert.equal((r as { branch?: string }).branch, 'kudbee/fix-20261007-120000');
  const r2 = await openAgentDraftPr(deps({ env: { ...ENV(), KUDBEE_PR_REMOTE_URL: path.join(tmp, 'missing.git') } }));
  assert.match((r2 as { error: string }).error, /Could not read the remote/);
});
