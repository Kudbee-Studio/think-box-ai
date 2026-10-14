// The Starfall game is served by the dashboard at /game/ (public/game/), linked from the header. Every file it names exists, it has no inline script (the dashboard's
// Content-Security-Policy is script-src 'self'), it uses relative paths (it lives in a sub-folder), and the real server serves it with its security headers.
import assert from 'node:assert/strict';
import { spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { freePort } from './helpers/free-port.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const game = path.join(appDir, 'public', 'game');
const html = fs.readFileSync(path.join(game, 'index.html'), 'utf8');

test('the page uses relative paths and every file it names, and every module those scripts import, exists', () => {
  assert.ok(!/(?:href|src)="\//.test(html), 'no absolute paths: it is served from /game/');
  const refs = [...html.matchAll(/(?:href|src)="([^"#]+)"/g)].map((m) => m[1]!);
  assert.ok(refs.includes('./src/main.js') && refs.includes('./style.css'));
  const seen = new Set<string>(); const queue = refs.filter((r) => r.endsWith('.js')).map((r) => path.join(game, r));
  while (queue.length) {
    const file = queue.pop()!; if (seen.has(file)) continue; seen.add(file);
    assert.ok(fs.existsSync(file), `${path.relative(game, file)} exists`);
    for (const m of fs.readFileSync(file, 'utf8').matchAll(/from '(\.[^']+)'/g)) queue.push(path.join(path.dirname(file), m[1]!));
  }
  for (const r of refs) assert.ok(fs.existsSync(path.join(game, r)), r);
  assert.ok(seen.size >= 4, 'found the game modules');
});

test('no inline executable script and no inline handler, so the dashboard CSP cannot block the game', () => {
  for (const tag of html.split('<script').slice(1)) assert.ok(tag.slice(0, tag.indexOf('>')).includes('src='), 'script tags are external');
  for (const handler of [' onclick=', ' onload=', ' onerror=']) assert.ok(!html.toLowerCase().includes(handler), handler);
});

let server: ChildProcess; let base = ''; let tmp = '';
before(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-game-'));
  const port = await freePort(); base = `http://127.0.0.1:${port}`; const dead = 'http://127.0.0.1:9';
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], { cwd: appDir, stdio: 'ignore', env: { ...process.env, PORT: String(port), HOST: '127.0.0.1', INCEPTION_API_KEY: '', DEEPSEEK_API_KEY: '', XAI_API_KEY: '', OLLAMA_BASE_URL: dead, JANUS_BASE_URL: dead, UPSTASH_VECTOR_REST_URL: dead, UPSTASH_VECTOR_REST_TOKEN: 'none', THINKBOX_EMBEDDINGS: 'off', KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_LEARNING_DB: path.join(tmp, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws') } });
  for (let i = 0; i < 100; i++) { try { if ((await fetch(`${base}/api/health`)).ok) return; } catch { /* starting */ } await new Promise((r) => setTimeout(r, 150)); }
  throw new Error('server did not start');
});
after(() => { server?.kill(); fs.rmSync(tmp, { recursive: true, force: true }); });

test('the running dashboard serves the game and its scripts with the security headers, and the header links to /game/', async () => {
  const page = await fetch(`${base}/game/`);
  assert.equal(page.status, 200); assert.match(page.headers.get('content-type') ?? '', /text\/html/);
  assert.match(page.headers.get('content-security-policy') ?? '', /script-src 'self'/);
  assert.match(await page.text(), /<canvas id="game"/);
  for (const f of ['style.css', 'src/main.js', 'src/game.js', 'src/input.js', 'src/render.js']) assert.equal((await fetch(`${base}/game/${f}`)).status, 200, f);
  const dash = await (await fetch(`${base}/`)).text();
  assert.match(dash, /<a id="game-link"[^>]*href="\/game\/"/);
});
