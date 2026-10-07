// Open a DRAFT pull request from what the agent changed in the repository chosen with "use for agent" (Layer 5: runtime). Same rules as the convoy draft PR (draft-pr.ts):
//   - a HUMAN starts it from the dashboard socket (no model, no tool, no HTTP route reaches it), it is OFF unless KUDBEE_DRAFT_PR=on, and it asks the human again naming repository, base, branch and files;
//   - it pushes ONE new branch to the repository's GitHub URL (never `origin`), never force-pushes, and only when the clone is at the tip of the base branch (nothing unpublished is pushed);
//   - the commit is built from a temporary index, so the clone's files, index and branch are not touched (the changes stay visible and can still be undone);
//   - the pull request is created with --draft, hard-coded; it never marks ready and never merges; tokens are scrubbed from anything shown.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { defaultRun, draftPrConfig, scrub, type RunFn } from './draft-pr.ts';
import { listChanges } from './repo-changes.ts';

const BRANCH = /^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$/;
const AGENT = { name: 'kudbEE agent (draft)', email: 'kudbee-agent@users.noreply.github.com' };
const KIND: Record<string, string> = { modified: 'changed', untracked: 'new', added: 'new', deleted: 'deleted', renamed: 'renamed' };

export type AgentPrResult = { ok: true; url: string; branch: string; files: number } | { ok: false; error: string; branch?: string };
export interface AgentPrDeps { root: string | undefined; approve: (tool: string, args: Record<string, unknown>, reason: string) => Promise<boolean>; env?: Record<string, string | undefined>; run?: RunFn; now?: () => Date }

const fail = (error: string, branch?: string): AgentPrResult => ({ ok: false, error: scrub(error).trim().slice(0, 300), ...(branch ? { branch } : {}) });

let inFlight = false;

/** One at a time: a second click while one is being opened is refused. */
export async function openAgentDraftPr(deps: AgentPrDeps): Promise<AgentPrResult> {
  if (inFlight) return fail('A draft pull request is already being opened.');
  inFlight = true;
  try { return await open(deps); } finally { inFlight = false; }
}

async function open(deps: AgentPrDeps): Promise<AgentPrResult> {
  const run = deps.run ?? defaultRun; const env = deps.env ?? process.env;
  const cfg = draftPrConfig(env);
  if (!cfg.enabled) return fail('Draft pull requests are off. Set KUDBEE_DRAFT_PR=on in the server environment and restart to allow them.');
  if (!deps.root) return fail('Choose a repository for the agent first ("Use this repo for the agent").');
  if (!cfg.repo || !cfg.remoteUrl) return fail('This repository has no GitHub address (its origin is not a github.com owner/name), so there is nowhere to open a pull request.');
  const root = deps.root;
  const { files } = await listChanges(root);
  if (!files.length) return fail('There are no changes to open a pull request for.');
  // 1. the clone must be at the tip of the base branch on GitHub, so only the agent's change is published
  const head = (await run('git', ['rev-parse', 'HEAD'], { cwd: root })).out.trim();
  const when = (deps.now?.() ?? new Date()).toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, '').replace('T', '-');
  const branch = `kudbee/fix-${when}`;
  if (!BRANCH.test(branch) || !BRANCH.test(cfg.base)) return fail('The branch or base name is not allowed.');
  const ref = `refs/heads/${branch}`;
  const ls = await run('git', ['ls-remote', cfg.remoteUrl, `refs/heads/${cfg.base}`, ref], { cwd: root, net: true });
  if (ls.code !== 0) return fail(`Could not read the remote: ${ls.out}`);
  const tips = new Map(ls.out.split('\n').map((l) => l.trim().split(/\s+/)).filter((x) => x.length === 2).map(([sha, name]) => [name!, sha!]));
  const baseTip = tips.get(`refs/heads/${cfg.base}`);
  if (baseTip !== head) return fail(`This clone is at ${head.slice(0, 8)} but ${cfg.repo}'s ${cfg.base} is at ${baseTip?.slice(0, 8) ?? '(missing)'}: pull the latest, or clone again, so only your change is published.`);
  if (tips.has(ref)) return fail(`The branch ${branch} already exists on the remote; try again.`);
  // 2. ask the human again, with everything that will leave the machine
  const title = `kudbEE: ${files.slice(0, 3).map((f) => path.basename(f.path)).join(', ')}${files.length > 3 ? ` and ${files.length - 3} more` : ''}`.slice(0, 72);
  const list = files.map((f) => `${KIND[f.status] ?? f.status} ${f.path}`);
  const ok = await deps.approve('open_draft_pr', { repository: cfg.repo, base: cfg.base, branch, files: list.slice(0, 20), file_count: files.length, flags: 'draft only; one new branch; no force; never merged' },
    `Push ${files.length} changed file${files.length === 1 ? '' : 's'} as a new branch ${branch} to github.com/${cfg.repo} and open a DRAFT pull request against ${cfg.base}?`);
  if (!ok) return fail('Not approved: nothing was pushed.');
  // 3. the commit, from a temporary index
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-agent-pr-'));
  const gitEnv = { GIT_INDEX_FILE: path.join(dir, 'index'), GIT_AUTHOR_NAME: AGENT.name, GIT_AUTHOR_EMAIL: AGENT.email, GIT_COMMITTER_NAME: AGENT.name, GIT_COMMITTER_EMAIL: AGENT.email };
  let commit: string;
  try {
    const step = async (args: string[]): Promise<string | null> => { const r = await run('git', args, { cwd: root, env: gitEnv }); return r.code === 0 ? r.out.trim() : null; };
    if (await step(['read-tree', 'HEAD']) === null || await step(['add', '-A']) === null) return fail('Could not prepare the commit.');
    const tree = await step(['write-tree']);
    const made = tree && /^[0-9a-f]{40}$/.test(tree) ? await step(['commit-tree', tree, '-p', head, '-m', title]) : null;
    if (!made || !/^[0-9a-f]{40}$/.test(made)) return fail('Could not create the commit.');
    commit = made;
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
  // 4. push one new branch (no --force), then the draft pull request (--draft is hard-coded)
  const push = await run('git', ['push', cfg.remoteUrl, `${commit}:${ref}`], { cwd: root, net: true });
  if (push.code !== 0) return fail(`The push failed: ${push.out}`);
  const body = `Opened by the kudbEE agent as a **draft**. Review it before merging.\n\n${list.map((l) => `- ${l}`).join('\n')}\n`;
  const gh = await run('gh', ['pr', 'create', '--repo', cfg.repo, '--draft', '--base', cfg.base, '--head', branch, '--title', title, '--body-file', '-'], { cwd: root, net: true, input: body });
  const url = gh.out.trim().split('\n').pop()?.trim() ?? '';
  const repoRe = cfg.repo.replace(/[.\\/]/g, '\\$&');
  if (gh.code !== 0 || !new RegExp(`^https://github\\.com/${repoRe}/pull/\\d+$`).test(url)) return fail(`The branch ${branch} is pushed but the draft pull request was not created: ${gh.out}`, branch);
  return { ok: true, url, branch, files: files.length };
}
