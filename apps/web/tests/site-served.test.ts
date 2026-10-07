// The product website is served by the dashboard at /site/ (public/site/): every file it references exists, nothing in it is blocked by the dashboard's
// Content-Security-Policy (no inline executable script), and the real server serves it with the security headers and links to it from the header.
import assert from 'node:assert/strict';
import { spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { freePort } from './helpers/free-port.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const site = path.join(appDir, 'public', 'site');
const html = fs.readFileSync(path.join(site, 'index.html'), 'utf8');

test('every local file the site page, its stylesheet and its manifest name exists', () => {
  const refs = [...html.matchAll(/(?:href|src)="([^"#]+)"/g)].map((m) => m[1]!).filter((r) => !/^(https?:|mailto:|data:)/.test(r));
  const css = fs.readFileSync(path.join(site, 'styles.css'), 'utf8');
  refs.push(...[...css.matchAll(/url\(([^)]+)\)/g)].map((m) => m[1]!.replace(/["']/g, '')).filter((r) => !/^(data:|#)/.test(r)));
  const manifest = JSON.parse(fs.readFileSync(path.join(site, 'manifest.webmanifest'), 'utf8')) as { icons: Array<{ src: string }> };
  refs.push(...manifest.icons.map((i) => i.src));
  assert.ok(refs.length > 20, 'found the references');
  for (const r of new Set(refs)) assert.ok(fs.existsSync(path.join(site, r.split('?')[0]!)), `${r} exists under public/site`);
});

test('the site has no inline executable script, so the dashboard CSP (script-src self) cannot block it', () => {
  const tags = html.split('<script').slice(1).map((chunk) => chunk.slice(0, chunk.indexOf('>')));
  assert.ok(tags.length >= 5, 'found the script tags');
  for (const attrs of tags) assert.ok(attrs.includes('src=') || attrs.includes('type="application/ld+json"') || attrs.includes('type="application/json"'), `script tag is external or a data block: <script${attrs}>`);
  for (const handler of [' onclick=', ' onload=', ' onerror=', ' onchange=', ' onsubmit=']) assert.ok(!html.toLowerCase().includes(handler), `no inline handler ${handler.trim()}`);
});

let server: ChildProcess; let base = ''; let tmp = '';
before(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-site-'));
  const port = await freePort(); base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], { cwd: appDir, stdio: 'ignore', env: { ...process.env, PORT: String(port), HOST: '127.0.0.1', INCEPTION_API_KEY: '', DEEPSEEK_API_KEY: '', XAI_API_KEY: '', OLLAMA_BASE_URL: 'http://127.0.0.1:9', JANUS_BASE_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: '', KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_LEARNING_DB: path.join(tmp, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), THINKBOX_EMBEDDINGS: 'off' } });
  for (let i = 0; i < 100; i++) { try { if ((await fetch(`${base}/api/health`)).ok) return; } catch { /* starting */ } await new Promise((r) => setTimeout(r, 150)); }
  throw new Error('server did not start');
});
after(() => { server?.kill(); fs.rmSync(tmp, { recursive: true, force: true }); });

test('the running dashboard serves the site with its security headers, and the header links to it', async () => {
  const page = await fetch(`${base}/site/`);
  assert.equal(page.status, 200); assert.match(page.headers.get('content-type') ?? '', /text\/html/);
  assert.match(page.headers.get('content-security-policy') ?? '', /script-src 'self'/);
  assert.match(await page.text(), /Agents propose\./);
  for (const asset of ['/site/styles.css', '/site/script.js', '/site/theme-init.js', '/site/cube.js', '/site/vendor/three.module.min.js', '/site/assets/favicon.svg', '/site/assets/fonts/InterTight-latin-var.woff2']) assert.equal((await fetch(`${base}${asset}`)).status, 200, asset);
  const dash = await (await fetch(`${base}/`)).text();
  assert.match(dash, /<a id="site-link"[^>]*href="\/site\/"/);
});
