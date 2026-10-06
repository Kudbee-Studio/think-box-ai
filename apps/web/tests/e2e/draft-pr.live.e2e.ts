// Opt-in (npm run test:e2e:draft-pr): the pre-registered pass criteria in docs/evidence/p3.43-live-draft-pr/PLAN.md.
// REAL Chromium, a REAL server (random 127.0.0.1 port, throwaway data, never :3000), REAL Mercury (key from the repo .env, never printed or written), a throwaway CLONE of the real
// GitHub repository, and the machine's REAL git and gh logins. The ONLY thing that writes to GitHub is the app, after the Playwright click that approves the draft-PR request: one new
// branch and one DRAFT pull request. This script itself only reads GitHub (ls-remote, clone, `gh api` GET, `gh pr list`). Every click is Playwright acting on the founder's GO, not a person.
// Exit codes: 0 PASS, 1 FAIL, 2 NOT RUN (a precondition failed before anything was written anywhere).
import { execFileSync, spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, type Page } from 'playwright';
import { WebSocket } from 'ws';
import { probeSandbox } from '../../scratch-runner.ts';
import { readTextIfPresent, writeEvidence } from '../helpers/evidence-file.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const repoRoot = path.resolve(appDir, '../..');
const OUT = path.join(repoRoot, 'docs/evidence/p3.43-live-draft-pr');
const REPO = 'Kudbee-Studio/think-box-ai';
const URL = `https://github.com/${REPO}.git`;
const CAP = '0.05';
const FILE = 'docs/scratch-runner-design.md';
const GOAL = "In docs/scratch-runner-design.md, the Status line near the top says slice 4 is '4 (the next PR, below)'. That PR is now merged as #381. Change that phrase to '4 (PR #381, below)' and change nothing else.";
const RUN = process.env.P343_RUN_LABEL || 'run';
const key = process.env.INCEPTION_API_KEY || readTextIfPresent(path.join(repoRoot, '.env')).match(/^INCEPTION_API_KEY=(.+)$/m)?.[1]?.trim().replace(/^["']|["']$/g, '') || '';
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const log = (s: string) => console.log(`[draft-pr ${new Date().toISOString().slice(11, 19)}] ${s}`);
const notRun = (why: string): never => { console.error(`NOT RUN: ${why}`); process.exit(2); };
if (!key) notRun('No INCEPTION_API_KEY in the environment or the repo .env');

const sh = (cmd: string, args: string[], opts: { cwd?: string; input?: string; env?: Record<string, string> } = {}): string =>
  execFileSync(cmd, args, { cwd: opts.cwd, input: opts.input, encoding: 'utf8', env: { ...process.env, ...(opts.env ?? {}) }, stdio: ['pipe', 'pipe', 'pipe'], maxBuffer: 50 * 1024 * 1024 }).trim();
const heads = (): string[] => sh('git', ['ls-remote', '--heads', URL]).split('\n').filter(Boolean).sort();
const newestPr = (): number => Number(JSON.parse(sh('gh', ['pr', 'list', '-R', REPO, '--state', 'all', '--limit', '1', '--json', 'number']))[0]?.number ?? 0);
const openPrs = (): string => sh('gh', ['pr', 'list', '-R', REPO, '--state', 'open', '--limit', '100', '--json', 'number,isDraft']);
const realGit = (...a: string[]): string => sh('git', a, { cwd: repoRoot });
const EXCLUDE = [':(exclude)docs/evidence/p3.43-live-draft-pr'];
const realState = (): string => createHash('sha256').update(realGit('status', '--porcelain', '--', '.', ...EXCLUDE) + realGit('diff', '--', '.', ...EXCLUDE) + realGit('rev-parse', 'HEAD')).digest('hex');
const scratchDirs = (): number => fs.readdirSync(os.tmpdir()).filter((n) => n.startsWith('kudbee-scratch-') || n.startsWith('kudbee-pr-')).length;

// ---- preconditions: nothing is written anywhere until all of these hold ----
const probe = await probeSandbox();
if (!probe.ok) notRun(`sandbox not proven: ${(probe as { reason: string }).reason}`);
try { sh('gh', ['auth', 'status']); } catch { notRun('gh is not logged in'); }
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-draftpr-live-'));
const clone = path.join(tmp, 'clone');
process.on('exit', () => { try { server?.kill(); } catch { /* gone */ } fs.rmSync(tmp, { recursive: true, force: true }); });
let server: ReturnType<typeof spawn> | undefined;
const headsBefore = heads();
const mainTip = headsBefore.find((l) => l.endsWith('\trefs/heads/main'))?.split('\t')[0] ?? '';
if (!/^[0-9a-f]{40}$/.test(mainTip)) notRun('could not read GitHub main');
sh('git', ['clone', '--quiet', URL, clone]);
const cloneHead = sh('git', ['rev-parse', 'HEAD'], { cwd: clone });
if (cloneHead !== mainTip) notRun(`the clone's HEAD ${cloneHead.slice(0, 8)} is not GitHub's main ${mainTip.slice(0, 8)} (main moved while cloning)`);
fs.symlinkSync(path.join(appDir, 'node_modules'), path.join(clone, 'apps/web/node_modules'));
const prBefore = newestPr(); const openBefore = openPrs();
const before = { real: realState(), scratch: scratchDirs() };
log(`preconditions ok: main ${mainTip.slice(0, 8)}, ${headsBefore.length} heads, newest PR #${prBefore}`);

const port = 26000 + Math.floor(Math.random() * 8000);
const base = `http://127.0.0.1:${port}`;
try { if ((await fetch(`${base}/api/health`, { signal: AbortSignal.timeout(1000) })).ok) notRun(`something is already listening on ${base}`); } catch { /* free */ }
server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
  cwd: appDir, stdio: 'ignore',
  env: { ...process.env, PORT: String(port), HOST: '127.0.0.1', INCEPTION_API_KEY: key, INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434', JANUS_BASE_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: '',
    KUDBEE_DAILY_BUDGET_USD: CAP, KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_LEARNING_DB: path.join(tmp, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), KUDBEE_REPO_ROOT: clone, KUDBEE_REPO: REPO, KUDBEE_DRAFT_PR: 'on' },
});
const fetched: string[] = [];
const getJson = async (p: string): Promise<any> => { const t = await (await fetch(`${base}${p}`)).text(); fetched.push(t); return JSON.parse(t); };
for (let i = 0; i < 120; i++) { try { if ((await fetch(`${base}/api/health`)).ok) break; } catch { /* starting */ } await sleep(250); }

