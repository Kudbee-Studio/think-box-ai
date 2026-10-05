// Opt-in live-browser verification of the Convoys window (npm run test:e2e:convoy). Real server.ts, real Chromium at 1440 and 390 px.
// Fake GitHub + fake Ollama + scripted Mercury stand-in (no provider contacted, $0). Proves in a REAL browser: PLAN ONLY is unmistakable and
// runs nothing, submit queues PENDING, approving goes through the dashboard, the tool approval is shown, LIVE EXECUTION runs real workers through the
// governed tool, ONE convoy row with drill-down (runs -> tools -> evidence), and GROUNDING FAILED is shown as a failure.
// Writes docs/evidence/model-integration/convoy-e2e.json + screenshots. Needs Chromium (see the P3.21 evidence README).
import { spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, type Page } from 'playwright';
import { call, say, startMockInception, type MockInception } from '../helpers/mock-inception.ts';
import { writeEvidence } from '../helpers/evidence-file.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const OUT = path.resolve(appDir, '../../docs/evidence/model-integration');
const QWEN = 'qwen2.5:3b';
const VIEWPORTS = [{ name: '1440', width: 1440, height: 900 }, { name: '390', width: 390, height: 844 }];
const pr = (n: number, o: Record<string, unknown> = {}) => ({ number: n, title: `PR ${n}`, state: 'closed', merged_at: '2026-10-04T10:00:00Z', draft: false, user: { login: 'dev' }, head: { ref: `feat/pr${n}` }, updated_at: '2026-10-04T10:00:00Z', html_url: `https://github.com/Acme/widgets/pull/${n}`, ...o });
type Result = { viewport: string; step: string; status: 'PASS' | 'FAIL'; note: string; screenshot?: string };
const results: Result[] = []; const consoleErrors: string[] = [];
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const log = (s: string) => console.log(`[convoy-e2e ${new Date().toISOString().slice(11, 19)}] ${s}`);
function assert(cond: unknown, msg: string): asserts cond { if (!cond) throw new Error(msg); }

let mock: MockInception; let ollama: http.Server; let github: http.Server; let server: ChildProcess; let base = ''; let tmp = '';
let githubHits = 0; let ollamaChats = 0; let qwenScript: any[] = [];

async function start() {
  mock = await startMockInception();
  ollama = http.createServer((req, res) => {
    let b = ''; req.on('data', (d) => { b += d; });
    req.on('end', () => {
      res.setHeader('content-type', 'application/json');
      if (req.url === '/api/tags') return void res.end(JSON.stringify({ models: [{ name: QWEN, size: 1 }] }));
      if (req.url === '/api/show') return void res.end(JSON.stringify({ capabilities: ['completion', 'tools'] }));
      if (req.url === '/api/chat') { ollamaChats += 1; const n = qwenScript.shift(); if (!n) { res.statusCode = 500; return void res.end('{"error":"script exhausted"}'); } return void res.end(JSON.stringify({ ...n, done: true })); }
      res.statusCode = 404; res.end('{}');
    });
  });
  github = http.createServer((_req, res) => { githubHits += 1; res.setHeader('content-type', 'application/json'); res.end(JSON.stringify([pr(361), pr(360, { merged_at: null, state: 'open', draft: true })])); });
  await Promise.all([new Promise<void>((r) => ollama.listen(0, '127.0.0.1', r)), new Promise<void>((r) => github.listen(0, '127.0.0.1', r))]);
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-convoy-e2e-'));
  const port = 24000 + Math.floor(Math.random() * 10000);
  base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir, stdio: 'ignore',
    env: { ...process.env, PORT: String(port), INCEPTION_API_KEY: 'e2e-key', INCEPTION_API_KEY_2: '', INCEPTION_BASE_URL: mock.baseUrl, OLLAMA_BASE_URL: `http://127.0.0.1:${(ollama.address() as { port: number }).port}`,
      KUDBEE_GITHUB_API: `http://127.0.0.1:${(github.address() as { port: number }).port}`, KUDBEE_REPO: 'Acme/widgets', JANUS_BASE_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: 'none',
      THINKBOX_EMBEDDINGS: 'off', KUDBEE_DAILY_BUDGET_USD: '0', KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_LEARNING_DB: path.join(tmp, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), THINKBOX_LOCAL_MODEL: QWEN },
  });
  for (let i = 0; i < 100; i++) { try { if ((await fetch(`${base}/api/health`)).ok) return; } catch { /* starting */ } await sleep(150); }
  throw new Error('server did not start');
}

