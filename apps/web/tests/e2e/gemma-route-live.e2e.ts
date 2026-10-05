// Opt-in (npm run test:e2e:gemma-route): REAL Chromium, a REAL server on 127.0.0.1:3000 (throwaway data dir, NO Mercury key, so no spend), REAL Ollama, REAL GitHub
// (read-only public API). The model field is left BLANK, so the plan's model comes from the measured routing table. Each goal: plan -> submit -> approve (convoy and
// tool access, clicked by Playwright, not a person) -> wait. Records the routed model, the plan's routing reason, latency, cold/warm and grounding. Only the first goal's
// answer is checked against GitHub's own newest PR; the rest are recorded, not truth-checked. Output: docs/evidence/p3.27-gemma/live-lookups.json
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { writeEvidence } from '../helpers/evidence-file.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const OUT = path.resolve(appDir, '../../docs/evidence/p3.27-gemma');
const REPO = 'Kudbee-Studio/think-box-ai';
const port = 3000; const base = `http://127.0.0.1:${port}`;
const CHAT_GOALS = ['Which pull requests are open?', 'What branches exist?', 'Did the last CI run pass?', 'Are there any open issues?'];
const CONVOY_GOALS = ['What is the last PR?', 'Which pull requests are open?', 'What branches exist?'];
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const log = (s: string) => console.log(`[gemma-route ${new Date().toISOString().slice(11, 19)}] ${s}`);
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-gemma-route-'));
const env: Record<string, string> = { ...process.env as Record<string, string>, PORT: String(port), HOST: '127.0.0.1', INCEPTION_API_KEY: '', INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434', JANUS_BASE_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: 'none', THINKBOX_EMBEDDINGS: 'off', KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_LEARNING_DB: path.join(tmp, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), KUDBEE_REPO: REPO };
delete env.THINKBOX_LOCAL_MODEL; delete env.KUDBEE_LOCAL_MODEL;
try { if ((await fetch(`${base}/api/health`, { signal: AbortSignal.timeout(1500) })).ok) { console.error(`something is already listening on ${base}; refusing to start a second server`); process.exit(2); } } catch { /* free */ }
const server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], { cwd: appDir, stdio: 'ignore', env });
process.on('exit', () => { try { server.kill(); } catch { /* gone */ } fs.rmSync(tmp, { recursive: true, force: true }); });

async function githubNewest(): Promise<number> {
  const r = await fetch(`https://api.github.com/repos/${REPO}/pulls?state=all&sort=created&direction=desc&per_page=1`, { headers: { 'User-Agent': 'kudbee-gemma-route' } });
  return ((await r.json()) as Array<{ number: number }>)[0]!.number;
}

