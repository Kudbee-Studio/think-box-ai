// Slice 4 through the REAL server: SIMULATE convoy -> sandbox verifies -> a human accepts the review -> a human opens a DRAFT pull request. Scripted Mercury, a fixture git
// repository, a local BARE repository standing in for GitHub, and a fake `gh` on PATH. Nothing reaches the network; nothing here pushes to a real repository.
import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawn, type ChildProcess } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';
import { probeSandbox } from '../scratch-runner.ts';
import { call, say, startMockInception, type MockInception } from './helpers/mock-inception.ts';
import { freePort } from './helpers/free-port.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const probe = await probeSandbox();
const skip = probe.ok ? false : `no proven sandbox here: ${(probe as { reason: string }).reason}`;
const REPO = 'Acme/widgets';

let mock: MockInception; let server: ChildProcess; let base = ''; let tmp = ''; let fx = ''; let bare = ''; let ghLog = ''; let sha = '';
const G = (cwd: string, ...a: string[]): string => execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', ...a], { cwd, encoding: 'utf8' }).trim();
const put = (rel: string, text: string): void => { fs.mkdirSync(path.dirname(path.join(fx, rel)), { recursive: true }); fs.writeFileSync(path.join(fx, rel), text); };
const fixtureState = (): string => createHash('sha256').update(G(fx, 'status', '--porcelain', '--ignored') + G(fx, 'rev-parse', 'HEAD') + G(fx, 'for-each-ref') + fs.readFileSync(path.join(fx, '.git', 'index'))).digest('hex');
const remoteRefs = (): string[] => G(bare, 'for-each-ref', '--format=%(refname)').split('\n').filter(Boolean);
const ghCalls = (): string[][] => (fs.existsSync(ghLog) ? fs.readFileSync(ghLog, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l) as string[]) : []);

before(async () => {
  if (skip) return;
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'dpr-server-')); fx = path.join(tmp, 'fixture'); bare = path.join(tmp, 'remote.git'); ghLog = path.join(tmp, 'gh.log');
  put('apps/web/package.json', JSON.stringify({ name: 'fixture', scripts: { lint: 'node -e "0"', typecheck: 'node -e "0"', 'typecheck:tsc': 'node -e "0"', test: 'node --test "tests/*.test.js"' } }));
  put('apps/web/src/greeter.js', "function greet(name) {\n  return 'helo ' + name;\n}\nmodule.exports = { greet };\n");
  put('apps/web/tests/greeter.test.js', "const { test } = require('node:test'); const assert = require('node:assert'); const { greet } = require('../src/greeter.js');\ntest('greets', () => assert.equal(greet('x'), 'hello x'));\n");
  put('apps/web/.gitignore', 'node_modules\n'); fs.mkdirSync(path.join(fx, 'apps/web/node_modules'), { recursive: true });
  G(fx, 'init', '-q', '-b', 'main'); G(fx, 'add', '-A'); G(fx, 'commit', '-qm', 'fixture'); sha = G(fx, 'rev-parse', 'HEAD');
  execFileSync('git', ['init', '-q', '--bare', '-b', 'main', bare]); G(fx, 'push', '-q', bare, 'main:refs/heads/main');
  // a fake gh: records its arguments and its stdin, prints a pull request URL
  const bin = path.join(tmp, 'bin'); fs.mkdirSync(bin);
  fs.writeFileSync(path.join(bin, 'gh'), `#!/bin/sh\nnode -e 'const fs=require("fs");const body=fs.readFileSync(0,"utf8");fs.appendFileSync(${JSON.stringify(ghLog)},JSON.stringify(process.argv.slice(1).concat(["BODY:"+body.length]))+"\\n")' -- "$@"\necho "https://github.com/${REPO}/pull/42"\n`, { mode: 0o755 });
  mock = await startMockInception();
  const port = await freePort(); base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir, stdio: 'ignore',
    env: { ...process.env, PATH: `${bin}:${process.env.PATH}`, PORT: String(port), HOST: '127.0.0.1', INCEPTION_API_KEY: 'test-key', INCEPTION_API_KEY_2: '', INCEPTION_BASE_URL: mock.baseUrl, OLLAMA_BASE_URL: 'http://127.0.0.1:9', JANUS_BASE_URL: 'http://127.0.0.1:9',
      UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: 'none', KUDBEE_DAILY_BUDGET_USD: '0', KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_LEARNING_DB: path.join(tmp, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), THINKBOX_EMBEDDINGS: 'off',
      KUDBEE_REPO_ROOT: fx, KUDBEE_REPO: REPO, KUDBEE_DRAFT_PR: 'on', KUDBEE_PR_REMOTE_URL: bare },
  });
  for (const end = Date.now() + 20000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) { try { if ((await fetch(`${base}/api/health`)).ok) return; } catch { /* starting */ } }
  throw new Error('server did not start');
});
after(async () => { server?.kill(); await mock?.close(); await new Promise((r) => setTimeout(r, 400)); if (tmp) fs.rmSync(tmp, { recursive: true, force: true }); });

