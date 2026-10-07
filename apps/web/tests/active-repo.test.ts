// "Use for agent": a cloned repository becomes the agent's repository root (its repository tools, SIMULATE and checks) and GitHub owner/name, per profile, and
// only a real clone inside <profile workspace>/repositories can be chosen.
import assert from 'node:assert/strict';
import { execFileSync, spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { ActiveRepoError, ActiveRepoManager } from '../active-repo.ts';
import { knownRepoFor } from '../repo-context.ts';
import { repoRoot } from '../repo-tools.ts';
import { freePort } from './helpers/free-port.ts';

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-active-repo-'));
after(() => fs.rmSync(tmp, { recursive: true, force: true }));
const git = (cwd: string, ...a: string[]): string => execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', ...a], { cwd, encoding: 'utf8' }).trim();
function clone(profileDir: string, name: string, origin: string | null): string {
  const dir = path.join(profileDir, 'repositories', name); fs.mkdirSync(dir, { recursive: true });
  git(dir, 'init', '-q', '-b', 'main'); fs.writeFileSync(path.join(dir, 'a.txt'), 'x'); git(dir, 'add', '-A'); git(dir, 'commit', '-qm', 'one');
  if (origin) git(dir, 'remote', 'add', 'origin', origin);
  return dir;
}
const mk = (env: Record<string, string | undefined>, root: string) => new ActiveRepoManager({ file: path.join(root, 'data', 'active-repo.json'), profileDir: (p) => path.join(root, 'ws', p), env });

test('choosing a clone points the agent at it, per profile, and clearing restores the boot values', () => {
  const root = path.join(tmp, 'a'); const env: Record<string, string | undefined> = { KUDBEE_REPO: 'boot-owner/boot-repo' };
  const m = mk(env, root);
  const one = clone(path.join(root, 'ws', 'default'), 'hello', 'https://github.com/octocat/Hello-World.git');
  clone(path.join(root, 'ws', 'work'), 'other', 'https://gitlab.com/x/y.git');
  assert.deepEqual(m.list('default'), ['hello']); assert.deepEqual(m.list('work'), ['other']);
  assert.equal(m.apply('default'), null); assert.equal(env.KUDBEE_REPO_ROOT, undefined); assert.equal(env.KUDBEE_REPO, 'boot-owner/boot-repo');
  const a = m.set('default', 'hello');
  assert.deepEqual([a.name, a.root, a.repo], ['hello', one, 'octocat/Hello-World']);
  assert.equal(env.KUDBEE_REPO_ROOT, one); assert.equal(env.KUDBEE_REPO, undefined, 'the configured repo no longer applies; the clone\'s own origin does');
  assert.equal(repoRoot(env), one); assert.equal(knownRepoFor(env, repoRoot(env)), 'octocat/Hello-World');
  assert.equal(m.active('default')?.name, 'hello'); assert.equal(m.active('work'), null, 'the choice is per profile');
  m.apply('work'); assert.equal(env.KUDBEE_REPO_ROOT, undefined, 'switching to a profile with no choice goes back to the boot checkout');
  m.apply('default'); assert.equal(env.KUDBEE_REPO_ROOT, one, 'and back');
  m.clear('default'); assert.equal(env.KUDBEE_REPO_ROOT, undefined); assert.equal(env.KUDBEE_REPO, 'boot-owner/boot-repo'); assert.equal(m.active('default'), null);
});

test('a choice survives a restart (it is saved), and a non-GitHub clone turns GitHub lookups off', () => {
  const root = path.join(tmp, 'b'); const env1: Record<string, string | undefined> = {};
  const dir = clone(path.join(root, 'ws', 'default'), 'lab', 'https://gitlab.com/x/y.git');
  mk(env1, root).set('default', 'lab');
  const env2: Record<string, string | undefined> = {}; const m2 = mk(env2, root);
  assert.equal(m2.apply('default')?.name, 'lab'); assert.equal(env2.KUDBEE_REPO_ROOT, dir);
  assert.equal(m2.active('default')?.repo, null); assert.equal(knownRepoFor(env2, dir), null, 'GitLab is not a GitHub repository: no GitHub lookups, no guessed owner');
});

test('only a real clone inside the profile repositories folder can be chosen', () => {
  const root = path.join(tmp, 'c'); const env: Record<string, string | undefined> = {}; const m = mk(env, root);
  const profile = path.join(root, 'ws', 'default'); clone(profile, 'ok', null);
  fs.mkdirSync(path.join(profile, 'repositories', 'plain')); fs.mkdirSync(path.join(root, 'outside'), { recursive: true }); clone(root, 'secret', null);
  fs.symlinkSync(path.join(root, 'outside'), path.join(profile, 'repositories', 'link'));
  for (const bad of ['../../outside', '..', '.hidden', 'plain', 'link', 'missing', '', 'a/b', 'x'.repeat(200), 42, null, undefined]) assert.throws(() => m.set('default', bad), ActiveRepoError, String(bad));
  assert.equal(m.set('default', 'ok').name, 'ok'); assert.deepEqual(m.list('default'), ['ok']);
  fs.rmSync(path.join(profile, 'repositories', 'ok'), { recursive: true }); assert.equal(m.active('default'), null, 'a deleted clone is no longer active'); m.apply('default'); assert.equal(env.KUDBEE_REPO_ROOT, undefined);
});

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
test('real server: only the dashboard can choose the repository; the choice shows in the API, per profile, and after a restart', async () => {
  const wsRoot = path.join(tmp, 'srv', 'ws'); const dataDir = path.join(tmp, 'srv', 'data'); fs.mkdirSync(wsRoot, { recursive: true });
  const dead = 'http://127.0.0.1:9';
  const boot = async (): Promise<{ base: string; stop: () => void }> => {
    const port = await freePort(); const base = `http://127.0.0.1:${port}`;
    const s: ChildProcess = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], { cwd: appDir, stdio: 'ignore', env: { ...process.env, PORT: String(port), HOST: '127.0.0.1', INCEPTION_API_KEY: '', DEEPSEEK_API_KEY: '', XAI_API_KEY: '', OLLAMA_BASE_URL: dead, JANUS_BASE_URL: dead, UPSTASH_VECTOR_REST_URL: dead, UPSTASH_VECTOR_REST_TOKEN: 'none', THINKBOX_EMBEDDINGS: 'off', KUDBEE_DATA_DIR: dataDir, KUDBEE_LEARNING_DB: path.join(tmp, 'srv', 'l.db'), KUDBEE_WORKSPACE_DIR: wsRoot } });
    for (let i = 0; i < 100; i++) { try { if ((await fetch(`${base}/api/health`)).ok) return { base, stop: () => s.kill() }; } catch { /* starting */ } await new Promise((r) => setTimeout(r, 150)); }
    s.kill(); throw new Error('server did not start');
  };
  let s = await boot();
  try {
    const profile = (await (await fetch(`${s.base}/api/profiles/active`)).json() as { id: string }).id;
    clone(path.join(wsRoot, '_profiles', profile), 'hello', 'https://github.com/octocat/Hello-World.git');
    const view = async (): Promise<{ active: { name: string; repo: string | null } | null; repositories: string[] }> => (await fetch(`${s.base}/api/repo/active`)).json() as never;
    assert.deepEqual(await view(), { active: null, repositories: ['hello'] });
    const post = (body: unknown, headers: Record<string, string> = {}) => fetch(`${s.base}/api/repo/active`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) });
    assert.equal((await post({ name: 'hello' })).status, 403, 'no dashboard origin, no local token: refused');
    assert.equal((await post({ name: 'hello' }, { Origin: 'http://evil.example' })).status, 403);
    assert.equal((await post({ name: '../x' }, { Origin: s.base })).status, 400);
    assert.equal((await post({ name: 'hello' }, { Origin: s.base })).status, 200);
    assert.deepEqual(await view(), { active: { name: 'hello', repo: 'octocat/Hello-World' }, repositories: ['hello'] });
    s.stop(); await new Promise((r) => setTimeout(r, 400)); s = await boot();
    assert.equal((await view()).active?.name, 'hello', 'still chosen after a restart');
    assert.equal((await fetch(`${s.base}/api/repo/active`, { method: 'DELETE', headers: { Origin: s.base } })).status, 200);
    assert.equal((await view()).active, null);
  } finally { s.stop(); }
});