async function shot(page: Page, file: string): Promise<string | undefined> {
  try { await page.screenshot({ path: path.join(OUT, file), animations: 'disabled', timeout: 8000 }); return file; } catch { return undefined; }
}
async function step(vp: string, name: string, page: Page, fn: () => Promise<string>): Promise<void> {
  let status: Result['status'] = 'PASS'; let note = '';
  try { note = await fn(); } catch (e) { status = 'FAIL'; note = String((e as Error).message ?? e).replace(/\x1b\[[0-9;]*m/g, '').slice(0, 1500); }
  const screenshot = await shot(page, `convoy-${vp}-${name.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}.png`);
  results.push({ viewport: vp, step: name, status, note, screenshot });
  log(`${status} ${vp}px ${name}${status === 'FAIL' ? ` - ${note}` : ''}`);
}
const runsCount = async () => ((await (await fetch(`${base}/api/runs?children=1`)).json()) as any).runs.length as number;
const badge = (page: Page) => page.locator('#convoy-detail .convoy-badge-big').innerText();
const nativeCall = (args: unknown) => ({ message: { role: 'assistant', content: '', tool_calls: [{ function: { name: 'live_lookup', arguments: args } }] }, prompt_eval_count: 100, eval_count: 10 });
const nativeSay = (content: string) => ({ message: { role: 'assistant', content }, prompt_eval_count: 120, eval_count: 20 });

async function plan(page: Page, goal: string) {
  await page.fill('#convoy-goal', goal);
  await page.fill('#convoy-model', QWEN);
  await page.click('#convoy-plan');
  await page.waitForSelector('#convoy-detail', { timeout: 8000 });
}
async function approveToolIfAsked(page: Page) {
  await page.waitForSelector('#approve-approval', { state: 'visible', timeout: 15000 });
  await page.click('#approve-approval');
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  await start();
  const browser = await chromium.launch();
  try {
    for (const vp of VIEWPORTS) {
      const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
      ctx.setDefaultTimeout(8000);
      const page = await ctx.newPage();
      page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(`${vp.name}: ${m.text().slice(0, 250)}`); });
      page.on('pageerror', (e) => consoleErrors.push(`${vp.name}: PAGEERROR ${e.message}`.slice(0, 250)));
      await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
      await page.waitForSelector('#goal-input', { timeout: 15000 });
      await page.waitForFunction(() => { const s = document.querySelector('#model-select') as HTMLSelectElement | null; return !!s && s.options.length > 0 && s.options[0].value !== ''; }, null, { timeout: 15000 });
      let convoyId = '';

      await step(vp.name, 'a plan only', page, async () => {
        const before = { runs: await runsCount(), github: githubHits, ollama: ollamaChats, mercury: mock.requests.length };
        await page.click('#convoys-button');
        await page.waitForSelector('#convoy-window', { state: 'visible' });
        await plan(page, 'What is the last PR?');
        const b = await badge(page);
        assert(/PLAN ONLY/.test(b) && /NOTHING HAS RUN/.test(b), `badge was "${b}"`);
        assert(!/LIVE/.test(b), 'a plan must never say LIVE');
        assert((await page.locator('#convoy-approve').count()) === 0, 'a plan has no approve button');
        assert((await page.locator('#convoy-submit').count()) === 1, 'a plan offers Submit for approval');
        const text = await page.locator('#convoy-detail').innerText();
        for (const must of ['Live lookup', QWEN, 'live_lookup', 'read_only', 'Worker budget', 'Fallback: mercury-2', 'Expected: 1 dashboard row', 'A human must approve', 'risk low']) assert(text.toLowerCase().includes(must.toLowerCase()), `plan view lacks "${must}"`);
        convoyId = (await page.locator('.convoy-row-selected').getAttribute('data-convoy-id')) || '';
        assert(convoyId, 'the new convoy is listed and selected');
        await sleep(300);
        assert(await runsCount() === before.runs && githubHits === before.github && ollamaChats === before.ollama && mock.requests.length === before.mercury, 'planning ran something');
        return `badge "${b}"; no worker, model, network or run record was created`;
      });

      await step(vp.name, 'b queued approval', page, async () => {
        const before = { runs: await runsCount(), github: githubHits, ollama: ollamaChats };
        await page.click('#convoy-submit');
        await page.waitForSelector('#convoy-approve', { timeout: 8000 });
        const b = await badge(page);
        assert(/PENDING APPROVAL/.test(b) && /NOTHING RUNS YET/.test(b), `badge was "${b}"`);
        const text = await page.locator('#convoy-detail').innerText();
        assert(/Approval · PENDING/i.test(text) && text.includes('expires'), 'approval section shows PENDING and an expiry');
        await sleep(300);
        assert(await runsCount() === before.runs && githubHits === before.github && ollamaChats === before.ollama, 'execution started while pending');
        return `badge "${b}"; approval PENDING with expiry; execution blocked`;
      });

      await step(vp.name, 'c live run', page, async () => {
        qwenScript = [nativeCall({ recipe: 'latest_pr' }), nativeSay('The last PR is #361, PR 361, and it is merged.')];
        await page.click('#convoy-approve');
        await approveToolIfAsked(page);
        await page.waitForFunction(() => /COMPLETED/.test(document.querySelector('#convoy-detail .convoy-state')?.textContent || ''), null, { timeout: 20000 });
        const b = await badge(page);
        assert(b === 'LIVE EXECUTION', `badge was "${b}"`);
        const text = await page.locator('#convoy-detail').innerText();
        for (const must of ['GROUNDED', '#361', 'tool call', 'evidence chain', 'APPROVED', 'by human', 'evidence chain verified']) assert(text.toLowerCase().includes(must.toLowerCase()), `result view lacks "${must}"`);
        assert(githubHits >= 1, 'GitHub was asked through the governed tool');
        return `badge "${b}"; COMPLETED; GROUNDED; the human approval is in the evidence chain`;
      });

      await step(vp.name, 'd one row and drill down', page, async () => {
        assert((await page.locator('.convoy-row').count()) === (await ((await fetch(`${base}/api/convoys`)).json() as Promise<any>)).convoys.length, 'one row per convoy');
        assert((await page.locator(`.convoy-row[data-convoy-id="${convoyId}"]`).count()) === 1, 'exactly one row for this convoy');
        const topRuns = ((await (await fetch(`${base}/api/runs`)).json()) as any).runs;
        assert(!topRuns.some((r: any) => r.jobId === convoyId), 'the child run is not a top-level row');
        await page.locator('#convoy-detail details.convoy-run > summary').first().click();
        await page.waitForSelector('.convoy-tool-output', { state: 'visible', timeout: 5000 });
        const out = await page.locator('.convoy-tool-output').first().innerText();
        assert(/live_lookup|latest_pr/.test(out) && /361/.test(out), 'the tool output (evidence) is shown');
        await page.locator('#convoy-detail details.convoy-evidence > summary').first().click();
        const ev = await page.locator('#convoy-detail details.convoy-evidence').first().innerText();
        assert(/#361/.test(ev) && /merged/.test(ev), 'evidence items are shown');
        return 'one convoy row; drill-down: run -> tool call and its output -> evidence items (#361 merged)';
      });

      await step(vp.name, 'e grounding failed is a failure', page, async () => {
        await plan(page, 'What is the last PR?');
        await page.click('#convoy-submit');
        await page.waitForSelector('#convoy-approve');
        qwenScript = [nativeCall({ recipe: 'latest_pr' }), nativeSay('The last PR is #999, merged.')];
        mock.script([call('live_lookup', { recipe: 'latest_pr' }), say('Also wrong: #888 is merged.')]);
        await page.click('#convoy-approve');
        await page.waitForFunction(() => /FAILED/.test(document.querySelector('#convoy-detail .convoy-state')?.textContent || ''), null, { timeout: 25000 }).catch(async () => { await approveToolIfAsked(page); });
        await page.waitForFunction(() => /FAILED/.test(document.querySelector('#convoy-detail .convoy-state')?.textContent || ''), null, { timeout: 25000 });
        const text = await page.locator('#convoy-detail').innerText();
        assert(text.includes('GROUNDING FAILED') && /not shown as verified/.test(text), 'the failure is shown as GROUNDING FAILED');
        assert(/id: #(999|888)/.test(text), 'the unsupported claim is named');
        assert((await page.locator('#convoy-detail .convoy-answer').count()) === 0, 'no answer is presented as verified');
        return 'a wrong answer from both workers ends FAILED with GROUNDING FAILED, the unsupported claims, and no verified answer';
      });

      await step(vp.name, 'g think token mode and job state', page, async () => {
        // modes: OBSERVE and LEARN can be chosen, SIMULATE and AUTONOMOUS are shown but disabled
        assert((await page.locator('#convoy-mode-simulate').isDisabled()) && (await page.locator('#convoy-mode-autonomous').isDisabled()), 'SIMULATE and AUTONOMOUS must not be selectable yet');
        assert(await page.locator('#convoy-mode-observe').isChecked(), 'OBSERVE is the default');
        await page.check('#convoy-mode-learn');
        qwenScript = [nativeCall({ recipe: 'latest_pr' }), nativeSay('The last PR is #361, PR 361, and it is merged.')];
        await plan(page, 'What is the last PR?');
        await page.waitForFunction(() => /PLAN ONLY/.test(document.querySelector('#convoy-detail .convoy-badge-big')?.textContent || ''), null, { timeout: 8000 });
        const planned = await page.locator('#convoy-detail').innerText();
        assert(/MODE LEARN/i.test(planned), `the plan shows it was planned under LEARN; page said: ${planned.slice(0, 400).replace(/\n/g, ' | ')}`);
        await page.click('#convoy-submit');
        await page.waitForSelector('#convoy-approve');
        await page.click('#convoy-approve');
        await page.waitForFunction(() => /COMPLETED/.test(document.querySelector('#convoy-detail .convoy-state')?.textContent || ''), null, { timeout: 25000 }).catch(async () => { await approveToolIfAsked(page); });
        await page.waitForFunction(() => /COMPLETED/.test(document.querySelector('#convoy-detail .convoy-state')?.textContent || ''), null, { timeout: 25000 });
        const js = page.locator('#convoy-jobstate');
        const text = await js.innerText();
        assert(/STABLE/.test(text) && /verdict pass/.test(text), `job state text was: ${text.slice(0, 200)}`);
        assert((await js.locator('.convoy-cell').count()) === 100, 'the job state draws 100 cells');
        assert((await js.locator('.convoy-cell.is-locked').count()) > 0, 'verified cells are locked');
        assert(/CANDIDATE/.test(text), 'the learned Think Token is a CANDIDATE, never accepted');
        assert(/Stages with no signal for a convoy stay off: repair, harvest, commons/.test(text), 'it says which stages have no signal');
        assert((await page.locator('#convoy-stop').count()) === 0, 'no Stop button once finished');
        return 'LEARN planned; SIMULATE and AUTONOMOUS disabled; job state shows 100 cells with verified cells, STABLE, verdict pass, and a CANDIDATE token';
      });

      await step(vp.name, 'h agent board and outcome review', page, async () => {
        const lanes = await page.locator('#convoy-board .convoy-lane').evaluateAll((els) => els.map((e) => (e as HTMLElement).dataset.lane));
        assert(JSON.stringify(lanes) === JSON.stringify(['ready', 'open', 'review', 'finished']), `lanes were ${lanes}`);
        const heads = (await page.locator('#convoy-board .convoy-lane-head').allInnerTexts()).join(' | ');
        assert(/READY/.test(heads) && /OPEN/.test(heads) && /REVIEW/.test(heads) && /FINISHED/.test(heads), `lane heads: ${heads}`);
        const card = page.locator('#convoy-board .convoy-lane-review .convoy-card').first();
        await card.waitFor({ state: 'visible', timeout: 8000 });
        const convoy = (await card.getAttribute('data-convoy-id')) || '';
        assert(/awaiting human review/.test(await card.innerText()), 'a REVIEW card says it awaits a human');
        await card.locator('.convoy-card-accept').click();
        await page.waitForFunction((id) => !!document.querySelector(`#convoy-board .convoy-lane-finished .convoy-card[data-convoy-id="${id}"]`), convoy, { timeout: 8000 });
        const done = await page.locator(`#convoy-board .convoy-lane-finished .convoy-card[data-convoy-id="${convoy}"]`).first().innerText();
        assert(/outcome accepted/.test(done), `finished card said: ${done}`);
        assert((await page.locator(`#convoy-board .convoy-lane-review .convoy-card[data-convoy-id="${convoy}"]`).count()) === 0, 'it left REVIEW');
        const api = ((await (await fetch(`${base}/api/convoys/${convoy}`)).json()) as any).convoy;
        assert(api.review.state === 'accepted' && api.review.decided_by === 'human' && api.chain.ok, 'recorded as a human decision in an intact chain');
        return `lanes READY/OPEN/REVIEW/FINISHED; a REVIEW card was accepted by click and moved to FINISHED ("${done.replace(/\n/g, ' ')}"); the decision is a human entry in the chain`;
      });

      await step(vp.name, 'i layered agent windows', page, async () => {
        // the header chip and the goal bar reach the same features
        const chip = await page.locator('#convoy-chip').innerText().catch(() => '');
        if (vp.width > 700) assert(/READY \d+ · OPEN \d+ · REVIEW \d+/.test(chip), `the header chip said "${chip}"`);
        // a board card is an agent: clicking it opens its own window
        const card = page.locator('#convoy-board .convoy-lane-finished .convoy-card-open').first();
        await card.click();
        await page.waitForSelector('.process-window-agent', { state: 'visible', timeout: 8000 });
        await page.waitForSelector('.process-window-agent .pw-lane', { timeout: 8000 });
        const agentText = await page.locator('.process-window-agent .pw-body').innerText();
        for (const must of ['FINISHED', 'Bead', 'tb-', 'Goal', 'Grounding', 'GROUNDED']) assert(agentText.includes(must) || agentText.toUpperCase().includes(must.toUpperCase()), `the agent window lacks "${must}": ${agentText.slice(0, 300)}`);
        // deeper: Run steps, then a Tool call, then Evidence, each its own window layered over the last
        await page.locator('.process-window-agent .pw-go-run').click();
        await page.waitForSelector('.process-window-run .pw-step-tool', { state: 'visible', timeout: 8000 });
        await page.locator('.process-window-run .pw-step-tool').first().click();
        await page.waitForSelector('.process-window-tool .pw-go-evidence', { state: 'visible', timeout: 8000 });
        await page.locator('.process-window-tool .pw-go-evidence').click();
        await page.waitForSelector('.process-window-evidence .pw-item', { state: 'visible', timeout: 8000 });
        const stack = await page.evaluate(() => ['agent', 'run', 'tool', 'evidence'].map((k) => { const el = document.querySelector(`.process-window-${k}`) as HTMLElement | null; return { k, z: Number(el?.style.zIndex || 0), visible: !!el && !el.hidden }; }));
        assert(stack.every((x) => x.visible), `not all four windows are open: ${JSON.stringify(stack)}`);
        assert(stack[0]!.z < stack[1]!.z && stack[1]!.z < stack[2]!.z && stack[2]!.z < stack[3]!.z, `the windows are not layered in order: ${JSON.stringify(stack)}`);
        await shot(page, `convoy-${vp.name}-i-four-layered-windows.png`);
        const evText = await page.locator('.process-window-evidence .pw-body').innerText();
        assert(/#361/.test(evText) && /merged/.test(evText), `the evidence window did not show the PR: ${evText.slice(0, 200)}`);
        const toolText = await page.locator('.process-window-tool').innerText();
        assert(/live_lookup/.test(toolText) && /Arguments/i.test(toolText), 'the tool window shows the call and its arguments');
        // re-opening an open window brings it forward instead of making a copy
        await page.locator('.process-window-agent .pw-go-run').click().catch(() => undefined);
        assert((await page.locator('.process-window-run').count()) === 1, 'a window must not be opened twice');
        // closing the deepest one leaves the others
        await page.locator('.process-window-evidence .pw-close').click();
        assert((await page.locator('.process-window-evidence').count()) === 0 && (await page.locator('.process-window-tool').count()) === 1, 'closing one window leaves the rest');
        // the goal bar plans a convoy with what is typed there
        await page.locator('.process-window .pw-close').evaluateAll((els) => els.forEach((e) => (e as HTMLElement).click()));
        await page.fill('#goal-input', 'What is the last PR?').catch(() => undefined);
        await page.click('#plan-convoy');
        await page.waitForSelector('#convoy-goal', { state: 'visible', timeout: 8000 });
        const preset = await page.inputValue('#convoy-goal');
        assert(preset === 'What is the last PR?', `the goal bar goal did not reach the planner: "${preset}"`);
        return `card -> Agent -> Run steps -> Tool call -> Evidence opened as four layered windows (z ${stack.map((x) => x.z).join(' < ')}); no duplicates; closing one keeps the rest; "Plan as convoy" carries the goal over; chip "${chip}"`;
      });

      await step(vp.name, 'f layout', page, async () => {
        const overflow = await page.evaluate(() => { const w = document.querySelector('#convoy-window .modal') as HTMLElement | null; const r = w?.getBoundingClientRect(); return { right: r ? Math.round(r.right) : -1, vw: window.innerWidth, scrollX: document.documentElement.scrollWidth - window.innerWidth }; });
        assert(overflow.right <= overflow.vw + 1, `the Convoys window is wider than the viewport (right ${overflow.right} > ${overflow.vw})`);
        assert(overflow.scrollX <= 1, `the page scrolls horizontally by ${overflow.scrollX}px`);
        return `window fits (right edge ${overflow.right} of ${overflow.vw})`;
      });
      await ctx.close();
    }
  } finally {
    await browser.close(); server.kill(); await Promise.all([new Promise((r) => ollama.close(r)), new Promise((r) => github.close(r)), mock.close()]);
    fs.rmSync(tmp, { recursive: true, force: true });
  }
  results.push({ viewport: 'all', step: 'console errors', status: consoleErrors.length ? 'FAIL' : 'PASS', note: consoleErrors.length ? consoleErrors.slice(0, 5).join(' | ') : 'none' });
  await writeEvidence(OUT, path.join(OUT, 'convoy-e2e.json'), { generated_at: new Date().toISOString(), note: 'real Chromium + real server.ts; fake GitHub, fake Ollama, scripted Mercury stand-in', passed: results.filter((r) => r.status === 'PASS').length, total: results.length, results });
  log(`${results.filter((r) => r.status === 'PASS').length}/${results.length} passed`);
  process.exit(results.every((r) => r.status === 'PASS') ? 0 : 1);
}
main().catch((e) => { console.error(e); process.exit(2); });
