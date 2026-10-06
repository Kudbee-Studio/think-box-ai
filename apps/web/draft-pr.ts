// Open a DRAFT pull request from a verified SIMULATE proposal (Layer 5: runtime). Slice 4 of the scratch runner (docs/scratch-runner-design.md).
// This is the first thing in the plan that reaches outside the machine, so it is narrow by construction:
//   - a HUMAN starts it (a dashboard message), after a human accepted the convoy's review; no model and no tool can reach it;
//   - it is OFF unless KUDBEE_DRAFT_PR=on, and it only ever targets the configured repository and base branch, never `origin`;
//   - what it pushes is the convoy's recorded, verified patch (its hash is re-checked), as ONE commit on top of the pinned base commit, built without touching your working tree;
//   - the base commit must be the remote base branch's tip (otherwise the push would carry unpublished history), and the branch must not exist yet;
//   - it never force-pushes, never marks a PR ready, never merges; the pull request is created with --draft, hard-coded;
//   - it asks the human again, naming repository, base, branch, patch hash, files and flags;
//   - it never reads a token: pushes use the machine's git login and the PR is created by the already logged-in `gh` CLI. Any token that appears in an error is scrubbed.
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { describeReport } from './check-claims.ts';
import type { ConvoyRecord, ConvoyStore } from './convoy.ts';
import { patchProblem, reviewPatch, type ScratchReport } from './scratch-runner.ts';

export interface DraftPrConfig { enabled: boolean; repo: string | null; base: string; remoteUrl: string | null }
export type RunFn = (cmd: string, args: string[], opts?: { cwd?: string; input?: string; net?: boolean; env?: Record<string, string> }) => Promise<{ code: number; out: string }>;

const REPO = /^[\w.-]+\/[\w.-]+$/;
const BRANCH = /^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$/;
const AGENT = { name: 'kudbEE agent (draft)', email: 'kudbee-agent@users.noreply.github.com' };

/** Reads the switches from the environment. Off unless KUDBEE_DRAFT_PR=on; the remote is the configured repository on GitHub unless KUDBEE_PR_REMOTE_URL says otherwise (tests, or a mirror). */
export function draftPrConfig(env: Record<string, string | undefined> = process.env): DraftPrConfig {
  const repo = env.KUDBEE_REPO && REPO.test(env.KUDBEE_REPO) ? env.KUDBEE_REPO : null;
  const base = env.KUDBEE_PR_BASE && BRANCH.test(env.KUDBEE_PR_BASE) ? env.KUDBEE_PR_BASE : 'main';
  const remoteUrl = env.KUDBEE_PR_REMOTE_URL?.trim() || (repo ? `https://github.com/${repo}.git` : null);
  return { enabled: env.KUDBEE_DRAFT_PR === 'on', repo, base, remoteUrl };
}

/** Removes anything that looks like a credential from text that may be shown or stored. */
export function scrub(text: string, env: Record<string, string | undefined> = process.env): string {
  let out = String(text);
  for (const v of [env.GH_TOKEN, env.GITHUB_TOKEN]) if (v && v.length >= 8) out = out.split(v).join('***');
  return out.replace(/\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b/g, '***').replace(/(https?:\/\/)[^/@\s]+:[^/@\s]+@/g, '$1***@');
}

export const defaultRun: RunFn = (cmd, args, opts = {}) => new Promise((resolve) => {
  // local git plumbing gets a minimal environment; network steps (push, gh) also get HOME (their logins live there) and the two token variables if the operator set them
  const env: Record<string, string> = { PATH: process.env.PATH ?? '/usr/bin:/bin', GIT_CONFIG_NOSYSTEM: '1', GIT_TERMINAL_PROMPT: '0', ...(opts.net ? { HOME: process.env.HOME ?? '', GH_PROMPT_DISABLED: '1', NO_COLOR: '1', ...(process.env.GH_TOKEN ? { GH_TOKEN: process.env.GH_TOKEN } : {}), ...(process.env.GITHUB_TOKEN ? { GITHUB_TOKEN: process.env.GITHUB_TOKEN } : {}) } : {}), ...(opts.env ?? {}) };
  const child = spawn(cmd, args, { cwd: opts.cwd, env, stdio: [opts.input !== undefined ? 'pipe' : 'ignore', 'pipe', 'pipe'] });
  const chunks: Buffer[] = [];
  child.stdout?.on('data', (d: Buffer) => chunks.push(d)); child.stderr?.on('data', (d: Buffer) => chunks.push(d));
  child.stdin?.on('error', () => undefined);
  const timer = setTimeout(() => { try { child.kill('SIGKILL'); } catch { /* gone */ } }, 120_000);
  child.on('error', (err) => { clearTimeout(timer); resolve({ code: 1, out: `could not start ${cmd}: ${err.message}` }); });
  child.on('close', (code) => { clearTimeout(timer); resolve({ code: code ?? 1, out: Buffer.concat(chunks).toString('utf8') }); });
  if (opts.input !== undefined) child.stdin?.end(opts.input);
});

