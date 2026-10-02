// Live check of "fresh evidence beats memory": run one goal through the real server path with the real model against a COPY of a data directory
// (so a stale memory in it is present), auto-approve network access, and record the thought stream and the answer. Usage:
//   node scripts/live-evidence-check.mjs <data-dir-to-copy> <out.json> "<goal>"      (needs INCEPTION_API_KEY in the repo .env)
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const appDir = path.join(root, 'apps/web');
const { WebSocket } = createRequire(path.join(appDir, 'package.json'))('ws');
const [dataSrc, outFile, goal] = process.argv.slice(2);
if (!dataSrc || !outFile || !goal) throw new Error('usage: live-evidence-check.mjs <data-dir> <out.json> "<goal>"');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'live-evidence-'));
fs.cpSync(dataSrc, path.join(dir, 'data'), { recursive: true, filter: (p) => !/\.bak-|think-tokens\.db-(shm|wal)$/.test(p) });
const port = 3500 + Math.floor(Math.random() * 400);
const child = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], { cwd: appDir, stdio: 'ignore',
  env: { ...process.env, PORT: String(port), KUDBEE_DATA_DIR: path.join(dir, 'data'), KUDBEE_WORKSPACE_DIR: path.join(dir, 'ws'), THINKBOX_TOKEN_MODEL_CALLS_PER_RUN: '0' } });
const out = { goal, thoughts: [], approvals: [] };
try {
  for (let i = 0; i < 60; i += 1) { try { if ((await fetch(`http://127.0.0.1:${port}/api/health`)).ok) break; } catch { /* starting */ } await sleep(500); }
  await new Promise((resolve) => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}`, { headers: { Origin: `http://127.0.0.1:${port}` } });
    const timer = setTimeout(() => { ws.close(); resolve(); }, 150_000);
    ws.on('message', (raw) => {
      let m; try { m = JSON.parse(raw.toString()); } catch { return; }
      if (m.type === 'init') ws.send(JSON.stringify({ type: 'run_goal', goal }));
      if (m.type === 'approval_request') { out.approvals.push(m.data.reason); ws.send(JSON.stringify({ type: 'approval_response', id: m.data.id, approved: true })); }
      if (m.type === 'thought') out.thoughts.push(`${m.data?.type}: ${String(m.data?.content ?? '').slice(0, 300)}`);
      if (m.type === 'result') { out.result = m.data; clearTimeout(timer); ws.close(); resolve(); }
    });
    ws.on('error', () => { clearTimeout(timer); resolve(); });
  });
  if (out.result?.run_id) out.run = await (await fetch(`http://127.0.0.1:${port}/api/runs/${out.result.run_id}`)).json().then((r) => ({ status: r.status, result: r.result, evidence_conflicts: r.evidence_conflicts ?? null, cost_usd: r.cost_usd, tool_calls: r.tool_calls }));
} finally { child.kill(); }
fs.writeFileSync(outFile, `${JSON.stringify(out, null, 2)}\n`);
console.log(JSON.stringify({ answer: out.result?.result, conflicts: out.run?.evidence_conflicts, cost: out.run?.cost_usd, evidence_thoughts: out.thoughts.filter((t) => /Evidence check|Think Token ranking|Using/.test(t)) }, null, 1));