const post = async (p: string, body: unknown = {}) => { const r = await fetch(`${base}${p}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }); return { status: r.status, body: await r.json() as any }; };
const get = async (p: string) => (await fetch(`${base}${p}`)).json() as Promise<any>;
function session(approve: (req: any) => boolean) {
  const ws = new WebSocket(`${base.replace('http', 'ws')}/ws`, { origin: base });
  const messages: any[] = []; const approvals: any[] = [];
  const ready = new Promise<void>((resolve, reject) => { ws.on('error', reject); ws.on('message', (raw) => {
    const m = JSON.parse(raw.toString()); messages.push(m);
    if (m.type === 'init') resolve();
    if (m.type === 'approval_request') { approvals.push(m.data); ws.send(JSON.stringify({ type: 'approval_response', id: m.data.id, approved: approve(m.data) })); }
  }); });
  const waitFor = (pred: (m: any) => boolean, ms = 30000): Promise<any> => new Promise((resolve, reject) => {
    const started = Date.now(); const tick = (): void => { const hit = messages.find(pred); if (hit) return resolve(hit); if (Date.now() - started > ms) return reject(new Error('timeout waiting for message')); setTimeout(tick, 25); }; tick();
  });
  return { ws, messages, approvals, ready, waitFor, send: (m: unknown) => ws.send(JSON.stringify(m)), close: () => ws.close() };
}

describe('SIMULATE -> accepted -> draft pull request, through the real server', { skip }, () => {
  let id = ''; let before: string;
  it('a SIMULATE convoy verifies the proposal in the sandbox (approved by a human) and waits for review', async () => {
    mock.script([call('propose_change', { edits: [{ path: 'apps/web/src/greeter.js', find: "'helo '", replace: "'hello '" }], summary: 'Fixes the typo.' }), say('Fixes the typo.')]);
    before = fixtureState();
    const planned = (await post('/api/convoys/plan', { goal: "The greeting test in apps/web/tests/greeter.test.js fails because greet() says 'helo' instead of 'hello'. Fix it.", mode: 'simulate' })).body.convoy;
    assert.equal(planned.plan.executable, true, JSON.stringify(planned.plan.blocked_reasons)); id = planned.id;
    assert.equal((await post(`/api/convoys/${id}/submit`)).status, 200);
    const s = session(() => true); await s.ready; s.send({ type: 'convoy_approve', id });
    await s.waitFor((m) => m.type === 'convoy_update' && m.data.id === id && ['COMPLETED', 'PARTIAL', 'FAILED'].includes(m.data.state)); s.close();
    const d = (await get(`/api/convoys/${id}`)).convoy;
    assert.equal(d.state, 'COMPLETED', JSON.stringify(d.error)); assert.equal(d.simulation.verified, true); assert.equal(d.review.state, 'pending');
    assert.equal(d.draft_pr_available, false); assert.match(d.draft_pr_reason, /a human must accept/);
    assert.equal(fixtureState(), before, 'the verification did not touch the checkout');
  });

  it('before the review is accepted a human is told no, and nothing is pushed or created', async () => {
    const s = session(() => true); await s.ready; s.send({ type: 'convoy_open_draft_pr', id });
    const err = await s.waitFor((m) => m.type === 'convoy_error' && m.data.id === id); s.close();
    assert.match(err.data.error, /a human must accept the convoy's outcome first/); assert.equal(s.approvals.length, 0, 'no approval was even requested');
    assert.deepEqual(remoteRefs(), ['refs/heads/main']); assert.deepEqual(ghCalls(), []);
  });

  it('after acceptance, a DECLINED approval pushes nothing and creates nothing; the request names the repository, base, branch, patch and files', async () => {
    const accept = session(() => true); await accept.ready; accept.send({ type: 'convoy_review', id, decision: 'accept' });
    await accept.waitFor((m) => m.type === 'convoy_update' && m.data.id === id && m.data.review === 'accepted'); accept.close();
    const d = (await get(`/api/convoys/${id}`)).convoy; assert.equal(d.draft_pr_available, true);
    const s = session(() => false); await s.ready; s.send({ type: 'convoy_open_draft_pr', id });
    const err = await s.waitFor((m) => m.type === 'convoy_error' && m.data.id === id); s.close();
    assert.match(err.data.error, /declined: nothing was pushed/);
    const req = s.approvals[0]; assert.equal(req.tool, 'open_draft_pr');
    assert.match(req.reason, new RegExp(`^Open a DRAFT pull request on ${REPO} \\(base main, new branch kudbee/sim-${id.slice(0, 8)}-[0-9a-f]{8}\\)`));
    assert.equal(req.args.repo, REPO); assert.equal(req.args.draft, true); assert.equal(req.args.base_commit, sha); assert.deepEqual(req.args.files, ['apps/web/src/greeter.js']);
    assert.deepEqual(remoteRefs(), ['refs/heads/main']); assert.deepEqual(ghCalls(), []);
  });

  it('an APPROVED request pushes exactly one new branch, creates the draft, records it on the convoy, and leaves the checkout untouched', async () => {
    const s = session(() => true); await s.ready; s.send({ type: 'convoy_open_draft_pr', id });
    const upd = await s.waitFor((m) => m.type === 'convoy_update' && m.data.id === id && m.data.draft_pr?.state === 'opened'); s.close();
    assert.equal(upd.data.draft_pr.url, `https://github.com/${REPO}/pull/42`);
    const refs = remoteRefs(); assert.equal(refs.length, 2); assert.ok(refs.includes('refs/heads/main') && refs.includes(`refs/heads/kudbee/sim-${id.slice(0, 8)}-${upd.data.draft_pr.branch.slice(-8)}`));
    assert.equal(G(bare, 'rev-parse', 'refs/heads/main'), sha, 'the remote base did not move');
    assert.match(G(bare, 'show', `${upd.data.draft_pr.branch}:apps/web/src/greeter.js`), /'hello '/);
    const calls = ghCalls(); assert.equal(calls.length, 1);
    assert.deepEqual(calls[0]!.slice(0, 9), ['pr', 'create', '--repo', REPO, '--draft', '--base', 'main', '--head', upd.data.draft_pr.branch]);
    const d = (await get(`/api/convoys/${id}`)).convoy;
    assert.equal(d.draft_pr.state, 'opened'); assert.equal(d.draft_pr.by, 'human'); assert.equal(d.draft_pr_available, false); assert.equal(d.chain.ok, true, 'the evidence chain still verifies');
    assert.ok(d.events.some((e: any) => /draft pull request opened: https:\/\/github\.com\/Acme\/widgets\/pull\/42/.test(e.note ?? e.message ?? JSON.stringify(e))));
    assert.equal(fixtureState(), before, 'the checkout (refs, index, work tree) is exactly as it was');
  });

  it('a second request for the same convoy is refused: it was already opened', async () => {
    const s = session(() => true); await s.ready; s.send({ type: 'convoy_open_draft_pr', id });
    const err = await s.waitFor((m) => m.type === 'convoy_error' && m.data.id === id && /already opened/.test(m.data.error)); s.close();
    assert.match(err.data.error, /already opened: https:\/\/github\.com\/Acme\/widgets\/pull\/42/); assert.equal(s.approvals.length, 0);
    assert.equal(ghCalls().length, 1); assert.equal(remoteRefs().length, 2);
  });

  it('the draft PR is reachable only over the authenticated socket: there is no HTTP route for it', async () => {
    for (const p of [`/api/convoys/${id}/draft-pr`, `/api/convoys/${id}/open_draft_pr`, '/api/draft-pr']) { const r = await fetch(`${base}${p}`, { method: 'POST' }); assert.ok(r.status === 404 || r.status === 405, `${p} -> ${r.status}`); }
    assert.equal(ghCalls().length, 1);
  });
});
