// Local recipes through the real server: the lookup runs in code through the governed path (approval and all), the local model words the answer,
// the answer is checked against the data, and a worker agent is never involved. Fake Ollama, fake GitHub, mock Inception (must stay untouched).
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';
import { startMockInception, type MockInception } from './helpers/mock-inception.ts';
import { freePort } from './helpers/free-port.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const MODEL = 'smollm2:360m';
const ORIGINAL_PRS = [{ number: 330, title: 'P3.18: escalate goals', draft: true, user: { login: 'KudbeeZero' }, updated_at: '2026-10-02T21:42:25Z', html_url: 'https://github.com/Acme/widgets/pull/330' }];
const prs: any[] = [...ORIGINAL_PRS];
let ollama: http.Server;
let github: http.Server;
let mock: MockInception;
let server: ChildProcess;
let base = '';
let tmp = '';
let modelReply = 'We are on PR #330, a draft.';
const chats: any[] = [];
const githubHits: string[] = [];
let githubBody: unknown = null;

before(async () => {
  mock = await startMockInception();
  ollama = http.createServer((req, res) => {
    let body = '';
    req.on('data', (d) => { body += d; });
    req.on('end', () => {
      if (req.url === '/api/tags') { res.setHeader('content-type', 'application/json'); return void res.end(JSON.stringify({ models: [{ name: MODEL, size: 725_000_000 }] })); }
      if (req.url === '/api/chat') {
        chats.push(JSON.parse(body));
        res.setHeader('content-type', 'application/x-ndjson');
        res.write(`${JSON.stringify({ message: { content: modelReply }, done: false })}\n`);
        return void res.end(`${JSON.stringify({ message: { content: '' }, done: true })}\n`);
      }
      res.statusCode = 404; res.end('{}');
    });
  });
  github = http.createServer((req, res) => {
    githubHits.push(String(req.url));
    res.setHeader('content-type', 'application/json');
    res.end(JSON.stringify(githubBody ?? prs));
  });
  await Promise.all([new Promise<void>((r) => ollama.listen(0, '127.0.0.1', r)), new Promise<void>((r) => github.listen(0, '127.0.0.1', r))]);
  const ollamaUrl = `http://127.0.0.1:${(ollama.address() as { port: number }).port}`;
  const githubUrl = `http://127.0.0.1:${(github.address() as { port: number }).port}`;
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-recipes-'));
  const port = await freePort();
  base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: { ...process.env, PORT: String(port), INCEPTION_API_KEY: 'test-key', INCEPTION_API_KEY_2: '', INCEPTION_BASE_URL: mock.baseUrl, OLLAMA_BASE_URL: ollamaUrl, KUDBEE_GITHUB_API: githubUrl, KUDBEE_REPO: 'Acme/widgets',
      JANUS_BASE_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: 'none', KUDBEE_DAILY_BUDGET_USD: '0', KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), THINKBOX_EMBEDDINGS: 'off', THINKBOX_LOCAL_MODEL: MODEL },
    stdio: 'ignore',
  });
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) {
    try { if ((await fetch(`${base}/api/health`)).ok) return; } catch { /* starting */ }
  }
  throw new Error('server did not start');
});
after(async () => {
  server?.kill();
  await Promise.all([new Promise((r) => ollama.close(r)), new Promise((r) => github.close(r)), mock.close()]);
  fs.rmSync(tmp, { recursive: true, force: true });
});

/** Runs one goal on the local model in a fresh session; answers any approval request with `approve`. */
const run = (goal: string, approve = true): Promise<any[]> => new Promise((resolve, reject) => {
  const ws = new WebSocket(`${base.replace('http', 'ws')}/ws`, { origin: base });
  const messages: any[] = [];
  const timer = setTimeout(() => reject(new Error('no result')), 20000);
  ws.on('error', reject);
  ws.on('message', (raw) => {
    const m = JSON.parse(raw.toString());
    messages.push(m);
    if (m.type === 'init') ws.send(JSON.stringify({ type: 'run_goal', goal, model: MODEL }));
    if (m.type === 'approval_request') ws.send(JSON.stringify({ type: 'approval_response', id: m.data.id, approved: approve }));
    if (m.type === 'result') { clearTimeout(timer); ws.close(); resolve(messages); }
  });
});
const result = (messages: any[]) => messages.find((m) => m.type === 'result').data;
const streamed = (messages: any[]) => messages.filter((m) => m.type === 'stream').map((m) => m.data).join('');

