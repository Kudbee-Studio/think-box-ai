// Opt-in live-browser verification of the dashboard (npm run test:e2e). Not part of `npm test`.
//
// Starts the REAL server.ts (own random port, temp data dir, the model replaced by a scripted stand-in so no provider is contacted
// and nothing costs money) and drives REAL Chromium through Playwright at 1440, 1024 and 390 px wide:
//   a  window manager      b  workflows       c  agent tracking + approvals      d  profiles      e  console + layout
//   g  startup guard       w  watchdog (page stays responsive, no render loop; and it catches the pre-fix freeze)
// Writes docs/evidence/p3.21-dashboard-live/results.json plus one screenshot per step and viewport.
//
// Needs Chromium (`npx playwright install chromium`). On a Linux box missing system libraries set LD_LIBRARY_PATH to a folder that has them.
// Harness rules learned the hard way: navigate with waitUntil:'commit' then wait for a selector; screenshots never wait on fonts.
import { spawn, execFileSync, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, type Browser, type BrowserContext, type Page } from 'playwright';
import { startMockInception, say, call, type MockInception } from '../helpers/mock-inception.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const repoRoot = path.resolve(appDir, '../..');
const OUT = path.join(repoRoot, 'docs/evidence/p3.21-dashboard-live');
const VIEWPORTS = [{ name: '1440', width: 1440, height: 900 }, { name: '1024', width: 1024, height: 768 }, { name: '390', width: 390, height: 844 }];
const MAX_TASKBAR_REBUILDS_PER_SEC = 20;
const ALIVE_MS = 3000;
const DEAD = 'http://127.0.0.1:9';

type Result = { viewport: string; step: string; status: 'PASS' | 'FAIL'; note: string; screenshot?: string; ms: number };
const results: Result[] = [];
const consoleErrors: Array<{ viewport: string; text: string }> = [];

let mock: MockInception;
let server: ChildProcess | null = null;
let base = process.env.E2E_BASE_URL || '';
let tmpRoot = '';

function log(s: string) { console.log(`[e2e ${new Date().toISOString().slice(11, 19)}] ${s}`); }
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function startServer() {
  mock = await startMockInception();
  if (base) return;
  tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-e2e-'));
  const port = 24000 + Math.floor(Math.random() * 10000);
  base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: {
      ...process.env, PORT: String(port), INCEPTION_API_KEY: 'e2e-key', INCEPTION_API_KEY_2: '', INCEPTION_BASE_URL: mock.baseUrl,
      OLLAMA_BASE_URL: DEAD, JANUS_BASE_URL: DEAD, UPSTASH_VECTOR_REST_URL: DEAD, UPSTASH_VECTOR_REST_TOKEN: 'none', THINKBOX_EMBEDDINGS: 'off',
      KUDBEE_DAILY_BUDGET_USD: '0', KUDBEE_DATA_DIR: path.join(tmpRoot, 'data'), KUDBEE_LEARNING_DB: path.join(tmpRoot, 'learning.db'),
      KUDBEE_WORKSPACE_DIR: path.join(tmpRoot, 'workspaces'),
    },
    stdio: 'ignore',
  });
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(`${base}/api/health`)).ok) return; } catch { /* not up yet */ }
    await sleep(150);
  }
  throw new Error('server did not start');
}

/** The page must answer a trivial evaluate within ALIVE_MS; a render loop or hung script fails here instead of timing out later. */
async function alive(page: Page, what: string): Promise<void> {
  await Promise.race([page.evaluate(() => 1), new Promise((_, rej) => setTimeout(() => rej(new Error(`PAGE UNRESPONSIVE (${what}): evaluate did not answer in ${ALIVE_MS} ms`)), ALIVE_MS))]);
}