for (let i = 0; i < 120; i++) { try { if ((await fetch(`${base}/api/health`)).ok) break; } catch { /* starting */ } await sleep(250); }
const results: Array<Record<string, unknown>> = []; const consoleErrors: string[] = [];
const approveIfShown = async (page: import('playwright').Page): Promise<void> => { try { if (await page.locator('#approve-approval').isVisible()) await page.click('#approve-approval', { timeout: 2000 }); } catch { /* not shown, or already gone */ } };
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

  // Part A: the dashboard goal box, with qwen2.5:3b selected (what an operator had picked). A lookup must be re-routed to the model the table qualifies.
  for (const goal of CHAT_GOALS) {
    const r: Record<string, unknown> = { path: 'dashboard-chat', goal, selected: 'qwen2.5:3b' }; results.push(r);
    const t0 = Date.now();
    try {
      await page.selectOption('#model-select', 'qwen2.5:3b');
      const before = ((await page.locator('body').innerText()).match(/route: /g) ?? []).length;
      await page.fill('#goal-input', goal);
      await page.click('#run-goal');
      let text = '';
      for (let i = 0; i < 1200; i += 1) {
        await approveIfShown(page);
        text = await page.locator('body').innerText();
        if ((text.match(/route: /g) ?? []).length > before) break;
        await sleep(500);
      }
      const routes = [...text.matchAll(/route: [^\n]+/g)].map((m) => m[0]);
      const tail = text.slice(text.lastIndexOf(goal.toUpperCase().slice(0, 12)) >= 0 ? text.lastIndexOf(goal.toUpperCase().slice(0, 12)) : 0);
      r.route_line = routes.at(-1) ?? null; r.wall_ms = Date.now() - t0;
      r.routed_thought = /Routed to gemma3:4b instead of qwen2\.5:3b/.test(tail);
      r.reason_shown = (tail.match(/Routed to gemma3:4b instead of qwen2\.5:3b: [^\n]+/) ?? [null])[0];
      r.answered_by_gemma = /gemma3:4b/.test(String(r.route_line));
      r.grounded = !/GROUNDING FAILED/.test(tail);
      r.pass = Boolean(r.routed_thought) && Boolean(r.answered_by_gemma) && Boolean(r.grounded);
      log(`${r.pass ? 'PASS' : 'FAIL'} chat "${goal}" ${r.route_line} ${r.wall_ms}ms`);
    } catch (e) { r.pass = false; r.error = String((e as Error).message ?? e).slice(0, 600); log(`FAIL chat "${goal}": ${String(r.error).slice(0, 200)}`); }
  }

  // Part B: the convoy path with the model field blank, so the plan's model comes from the table.
  for (const goal of CONVOY_GOALS) {
    const r: Record<string, unknown> = { path: 'convoy', goal }; results.push(r);
    const t0 = Date.now();
    try {
      await page.click('#convoys-button');
      await page.waitForSelector('#convoy-window', { state: 'visible' });
      await page.fill('#convoy-goal', goal);
      await page.fill('#convoy-model', '');
      await page.click('#convoy-plan');
      await page.waitForSelector('#convoy-detail');
      const id = (await page.locator('.convoy-row-selected').getAttribute('data-convoy-id')) || '';
      r.convoy_id = id;
      const planned = ((await (await fetch(`${base}/api/convoys/${id}`)).json()) as any).convoy;
      r.routing = planned.plan.routing;
      await page.click('#convoy-submit');
      await page.waitForSelector('#convoy-approve');
      await page.click('#convoy-approve');
      for (let i = 0; i < 1200; i += 1) {
        await approveIfShown(page);
        const st = (await page.locator('#convoy-detail .convoy-state').innerText().catch(() => '')) || '';
        if (/COMPLETED|FAILED|PARTIAL/.test(st)) break;
        await sleep(500);
      }
      const d = ((await (await fetch(`${base}/api/convoys/${id}`)).json()) as any).convoy;
      let route: string | null = null;
      for (const run of d.runs ?? []) { const full = (await (await fetch(`${base}/api/runs/${run.id}`)).json()) as any; const ev = (full.events ?? full.run?.events ?? []).map((e: any) => String(e.content ?? '')).find((c: string) => c.startsWith('route:')); if (ev) route = ev; }
      r.state = d.state; r.grounding = d.grounding?.status ?? null; r.final_answer = d.final_answer ?? null; r.worker_model = d.workers?.[0]?.model; r.wall_ms = Date.now() - t0; r.route_line = route; r.cost_usd = d.cost_usd;
      r.routed_by_table = Boolean(r.routing) && (r.routing as any).source === 'measured' && (r.routing as any).model === 'gemma3:4b' && r.worker_model === 'gemma3:4b';
      r.pass = r.routed_by_table === true && /COMPLETED/.test(String(d.state)) && r.grounding === 'GROUNDED';
      if (goal === CONVOY_GOALS[0]) { const n = await githubNewest(); r.github_newest = n; r.answer_names_github_newest = new RegExp(`#${n}\\b`).test(String(d.final_answer ?? '')); r.pass = r.pass === true && r.answer_names_github_newest === true; }
      log(`${r.pass ? 'PASS' : 'FAIL'} convoy "${goal}" model=${r.worker_model} ${route ?? '(no route line)'} ${r.state}/${r.grounding}`);
    } catch (e) { r.pass = false; r.error = String((e as Error).message ?? e).slice(0, 600); log(`FAIL convoy "${goal}": ${String(r.error).slice(0, 200)}`); }
    try { await page.click('.convoy-close', { timeout: 1500 }); } catch { /* window may stay open */ }
  }
} finally { await browser.close(); }
const ok = results.length === CHAT_GOALS.length + CONVOY_GOALS.length && results.every((r) => r.pass === true) && !consoleErrors.length;
await writeEvidence(OUT, path.join(OUT, 'live-lookups.json'), { generated_at: new Date().toISOString(), note: 'real Chromium, real server on 127.0.0.1:3000 (throwaway data, no Mercury key), real Ollama, real GitHub read-only API; clicks by Playwright, not a person; chat goals start with qwen2.5:3b selected, convoy goals leave the model blank; only the first convoy answer is checked against GitHub, the rest are recorded not truth-checked', passed: ok, console_errors: consoleErrors, results });
log(ok ? 'ALL PASS' : 'NOT ALL PASS');
process.exit(ok ? 0 : 1);
