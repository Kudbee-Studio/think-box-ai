// Opt-in (npm run test:e2e:escalation-convoy): the pre-registered pass criteria in docs/evidence/p3.36-live-escalation/PLAN.md.
// REAL Chromium, a REAL server (random 127.0.0.1 port, throwaway data, never :3000), REAL Ollama (qwen2.5:3b), REAL Mercury (key from the repo .env, never printed or
// written), the fixture repository of the P3.34 held-out world. Every click (plan, submit, approve) is made through the dashboard UI by Playwright, not a person.
// Output: docs/evidence/p3.36-live-escalation/live-convoys.json and one screenshot of the first escalated convoy.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, type Page } from 'playwright';
import { HELD2_GOALS, HELD2_MODULES, startHeld2World } from '../helpers/ab-fixture.ts';
import { readTextIfPresent, writeEvidence } from '../helpers/evidence-file.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const repoRoot = path.resolve(appDir, '../..');
const OUT = path.join(repoRoot, 'docs/evidence/p3.36-live-escalation');
const CAP = '0.05';
const key = process.env.INCEPTION_API_KEY || readTextIfPresent(path.join(repoRoot, '.env')).match(/^INCEPTION_API_KEY=(.+)$/m)?.[1]?.trim().replace(/^["']|["']$/g, '') || '';
if (!key) { console.error('No INCEPTION_API_KEY in the environment or the repo .env'); process.exit(2); }
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const log = (s: string) => console.log(`[escalation-convoy ${new Date().toISOString().slice(11, 19)}] ${s}`);

const mod = (i: number) => HELD2_MODULES[i]!;
const constantGoal = (i: number) => ({ id: `constant-${mod(i).file}`, goal: `Which file defines CAP_${i + 1} and what is its value?`, shape: 'constant' as const,
  check: (f: any) => Boolean(f?.found) && f.file === `src/${mod(i).file}.ts` && new RegExp(`\\b${(i + 3) * 7}\\b`).test(String(f.quote ?? '')) });
const GOALS = [
  ...HELD2_GOALS.slice(0, 3).map((g, i) => ({ id: g.id, goal: g.goal, shape: 'untested' as const, check: (f: any) => Boolean(f?.found) && f.file === `src/${mod(i).file}.ts` && String(f.quote ?? '').includes(mod(i).untested) })),
  constantGoal(2), constantGoal(7),
  { id: 'missing-dissolveQuasar', goal: 'Find a function named dissolveQuasar.', shape: 'missing' as const, check: (f: any) => f?.found === false },
];

const world = await startHeld2World();
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-esc-convoy-'));
const port = 26000 + Math.floor(Math.random() * 8000);
const base = `http://127.0.0.1:${port}`;
try { if ((await fetch(`${base}/api/health`, { signal: AbortSignal.timeout(1000) })).ok) { console.error(`something is already listening on ${base}`); process.exit(2); } } catch { /* free */ }
const server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
  cwd: appDir, stdio: 'ignore',
  env: { ...process.env, PORT: String(port), HOST: '127.0.0.1', INCEPTION_API_KEY: key, INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434', JANUS_BASE_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: '',
    KUDBEE_DAILY_BUDGET_USD: CAP, KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_LEARNING_DB: path.join(tmp, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), KUDBEE_REPO_ROOT: world.root, KUDBEE_REPO: 'Acme/widgets' },
});
process.on('exit', () => { try { server.kill(); } catch { /* gone */ } fs.rmSync(tmp, { recursive: true, force: true }); });

const fetched: string[] = []; // every API response text and page text, searched for the key at the end
const getJson = async (p: string): Promise<any> => { const t = await (await fetch(`${base}${p}`)).text(); fetched.push(t); return JSON.parse(t); };
const approveIfShown = async (page: Page): Promise<void> => { try { if (await page.locator('#approve-approval').isVisible()) await page.click('#approve-approval', { timeout: 2000 }); } catch { /* not shown */ } };

