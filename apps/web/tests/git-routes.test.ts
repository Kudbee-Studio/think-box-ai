// /api/git (PR #289) mounted on the real server.ts, plus the input hardening needed to expose it:
// no shell injection through url/branch, and file access confined to the git workspace.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { GITHUB_HTTPS_URL, SAFE_BRANCH } from '../git-repo-manager.ts';
import { freePort } from './helpers/free-port.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let tmp: string, server: ChildProcess, base: string, canary: string, gitRoot: string;
const J = { 'Content-Type': 'application/json' };
const post = (u: string, body: unknown) => fetch(`${base}${u}`, { method: 'POST', headers: J, body: JSON.stringify(body) });

before(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-git-test-'));
  canary = path.join(tmp, 'outside-secret.txt');
  fs.writeFileSync(canary, 'TOP-SECRET-CANARY');
  gitRoot = path.join(tmp, 'ws', '_git');
  const port = await freePort();
  base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir, stdio: 'ignore',
    env: { ...process.env, PORT: String(port), INCEPTION_API_KEY: 'test', INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: 'http://127.0.0.1:9', JANUS_BASE_URL: 'http://127.0.0.1:9',
      UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: 'n', KUDBEE_DAILY_BUDGET_USD: '0',
      KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws') },
  });
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) {
    try { if ((await fetch(`${base}/api/health`)).ok) return; } catch { /* starting */ }
  }
  throw new Error('server did not start');
});
after(() => { server?.kill(); fs.rmSync(tmp, { recursive: true, force: true }); });

test('routes are mounted (were 404 before)', async () => {
  const r = await fetch(`${base}/api/git/repos`);
  assert.equal(r.status, 200);
  assert.deepEqual(await r.json(), []);
});

test('validators accept public github https repos and normal branches only', () => {
  for (const ok of ['https://github.com/octocat/Hello-World', 'https://github.com/octocat/Hello-World.git']) assert.ok(GITHUB_HTTPS_URL.test(ok), ok);
  for (const bad of ['http://github.com/a/b', 'file:///etc/passwd', 'https://evil.com/a/b', 'https://github.com/a/b; touch x', 'https://github.com/a/b && id',
    'https://github.com/a/b`id`', 'https://github.com/a/b\nid', '--upload-pack=x', 'git@github.com:a/b.git', 'https://github.com/a/b/c', 'https://github.com/../b', '']) {
    assert.equal(GITHUB_HTTPS_URL.test(bad), false, bad);
  }
  for (const ok of ['main', 'feature/x-1', 'v1.2.3']) assert.ok(SAFE_BRANCH.test(ok), ok);
  for (const bad of ['-x', '--upload-pack=touch x', 'main; id', 'a b', '$(id)', '`id`', '', '.hidden']) assert.equal(SAFE_BRANCH.test(bad), false, bad);
});

test('clone: shell metacharacters in url/branch are rejected (400) and nothing executes', async () => {
  const marker = path.join(tmp, 'PWNED');
  for (const body of [
    { url: `https://github.com/a/b; touch ${marker}` }, { url: `https://github.com/a/b && touch ${marker}` }, { url: `https://github.com/a/b$(touch ${marker})` },
    { url: 'https://github.com/octocat/Hello-World', branch: `main; touch ${marker}` }, { url: 'https://github.com/octocat/Hello-World', branch: `--upload-pack=touch ${marker}` },
    { url: 'file:///etc/passwd' }, { url: 'https://evil.example/x/y' },
  ]) {
    const r = await post('/api/git/clone', body);
    assert.equal(r.status, 400, JSON.stringify(body));
  }
  assert.equal(fs.existsSync(marker), false, 'no command ran');
});

test('files: absolute paths, .. and outside targets are refused; canary untouched', async () => {
  for (const p of [canary, '/etc/passwd', `${gitRoot}/../../outside-secret.txt`, '../outside-secret.txt', '../../../../etc/passwd']) {
    const r = await fetch(`${base}/api/git/file?path=${encodeURIComponent(p)}`);
    assert.ok([400, 403].includes(r.status), `read ${p} -> ${r.status}`);
    assert.equal((await r.text()).includes('TOP-SECRET-CANARY'), false);
    const w = await post('/api/git/save', { path: p, content: 'OVERWRITTEN' });
    assert.ok([400, 403].includes(w.status), `write ${p} -> ${w.status}`);
  }
  assert.equal(fs.readFileSync(canary, 'utf8'), 'TOP-SECRET-CANARY');
});

test('files: a symlink inside the workspace pointing outside is refused', async () => {
  fs.mkdirSync(gitRoot, { recursive: true });
  fs.symlinkSync(tmp, path.join(gitRoot, 'escape'));
  const r = await fetch(`${base}/api/git/file?path=${encodeURIComponent('escape/outside-secret.txt')}`);
  assert.ok([400, 403].includes(r.status), String(r.status));
  assert.equal((await post('/api/git/save', { path: 'escape/new.txt', content: 'x' })).status, 400);
  assert.equal(fs.existsSync(path.join(tmp, 'new.txt')), false);
});

test('files: save and read inside the workspace work (relative and absolute-inside)', async () => {
  const w = await post('/api/git/save', { path: 'demo/a.ts', content: 'export const a = 1;' });
  assert.equal(w.status, 200);
  const saved: any = await w.json();
  assert.ok(saved.path.startsWith(fs.realpathSync(gitRoot)));
  const rel: any = await (await fetch(`${base}/api/git/file?path=${encodeURIComponent('demo/a.ts')}`)).json();
  assert.equal(rel.content, 'export const a = 1;'); assert.equal(rel.language, 'typescript');
  const abs: any = await (await fetch(`${base}/api/git/file?path=${encodeURIComponent(saved.path)}`)).json();
  assert.equal(abs.content, 'export const a = 1;');
});

test('a POST with no body at all is a 400, not a 500 (Express 5 leaves req.body undefined)', async () => {
  for (const route of ['/api/git/clone', '/api/git/save']) {
    const r = await fetch(`${base}${route}`, { method: 'POST' });
    assert.equal(r.status, 400, route);
  }
});
