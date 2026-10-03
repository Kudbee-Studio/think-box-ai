// P3.11 live link: the kudbee CLI and the dashboard share one engine. Real server.ts with a mocked model; the CLI is authenticated by a local token
// file (never printed), its runs are mirrored to subscribed dashboards, and the CLI refuses non-loopback servers.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, spawnSync, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';
import { startMockInception, say, type MockInception } from './helpers/mock-inception.ts';
import { TOKEN_FILE, TOKEN_HEADER, ensureLocalToken, isLoopbackUrl, readLocalToken, tokensMatch } from '../local-token.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEAD = 'http://127.0.0.1:9';
let mock: MockInception;
let server: ChildProcess;
let base: string;
let tmp: string;
let dataDir: string;
let log = '';

before(async () => {
  mock = await startMockInception();
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-link-'));
  dataDir = path.join(tmp, 'data');
  const port = 20000 + Math.floor(Math.random() * 20000);
  base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: { ...process.env, PORT: String(port), INCEPTION_API_KEY: 'test-key', INCEPTION_BASE_URL: mock.baseUrl, OLLAMA_BASE_URL: DEAD, JANUS_BASE_URL: DEAD, UPSTASH_VECTOR_REST_URL: DEAD, UPSTASH_VECTOR_REST_TOKEN: 'none',
      KUDBEE_DAILY_BUDGET_USD: '0', KUDBEE_REPO: 'Acme/widgets', KUDBEE_DATA_DIR: dataDir, KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), THINKBOX_EMBEDDINGS: 'off' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  server.stdout?.on('data', (d) => { log += d; });
  server.stderr?.on('data', (d) => { log += d; });
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) {
    try { if ((await fetch(`${base}/api/health`)).ok) return; } catch { /* starting */ }
  }
  throw new Error('server did not start');
});
after(async () => { server?.kill(); await mock.close(); fs.rmSync(tmp, { recursive: true, force: true }); });

const open = (headers: Record<string, string> = {}): Promise<{ ws: WebSocket; messages: any[]; sessionId: string }> =>
  new Promise((resolve, reject) => {
    const ws = new WebSocket(`${base.replace('http', 'ws')}/ws`, { origin: base, headers });
    const messages: any[] = [];
    ws.on('error', reject);
    ws.on('unexpected-response', (_req, res) => reject(new Error(`HTTP ${res.statusCode}`)));
    ws.on('message', (raw) => { const m = JSON.parse(raw.toString()); messages.push(m); if (m.type === 'init') resolve({ ws, messages, sessionId: m.data.sessionId }); });
  });

test('the server creates the token file with mode 0600; reading and comparing it works; nothing prints it', () => {
  const file = path.join(dataDir, TOKEN_FILE);
  assert.ok(fs.existsSync(file));
  assert.equal(fs.statSync(file).mode & 0o777, 0o600);
  const token = readLocalToken(dataDir)!;
  assert.match(token, /^[0-9a-f]{64}$/);
  assert.equal(ensureLocalToken(dataDir), token, 'ensure is idempotent');
  assert.equal(tokensMatch(token, token), true);
  assert.equal(tokensMatch(token, token.slice(1) + '0'), false);
  assert.equal(tokensMatch(token, undefined), false);
  assert.equal(log.includes(token), false, 'the server log never contains the token');
});

test('isLoopbackUrl accepts only this machine', () => {
  for (const ok of ['http://127.0.0.1:3000', 'http://localhost:3000', 'http://[::1]:3000']) assert.equal(isLoopbackUrl(ok), true, ok);
  for (const bad of ['http://192.168.1.5:3000', 'http://example.com', 'http://0.0.0.0:3000', 'not a url']) assert.equal(isLoopbackUrl(bad), false, bad);
});

test('a wrong token is refused; the right token and no token are both accepted (CLI vs dashboard)', async () => {
  await assert.rejects(open({ [TOKEN_HEADER]: 'f'.repeat(64) }), /HTTP 401|Unexpected server response|socket hang up/i);
  const cli = await open({ [TOKEN_HEADER]: readLocalToken(dataDir)! });
  const dash = await open();
  assert.notEqual(cli.sessionId, dash.sessionId);
  cli.ws.close(); dash.ws.close();
});

test('a goal run through a CLI session shows up live in a subscribed dashboard, labeled; an unsubscribed one hears nothing; approvals stay private', async () => {
  const watcher = await open();
  const bystander = await open();
  watcher.ws.send(JSON.stringify({ type: 'subscribe_runs' }));
  await new Promise((r) => setTimeout(r, 200));
  const cli = await open({ [TOKEN_HEADER]: readLocalToken(dataDir)! });
  mock.script([say('Linked answer from the CLI session.')]);
  cli.ws.send(JSON.stringify({ type: 'run_goal', goal: 'say something' }));
  for (const end = Date.now() + 15000; Date.now() < end && !watcher.messages.some((m) => m.type === 'mirror' && m.data.message.type === 'result'); await new Promise((r) => setTimeout(r, 100)));
  const mirrored = watcher.messages.filter((m) => m.type === 'mirror');
  assert.ok(mirrored.length > 0);
  assert.ok(mirrored.every((m) => m.data.client === 'cli' && m.data.session === cli.sessionId.slice(0, 8)));
  const result = mirrored.find((m) => m.data.message.type === 'result')!;
  assert.equal(result.data.message.data.result, 'Linked answer from the CLI session.');
  assert.ok(mirrored.some((m) => m.data.message.type === 'thought'));
  assert.equal(bystander.messages.filter((m) => m.type === 'mirror').length, 0, 'not subscribed: nothing relayed');
  assert.equal(mirrored.some((m) => m.data.message.type === 'approval_request'), false, 'approvals are never relayed');
  assert.equal(JSON.stringify(watcher.messages).includes(readLocalToken(dataDir)!), false, 'the token never reaches a dashboard');
  // the run is in the shared history
  const runs = ((await (await fetch(`${base}/api/runs?limit=100`)).json()) as { runs: Array<{ goal: string }> }).runs;
  assert.ok(runs.some((r) => r.goal === 'say something'));
  for (const c of [watcher, bystander, cli]) c.ws.close();
});