for (let i = 0; i < 120; i++) { try { if ((await fetch(`${base}/api/health`)).ok) break; } catch { /* starting */ } await sleep(250); }
const results: Array<Record<string, any>> = []; const consoleErrors: string[] = [];
let shotName: string | null = null;
const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  ctx.setDefaultTimeout(20000);
  const page = await ctx.newPage();
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 250)); });
  page.on('pageerror', (e) => consoleErrors.push(`PAGEERROR ${e.message}`.slice(0, 250)));
  await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
  await page.waitForSelector('#goal-input');
  await page.waitForFunction(() => { const sel = document.querySelector('#model-select') as HTMLSelectElement | null; return !!sel && [...sel.options].some((o) => o.value === 'qwen2.5:3b'); }, null, { timeout: 30000 });

  for (const g of GOALS) {
    const r: Record<string, any> = { goal_id: g.id, goal: g.goal, shape: g.shape }; results.push(r);
    const t0 = Date.now();
    try {
      await page.click('#convoys-button');
      await page.waitForSelector('#convoy-window', { state: 'visible' });
      await page.fill('#convoy-goal', g.goal);
      await page.fill('#convoy-model', '');
      await page.click('#convoy-plan');
      await page.waitForSelector('#convoy-detail');
      const id = (await page.locator('.convoy-row-selected').getAttribute('data-convoy-id')) || '';
      r.convoy_id = id;
      const planned = (await getJson(`/api/convoys/${id}`)).convoy;
      r.plan = { kind: planned.plan.workers[0]?.kind, model: planned.plan.workers[0]?.model, routing: planned.plan.routing, escalation: planned.plan.escalation, executable: planned.plan.executable, blocked: planned.plan.blocked_reasons };
      await page.click('#convoy-submit');
      await page.waitForSelector('#convoy-approve');
      await page.click('#convoy-approve');
      for (let i = 0; i < 1200; i += 1) {
        await approveIfShown(page);
        const st = (await page.locator('#convoy-detail .convoy-state').innerText().catch(() => '')) || '';
        if (/COMPLETED|FAILED|PARTIAL/.test(st)) break;
        await sleep(500);
      }
      const d = (await getJson(`/api/convoys/${id}`)).convoy;
      const w0 = d.workers[0]; const w1 = d.workers.find((w: any) => w.id === 'escalation-1');
      r.state = d.state; r.outcome = d.outcome; r.grounding = d.grounding?.status ?? null; r.cost_usd = d.cost_usd; r.wall_ms = Date.now() - t0;
      r.workers = d.workers.map((w: any) => ({ id: w.id, model: w.model, status: w.status, cost_usd: w.cost_usd, grounding: w.grounding?.status ?? null, failure: w.failure?.kind ?? null, answer: String(w.answer ?? '').slice(0, 120) }));
      r.finding = d.finding ? { found: d.finding.found, file: d.finding.file, line: d.finding.line } : null; r.finding_check = d.finding_check ?? null; r.run_ids = d.run_ids;
      r.machine_check = g.check(d.finding); r.final_answer = String(d.final_answer ?? '').slice(0, 160);
      r.escalated = Boolean(w1);
      // the first worker's reason, from its own record
      const first = w0; const expectsFinding = g.shape !== 'missing';
      r.first_worker_reason = first.status === 'failed' ? `failed: ${first.failure?.kind}` : first.grounding?.status !== 'GROUNDED' ? 'not grounded' : String(first.answer).startsWith('No finding') && expectsFinding ? 'no finding where one is expected' : 'accepted';
      const escalationEvents: string[] = [];
      if (w1) { const full = await getJson(`/api/runs/${w1.run_id}`); const evs = (full.events ?? full.run?.events ?? full.steps ?? full.run?.steps ?? []) as any[]; for (const e of evs) escalationEvents.push(String(e.content ?? '')); r.escalation_run_has_spend_line = escalationEvents.some((c) => /^spend: \$\d/.test(c)); r.escalation_run_model = full.model ?? full.run?.model ?? null; }
      const text = await page.locator('body').innerText(); fetched.push(text);
      r.page_shows_escalation_worker = /Escalation to mercury-2/.test(text);
      if (r.escalated && !shotName) { shotName = 'p3.36-escalated-convoy.png'; try { await page.screenshot({ path: path.join(OUT, shotName), animations: 'disabled', timeout: 8000 }); } catch { shotName = null; } }
      // criteria
      const c1 = r.plan.escalation?.model === 'mercury-2' && r.plan.executable === true;
      const c2 = r.state === 'COMPLETED' && r.grounding === 'GROUNDED' && r.machine_check === true;
      const c3 = !r.escalated || (w1.model === 'mercury-2' && w1.cost_usd > 0 && d.run_ids.length === 2 && r.first_worker_reason !== 'accepted' && r.escalation_run_has_spend_line === true);
      const c4 = r.escalated || (w0.status === 'completed' && w0.grounding?.status === 'GROUNDED' && w0.cost_usd === 0 && (d.finding?.found === true || g.shape === 'missing'));
      r.criteria = { c1_plan_names_escalation: c1, c2_completed_grounded_correct: c2, c3_escalated_ok: c3, c4_not_escalated_ok: c4 };
      r.pass = c1 && c2 && c3 && c4;
      log(`${r.pass ? 'PASS' : 'FAIL'} ${g.id} escalated=${r.escalated} first=${r.first_worker_reason} state=${r.state}/${r.grounding} cost=$${d.cost_usd} ${r.wall_ms}ms`);
    } catch (e) { r.pass = false; r.error = String((e as Error).message ?? e).slice(0, 600); log(`FAIL ${g.id}: ${String(r.error).slice(0, 200)}`); }
    try { await page.click('.convoy-close', { timeout: 1500 }); } catch { /* window may stay open */ }
  }
} finally { await browser.close(); }