const r: Record<string, any> = { prompts: [], steps: [] }; const consoleErrors: string[] = [];
let modalShot: string | null = null; let detailShot: string | null = null;
const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  ctx.setDefaultTimeout(20000);
  const page: Page = await ctx.newPage();
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 250)); });
  page.on('pageerror', (e) => consoleErrors.push(`PAGEERROR ${e.message}`.slice(0, 250)));
  await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
  await page.waitForSelector('#goal-input');
  await page.waitForFunction(() => { const sel = document.querySelector('#model-select') as HTMLSelectElement | null; return !!sel && [...sel.options].some((o) => o.value === 'mercury-2'); }, null, { timeout: 30000 });

  await page.click('#convoys-button');
  await page.waitForSelector('#convoy-window', { state: 'visible' });
  await page.fill('#convoy-goal', GOAL); await page.fill('#convoy-model', '');
  await page.check('#convoy-mode-simulate');
  const seen = new Set<string>(((await getJson('/api/convoys')).convoys ?? []).map((c: any) => c.id));
  await page.click('#convoy-plan');
  let id = '';
  for (let i = 0; i < 80 && !id; i += 1) { id = ((await getJson('/api/convoys')).convoys ?? []).find((c: any) => !seen.has(c.id) && c.goal === GOAL)?.id ?? ''; if (!id) await sleep(250); }
  if (!id) throw new Error('the plan did not create a convoy');
  r.convoy_id = id;
  await page.waitForSelector(`.convoy-row-selected[data-convoy-id="${id}"]`);
  await page.click('#convoy-submit'); await page.waitForSelector('#convoy-approve'); await page.click('#convoy-approve');

  // ---- phase 1: the sandbox run (approve it); phase 2: after the review, the draft-PR request (deny once, then approve) ----
  let draftClicks = 0; let denied = false; let phase: 'run' | 'draft' = 'run';
  const handleModal = async (): Promise<void> => {
    if (!(await page.locator('#approval-modal').isVisible().catch(() => false))) return;
    const reason = (await page.locator('#approval-reason').innerText()).trim(); const args = (await page.locator('#approval-args').innerText()).trim();
    fetched.push(reason, args);
    const isDraft = /DRAFT pull request/.test(reason);
    r.prompts.push({ kind: isDraft ? 'draft_pr' : 'run_checks', reason, args_preview: args.slice(0, 700) });
    const deny = isDraft && !denied;
    if (isDraft && !modalShot) { modalShot = 'p3.43-draft-pr-approval-modal.png'; try { await page.screenshot({ path: path.join(OUT, `${RUN}-${modalShot}`), animations: 'disabled', timeout: 8000 }); } catch { modalShot = null; } }
    if (deny) { denied = true; r.headsBeforeDeny = heads(); r.prBeforeDeny = openPrs(); }
    await page.click(deny ? '#deny-approval' : '#approve-approval', { timeout: 3000 }).catch(() => undefined);
    await sleep(400);
    if (deny) { await sleep(4000); r.headsAfterDeny = heads(); r.prAfterDeny = openPrs(); }
  };
  for (let i = 0; i < 1800; i += 1) {
    await handleModal();
    const st = (await page.locator('#convoy-detail .convoy-state').innerText().catch(() => '')) || '';
    if (/COMPLETED|FAILED|PARTIAL/.test(st)) break;
    await sleep(500);
  }
  let d = (await getJson(`/api/convoys/${id}`)).convoy;
  r.state = d.state; r.outcome = d.outcome; r.error = d.error ?? null; r.cost_usd = d.cost_usd; r.final_answer = String(d.final_answer ?? '').slice(0, 900);
  const sim = d.simulation ?? null;
  r.simulation = sim ? { sha: sim.sha, proposed_by: sim.proposed_by, summary: sim.summary, files: sim.files, flags: sim.flags, patch_sha256: sim.patch_sha256, patch: sim.patch, checks_ran: sim.checks_ran, verified: sim.verified, report_checks: sim.report?.checks?.map((c: any) => [c.check, c.passed, c.tests ?? null]) ?? null } : null;
  r.before_accept = { draft_pr_available: d.draft_pr_available, draft_pr_reason: d.draft_pr_reason, button_count: await page.locator('#convoy-open-draft-pr').count() };
  if (d.state === 'COMPLETED' && sim?.verified === true) {
    phase = 'draft'; void phase;
    await page.click('#convoy-accept'); r.steps.push('accepted the review');
    for (let i = 0; i < 40; i += 1) { d = (await getJson(`/api/convoys/${id}`)).convoy; if (d.review?.state === 'accepted') break; await sleep(250); }
    await page.waitForSelector('#convoy-open-draft-pr', { state: 'visible', timeout: 15000 });
    r.after_accept = { review: d.review?.state, draft_pr_available: d.draft_pr_available, button_count: await page.locator('#convoy-open-draft-pr').count() };
    for (let attempt = 0; attempt < 2; attempt += 1) {
      await page.click('#convoy-open-draft-pr'); draftClicks += 1; r.steps.push(`clicked Open a draft PR (${draftClicks})`);
      for (let i = 0; i < 60 && !(await page.locator('#approval-modal').isVisible().catch(() => false)); i += 1) await sleep(250);
      await handleModal();
      if (attempt === 0) { await sleep(1000); await page.waitForSelector('#convoy-open-draft-pr', { state: 'visible', timeout: 15000 }); }
    }
    try { await page.waitForSelector('#convoy-draft-link', { timeout: 90000 }); } catch { /* recorded below */ }
    r.link = await page.locator('#convoy-draft-link').getAttribute('href').catch(() => null);
    if (r.link) { detailShot = 'p3.43-convoy-detail.png'; try { await page.locator('#convoy-draft-link').scrollIntoViewIfNeeded(); await page.screenshot({ path: path.join(OUT, `${RUN}-${detailShot}`), animations: 'disabled', timeout: 8000 }); } catch { detailShot = null; } }
  }
  d = (await getJson(`/api/convoys/${id}`)).convoy; r.draft_pr_record = d.draft_pr ?? null;
  log(`convoy ${r.state}/${r.outcome} verified=${sim?.verified} link=${r.link} cost=$${d.cost_usd}`);
} catch (e) { r.exception = String((e as Error).message ?? e).slice(0, 500); log(`ERROR ${r.exception}`); }
finally { await browser.close(); }