const oneLine = (t: unknown, max: number): string => String(t ?? '').replace(/[\u0000-\u001f\u007f]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, max);
/** A one-line pull-request title from the goal: cut at a word boundary with an ellipsis, so a truncated title reads as truncated (it used to stop mid-word or mid-quote with nothing to say so). */
export function titleFromGoal(goal: unknown, max = 72): string {
  const line = oneLine(goal, 10_000);
  if (line.length <= max) return `kudbEE: ${line}`;
  const room = line.slice(0, max - 1);
  const cut = room.lastIndexOf(' ');
  return `kudbEE: ${(cut >= Math.floor(max / 2) ? room.slice(0, cut) : room).trimEnd()}\u2026`;
}
const FLAG_TEXT: Record<string, string> = {
  touches_tests: 'the patch edits tests, which are what judge it',
  touches_ci_or_gates: 'the patch edits CI, gates, package or compiler configuration',
  deletes_files: 'the patch deletes files',
  harness_detection: 'the source change refers to tests or detects the test harness, so it may special-case the checks',
  tests_edited_after_failure: 'it started editing tests only after an attempt failed',
};

/** Whether this convoy may be turned into a draft PR, without touching git or the network. */
export function draftPrEligibility(c: ConvoyRecord, cfg: DraftPrConfig): { ok: true } | { ok: false; error: string } {
  if (!cfg.enabled) return { ok: false, error: 'draft pull requests are off (set KUDBEE_DRAFT_PR=on to allow a human to open one)' };
  if (!cfg.repo || !cfg.remoteUrl) return { ok: false, error: 'no repository is configured (KUDBEE_REPO must be owner/name)' };
  const s = c.simulation;
  if (c.plan.think_mode !== 'simulate' || !s) return { ok: false, error: 'only a SIMULATE convoy with a proposed change can become a draft pull request' };
  if (c.state !== 'COMPLETED' || c.outcome !== 'success') return { ok: false, error: 'the convoy did not end in a verified success' };
  const report = s.report as unknown as ScratchReport | null;
  if (s.verified !== true || !s.checks_ran || !report || report.verified !== true || report.sha !== s.sha) return { ok: false, error: 'the proposal is not verified by a sandbox report for its own commit' };
  if (createHash('sha256').update(s.patch).digest('hex') !== s.patch_sha256 || report.patch_sha256 !== s.patch_sha256) return { ok: false, error: 'the recorded patch does not match the hash that was verified' };
  if (c.review?.state !== 'accepted') return { ok: false, error: `a human must accept the convoy's outcome first (its review is ${c.review?.state ?? 'absent'})` };
  if (c.draft_pr?.state === 'opened') return { ok: false, error: `a draft pull request was already opened: ${c.draft_pr.url}` };
  return { ok: true };
}

