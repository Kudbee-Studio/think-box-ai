// Opt-in: the Convoys window in REAL Chromium against a REAL server with REAL services: real GitHub, real Ollama (qwen2.5:3b), real Mercury.
// (npm run test:e2e:convoy-real). No fakes anywhere. Every click (plan, submit, approve the convoy, approve the tool access) is made through the
// dashboard UI. The clicker is Playwright, not a person: that is the honest limit of this proof. The answer shown in the page is also compared with
// what GitHub itself says is the newest pull request, fetched independently by this script. Spend is capped (ACCEPTANCE_CAP_USD, default $0.05).
// Mercury key comes from the repo .env and is never printed. Output: docs/evidence/model-integration/convoy-real-e2e.json + screenshots.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, type Page } from 'playwright';
import { readTextIfPresent, writeEvidence } from '../helpers/evidence-file.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const repoRoot = path.resolve(appDir, '../..');
const OUT = path.join(repoRoot, 'docs/evidence/model-integration');
const REPO = 'Kudbee-Studio/think-box-ai';
const CAP = process.env.ACCEPTANCE_CAP_USD || '0.05';
const key = process.env.INCEPTION_API_KEY || readTextIfPresent(path.join(repoRoot, '.env')).match(/^INCEPTION_API_KEY=(.+)$/m)?.[1]?.trim().replace(/^["']|["']$/g, '') || '';
if (!key) { console.error('No INCEPTION_API_KEY in the environment or the repo .env'); process.exit(2); }
const MODELS = (process.argv.slice(2).length ? process.argv.slice(2) : ['mercury-2', 'qwen2.5:3b']);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const log = (s: string) => console.log(`[real-e2e ${new Date().toISOString().slice(11, 19)}] ${s}`);
function assert(cond: unknown, msg: string): asserts cond { if (!cond) throw new Error(msg); }

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-real-e2e-'));
const port = 26000 + Math.floor(Math.random() * 8000);
const base = `http://127.0.0.1:${port}`;
const server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
  cwd: appDir, stdio: 'ignore',
  env: { ...process.env, PORT: String(port), INCEPTION_API_KEY: key, INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434', JANUS_BASE_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: 'none', THINKBOX_EMBEDDINGS: 'off',
    KUDBEE_DAILY_BUDGET_USD: CAP, KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_LEARNING_DB: path.join(tmp, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), KUDBEE_REPO: REPO, THINKBOX_LOCAL_MODEL: 'qwen2.5:3b' },
});
process.on('exit', () => { try { server.kill(); } catch { /* gone */ } fs.rmSync(tmp, { recursive: true, force: true }); });

async function shot(page: Page, name: string): Promise<string | undefined> {
  try { await page.screenshot({ path: path.join(OUT, name), animations: 'disabled', timeout: 8000 }); return name; } catch { return undefined; }
}

/** What GitHub itself says is the newest PR right now (independent of the app). */
async function githubNewest(): Promise<{ number: number; state: string }> {
  const r = await fetch(`https://api.github.com/repos/${REPO}/pulls?state=all&sort=created&direction=desc&per_page=1`, { headers: { 'User-Agent': 'kudbee-real-e2e' } });
  const body = (await r.json()) as any[];
  const pr = body[0];
  return { number: pr.number, state: pr.merged_at ? 'merged' : pr.state === 'open' ? (pr.draft ? 'open, draft' : 'open') : 'closed' };
}