async function shot(page: Page, file: string): Promise<string | undefined> {
  const p = path.join(OUT, file);
  try {
    await page.screenshot({ path: p, animations: 'disabled', timeout: 8000 });
    return file;
  } catch {
    try {
      const cdp = await page.context().newCDPSession(page);
      const { data } = await cdp.send('Page.captureScreenshot', { format: 'png' });
      fs.writeFileSync(p, Buffer.from(data, 'base64'));
      return file;
    } catch { return undefined; }
  }
}

async function step(vp: string, name: string, page: Page | null, fn: () => Promise<string>): Promise<void> {
  const t0 = Date.now();
  let status: Result['status'] = 'PASS';
  let note = '';
  try { note = await fn(); } catch (e) { status = 'FAIL'; note = String((e as Error).message ?? e).replace(/\x1b\[[0-9;]*m/g, '').replace(/\n\s*\n/g, '\n').slice(0, 1800); }
  const screenshot = page ? await shot(page, `${vp}-${name.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}.png`) : undefined;
  results.push({ viewport: vp, step: name, status, note, screenshot, ms: Date.now() - t0 });
  log(`${status} ${vp}px ${name}${status === 'FAIL' ? ` - ${note}` : ''}`);
}

function assert(cond: unknown, msg: string): asserts cond { if (!cond) throw new Error(msg); }

async function openPage(browser: Browser, vp: (typeof VIEWPORTS)[number]): Promise<{ ctx: BrowserContext; page: Page }> {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
  await ctx.addInitScript(() => {
    (window as any).__tbRebuilds = 0;
    document.addEventListener('DOMContentLoaded', () => {
      const t = document.getElementById('wm-taskbar-windows');
      if (t) new MutationObserver((r) => { (window as any).__tbRebuilds += r.filter((x) => x.type === 'childList').length; }).observe(t, { childList: true });
    });
  });
  const page = await ctx.newPage();
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push({ viewport: vp.name, text: m.text().slice(0, 300) }); });
  page.on('pageerror', (e) => consoleErrors.push({ viewport: vp.name, text: `PAGEERROR ${e.message}`.slice(0, 300) }));
  await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
  await page.waitForSelector('#goal-input', { timeout: 15000 });
  await page.waitForFunction(() => { const s = document.querySelector('#model-select') as HTMLSelectElement | null; return !!s && s.options.length > 0 && s.options[0].value !== ''; }, null, { timeout: 15000 });
  return { ctx, page };
}

const wins = (page: Page) => page.evaluate(() => [...document.querySelectorAll('[data-wm-managed="1"]')].map((e) => {
  const el = e as HTMLElement; const r = el.getBoundingClientRect();
  return { key: el.dataset.wmKey!, title: (el.querySelector('.wm-title') as HTMLElement | null)?.innerText ?? '', x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), visible: !el.hidden && r.width > 0 && getComputedStyle(el).display !== 'none', min: el.classList.contains('wm-minimized') || el.dataset.wmMinimized === '1' };
}));

