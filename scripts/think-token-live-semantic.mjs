// Live check of the real server path with embeddings on: which ranker ranked each goal, retrieval and goal latency, peak RAM.
// Usage: node scripts/think-token-live-semantic.mjs <seed.db> <out.json> [goals...]   (needs INCEPTION_API_KEY in the repo .env; a few cents of Mercury)
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const appDir = path.join(root, 'apps/web');
const { WebSocket } = createRequire(path.join(appDir, 'package.json'))('ws');
const [seed, outFile, ...argGoals] = process.argv.slice(2);
const GOALS = argGoals.length ? argGoals : [
  'Make a blank document with nothing inside it, then say what size the tool reported.',
  'Create a note holding one capital letter, then swap it for a different letter so only the new one remains.',
  'Give me a digest of the quarterly numbers document; I am not sure it was ever uploaded.',
];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const rss = (pid) => { try { const t = fs.readFileSync(`/proc/${pid}/status`, 'utf8'); return { rss_mb: Math.round(Number(/VmRSS:\s+(\d+)/.exec(t)[1]) / 1024), peak_mb: Math.round(Number(/VmHWM:\s+(\d+)/.exec(t)[1]) / 1024) }; } catch { return null; } };

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'tt-live-sem-'));
fs.mkdirSync(path.join(dir, 'data'), { recursive: true });
fs.copyFileSync(seed, path.join(dir, 'data', 'think-tokens.db'));
const port = 3400 + Math.floor(Math.random() * 400);
const child = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
  cwd: appDir, stdio: 'ignore',
  env: { ...process.env, PORT: String(port), KUDBEE_DATA_DIR: path.join(dir, 'data'), KUDBEE_WORKSPACE_DIR: path.join(dir, 'ws'), THINKBOX_TOKEN_MODEL_CALLS_PER_RUN: '0', THINKBOX_EMBED_CACHE: process.env.THINKBOX_EMBED_CACHE ?? path.join(appDir, 'data/models') },
});
const result = { started: new Date().toISOString(), goals: [] };
try {
  for (let i = 0; i < 60; i += 1) { try { if ((await fetch(`http://127.0.0.1:${port}/api/health`)).ok) break; } catch { /* starting */ } await sleep(500); }
  const t0 = Date.now();
  result.ram_before_model = rss(child.pid);
  await sleep(Number(process.env.WAIT_MS ?? 30000)); // the model loads in the background at start
  result.waited_ms = Date.now() - t0;
  result.ram_after_wait = rss(child.pid);
  for (const goal of GOALS) {
    const started = Date.now();
    const thoughts = [];
    await new Promise((resolve) => {
      const ws = new WebSocket(`ws://127.0.0.1:${port}`, { headers: { Origin: `http://127.0.0.1:${port}` } });
      const timer = setTimeout(() => { ws.close(); resolve(); }, 120_000);
      ws.on('message', (raw) => {
        let m; try { m = JSON.parse(raw.toString()); } catch { return; }
        if (m.type === 'init') ws.send(JSON.stringify({ type: 'run_goal', goal }));
        if (m.type === 'approval_request') ws.send(JSON.stringify({ type: 'approval_response', id: m.data.id, approved: true }));
        if (m.type === 'thought' && m.data?.type === 'think_token') thoughts.push(m.data.content);
        if (m.type === 'result') { clearTimeout(timer); ws.close(); resolve(); }
      });
      ws.on('error', () => { clearTimeout(timer); resolve(); });
    });
    result.goals.push({ goal, goal_ms: Date.now() - started, think_token_thoughts: thoughts, ram: rss(child.pid) });
    console.log(thoughts.find((t) => t.startsWith('Think Token ranking')) ?? '(no ranking thought)', `| ${Date.now() - started} ms`);
  }
  result.ram_end = rss(child.pid);
} finally {
  child.kill();
}
fs.writeFileSync(outFile, `${JSON.stringify(result, null, 2)}\n`);