export function renderPrBody(c: ConvoyRecord): string {
  const s = c.simulation!;
  const report = s.report as unknown as ScratchReport;
  const rows = report.checks.map((k) => `| ${k.check}${k.file ? ` ${k.file}` : ''} | ${k.passed ? 'passed' : 'FAILED'} | ${k.tests ? `${k.tests.pass} passed, ${k.tests.fail} failed` : ''} |`);
  const flags = s.flags.length ? ['', `**Flags for the reviewer:** ${s.flags.map((f) => `\`${f}\` (${FLAG_TEXT[f] ?? f})`).join('; ')}.`] : [];
  const rounds = (s.rounds?.length ?? 0) > 1 ? ['', `**Rounds:** ${s.rounds!.map((r) => `${r.round}: ${oneLine(r.outcome, 80)}`).join('; ')}.`] : [];
  return [
    '> A DRAFT opened from a kudbEE SIMULATE convoy after a human accepted its review. It is not merged and not marked ready: a person must review it.',
    '', `**Goal:** ${oneLine(c.goal, 400)}`,
    `**Proposed by:** ${oneLine(s.proposed_by, 60)} · **Convoy:** \`${c.id.slice(0, 8)}\` · **Base commit:** \`${s.sha.slice(0, 12)}\` · **Patch:** \`${s.patch_sha256.slice(0, 12)}\``,
    `**Files:** ${s.files.map((f) => `\`${oneLine(f, 120)}\``).join(', ')}`,
    '', `**The model's summary (its words, not a verdict):** ${oneLine(s.summary, 600) || '(none)'}`,
    '', '## Sandbox verification', '(The verdict comes from the sandbox report, not from the model.)', '',
    '| Check | Result | Tests |', '|---|---|---|', ...rows, '',
    `${describeReport(report)}`, '',
    "Verified means the repository's own checks passed on a throwaway copy with no network and no credentials. It is not proof the change is correct.",
    ...rounds, ...flags,
  ].join('\n');
}

export interface PreparedDraftPr {
  ok: true;
  cfg: DraftPrConfig & { repo: string; remoteUrl: string };
  sha: string; patch: string; patch_sha256: string; files: string[]; flags: string[];
  branch: string; title: string; body: string; message: string;
  /** Set when an earlier attempt already pushed the branch and only the pull request is missing. */
  resume?: { branch: string; commit: string };
  reason: string;
  display: Record<string, unknown>;
}

/** Everything that can be decided before asking the human: eligibility, the patch re-checked against the pinned commit, the branch, title and body, and the approval text. */
export async function prepareDraftPr(c: ConvoyRecord, cfg: DraftPrConfig, repoRoot: string): Promise<PreparedDraftPr | { ok: false; error: string }> {
  const e = draftPrEligibility(c, cfg);
  if (!e.ok) return e;
  const s = c.simulation!;
  const review = reviewPatch(s.patch);
  if (!review.ok) return { ok: false, error: `the recorded patch is refused now: ${review.error}` };
  const bad = await patchProblem(repoRoot, s.sha, s.patch);
  if (bad) return { ok: false, error: `the recorded patch no longer applies to ${s.sha.slice(0, 8)}: ${bad}` };
  const repo = cfg.repo!; const remoteUrl = cfg.remoteUrl!;
  const branch = `kudbee/sim-${c.id.slice(0, 8)}-${s.patch_sha256.slice(0, 8)}`;
  if (!BRANCH.test(branch)) return { ok: false, error: 'the branch name is not valid' };
  const title = titleFromGoal(c.goal);
  const flags = s.flags;
  const resume = c.draft_pr?.state === 'branch_pushed' && c.draft_pr.branch === branch ? { branch, commit: c.draft_pr.commit } : undefined;
  const flagWarn = flags.length ? ` WARNING: ${flags.map((f) => `${f} (${FLAG_TEXT[f] ?? f})`).join('; ')}.` : '';
  const reason = `${resume ? 'Finish opening' : 'Open'} a DRAFT pull request on ${repo} (base ${cfg.base}, new branch ${branch}) from SIMULATE convoy ${c.id.slice(0, 8)}: patch ${s.patch_sha256.slice(0, 12)} touching ${s.files.length} file(s): ${s.files.slice(0, 8).join(', ')}${s.files.length > 8 ? ', ...' : ''}.${flagWarn} The sandbox verified it and a human accepted the review. ${resume ? 'The branch is already pushed; this creates the draft pull request.' : 'This pushes one new branch'} using this machine's existing git and gh logins, and creates a draft. It never merges, never force-pushes, never marks a pull request ready.`;
  return {
    ok: true, cfg: { ...cfg, repo, remoteUrl }, sha: s.sha, patch: s.patch, patch_sha256: s.patch_sha256, files: s.files, flags, branch, title, body: renderPrBody(c),
    message: `${title}\n\nProposed by ${oneLine(s.proposed_by, 60)} in kudbEE SIMULATE convoy ${c.id.slice(0, 8)}; verified in a sandbox; patch ${s.patch_sha256.slice(0, 12)}.`,
    ...(resume ? { resume } : {}), reason,
    display: { repo, base: cfg.base, branch, convoy: c.id.slice(0, 8), base_commit: s.sha, patch_sha256: s.patch_sha256, files: s.files, flags, draft: true, resume: Boolean(resume), title },
  };
}