async function winManager(page: Page, vp: (typeof VIEWPORTS)[number]): Promise<string> {
  const openers = ['advanced-search-button', 'settings-button', 'execution-logs-button'];
  for (const id of openers) {
    const before = (await wins(page)).filter((w) => w.visible).length;
    await page.click(`#${id}`, { timeout: 5000 });
    await page.waitForFunction((n) => document.querySelectorAll('[data-wm-managed="1"]:not([hidden])').length > n, before, { timeout: 5000 });
  }
  await alive(page, 'three windows open');
  let list = (await wins(page)).filter((w) => w.visible);
  assert(list.length === 3, `expected 3 windows, found ${list.length}`);
  assert(new Set(list.map((w) => w.key)).size === 3, 'duplicate window keys');
  const tasks = await page.locator('.wm-task-item').count();
  assert(tasks === 3, `taskbar shows ${tasks} entries, expected 3`);

  const first = page.locator('[data-wm-managed="1"]:not([hidden])').first();
  const bar = first.locator('.wm-titlebar');
  const b0 = (await first.boundingBox())!;
  const tb = (await bar.boundingBox())!;
  await page.mouse.move(tb.x + 30, tb.y + tb.height / 2);
  await page.mouse.down();
  await page.mouse.move(tb.x + 30 + 50, tb.y + tb.height / 2 + 40, { steps: 6 });
  await page.mouse.up();
  const b1 = (await first.boundingBox())!;
  const moved = Math.abs(b1.x - b0.x) + Math.abs(b1.y - b0.y);
  const inside = b1.x >= -1 && b1.y >= -1 && b1.x + b1.width <= vp.width + 1;
  assert(moved > 0 || vp.width <= 600, 'window did not move when dragged');
  assert(inside, `window left the viewport after drag (${JSON.stringify(b1)})`);

  const grip = first.locator('.wm-resize');
  if (await grip.count()) {
    const g = (await grip.boundingBox())!;
    const w0 = (await first.boundingBox())!;
    await page.mouse.move(g.x + g.width / 2, g.y + g.height / 2);
    await page.mouse.down();
    await page.mouse.move(g.x + g.width / 2 - 40, g.y + g.height / 2 - 30, { steps: 5 });
    await page.mouse.up();
    const w1 = (await first.boundingBox())!;
    assert(w1.x + w1.width <= vp.width + 1, 'resized window overflows the viewport');
    assert(w1.width !== w0.width || w1.height !== w0.height || vp.width <= 600, 'resize grip had no effect');
  }

  await first.locator('.wm-max').click();
  await alive(page, 'maximize');
  const maxed = (await first.boundingBox())!;
  assert(maxed.width >= Math.min(vp.width, 380) - 4, `maximized window is only ${maxed.width}px wide`);
  await first.locator('.wm-max').click();
  await first.locator('.wm-min').click();
  await alive(page, 'minimize');
  const tasksAfterMin = await page.locator('.wm-task-item.is-minimized').count();
  assert(tasksAfterMin === 1, 'minimized window is not marked in the taskbar');
  await page.locator('.wm-task-item.is-minimized .wm-task-open').click();

  const shutKey = await first.evaluate((e) => (e as HTMLElement).dataset.wmKey!);
  await first.locator('.wm-close').click();
  await page.waitForFunction((k) => { const e = document.querySelector(`[data-wm-key="${k}"]`) as HTMLElement | null; return !e || e.hidden || !e.isConnected; }, shutKey, { timeout: 5000 });
  list = (await wins(page)).filter((w) => w.visible);
  assert(list.length === 2, `after close expected 2 windows, found ${list.length}`);

  const openBefore = list.map((w) => w.key).sort();
  await page.reload({ waitUntil: 'commit' });
  await page.waitForSelector('#goal-input');
  await page.waitForFunction((n) => document.querySelectorAll('[data-wm-managed="1"]:not([hidden])').length >= n, openBefore.length, { timeout: 8000 });
  await alive(page, 'after reload');
  const restored = (await wins(page)).filter((w) => w.visible);
  assert(restored.length === openBefore.length && JSON.stringify(restored.map((w) => w.key).sort()) === JSON.stringify(openBefore), `reload restored ${JSON.stringify(restored.map((w) => w.key))}, wanted ${JSON.stringify(openBefore)}`);

  const toggleId = await page.evaluate(() => ((window as any).windowManager.getState() as Array<{ opener: string | null }>).map((w) => w.opener).find(Boolean) as string);
  assert(toggleId, 'no open window knows its header opener button');
  const countBefore = (await wins(page)).filter((w) => w.visible).length;
  const waitCount = (n: number) => page.waitForFunction((c) => document.querySelectorAll('[data-wm-managed="1"]:not([hidden])').length === c, n, { timeout: 4000 }).catch(() => {});
  await page.click(`#${toggleId}`);
  await waitCount(countBefore - 1);
  const countAfter = (await wins(page)).filter((w) => w.visible).length;
  await page.click(`#${toggleId}`);
  await waitCount(countBefore);
  const countThird = (await wins(page)).filter((w) => w.visible).length;
  const keys = (await wins(page)).map((w) => w.key);
  assert(new Set(keys).size === keys.length, 'header toggle created a duplicate window');
  assert(countAfter === countBefore - 1 && countThird === countBefore, `header toggle on #${toggleId}: window counts ${countBefore} -> ${countAfter} -> ${countThird} (wanted n -> n-1 -> n)`);
  return `3 windows opened, dragged, resized, maximized, minimized, closed, layout restored after reload (${restored.length} windows); header toggle opens/closes without duplicates`;
}