async function main() {
  for (let i = 0; i < 100; i++) { try { if ((await fetch(`${base}/api/health`)).ok) break; } catch { /* starting */ } await sleep(150); }
  fs.mkdirSync(OUT, { recursive: true });
  const results: any[] = []; const consoleErrors: string[] = [];
  const browser = await chromium.launch();
  try {
    for (const model of MODELS) {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      ctx.setDefaultTimeout(15000);
      const page = await ctx.newPage();
      page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(`${model}: ${m.text().slice(0, 250)}`); });
      page.on('pageerror', (e) => consoleErrors.push(`${model}: PAGEERROR ${e.message}`.slice(0, 250)));
      await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
      await page.waitForSelector('#goal-input');
      await page.waitForFunction(() => { const s = document.querySelector('#model-select') as HTMLSelectElement | null; return !!s && s.options.length > 1; }, null, { timeout: 20000 });
      const tag = model.replace(/[^a-z0-9]+/gi, '-');
      const t0 = Date.now(); const r: any = { model, steps: [] }; results.push(r);
      try { const step = (s: string, note: string) => { r.steps.push({ step: s, note, at_ms: Date.now() - t0 }); log(`${model}: ${s} - ${note}`); };

      await page.click('#convoys-button');
      await page.waitForSelector('#convoy-window', { state: 'visible' });
      await page.fill('#convoy-goal', 'What is the last PR?');
      await page.fill('#convoy-model', model);
      await page.click('#convoy-plan');
      await page.waitForSelector('#convoy-detail');
      let badge = await page.locator('#convoy-detail .convoy-badge-big').innerText();
      assert(/PLAN ONLY/.test(badge), `badge was "${badge}"`);
      r.plan_badge = badge; r.convoy_id = (await page.locator('.convoy-row-selected').getAttribute('data-convoy-id')) || '';
      r.plan_shot = await shot(page, `real-${tag}-1-plan-only.png`); step('plan', badge);

      await page.click('#convoy-submit');
      await page.waitForSelector('#convoy-approve');
      badge = await page.locator('#convoy-detail .convoy-badge-big').innerText();
      assert(/PENDING APPROVAL/.test(badge), `badge was "${badge}"`);
      r.pending_shot = await shot(page, `real-${tag}-2-pending.png`); step('submit', badge);

      await page.click('#convoy-approve');
      step('approve clicked', 'convoy approved from the dashboard');
      await page.waitForSelector('#approve-approval', { state: 'visible', timeout: 60000 });
      r.tool_approval_text = (await page.locator('#approval-reason').innerText()).slice(0, 200);
      r.tool_approval_shot = await shot(page, `real-${tag}-3-tool-approval.png`);
      await page.click('#approve-approval');
      step('tool approval clicked', r.tool_approval_text);
      await page.waitForFunction(() => /COMPLETED|FAILED|PARTIAL/.test(document.querySelector('#convoy-detail .convoy-state')?.textContent || ''), null, { timeout: 600000 });
      const state = (await page.locator('#convoy-detail .convoy-state').innerText()).trim();
      badge = await page.locator('#convoy-detail .convoy-badge-big').innerText();
      const text = await page.locator('#convoy-detail').innerText();
      r.state = state; r.live_badge = badge; r.wall_ms = Date.now() - t0;
      r.final_shot = await shot(page, `real-${tag}-4-live-result.png`);
      const detail = ((await (await fetch(`${base}/api/convoys/${r.convoy_id}`)).json()) as any).convoy;
      const truth = await githubNewest();
      r.github_newest = truth; r.final_answer = detail.final_answer ?? null; r.grounding = detail.grounding?.status ?? null; r.cost_usd = detail.cost_usd; r.tokens = detail.tokens; r.tool_calls = detail.tool_calls; r.workers = detail.workers.map((w: any) => ({ id: w.id, model: w.model, status: w.status }));
      r.answer_names_github_newest = new RegExp(`#${truth.number}\\b`).test(detail.final_answer ?? '');
      r.evidence_newest = detail.evidence?.[0]?.items?.[0]?.number ?? null;
      r.chain = detail.chain;
      assert(badge === 'LIVE EXECUTION', `badge was "${badge}"`);
      assert(/COMPLETED/.test(state), `convoy ended ${state}: ${detail.error ?? ''}`);
      assert(/GROUNDED/.test(text), 'the page does not show GROUNDED');
      assert(r.evidence_newest === truth.number, `the evidence's newest PR #${r.evidence_newest} differs from GitHub's #${truth.number}`);
      assert(r.answer_names_github_newest, `the answer does not name GitHub's newest PR #${truth.number}: ${detail.final_answer}`);
      step('done', `${state}, ${r.grounding}, answer names #${truth.number}, $${r.cost_usd}`);
      r.status = 'PASS';
      } catch (e) {
        r.status = 'FAIL'; r.error = String((e as Error).message ?? e).slice(0, 1200); log(`FAIL ${model}: ${r.error.slice(0, 300)}`);
        try {
          const d = ((await (await fetch(`${base}/api/convoys/${r.convoy_id}`)).json()) as any).convoy;
          r.detail = d && { state: d.state, outcome: d.outcome, error: d.error, final_answer: d.final_answer, grounding: d.grounding, workers: d.workers?.map((w: any) => ({ id: w.id, model: w.model, status: w.status, answer: w.answer, failure: w.failure, grounding: w.grounding })), evidence: d.evidence?.map((x: any) => ({ recipe: x.recipe, items: x.items?.map((i: any) => ({ number: i.number, state: i.state, head_ref: i.head_ref })) })) };
        } catch { /* no detail */ }
        await shot(page, `real-${tag}-FAIL.png`);
      }
      await ctx.close();
    }
  } finally { await browser.close(); }
  const ok = results.length === MODELS.length && results.every((r) => r.status === 'PASS') && !consoleErrors.length;
  await writeEvidence(OUT, path.join(OUT, 'convoy-real-e2e.json'), { generated_at: new Date().toISOString(), note: 'real Chromium, real server, real GitHub, real Ollama, real Mercury; all clicks through the dashboard UI by Playwright (not a person); spend cap $' + CAP, passed: ok, console_errors: consoleErrors, results });
  log(ok ? 'ALL PASS' : 'FAILED');
  process.exit(ok ? 0 : 1);
}
main().catch((e) => { console.error(e); process.exit(2); });