const escalatedCount = results.filter((r) => r.escalated).length;
const totalCost = results.reduce((t, r) => t + (Number(r.cost_usd) || 0), 0);
const keyLeaked = fetched.some((t) => t.includes(key));
const criteria = {
  c1_to_c4_every_convoy: results.length === GOALS.length && results.every((r) => r.pass === true),
  c5_at_least_two_escalated: escalatedCount >= 2,
  c6_cost_within_cap: totalCost <= Number(CAP), c6_key_never_seen: !keyLeaked, c6_no_console_errors: consoleErrors.length === 0,
  c7_screenshot_saved: Boolean(shotName),
};
const verdict = !criteria.c1_to_c4_every_convoy || !criteria.c6_cost_within_cap || !criteria.c6_key_never_seen || !criteria.c6_no_console_errors || !criteria.c7_screenshot_saved ? 'FAIL' : criteria.c5_at_least_two_escalated ? 'PASS' : 'INCONCLUSIVE (fewer than 2 convoys escalated)';
await writeEvidence(OUT, path.join(OUT, 'live-convoys.json'), { generated_at: new Date().toISOString(), note: 'real Chromium, real server on a random 127.0.0.1 port (throwaway data), real Ollama qwen2.5:3b, real Mercury, fixture repository; clicks by Playwright, not a person', plan: 'docs/evidence/p3.36-live-escalation/PLAN.md', world_hash_note: 'P3.34 held-out world', escalated_count: escalatedCount, total_cost_usd: Number(totalCost.toFixed(6)), criteria, verdict, console_errors: consoleErrors, screenshot: shotName, results });
await world.close();
log(`verdict ${verdict}; escalated ${escalatedCount}/${GOALS.length}; cost $${totalCost.toFixed(4)}`);
process.exit(verdict === 'PASS' ? 0 : 1);