test('"WHAT PR ARE WE ON": the lookup needs approval like any network access, the local model words the answer, the data is shown with it, Mercury is untouched', async () => {
  chats.length = 0; githubHits.length = 0;
  const before = mock.requests.length;
  const messages = await run('WHAT PR ARE WE ON');
  const approval = messages.find((m) => m.type === 'approval_request');
  assert.ok(approval, 'the first network access asks for approval');
  assert.match(approval.data.reason, /First network access to 127\.0\.0\.1/);
  assert.deepEqual(githubHits, ['/repos/Acme/widgets/pulls?state=open&per_page=5', '/search/issues?q=repo%3AAcme%2Fwidgets%20type%3Apr%20state%3Aopen&per_page=1'], 'the list, then GitHub\'s own count of open pull requests');
  const prompt = chats.at(-1).messages.at(-1).content;
  assert.match(prompt, /#330 "P3\.18: escalate goals" \(draft\)/);
  assert.ok(chats.at(-1).messages.every((m: any) => m.role !== 'system'), 'plain chat to the small model');
  const r = result(messages);
  assert.equal(r.success, true);
  assert.equal(r.recipe, 'open_prs');
  assert.equal(r.grounded, true);
  assert.deepEqual({ path: r.route.path, model: r.route.model, recipe: r.route.recipe }, { path: 'recipe', model: MODEL, recipe: 'open_prs' });
  assert.equal(r.streamed, true);
  assert.equal(r.cost_usd, 0);
  assert.match(r.result, /^We are on PR #330, a draft\.\n\nOpen pull requests in Acme\/widgets \(live from GitHub just now\): 1\./);
  assert.equal(streamed(messages), r.result, 'what streamed is what the result holds');
  assert.equal(mock.requests.length, before, 'no worker agent');
  assert.ok(messages.some((m) => m.type === 'thought' && /every number and link in it is in the data/.test(m.data?.content ?? '')));
});

test('a sentence that invents a PR number is dropped and the data itself is shown', async () => {
  modelReply = 'We are on PR #999, which is merged.';
  try {
    const messages = await run('which pull requests are open?');
    const r = result(messages);
    assert.equal(r.success, true);
    assert.equal(r.grounded, false);
    assert.match(r.result, /^GROUNDING FAILED \(unsupported_claim\)/);
    assert.match(r.result, /- id: pr 999/);
    assert.doesNotMatch(r.result, /We are on PR #999, which is merged/, 'the unsupported sentence is not shown');
    assert.match(r.result, /Open pull requests in Acme\/widgets \(live from GitHub just now\): 1\./, 'the evidence is');
    assert.equal(r.grounding.status, 'GROUNDING FAILED');
    assert.equal(r.grounding.classification, 'unsupported_claim');
    assert.ok(messages.some((m) => m.type === 'thought' && /GROUNDING FAILED: smollm2:360m's sentence was not used/.test(m.data?.content ?? '')));
  } finally { modelReply = 'We are on PR #330, a draft.'; }
});

test('a denied approval fails the goal plainly: no lookup, no model call, no made-up answer', async () => {
  chats.length = 0; githubHits.length = 0;
  const messages = await run('what PR are we working on?', false);
  const r = result(messages);
  assert.equal(r.success, false);
  assert.match(r.error, /Denied by human reviewer/);
  assert.equal(githubHits.length, 0);
  assert.ok(!chats.some((c) => String(c.messages.at(-1)?.content).includes('Open pull requests')));
});

test('listing an empty workspace needs no approval, and the model is not even asked: the data alone is the answer', async () => {
  chats.length = 0;
  modelReply = 'I have a few documents in a separate folder.'; // what a small model made up for an empty workspace
  try {
    const messages = await run('list my files');
    assert.ok(!messages.some((m) => m.type === 'approval_request'));
    const r = result(messages);
    assert.equal(r.recipe, 'list_files');
    assert.equal(r.result, 'The workspace is empty.');
    assert.equal(r.grounded, false, 'no model sentence was used');
    assert.equal(chats.length, 0, 'the model was never asked');
    assert.ok(messages.some((m) => m.type === 'thought' && /Nothing to summarise/.test(m.data?.content ?? '')));
  } finally { modelReply = 'We are on PR #330, a draft.'; }
});

test('no open pull requests: the answer is the data, with no model sentence', async () => {
  chats.length = 0;
  prs.length = 0;
  try {
    const r = result(await run('WHAT PR ARE WE ON'));
    assert.equal(r.success, true);
    assert.match(r.result, /^Open pull requests in Acme\/widgets \(live from GitHub just now\): none\.$/);
    assert.equal(chats.length, 0);
  } finally { prs.push(...ORIGINAL_PRS); }
});

test('a goal that changes something is not a recipe: it is routed to the worker agent as before', async () => {
  mock.script([{ content: 'I would need to merge it with the tools.' }]);
  const before = mock.requests.length;
  const messages = await run('merge the open PR');
  assert.ok(mock.requests.length > before, 'mercury answered');
  assert.notEqual(result(messages).recipe, 'open_prs');
});

test('"what is the last PR?" asks for any state and reports the newest one as merged, not "open"', async () => {
  chats.length = 0; githubHits.length = 0;
  githubBody = [
    { number: 361, title: 'router and recipes', state: 'closed', merged_at: '2026-10-04T12:00:00Z', draft: false, user: { login: 'KudbeeZero' }, updated_at: '2026-10-04T12:00:00Z', html_url: 'https://github.com/Acme/widgets/pull/361' },
    { number: 360, title: 'dashboard live-verify', state: 'closed', merged_at: '2026-10-04T10:00:00Z', draft: false, user: { login: 'KudbeeZero' }, updated_at: '2026-10-04T10:00:00Z', html_url: 'https://github.com/Acme/widgets/pull/360' },
  ];
  modelReply = 'The last PR is #361, router and recipes, and it is merged.';
  const before = mock.requests.length;
  try {
    const r = result(await run('what is the last PR?'));
    assert.deepEqual(githubHits, ['/repos/Acme/widgets/pulls?state=all&sort=created&direction=desc&per_page=5']);
    assert.equal(r.recipe, 'latest_pr');
    assert.equal(r.grounded, true);
    assert.equal(r.cost_usd, 0);
    assert.match(r.result, /^The last PR is #361, router and recipes, and it is merged\.\n\nMost recent pull requests in Acme\/widgets, any state, newest first/);
    assert.match(r.result, /^- #361 "router and recipes" \(merged\)/m);
    assert.equal(mock.requests.length, before, 'no worker agent');
    modelReply = 'The last PR was #360, dashboard live-verify.';
    const older = result(await run('what is the last PR?'));
    assert.equal(older.grounded, false, 'a sentence about an older PR is not used');
    assert.match(older.result, /^GROUNDING FAILED/);
    assert.match(older.result, /does not name the newest pull request \(#361\)/);
    assert.match(older.result, /- #361 "router and recipes" \(merged\)/);
  } finally { githubBody = null; modelReply = 'We are on PR #330, a draft.'; }
});

test('"did CI pass?": the newest run\'s verdict comes from the data, and a flipped sentence is dropped', async () => {
  chats.length = 0; githubHits.length = 0;
  githubBody = { workflow_runs: [{ name: 'CI', head_branch: 'main', event: 'push', status: 'completed', conclusion: 'failure', run_number: 812, updated_at: '2026-10-04T10:00:00Z', html_url: 'https://github.com/Acme/widgets/actions/runs/1' }] };
  try {
    modelReply = 'Yes, CI passed on run 812.';
    const flipped = result(await run('did CI pass?'));
    assert.deepEqual(githubHits, ['/repos/Acme/widgets/actions/runs?per_page=5&exclude_pull_requests=true']);
    assert.equal(flipped.recipe, 'ci_status');
    assert.equal(flipped.grounded, false);
    assert.match(flipped.result, /^GROUNDING FAILED/);
    assert.doesNotMatch(flipped.result, /Yes, CI passed on run 812/, 'the flipped sentence is not shown');
    assert.match(flipped.result, /The newest run: failure\./);
    assert.equal(flipped.grounding.status, 'GROUNDING FAILED');
    modelReply = 'No, the newest CI run on main failed (run 812).';
    const honest = result(await run('did CI pass?'));
    assert.equal(honest.grounded, true);
    assert.match(honest.result, /^No, the newest CI run on main failed/);
  } finally { githubBody = null; modelReply = 'We are on PR #330, a draft.'; }
});