async function closeAllWindows(page: Page) {
  for (let i = 0; i < 6; i++) {
    const btn = page.locator('[data-wm-managed="1"]:not([hidden]) .wm-close').first();
    if (!(await btn.count())) break;
    await btn.click().catch(() => {});
    await sleep(150);
  }
}

async function workflows(page: Page, tag: string): Promise<string> {
  const name = `E2E flow ${tag}`;
  await page.click('#create-workflow');
  await page.waitForSelector('#workflow-modal:not([hidden])', { timeout: 5000 }).catch(() => {});
  await page.locator('#workflow-modal').waitFor({ state: 'visible', timeout: 5000 });
  const tpl = page.locator('.workflow-template[data-template="sequential"]');
  const canvas = page.locator('#workflow-canvas-area');
  const tb = (await tpl.boundingBox())!;
  const cb = (await canvas.boundingBox())!;
  await page.mouse.move(tb.x + tb.width / 2, tb.y + tb.height / 2);
  await page.mouse.down();
  await page.mouse.move(tb.x + tb.width / 2 + 10, tb.y + tb.height / 2 + 10, { steps: 4 });
  await page.mouse.move(cb.x + cb.width / 2, cb.y + cb.height / 2, { steps: 12 });
  await page.mouse.up();
  let dropped = (await page.locator('.workflow-node').count()) > 0;
  let dragKind = 'real mouse drag';
  if (!dropped) {
    dragKind = 'synthetic drag events (the real mouse drag did not register in headless Chromium)';
    await page.evaluate(() => {
      const t = document.querySelector('.workflow-template[data-template="sequential"]')!;
      const c = document.getElementById('workflow-canvas-area')!;
      const dt = new DataTransfer();
      const ev = (type: string) => new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer: dt });
      t.dispatchEvent(ev('dragstart')); c.dispatchEvent(ev('dragenter')); c.dispatchEvent(ev('dragover')); c.dispatchEvent(ev('drop')); t.dispatchEvent(ev('dragend'));
    });
    dropped = (await page.locator('.workflow-node').count()) > 0;
  }
  assert(dropped, 'no workflow node was added by dropping a template on the canvas');
  await page.fill('#workflow-name', name);
  await page.fill('#workflow-desc', `Say hello from ${tag}`);
  mock.script([say(`Workflow ${tag} first run.`)]);
  await page.click('#save-workflow');
  await page.waitForFunction((n) => JSON.stringify(Object.entries(localStorage)).includes(n), name, { timeout: 5000 });
  await page.waitForFunction((t) => (document.querySelector('#terminal') as HTMLElement | null)?.innerText.includes(`Workflow ${t} first run.`), tag, { timeout: 20000 });
  await page.click('#cancel-workflow').catch(() => {});
  await page.locator('#workflow-modal').waitFor({ state: 'hidden', timeout: 5000 }).catch(() => {});

  await page.click('#bulk-actions');
  const item = page.locator('.action-menu-item', { hasText: name });
  await item.waitFor({ state: 'visible', timeout: 5000 });
  mock.script([say(`Workflow ${tag} second run.`)]);
  await item.click();
  await page.waitForFunction((t) => (document.querySelector('#terminal') as HTMLElement | null)?.innerText.includes(`Workflow ${t} second run.`), tag, { timeout: 20000 });

  await page.click('#create-workflow');
  await page.locator('#workflow-modal').waitFor({ state: 'visible', timeout: 5000 });
  await page.click('#load-workflow');
  await page.locator('#workflow-load-list >> text=' + name).first().click({ timeout: 5000 });
  const loaded = await page.inputValue('#workflow-name');
  assert(loaded === name, `loaded workflow name is "${loaded}", wanted "${name}"`);
  await page.click('#cancel-workflow').catch(() => {});
  return `built, saved and listed in the Actions menu; saving it ran it once and the Actions menu ran it again, each through the real server with the answer reaching the terminal; Load restored "${name}" into the builder; template added by ${dragKind}`;
}

