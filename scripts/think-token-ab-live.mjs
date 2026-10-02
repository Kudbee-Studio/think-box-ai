// ADR 029 P3 live A/B: does retrieving Think Tokens change real runs?
//
// Usage: node scripts/think-token-ab-live.mjs <seed-think-tokens.db> <out.json> [reps=2] [goals-module.mjs]
// A goals module exports `GOALS` (see below); it defaults to the built-in set. Total worker cost is summed from the server's run
// records and the script stops once it passes MAX_SPEND_USD (default 2).
//
// For each arm (retrieval off, retrieval on) it starts a real server on 127.0.0.1 against its OWN COPY of the seed database
// and its own throwaway data/workspace dirs, with THINKBOX_TOKEN_MODEL_CALLS_PER_RUN=0 so no run learns anything (both arms see
// the same fixed token set). It then runs every goal `reps` times over the real WebSocket protocol with the real model (Mercury 2 via
// the repo-root .env key, which this script never reads or prints) and records, per run, what the server recorded
// (status, steps, tool calls, tokens, cost, time) plus an objective file check. Nothing is simulated.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const appDir = path.join(root, 'apps/web');
const { WebSocket } = createRequire(path.join(appDir, 'package.json'))('ws');
const [seed, outFile, repsArg, goalsModule] = process.argv.slice(2);
const MAX_SPEND_USD = Number(process.env.MAX_SPEND_USD ?? 2);
if (!seed || !outFile) throw new Error('usage: think-token-ab-live.mjs <seed.db> <out.json> [reps]');
const REPS = Number(repsArg ?? 2);

// Each goal has an objective check on the files the run left in its workspace. `related` marks goals the seed tokens are about.
const BUILTIN_GOALS = [
  { id: 'checklist', related: true, goal: 'Use write_file to save a release checklist (a markdown heading and at least 4 bullet items) in release.md, then confirm it was created.', check: (f) => /^#/m.test(f['release.md'] ?? '') && (f['release.md'].match(/^\s*[-*] /gm) ?? []).length >= 4 },
  { id: 'notes', related: true, goal: 'Create notes.md containing a markdown heading "Notes" and three bullet points about testing, then tell me how many bytes it is.', check: (f) => /Notes/.test(f['notes.md'] ?? '') && (f['notes.md'].match(/^\s*[-*] /gm) ?? []).length >= 3 },
  { id: 'two-files', related: true, goal: 'Write alpha.md with the single line "alpha" and beta.md with the single line "beta", then list the workspace.', check: (f) => /alpha/.test(f['alpha.md'] ?? '') && /beta/.test(f['beta.md'] ?? '') },
  { id: 'exact-line', related: true, goal: 'Write changelog.md whose entire content is exactly the line "v1.2.3 - fixed login" and verify the content by reading it back.', check: (f) => (f['changelog.md'] ?? '').trim() === 'v1.2.3 - fixed login' },
  { id: 'arithmetic', related: false, goal: 'What is 17 * 23? Answer with just the number and do not use any tools.', check: (_f, answer) => /391/.test(answer ?? '') },
  { id: 'no-file', related: false, goal: 'Name the three primary colors in one short sentence. Do not use any tools.', check: (_f, answer) => /red/i.test(answer ?? '') && /blue/i.test(answer ?? '') && /yellow/i.test(answer ?? '') },
];

const GOALS = goalsModule ? (await import(path.resolve(goalsModule))).GOALS : BUILTIN_GOALS;
let spent = 0;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function startServer(arm, port) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), `tt-ab-${arm}-`));
  const data = path.join(dir, 'data');
  fs.mkdirSync(data, { recursive: true });
  fs.copyFileSync(seed, path.join(data, 'think-tokens.db'));
  const env = {
    ...process.env, PORT: String(port), KUDBEE_DATA_DIR: data, KUDBEE_WORKSPACE_DIR: path.join(dir, 'ws'),
    THINKBOX_TOKEN_RETRIEVAL: arm === 'off' ? 'off' : '1', THINKBOX_TOKEN_MODEL_CALLS_PER_RUN: '0',
  };
  const child = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], { cwd: appDir, env, stdio: ['ignore', 'ignore', 'ignore'] });
  for (let i = 0; i < 60; i += 1) {
    try { if ((await fetch(`http://127.0.0.1:${port}/api/runs`)).ok) return { child, dir, port }; } catch { /* not up yet */ }
    await sleep(500);
  }
  child.kill();
  throw new Error(`server for arm ${arm} did not start`);
}

