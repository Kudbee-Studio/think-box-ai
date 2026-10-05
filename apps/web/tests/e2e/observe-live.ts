// Opt-in LIVE proof of M1 (npm run test:live-observe): a real server, real Qwen (Ollama), the REAL repository, read-only repo tools, a convoy approved over the
// socket. No fakes. The finding is then re-checked INDEPENDENTLY by this script (reads the file itself and greps tests/). Output:
// docs/evidence/model-integration/observe-live-<goal>.json. Approvals are granted by the script (stand-in for the human); mode OBSERVE writes nothing.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';
import { writeEvidence } from '../helpers/evidence-file.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const repoRoot = path.resolve(appDir, '../..');
const OUT = path.join(repoRoot, 'docs/evidence/model-integration/observe-live-<goal>.json');
const model = process.argv[2] || 'qwen2.5:3b';
const goal = process.argv[3] || 'Find one function in apps/web that has no test';
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-observe-'));
const port = 27000 + Math.floor(Math.random() * 8000);
const base = `http://127.0.0.1:${port}`;
const server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], { cwd: appDir, stdio: 'ignore',
  env: { ...process.env, PORT: String(port), INCEPTION_API_KEY: '', INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434', JANUS_BASE_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: 'none', THINKBOX_EMBEDDINGS: 'off', KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_LEARNING_DB: path.join(tmp, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), KUDBEE_REPO_ROOT: repoRoot, THINKBOX_LOCAL_MODEL: model } });
process.on('exit', () => { try { server.kill(); } catch { /* gone */ } fs.rmSync(tmp, { recursive: true, force: true }); });
const post = async (p: string, body: unknown) => { const r = await fetch(`${base}${p}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }); return { status: r.status, body: await r.json() as any }; };
const get = async (p: string) => (await fetch(`${base}${p}`)).json() as Promise<any>;

for (let i = 0; i < 100; i++) { try { if ((await fetch(`${base}/api/health`)).ok) break; } catch { /* starting */ } await sleep(150); }
const messages: any[] = []; const approvals: any[] = [];
const ws = new WebSocket(`${base.replace('http', 'ws')}/ws`, { origin: base });
await new Promise<void>((resolve, reject) => { ws.on('error', reject); ws.on('message', (raw) => { const m = JSON.parse(raw.toString()); messages.push(m); if (m.type === 'init') resolve(); if (m.type === 'approval_request') { approvals.push(m.data); ws.send(JSON.stringify({ type: 'approval_response', id: m.data.id, approved: true })); } }); });
const planned = (await post('/api/convoys/plan', { goal, model })).body.convoy;
console.log(`PLAN   ${planned.state} mode=${planned.mode} think_mode=${planned.plan.think_mode} executable=${planned.plan.executable} workers=${planned.plan.workers.map((w: any) => `${w.id}:${w.model}`).join(',')} ${planned.plan.blocked_reasons.join('; ')}`);
if (!planned.plan.executable) { await writeEvidence(path.dirname(OUT), OUT, { goal, model, plan: planned.plan, stopped: 'not executable' }); process.exit(1); }
await post(`/api/convoys/${planned.id}/submit`, {});
const t0 = Date.now();
ws.send(JSON.stringify({ type: 'convoy_approve', id: planned.id }));
for (;;) { await sleep(500); const hit = messages.find((m) => m.type === 'convoy_update' && m.data.id === planned.id && ['COMPLETED', 'PARTIAL', 'FAILED'].includes(m.data.state)); if (hit) break; if (Date.now() - t0 > 600_000) throw new Error('timeout'); }
const c = (await get(`/api/convoys/${planned.id}`)).convoy;
// independent verification, outside the app: read the cited file ourselves and grep the tests folder
let independent: any = { skipped: 'no finding' };
if (c.finding?.found) {
  const abs = path.join(repoRoot, c.finding.file);
  const lines = fs.existsSync(abs) ? fs.readFileSync(abs, 'utf8').split('\n') : [];
  const norm = (s: string) => s.replace(/\s+/g, ' ').trim().toLowerCase();
  const window = norm(lines.slice(c.finding.line - 1, c.finding.line + 2).join(' '));
  const name = c.finding.absence_search?.query;
  let hits: string[] = [];
  if (name) { const walk = (d: string) => { for (const e of fs.readdirSync(d, { withFileTypes: true })) { const p = path.join(d, e.name); if (e.isSymbolicLink() || e.name === 'node_modules') continue; if (e.isDirectory()) walk(p); else if (/\.(ts|js|mjs)$/.test(e.name) && fs.readFileSync(p, 'utf8').includes(name)) hits.push(path.relative(repoRoot, p)); } }; walk(path.join(repoRoot, c.finding.absence_search.path || 'apps/web/tests')); }
  independent = { file_exists: lines.length > 0, quote_at_line: window.includes(norm(c.finding.quote)), absence_query: name ?? null, absence_scope: c.finding.absence_search?.path ?? null, files_containing_query_in_scope: hits };
}
console.log(`${c.state} outcome=${c.outcome} ${Date.now() - t0}ms tools=${c.tool_calls} tokens=${c.tokens} cost=$${c.cost_usd} grounding=${c.grounding?.status ?? 'n/a'}\n  finding: ${JSON.stringify(c.finding)}\n  disk: ${JSON.stringify(c.finding_check)}\n  independent: ${JSON.stringify(independent)}\n  error: ${c.error ?? '-'}`);
await writeEvidence(path.dirname(OUT), OUT, { generated_at: new Date().toISOString(), note: 'real server, real Qwen via Ollama, the real repository; tool approvals (none expected for read-only tools) granted by the script', goal, model, wall_ms: Date.now() - t0, plan: { think_mode: planned.plan.think_mode, workers: planned.plan.workers, budget_use: planned.plan.budget_use }, policy: planned.policy.rules.map((r: any) => r.id), approvals_prompted: approvals.length, state: c.state, outcome: c.outcome, finding: c.finding, finding_check: c.finding_check, grounding: c.grounding, final_answer: c.final_answer, error: c.error, tool_calls: c.tool_calls, tokens: c.tokens, cost_usd: c.cost_usd, repo_evidence: c.repo_evidence, steps: c.runs?.[0]?.steps?.map((s: any) => ({ kind: s.kind, name: s.name, ok: s.ok, args: s.args, content: s.content?.slice(0, 300) })), independent_check: independent, events: c.events.map((e: any) => ({ seq: e.seq, state: e.state, by: e.by })) });
ws.close(); process.exit(0);