// ---- independent verification: GitHub's API and git plumbing, not the app's records ----
const headsAfter = heads(); r.headsAfter = headsAfter;
const added = headsAfter.filter((l) => !headsBefore.includes(l)); const removed = headsBefore.filter((l) => !headsAfter.includes(l));
const prNum = Number(/\/pull\/(\d+)$/.exec(String(r.link ?? ''))?.[1] ?? 0);
let api: any = null; let apiFiles: any[] = []; let treeOk = false; let parentOk = false; let authorOk = false; let secondRefused = false; let secondNoNewRef = false;
const branch = String(r.draft_pr_record?.branch ?? '');
if (prNum) {
  const t = sh('gh', ['api', `repos/${REPO}/pulls/${prNum}`]); fetched.push(t); api = JSON.parse(t);
  const f = sh('gh', ['api', `repos/${REPO}/pulls/${prNum}/files`]); fetched.push(f); apiFiles = JSON.parse(f);
}
if (branch && r.simulation?.sha) {
  try {
    sh('git', ['fetch', '--quiet', URL, `refs/heads/${branch}:refs/remotes/live/branch`], { cwd: clone });
    const commit = sh('git', ['rev-parse', 'refs/remotes/live/branch'], { cwd: clone });
    parentOk = sh('git', ['rev-list', '--parents', '-n', '1', commit], { cwd: clone }) === `${commit} ${r.simulation.sha}`;
    authorOk = sh('git', ['log', '-1', '--format=%an <%ae>', commit], { cwd: clone }) === 'kudbEE agent (draft) <kudbee-agent@users.noreply.github.com>';
    const idx = path.join(tmp, 'verify.index'); const env = { GIT_INDEX_FILE: idx };
    sh('git', ['read-tree', r.simulation.sha], { cwd: clone, env }); sh('git', ['apply', '--cached', '--whitespace=nowarn', '-'], { cwd: clone, env, input: r.simulation.patch });
    treeOk = sh('git', ['write-tree'], { cwd: clone, env }) === sh('git', ['rev-parse', `${commit}^{tree}`], { cwd: clone });
  } catch (e) { r.verify_error = String((e as Error).message).slice(0, 300); }
  // a second request for the same convoy must be refused, and must add no ref
  const refsBeforeSecond = heads();
  const msgs: any[] = [];
  await new Promise<void>((resolve) => {
    const ws = new WebSocket(`${base.replace('http', 'ws')}/ws`, { origin: base }); const t = setTimeout(() => { ws.close(); resolve(); }, 8000);
    ws.on('message', (raw) => { const m = JSON.parse(raw.toString()); msgs.push(m); if (m.type === 'init') ws.send(JSON.stringify({ type: 'convoy_open_draft_pr', id: r.convoy_id })); if (m.type === 'convoy_error') { clearTimeout(t); ws.close(); resolve(); } });
    ws.on('error', () => { clearTimeout(t); resolve(); });
  });
  const err = msgs.find((m) => m.type === 'convoy_error' && m.data.id === r.convoy_id);
  secondRefused = Boolean(err && /already opened/.test(err.data.error) && !msgs.some((m) => m.type === 'approval_request'));
  secondNoNewRef = JSON.stringify(heads()) === JSON.stringify(refsBeforeSecond);
  r.second_request = err?.data?.error ?? null;
}
const prompt = (k: string) => r.prompts.filter((p: any) => p.kind === k);
const dp = r.prompts.filter((p: any) => p.kind === 'draft_pr');
const sim = r.simulation;
const criteria = {
  c1_preconditions: true, // reaching this line means: sandbox proven, gh logged in, clone HEAD == GitHub main (else exit 2 before the server started)
  c2_verified_before_offer: r.state === 'COMPLETED' && r.outcome === 'success' && sim?.verified === true && sim.report_checks?.length === 4 && sim.report_checks.every((c: any) => c[1] === true) && JSON.stringify(sim.files) === JSON.stringify([FILE]) && sim.flags.length === 0
    && r.before_accept?.button_count === 0 && r.before_accept?.draft_pr_available === false && r.after_accept?.button_count === 1 && r.after_accept?.draft_pr_available === true,
  c3_denied_creates_nothing: Boolean(r.headsBeforeDeny) && JSON.stringify(r.headsBeforeDeny) === JSON.stringify(r.headsAfterDeny) && JSON.stringify(headsBefore) === JSON.stringify(r.headsBeforeDeny) && r.prBeforeDeny === r.prAfterDeny && r.prBeforeDeny === openBefore,
  c4_prompt_content: dp.length === 2 && dp.every((p: any) => p.reason.includes(REPO) && p.reason.includes('base main') && new RegExp(`new branch kudbee/sim-${String(r.convoy_id).slice(0, 8)}-${String(sim?.patch_sha256).slice(0, 8)}\\)`).test(p.reason) && p.reason.includes(String(sim?.patch_sha256).slice(0, 12)) && p.reason.includes(FILE) && /never merges/.test(p.reason)),
  c5_exactly_one_ref_added: added.length === 1 && removed.length === 0 && added[0]!.endsWith(`\trefs/heads/${branch}`) && /^kudbee\/sim-[0-9a-f]{8}-[0-9a-f]{8}$/.test(branch) && headsAfter.find((l) => l.endsWith('\trefs/heads/main'))?.split('\t')[0] === mainTip,
  c6_pull_request_on_github: Boolean(api) && prNum === prBefore + 1 && api.draft === true && api.state === 'open' && api.merged === false && api.base?.ref === 'main' && api.head?.ref === branch && api.head?.repo?.full_name === REPO && api.commits === 1 && api.changed_files === 1
    && apiFiles.length === 1 && apiFiles[0].filename === FILE && String(api.title).startsWith('kudbEE: ') && String(api.body).includes(String(sim?.patch_sha256).slice(0, 12)) && /the model's summary \(its words, not a verdict\)/i.test(String(api.body)) && /not proof/.test(String(api.body)),
  c7_commit_is_what_was_verified: parentOk && treeOk && authorOk,
  c8_nothing_else_changed: r.draft_pr_record?.state === 'opened' && r.draft_pr_record?.url === r.link && secondRefused && secondNoNewRef && realState() === before.real && scratchDirs() === before.scratch
    && !fetched.some((t) => t.includes(key) || /\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b/.test(t)) && consoleErrors.length === 0 && Number(r.cost_usd) <= Number(CAP) && port !== 3000,
  c9_screenshots: Boolean(modalShot) && Boolean(detailShot),
};
void prompt;
const verdict = Object.values(criteria).every(Boolean) ? 'PASS' : 'FAIL';
await writeEvidence(OUT, path.join(OUT, `${RUN}-live.json`), {
  generated_at: new Date().toISOString(), note: 'real Chromium, real server on a random 127.0.0.1 port (throwaway data), real Mercury, a throwaway clone of the real repository, the machine\'s real git and gh logins; clicks by Playwright acting on the founder\'s GO, not a person',
  plan: 'docs/evidence/p3.43-live-draft-pr/PLAN.md', github_main_at_start: mainTip, newest_pr_before: prBefore, heads_added: added, heads_removed: removed, pull_request: api ? { number: api.number, url: api.html_url, draft: api.draft, state: api.state, merged: api.merged, base: api.base?.ref, head: api.head?.ref, commits: api.commits, changed_files: api.changed_files, title: api.title, body: api.body, user: api.user?.login } : null,
  independent: { parentOk, treeOk, authorOk, secondRefused, secondNoNewRef, files: apiFiles.map((f) => f.filename) }, criteria, verdict, console_errors: consoleErrors, screenshots: [modalShot, detailShot].filter(Boolean).map((s) => `${RUN}-${s}`), result: r,
});
log(`verdict ${verdict} ${JSON.stringify(criteria)}`);
process.exit(verdict === 'PASS' ? 0 : 1);