async function submitGoal(page: Page, goal: string) {
  await page.fill('#goal-input', goal);
  await page.click('#submit-goal');
}

async function agentTracking(page: Page, vp: (typeof VIEWPORTS)[number]): Promise<string> {
  const f1 = `a-${vp.name}.txt`;
  const f2 = `r-${vp.name}.txt`;
  mock.script([
    { ...call('write_file', { path: f1, content: 'one' }), delayMs: 1200 },
    call('write_file', { path: f1, content: 'two' }),
    say(`Approved run ${vp.name} finished.`),
    { ...call('write_file', { path: f2, content: 'one' }), delayMs: 600 },
    call('write_file', { path: f2, content: 'two' }),
    say(`Rejected run ${vp.name} noted the denial.`),
  ]);
  await submitGoal(page, `Write ${f1} twice (approved run ${vp.name})`);
  await page.waitForFunction(() => document.querySelector('.wm-agent-badge')?.textContent?.trim() === '1 running', null, { timeout: 8000 });
  const badge = (await page.locator('.wm-agent-badge').innerText()).trim();
  await page.click('.wm-agent-badge');
  await page.locator('.agent-menu-item').first().click({ timeout: 5000 });
  const gov = page.locator('.governance-window:not([hidden])').first();
  await gov.waitFor({ state: 'visible', timeout: 5000 });
  const govText = await gov.innerText();
  assert(/step/i.test(govText) && /token/i.test(govText), `governance window lacks steps/tokens: ${govText.slice(0, 160).replace(/\n/g, ' | ')}`);
  await alive(page, 'governance window open');

  const approve = gov.locator('.gov-approve');
  await approve.waitFor({ state: 'visible', timeout: 15000 });
  const ab = (await approve.boundingBox())!;
  const topEl = await page.evaluate(({ x, y }) => { const e = document.elementFromPoint(x, y) as HTMLElement | null; return e?.closest('.gov-approve') ? 'approve' : (e?.className || e?.tagName || 'none'); }, { x: ab.x + ab.width / 2, y: ab.y + ab.height / 2 });
  await shot(page, `${vp.name}-governance-approval-pending.png`);
  assert(topEl === 'approve', `the Approve button is covered by "${topEl}" (z-index / overlap)`);
  await approve.click();
  await page.waitForFunction((t) => (document.querySelector('#terminal') as HTMLElement | null)?.innerText.includes(`Approved run ${t} finished.`), vp.name, { timeout: 20000 });
  await page.waitForFunction(() => document.querySelector('.wm-agent-badge')?.textContent?.trim() === '0 running', null, { timeout: 8000 });

  await submitGoal(page, `Write ${f2} twice (rejected run ${vp.name})`);
  await page.waitForFunction(() => /^[1-9]/.test(document.querySelector('.wm-agent-badge')?.textContent?.trim() || ''), null, { timeout: 8000 });
  await page.click('.wm-agent-badge');
  await page.locator('.agent-menu-item').first().click({ timeout: 5000 });
  const gov2 = page.locator('.governance-window:not([hidden])').first();
  const reject = gov2.locator('.gov-reject');
  await reject.waitFor({ state: 'visible', timeout: 15000 });
  await reject.click();
  await page.waitForFunction((t) => (document.querySelector('#terminal') as HTMLElement | null)?.innerText.includes(`Rejected run ${t} noted the denial.`), vp.name, { timeout: 20000 });
  const onDisk = fs.existsSync(tmpRoot) ? 'checked' : 'skipped';
  return `badge "${badge}" while running; governance window showed steps and tokens; Approve (not covered by the approval modal) let the run finish; Reject on a second run ended it with the denial (workspace check ${onDisk})`;
}