function runGoal(port, goal) {
  return new Promise((resolve) => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}`, { headers: { Origin: `http://127.0.0.1:${port}` } });
    let sessionId = null;
    const done = (v) => { try { ws.close(); } catch { /* closed */ } resolve({ sessionId, ...v }); };
    const timer = setTimeout(() => done({ timeout: true }), 180_000);
    ws.on('message', (raw) => {
      let msg; try { msg = JSON.parse(raw.toString()); } catch { return; }
      if (msg.type === 'init' && !sessionId) { sessionId = msg.data.sessionId; ws.send(JSON.stringify({ type: 'run_goal', goal })); }
      if (msg.type === 'approval_request') ws.send(JSON.stringify({ type: 'approval_response', id: msg.data.id, approved: true }));
      if (msg.type === 'result') { clearTimeout(timer); done({ result: msg.data }); }
    });
    ws.on('error', () => { clearTimeout(timer); done({ error: true }); });
  });
}

function readFiles(dir, sessionId) {
  const out = {};
  const base = path.join(dir, 'ws', String(sessionId));
  try { for (const name of fs.readdirSync(base)) { const p = path.join(base, name); if (fs.statSync(p).isFile()) out[name] = fs.readFileSync(p, 'utf8'); } } catch { /* no workspace */ }
  return out;
}

const rows = [];
let port = 3300 + Math.floor(Math.random() * 400);
for (const arm of ['off', 'on']) {
  const srv = await startServer(arm, port);
  try {
    for (const g of GOALS) {
      for (let rep = 1; rep <= REPS; rep += 1) {
        const t0 = Date.now();
        const r = await runGoal(srv.port, g.goal);
        const run = r.result?.run_id ? await (await fetch(`http://127.0.0.1:${srv.port}/api/runs/${r.result.run_id}`)).json() : null;
        const files = readFiles(srv.dir, r.sessionId);
        const answer = String(run?.result ?? '');
        const completed = run?.status === 'completed';
        rows.push({
          arm, goal: g.id, related: g.related, rep, completed, objective_ok: completed && Boolean(g.check(files, answer)),
          steps: run?.steps?.length ?? null, tool_calls: run?.tool_calls ?? null, prompt_tokens: run?.prompt_tokens ?? null, completion_tokens: run?.completion_tokens ?? null,
          cost_usd: run?.cost_usd ?? null, duration_ms: run?.duration_ms ?? Date.now() - t0, tokens_injected: run?.think_tokens ?? [], timeout: Boolean(r.timeout), error: run?.error ?? null,
        });
        spent += run?.cost_usd ?? 0;
        console.log(arm, g.id, rep, completed ? 'completed' : 'NOT completed', rows.at(-1).objective_ok ? 'ok' : 'check-failed', `tools=${rows.at(-1).tool_calls}`, `injected=${rows.at(-1).tokens_injected.length}`);
      }
      if (spent > MAX_SPEND_USD) break;
    }
  } finally {
    srv.child.kill();
    port += 1;
    await sleep(500);
  }
}
fs.writeFileSync(outFile, `${JSON.stringify({ seed: path.basename(seed), reps: REPS, spent_usd: spent, stopped_on_spend_cap: spent > MAX_SPEND_USD, goals: GOALS.map(({ id, related, goal }) => ({ id, related, goal })), rows }, null, 2)}\n`);
console.log('wrote', outFile, rows.length, 'runs');
