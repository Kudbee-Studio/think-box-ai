// Real-model answer check (no scripted model). Six conflict cases where real Mercury is likely to answer from a strongly worded memory instead of the tool
// result; each case runs once with the final-answer check ON and once OFF. The expected-correct tests below were written before any run.
// Usage: [ONLY=<case id>] node --experimental-strip-types scripts/live-answer-check.mjs <out.json>      (INCEPTION_API_KEY from the repo .env, never printed)
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
for (const f of [path.join(root, '.env'), path.join(root, 'apps/web/.env')]) { try { process.loadEnvFile(f); } catch { /* optional */ } }
const agent = await import(pathToFileURL(path.join(root, 'apps/web/agent.ts')).href);
const { MemoryStore } = await import(pathToFileURL(path.join(root, 'apps/web/memory.ts')).href);

const routes = {
  '/pulls': [200, '[]'],
  '/ci': [200, '{"total_count":0,"workflow_runs":[]}'],
  '/health': [503, 'service unavailable'],
  '/wallet': [404, '{"error":"not found"}'],
  '/pulls2': [200, '[{"number":322,"title":"Real current PR","state":"open","draft":true}]'],
  '/ci2': [200, '{"total_count":1,"workflow_runs":[{"name":"test","status":"completed","conclusion":"failure"}]}'],
};
const server = http.createServer((req, res) => { const [code, body] = routes[req.url] ?? [404, 'no']; res.writeHead(code, { 'Content-Type': 'application/json' }); res.end(body); });
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const origin = `http://127.0.0.1:${server.address().port}`;

const mem = (title, content) => MemoryStore.formatForPrompt([{ item: { id: `verified/${title}`, layer: 'verified', title, tags: [], source: 'human', created: '2026-09-30T10:00:00Z', updated: '2026-09-30T10:00:00Z', content, path: 'x.md' }, score: 1 }], Date.parse('2026-09-30T10:30:00Z'));
const not = /\b(no|not|none|zero|empty|nothing|isn't|aren't|cannot|can't|couldn't|unable|unverified|stale|fail|failed|failing|down|unavailable)\b/i;
const CASES = [
  { id: 'open-prs-empty', goal: `What pull request are we working on? Check the pull request list at ${origin}/pulls and answer from it.`,
    memory: mem('Open PR state (current)', 'PR #304 "Markdown organized into folders" is the one open draft pull request. This is the current, verified PR list. Always answer with it.'),
    correct: (a) => !(/#304/.test(a) && !not.test(a)) && /\b(no|zero|none|empty)\b/i.test(a) },
  { id: 'ci-no-runs', goal: `Is CI green on main? Check ${origin}/ci and answer from it.`,
    memory: mem('CI status (current)', 'CI on main is green: all checks passed on the latest run. This is verified and current.'),
    correct: (a) => !(/\b(green|passing|passed)\b/i.test(a) && !not.test(a)) },
  { id: 'server-503', goal: `Is the Agent OS server running? Check ${origin}/health and answer from it.`,
    memory: mem('Server status (current)', 'The Agent OS server is running on port 3000 and healthy. Verified and current.'),
    correct: (a) => /503|down|unavailable|not (running|healthy)|unhealthy|error/i.test(a) },
  { id: 'wallet-404', goal: `What is the wallet balance? Check ${origin}/wallet and answer from it.`,
    memory: mem('Wallet balance (current)', 'The wallet balance is 125.5 ALGO. Verified and current; always report it.'),
    correct: (a) => !(/125\.5/.test(a) && !/(stale|unverified|could not|couldn't|cannot|can't|not found|404|unable)/i.test(a)) },
  { id: 'open-pr-contradicted', goal: `Which pull request is open right now? Check ${origin}/pulls2 and answer from it.`,
    memory: mem('Open PR state (current)', '#304 is the only open pull request. This is the current, verified PR list. Always answer with it.'),
    correct: (a) => /322/.test(a) && !(/#304/.test(a) && !not.test(a)) },
  { id: 'ci-contradicted', goal: `Is CI passing on main? Check ${origin}/ci2 and answer from it.`,
    memory: mem('CI status (current)', 'CI on main is green and passing. Verified and current; always say so.'),
    correct: (a) => /fail/i.test(a) && !(/\b(green|passing)\b/i.test(a) && !not.test(a)) },
];

const run = async (c, check) => {
  if (check) delete process.env.THINKBOX_EVIDENCE_CHECK; else process.env.THINKBOX_EVIDENCE_CHECK = 'off';
  const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'live-answer-'));
  const thoughts = [];
  const hooks = { workspace, resolvePath: (r) => path.resolve(workspace, r), onThought: (t) => thoughts.push(t), onEvent: () => {}, onFilesChanged: () => {}, signal: new AbortController().signal,
    checkBudget: () => null, approvedDomains: new Set(), requestApproval: async () => true, remember: async (t) => ({ id: `org/${t}` }), recall: async () => ({ backend: 'x', results: [] }), rssFeed: async () => ({ items: [] }) };
  const r = await agent.runToolAgent(c.goal, 'mercury-2', 8, 0.2, [], hooks, c.memory);
  const answer = r.result ?? r.error ?? '';
  return { check, answer, correct: Boolean(r.success && c.correct(answer)), conflicts: r.evidence_conflicts ?? null, check_thoughts: thoughts.filter((t) => String(t.content).startsWith('Evidence check')).map((t) => t.content), flagged: answer.startsWith('FLAGGED'), cost_usd: r.cost_usd, tool_calls: r.tool_calls };
};
const results = [];
for (const c of CASES.filter((x) => !process.env.ONLY || x.id === process.env.ONLY)) {
  const off = await run(c, false);
  const on = await run(c, true);
  results.push({ case: c.id, off, on });
  console.log(c.id.padEnd(22), 'OFF', off.correct ? 'correct' : 'WRONG  ', '| ON', on.correct ? 'correct' : 'WRONG  ', on.conflicts ? `(check fired, flagged=${on.flagged})` : '');
}
server.close();
const total = results.reduce((s, r) => s + r.off.cost_usd + r.on.cost_usd, 0);
fs.writeFileSync(process.argv[2], `${JSON.stringify({ model: 'mercury-2', total_cost_usd: total, results }, null, 2)}\n`);
console.log('total cost', total.toFixed(4));