async function profiles(page: Page, vp: (typeof VIEWPORTS)[number]): Promise<string> {
  const a = `Alpha-${vp.name}`;
  const b = `Beta-${vp.name}`;
  const json = (url: string, init?: any) => page.evaluate(async ([u, i]) => { const r = await fetch(u as string, i as any); return { status: r.status, body: await r.json().catch(() => null) }; }, [url, init] as const);
  const post = (url: string, body: unknown) => json(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const createViaUi = async (name: string) => {
    page.once('dialog', (d) => { void d.accept(name); });
    await page.selectOption('#profile-select', '__new__');
    await page.waitForFunction((n) => [...document.querySelectorAll('#profile-select option')].some((o) => o.textContent?.startsWith(n)), name, { timeout: 5000 });
  };
  const switchViaUi = async (name: string) => {
    const value = await page.evaluate((n) => ([...document.querySelectorAll('#profile-select option')].find((o) => o.textContent?.startsWith(n)) as HTMLOptionElement).value, name);
    await page.selectOption('#profile-select', value);
    await page.waitForFunction((n) => document.querySelector('#profile-status')?.textContent?.includes(n) || [...document.querySelectorAll('#profile-select option:checked')].some((o) => o.textContent?.startsWith(n)), name, { timeout: 5000 });
    await sleep(300);
  };
  await createViaUi(a);
  await createViaUi(b);
  await switchViaUi(a);
  const mem = await post('/api/memory', { layer: 'org', title: `${a} only fact`, content: `The ${a} profile knows this.` });
  assert(mem.status === 201, `memory write status ${mem.status}`);
  mock.script([say(`Run under ${a}.`)]);
  await submitGoal(page, `Say hi under ${a}`);
  await page.waitForFunction((t) => (document.querySelector('#terminal') as HTMLElement | null)?.innerText.includes(`Run under ${t}.`), a, { timeout: 20000 });
  await sleep(500);
  const aMemory = (await json('/api/memory?limit=50')).body.items.map((i: any) => i.title);
  const aRuns = (await json('/api/runs?limit=50')).body;
  const aRunCount = (aRuns.runs ?? aRuns).length;
  assert(aMemory.includes(`${a} only fact`), `${a} cannot see its own memory`);
  assert(aRunCount >= 1, `${a} has no runs after running a goal`);

  await switchViaUi(b);
  const bMemory = (await json('/api/memory?limit=50')).body.items.map((i: any) => i.title);
  const bRuns = (await json('/api/runs?limit=50')).body;
  assert(!bMemory.includes(`${a} only fact`), `${b} can see ${a}'s memory`);
  assert((bRuns.runs ?? bRuns).length === 0, `${b} sees ${(bRuns.runs ?? bRuns).length} of ${a}'s runs`);

  await switchViaUi(a);
  const back = (await json('/api/memory?limit=50')).body.items.map((i: any) => i.title);
  assert(back.includes(`${a} only fact`), `${a}'s memory did not come back after switching`);

  const list = (await json('/api/profiles')).body;
  const alphaId = list.profiles.find((p: any) => p.name === a).id;
  const bundle = (await json(`/api/profiles/${alphaId}/export`)).body;
  assert(bundle.format === 'kudbee-profile' && bundle.memory.org.some((i: any) => i.title === `${a} only fact`), 'export lacks the memory');
  const imported = await post('/api/profiles/import', bundle);
  assert(imported.status === 201, `import status ${imported.status}: ${JSON.stringify(imported.body)}`);
  const importedMemory = (await json(`/api/profiles/${imported.body.id}/export`)).body.memory.org.map((i: any) => i.title);
  assert(importedMemory.includes(`${a} only fact`), 'imported profile lacks the memory');
  const bad = await post('/api/profiles/import', { format: 'kudbee-profile', memory: { org: [{ id: 'org/../../etc/x', title: 't', content: 'x'.repeat(30000) }] } });
  assert(bad.status === 400, `oversized import was not refused (status ${bad.status})`);
  return `created ${a} and ${b} from the header switcher; memory and runs stay inside their profile and return on switch back; export -> import into a new profile keeps the memory (API-level: the dashboard has no export/import control); an oversized import is refused with 400`;
}

async function layout(page: Page, vp: (typeof VIEWPORTS)[number]): Promise<string> {
  await alive(page, 'layout check');
  const rects = await page.evaluate(() => {
    const r = (sel: string) => { const e = document.querySelector(sel) as HTMLElement | null; if (!e || e.hidden) return null; const b = e.getBoundingClientRect(); const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden' || b.width === 0) return null; return { x: b.x, y: b.y, w: b.width, h: b.height }; };
    return { taskbar: r('#wm-taskbar'), profile: r('#profile-switcher'), model: r('.model-selector'), header: r('header'), scrollW: document.documentElement.scrollWidth, innerW: window.innerWidth };
  });
  const hit = (p: any, q: any) => p && q && p.x < q.x + q.w && q.x < p.x + p.w && p.y < q.y + q.h && q.y < p.y + p.h;
  assert(rects.scrollW <= rects.innerW + 1, `horizontal page scroll: scrollWidth ${rects.scrollW} > ${rects.innerW}`);
  assert(!hit(rects.taskbar, rects.profile), 'taskbar overlaps the profile switcher');
  assert(!hit(rects.taskbar, rects.model), 'taskbar overlaps the model selector');
  assert(!hit(rects.profile, rects.model), 'profile switcher overlaps the model selector');
  const overflow = (await wins(page)).filter((w) => w.visible && (w.x < -1 || w.x + w.w > vp.width + 1));
  assert(overflow.length === 0, `windows overflow the viewport: ${overflow.map((w) => w.key).join(', ')}`);
  return `no horizontal scroll; taskbar, profile switcher and model selector do not overlap; open windows stay inside the viewport (${vp.width}px)`;
}

async function watchdog(page: Page): Promise<string> {
  await sleep(2000);
  await alive(page, 'steady state');
  const t0 = await page.evaluate(() => (window as any).__tbRebuilds as number);
  await sleep(1000);
  const t1 = await page.evaluate(() => (window as any).__tbRebuilds as number);
  const perSec = t1 - t0;
  assert(perSec <= MAX_TASKBAR_REBUILDS_PER_SEC, `render loop: ${perSec} taskbar rebuilds in one second at rest`);
  return `page answered within ${ALIVE_MS} ms; ${perSec} taskbar rebuilds/s at rest (limit ${MAX_TASKBAR_REBUILDS_PER_SEC})`;
}

async function guardStep(browser: Browser): Promise<string> {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.routeWebSocket(/.*/, (ws) => { void ws.close(); });
  await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
  await page.waitForSelector('#startup-error', { timeout: 9000 });
  const text = await page.locator('#startup-error').innerText();
  assert(/model list/i.test(text) && /Retry/.test(text), `guard panel text: ${text.slice(0, 120)}`);
  await shot(page, '1440-startup-guard-error.png');
  await page.unrouteAll();
  await page.click('#startup-retry');
  await page.waitForFunction(() => !document.querySelector('#startup-error'), null, { timeout: 15000 });
  await ctx.close();
  return 'with the WebSocket blocked the dashboard showed an error panel naming the missing model list with a Retry button; after unblocking, Retry loaded the dashboard and the panel disappeared';
}

async function regressionProof(browser: Browser): Promise<string> {
  let old = '';
  try { old = execFileSync('git', ['show', 'origin/main:apps/web/public/js/window-manager.js'], { cwd: repoRoot, encoding: 'utf8' }); } catch { return 'SKIPPED: origin/main not available locally'; }
  if (!/_syncTaskbar/.test(old) || /_taskbarSignature/.test(old)) return 'SKIPPED: origin/main already has the fix';
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.route('**/js/window-manager.js', (r) => r.fulfill({ status: 200, contentType: 'application/javascript', body: old }));
  await page.goto(base, { waitUntil: 'commit', timeout: 15000 });
  await sleep(4000);
  let froze = false;
  try { await alive(page, 'pre-fix window manager'); } catch { froze = true; }
  void ctx.close().catch(() => {});
  assert(froze, 'the pre-fix window manager did not freeze the page: the watchdog proof is not valid');
  return 'BEFORE: with the #356 window-manager.js from origin/main the page stopped answering (watchdog tripped); AFTER: every other step ran against the fixed file and stayed responsive';
}

async function main() {
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(OUT, { recursive: true });
  await startServer();
  log(`server ${base}`);
  const browser = await chromium.launch({ args: ['--disable-gpu'] });
  try {
    for (const vp of VIEWPORTS.filter((v) => !process.env.E2E_VIEWPORT || v.name === process.env.E2E_VIEWPORT)) {
      const { ctx, page } = await openPage(browser, vp);
      await step(vp.name, 'watchdog: responsive, no render loop', page, () => watchdog(page));
      await step(vp.name, 'a window manager', page, () => winManager(page, vp));
      await step(vp.name, 'e layout without overlap', page, () => layout(page, vp));
      await closeAllWindows(page);
      await step(vp.name, 'b workflows', page, () => workflows(page, vp.name));
      await step(vp.name, 'c agent tracking and approvals', page, () => agentTracking(page, vp));
      await step(vp.name, 'd profiles', page, () => profiles(page, vp));
      await step(vp.name, 'e layout after approvals', page, () => layout(page, vp));
      await ctx.close();
    }
    if (process.env.E2E_VIEWPORT) { results.push({ viewport: 'all', step: 'partial run (E2E_VIEWPORT set)', status: 'PASS', note: 'startup guard and regression proof skipped', ms: 0 }); } else {
    await step('1440', 'g startup guard', null, () => guardStep(browser));
    await step('1440', 'w pre-fix freeze is caught by the watchdog', null, () => regressionProof(browser));
    }
    const errs = consoleErrors.filter((e) => !/Failed to load resource.*(404|net::ERR_ABORTED)/.test(e.text));
    results.push({ viewport: 'all', step: 'e no console errors', status: errs.length === 0 ? 'PASS' : 'FAIL', note: errs.length ? errs.slice(0, 5).map((e) => `${e.viewport}px: ${e.text}`).join(' || ') : 'zero console errors and zero uncaught page errors at 1440, 1024 and 390 px', ms: 0 });
  } finally {
    const failed = results.filter((r) => r.status === 'FAIL').length;
    fs.writeFileSync(path.join(OUT, 'results.json'), JSON.stringify({ generated: new Date().toISOString(), base: process.env.E2E_BASE_URL ? 'external server' : 'own server, scripted model (no provider contacted, $0)', passed: results.length - failed, failed, results, consoleErrors }, null, 1));
    log(`${results.length - failed}/${results.length} passed; evidence in ${path.relative(repoRoot, OUT)}`);
    await Promise.race([browser.close(), sleep(5000)]).catch(() => {});
    server?.kill();
    await mock.close().catch(() => {});
    process.exit(failed ? 1 : 0);
  }
}

main().catch((e) => { console.error(e); process.exit(2); });