/** One commit on top of `sha` whose tree is `sha`'s tree with the patch applied, built with a temporary index: no ref, no work tree and no real index is touched (only an unreferenced object is added). */
export async function buildCommit(repoRoot: string, sha: string, patch: string, message: string, run: RunFn = defaultRun): Promise<{ ok: true; commit: string } | { ok: false; error: string }> {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-pr-'));
  const env = { GIT_INDEX_FILE: path.join(dir, 'index'), GIT_AUTHOR_NAME: AGENT.name, GIT_AUTHOR_EMAIL: AGENT.email, GIT_COMMITTER_NAME: AGENT.name, GIT_COMMITTER_EMAIL: AGENT.email };
  try {
    const read = await run('git', ['read-tree', sha], { cwd: repoRoot, env });
    if (read.code !== 0) return { ok: false, error: `could not read the base commit: ${scrub(read.out).trim().slice(0, 160)}` };
    const apply = await run('git', ['apply', '--cached', '--whitespace=nowarn', '-'], { cwd: repoRoot, env, input: patch });
    if (apply.code !== 0) return { ok: false, error: `the patch does not apply to the base commit: ${scrub(apply.out).trim().slice(0, 160)}` };
    const tree = await run('git', ['write-tree'], { cwd: repoRoot, env });
    if (tree.code !== 0 || !/^[0-9a-f]{40}$/.test(tree.out.trim())) return { ok: false, error: `could not write the tree: ${scrub(tree.out).trim().slice(0, 160)}` };
    const commit = await run('git', ['commit-tree', tree.out.trim(), '-p', sha, '-m', message], { cwd: repoRoot, env });
    if (commit.code !== 0 || !/^[0-9a-f]{40}$/.test(commit.out.trim())) return { ok: false, error: `could not create the commit: ${scrub(commit.out).trim().slice(0, 160)}` };
    return { ok: true, commit: commit.out.trim() };
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
}

export interface DraftPrResult { ok: boolean; error?: string; state?: 'branch_pushed' | 'opened'; branch?: string; commit?: string; url?: string; number?: number; steps: Array<{ step: string; ok: boolean; detail: string }> }

/** Pushes the branch and creates the draft pull request. Every step is recorded; a failure after the push says so, so a retry only creates the pull request. */
export async function openDraftPr(p: PreparedDraftPr, repoRoot: string, run: RunFn = defaultRun): Promise<DraftPrResult> {
  const steps: DraftPrResult['steps'] = [];
  const note = (step: string, ok: boolean, detail: string): void => { steps.push({ step, ok, detail: scrub(detail).slice(0, 300) }); };
  const { cfg, branch } = p;
  const ref = `refs/heads/${branch}`;
  // 1. what GitHub has now: the base branch's tip must be the commit the proposal was made on, and the new branch must not exist (unless this finishes an earlier push)
  const ls = await run('git', ['ls-remote', cfg.remoteUrl, `refs/heads/${cfg.base}`, ref], { cwd: repoRoot, net: true });
  if (ls.code !== 0) { note('ls-remote', false, ls.out); return { ok: false, error: `could not read the remote: ${scrub(ls.out).trim().slice(0, 200)}`, steps }; }
  const tips = new Map(ls.out.split('\n').map((l) => l.trim().split(/\s+/)).filter((x) => x.length === 2).map(([sha, name]) => [name!, sha!]));
  const baseTip = tips.get(`refs/heads/${cfg.base}`); const branchTip = tips.get(ref);
  note('ls-remote', true, `${cfg.base} is at ${baseTip?.slice(0, 8) ?? '(missing)'}`);
  let commit: string;
  if (p.resume) {
    if (branchTip !== p.resume.commit) return { ok: false, error: `the branch ${branch} on the remote is not the commit this convoy pushed (${branchTip?.slice(0, 8) ?? 'missing'}); nothing was changed`, steps };
    commit = p.resume.commit;
  } else {
    if (baseTip !== p.sha) return { ok: false, error: `the proposal was made on ${p.sha.slice(0, 8)} but ${cfg.repo}'s ${cfg.base} is at ${baseTip?.slice(0, 8) ?? '(missing)'}: bring your checkout up to date and run the convoy again (pushing from another base would publish unpublished history)`, steps };
    if (branchTip) return { ok: false, error: `the branch ${branch} already exists on the remote; nothing was changed`, steps };
    // 2. the commit, built without touching the work tree
    const built = await buildCommit(repoRoot, p.sha, p.patch, p.message, run);
    if (!built.ok) { note('commit', false, built.error); return { ok: false, error: built.error, steps }; }
    commit = built.commit; note('commit', true, `commit ${commit.slice(0, 8)} on ${p.sha.slice(0, 8)}`);
    // 3. push one new branch: no --force, no refspec but this one
    const push = await run('git', ['push', cfg.remoteUrl, `${commit}:${ref}`], { cwd: repoRoot, net: true });
    if (push.code !== 0) { note('push', false, push.out); return { ok: false, error: `the push failed: ${scrub(push.out).trim().slice(0, 240)}`, steps }; }
    note('push', true, `${branch} pushed`);
  }
  // 4. the draft pull request: --draft is hard-coded, there is no --web, no merge and no ready
  const gh = await run('gh', ['pr', 'create', '--repo', cfg.repo, '--draft', '--base', cfg.base, '--head', branch, '--title', p.title, '--body-file', '-'], { cwd: repoRoot, net: true, input: p.body });
  const url = gh.out.trim().split('\n').pop()?.trim() ?? '';
  const m = new RegExp(`^https://github\\.com/${cfg.repo.replace(/[.\\/]/g, '\\$&')}/pull/(\\d+)$`).exec(url);
  if (gh.code !== 0 || !m) { note('gh pr create', false, gh.out); return { ok: false, state: 'branch_pushed', branch, commit, error: `the branch is pushed but the draft pull request was not created: ${scrub(gh.out).trim().slice(0, 240)}`, steps }; }
  note('gh pr create', true, url);
  return { ok: true, state: 'opened', branch, commit, url, number: Number(m[1]), steps };
}

/** The whole human-initiated flow, for the dashboard socket: prepare, ask the human, push + create, record on the convoy. Returns the updated convoy, or what to tell the human. */
export async function requestDraftPr(deps: { store: ConvoyStore; id: string; repoRoot: string; approve: (tool: string, args: Record<string, unknown>, reason: string) => Promise<boolean>; config?: DraftPrConfig; run?: RunFn }): Promise<{ ok: true; convoy: ConvoyRecord } | { ok: false; error: string; convoy?: ConvoyRecord }> {
  const c = deps.store.get(deps.id);
  if (!c) return { ok: false, error: 'no such convoy' };
  const prepared = await prepareDraftPr(c, deps.config ?? draftPrConfig(), deps.repoRoot);
  if (!prepared.ok) return prepared;
  if (!(await deps.approve('open_draft_pr', prepared.display, prepared.reason))) return { ok: false, error: 'declined: nothing was pushed and no pull request was created' };
  const result = await openDraftPr(prepared, deps.repoRoot, deps.run);
  const convoy = result.state && result.branch && result.commit
    ? deps.store.recordDraftPr(c.id, { state: result.state, repo: prepared.cfg.repo, base: prepared.cfg.base, branch: result.branch, commit: result.commit, ...(result.url ? { url: result.url, number: result.number } : {}), ...(result.ok ? {} : { error: result.error }), by: 'human', at: Date.now() })
    : undefined;
  return result.ok ? { ok: true, convoy: convoy! } : { ok: false, error: result.error ?? 'the draft pull request was not opened', ...(convoy ? { convoy } : {}) };
}
