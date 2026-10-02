// Headless Chrome: dashboard Think Tokens under prefers-reduced-motion (ADR 029 P3.3 evidence).
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH ?? 'playwright');

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const appDir = path.join(root, 'apps/web');
const out = process.argv[2] || '/opt/cursor/artifacts/think-tokens-reduced-motion.png';
const seed = path.join(root, 'docs/evidence/adr-029-p3/p33-seed.db');

const port = 20000 + Math.floor(Math.random() * 20000);
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'tt-rm-'));
const data = path.join(dir, 'data');
fs.mkdirSync(data, { recursive: true });
fs.copyFileSync(seed, path.join(data, 'think-tokens.db'));

const env = {
  ...process.env,
  PORT: String(port),
  KUDBEE_DATA_DIR: data,
  KUDBEE_WORKSPACE_DIR: path.join(dir, 'ws'),
  INCEPTION_API_KEY: process.env.INCEPTION_API_KEY || 'test',
  OLLAMA_BASE_URL: 'http://127.0.0.1:9',
  JANUS_BASE_URL: 'http://127.0.0.1:9',
  UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9',
};

const child = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
  cwd: appDir,
  env,
  stdio: 'ignore',
});
const base = `http://127.0.0.1:${port}`;

async function waitHealth() {
  for (let i = 0; i < 60; i += 1) {
    try {
      if ((await fetch(`${base}/api/health`)).ok) return;
    } catch { /* starting */ }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error('server did not start');
}

try {
  await waitHealth();
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    reducedMotion: 'reduce',
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });

  await page.goto(`${base}/`, { waitUntil: 'networkidle' });
  await page.click('button#btnThinkTokens, [data-action="think-tokens"], button:has-text("Think Tokens")').catch(async () => {
    await page.evaluate(() => {
      const b = [...document.querySelectorAll('button')].find((x) => /think token/i.test(x.textContent || ''));
      b?.click();
    });
  });
  await page.waitForTimeout(1500);
  const cubeTwist = await page.evaluate(() => {
    const cube = document.querySelector('.think-cube');
    if (!cube) return { missing: true };
    const style = getComputedStyle(cube);
    return {
      hasTwistClass: cube.classList.contains('tt-twist'),
      animationName: style.animationName,
      animationDuration: style.animationDuration,
    };
  });
  const energyRing = await page.evaluate(() => {
    const ring = document.querySelector('.energy-core[data-state="active"] .energy-ring');
    if (!ring) return { activeCore: false };
    const style = getComputedStyle(ring);
    return { animationName: style.animationName };
  });

  fs.mkdirSync(path.dirname(out), { recursive: true });
  await page.screenshot({ path: out, fullPage: false });
  await browser.close();

  const report = {
    screenshot: out,
    prefers_reduced_motion: true,
    console_errors: errors,
    cube: cubeTwist,
    energy_core_ring: energyRing,
  };
  const reportPath = out.replace(/\.png$/, '.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
} finally {
  child.kill();
  fs.rmSync(dir, { recursive: true, force: true });
}