test('a goal run from a dashboard session is not mirrored (only CLI runs are)', async () => {
  const watcher = await open();
  watcher.ws.send(JSON.stringify({ type: 'subscribe_runs' }));
  const other = await open();
  await new Promise((r) => setTimeout(r, 200));
  mock.script([say('From a dashboard.')]);
  other.ws.send(JSON.stringify({ type: 'run_goal', goal: 'dashboard goal' }));
  for (const end = Date.now() + 15000; Date.now() < end && !other.messages.some((m) => m.type === 'result'); await new Promise((r) => setTimeout(r, 100)));
  assert.equal(watcher.messages.filter((m) => m.type === 'mirror').length, 0);
  watcher.ws.close(); other.ws.close();
});

test('the kudbee CLI refuses a non-loopback KUDBEE_URL without sending anything, and connects to the loopback server with the token', () => {
  const run = (env: Record<string, string>, ...args: string[]) => spawnSync(process.execPath, ['--experimental-strip-types', '--no-warnings', 'cli.ts', ...args], { cwd: appDir, env: { ...process.env, ...env }, encoding: 'utf8', timeout: 20000 });
  const refused = run({ KUDBEE_URL: 'http://192.0.2.1:3000', KUDBEE_DATA_DIR: dataDir }, '/status');
  assert.equal(refused.status, 2);
  assert.match(refused.stderr, /must point to this machine/);
  const ok = run({ KUDBEE_URL: base, KUDBEE_DATA_DIR: dataDir }, '/status');
  assert.equal(ok.status, 0, ok.stderr);
  assert.match(ok.stdout, /Connected to the running Agent OS/);
  assert.equal(ok.stdout.includes(readLocalToken(dataDir)!) || ok.stderr.includes(readLocalToken(dataDir)!), false, 'the CLI never prints the token');
});

// Asynchronous on purpose: the scripted model lives in this process, so a blocking spawnSync would starve it.
const runCli = (args: string[], home: string): Promise<{ status: number | null; stdout: string; stderr: string }> => new Promise((resolve) => {
  const child = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'cli.ts', ...args], { cwd: appDir, env: { ...process.env, KUDBEE_URL: base, KUDBEE_DATA_DIR: dataDir, HOME: home } });
  let stdout = '';
  let stderr = '';
  child.stdout.on('data', (d) => (stdout += d));
  child.stderr.on('data', (d) => (stderr += d));
  const timer = setTimeout(() => child.kill(), 60000);
  child.on('close', (status) => { clearTimeout(timer); resolve({ status, stdout, stderr }); });
});
const strip = (t: string): string => t.replace(/\x1b\[[0-9;]*m/g, '');

test('/capacity prints the same server capacity numbers the dashboard shows', async () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-home-'));
  const out = await runCli(['/capacity'], home);
  const text = strip(out.stdout);
  assert.equal(out.status, 0, out.stderr);
  assert.match(text, /Capacity \(server\)/);
  assert.match(text, /Agents running: \d+ of \d+ connected session/);
  assert.match(text, /Pending approvals: \d+/);
  assert.match(text, /System memory: [\d.]+% of [\d.]+ GB/);
  assert.doesNotMatch(text, /Error fetching capacity|undefined|NaN/);
});

test('live-run fixes through the real server and CLI: the planner is told the known repository; the final answer is printed after an evidence-check retry; no repeated Ollama warning when Ollama is absent', async () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-home-'));
  const verdict = (conflict: boolean, detail: string) => say(JSON.stringify({ conflict, detail }));
  mock.script([
    { tool_calls: [{ name: 'fetch_url', args: { url: `${mock.origin}/api/pulls` } }] },
    say('We are working on PR #304, a draft.'),
    verdict(true, 'The pulls API returned an empty list, so no pull request is open.'),
    say('There are no open pull requests: the API returned an empty list. The memory about #304 is stale.'),
    verdict(false, ''),
  ]);
  const first = await runCli(['run', '--yes', 'which pull request is open?'], home);
  const out = strip(first.stdout);
  assert.equal(first.status, 0, `${first.stderr}\n${out.slice(-1500)}`);
  assert.match(mock.requests[0]!.messages[0]!.content!, /KNOWN REPOSITORY: .*Acme\/widgets/, 'the planner context names the repository');
  assert.match(out, /evidence check: the first answer conflicted/);
  assert.match(out, /✓ There are no open pull requests: the API returned an empty list\./, 'the corrected final answer is printed');
  assert.doesNotMatch(out, /not found in Ollama|local model/i, 'Ollama is absent here: no warning');
  mock.script([say('Plain answer.')]);
  const second = await runCli(['run', '--yes', 'say hi'], home);
  assert.doesNotMatch(strip(second.stdout), /not found in Ollama|local model/i);
  assert.match(strip(second.stdout), /✓ Plain answer\./);
  assert.equal(fs.existsSync(path.join(home, '.kudbee', 'local-model-warned')), false, 'nothing to warn about, so no marker either');
});
