// Batch coverage for the kudbee CLI's command surface and the server routes it drives. Real server.ts with a mocked model;
// every command is read-only or self-contained and must exit 0. Interactive-only commands (/skill, /plugin) are left out.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { startMockInception, type MockInception } from './helpers/mock-inception.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEAD = 'http://127.0.0.1:9';
let mock: MockInception;
let server: ChildProcess;
let base: string;
let tmp: string;
let dataDir: string;

before(async () => {
  mock = await startMockInception();
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-cli-cmd-'));
  dataDir = path.join(tmp, 'data');
  const port = 20000 + Math.floor(Math.random() * 20000);
  base = `http://127.0.0.1:${port}`;
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: { ...process.env, PORT: String(port), INCEPTION_API_KEY: 'test-key', INCEPTION_BASE_URL: mock.baseUrl, OLLAMA_BASE_URL: DEAD, JANUS_BASE_URL: DEAD,
      UPSTASH_VECTOR_REST_URL: DEAD, UPSTASH_VECTOR_REST_TOKEN: 'none', KUDBEE_DAILY_BUDGET_USD: '0', KUDBEE_DATA_DIR: dataDir,
      KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), THINKBOX_EMBEDDINGS: 'off' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) {
    try { if ((await fetch(`${base}/api/health`)).ok) return; } catch { /* starting */ }
  }
  throw new Error('server did not start');
});
after(async () => { server?.kill(); await mock.close(); fs.rmSync(tmp, { recursive: true, force: true }); });

const runCli = (args: string[], home: string): Promise<{ status: number | null; stdout: string; stderr: string }> => new Promise((resolve) => {
  const child = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'cli.ts', ...args], { cwd: appDir, env: { ...process.env, KUDBEE_URL: base, KUDBEE_DATA_DIR: dataDir, HOME: home } });
  let stdout = '';
  let stderr = '';
  child.stdout.on('data', (d) => (stdout += d));
  child.stderr.on('data', (d) => (stderr += d));
  const timer = setTimeout(() => child.kill(), 30000);
  child.on('close', (status) => { clearTimeout(timer); resolve({ status, stdout, stderr }); });
});

const home = (): string => fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-cli-home-'));

// Each command is its own test so one failure points at that command; the point is to exercise the switch and the routes.
const COMMANDS: string[][] = [
  ['/help'], ['/models'], ['/agents'], ['/agent'], ['/plugins'], ['/files'], ['/session'], ['/tokens'], ['/runs'],
  ['/memory'], ['/notes'], ['/metrics'], ['/model'], ['/config'], ['/capacity'], ['/agent', 'hermes'],
  ['/notes', 'org'], ['/tokens', '--run', 'none'],
];

for (const args of COMMANDS) {
  test(`CLI ${args.join(' ')} exits 0`, async () => {
    const out = await runCli(args, home());
    assert.equal(out.status, 0, `${args.join(' ')} -> ${out.status}: ${out.stderr}`);
    assert.equal(/kudbee: /.test(out.stderr), false, out.stderr);
  });
}

test('CLI /remember then /forget exercises the memory write/delete routes', async () => {
  const h = home();
  const remembered = await runCli(['/remember', 'Coverage note', '-', 'a note written by the CLI coverage test'], h);
  assert.equal(remembered.status, 0, remembered.stderr);
  const forgotten = await runCli(['/forget', 'Coverage note'], h);
  assert.equal(forgotten.status, 0, forgotten.stderr);
});
