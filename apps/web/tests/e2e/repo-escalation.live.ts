// Opt-in live run for P3.32 (npm run test:live-repo-escalation): the pre-registered plan in docs/evidence/p3.32-escalation/PLAN.md.
// For each frozen repository goal: the local attempt (qwen2.5:3b), then, when the fixed trigger fires, ONE Mercury attempt through the same governed loop.
// One JSON row per goal is appended to raw-primary.jsonl / raw-secondary.jsonl; a file that already exists is never overwritten (no re-runs, no edits).
// Analysis is repo-escalation-report.ts, from those rows only. The Mercury key comes from .env and is never printed or written.
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { accepted, attemptRepo, repoEscalationReason, type RepoAttempt } from '../../escalation.ts';
import { scoreTrial } from '../../local-eval.ts';
import type { LocalChat } from '../../local-tools.ts';
import { createMercuryChat, loopCostUsd } from '../../mercury-chat.ts';
import { createModelClients } from '../../ollama-client.ts';
import { AB_GOALS, TRAIN_GOALS, startAbWorld, startTrainWorld } from '../helpers/ab-fixture.ts';
import { EVAL_REPO } from '../helpers/local-eval-fixture.ts';
import { lookupHooks } from '../helpers/lookup-hooks.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
for (const p of [path.resolve(here, '../../.env'), path.resolve(here, '../../../../.env')]) { try { process.loadEnvFile(p); } catch { /* none here */ } }

const LOCAL_MODEL = 'qwen2.5:3b';
const MERCURY = 'mercury-2';
const CAP_USD = 0.5;
/** Per-goal reserve: no escalation starts once the running total is within this of the cap. */
const PER_GOAL_RESERVE_USD = 0.05;
const outDir = path.resolve(here, '../../../../docs/evidence/p3.32-escalation');
fs.mkdirSync(outDir, { recursive: true });
if (!process.env.INCEPTION_API_KEY) { console.error('INCEPTION_API_KEY is not set (.env); nothing was run'); process.exit(2); }
const commit = execFileSync('git', ['rev-parse', '--short=8', 'HEAD'], { encoding: 'utf8' }).trim();

const clients = createModelClients({ ollamaBaseUrl: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434', janusBaseUrl: 'http://127.0.0.1:9', janusEnabled: () => false });
const mercury = createMercuryChat();
let spent = 0;

interface SetSpec { name: 'primary' | 'secondary'; goals: typeof AB_GOALS; seedBase: number; world: typeof startAbWorld; repoGoals: (g: { class: string }) => boolean }
const sets: SetSpec[] = [
  { name: 'primary', goals: AB_GOALS, seedBase: 1000, world: startAbWorld, repoGoals: (g) => g.class === 'repo' },
  { name: 'secondary', goals: TRAIN_GOALS, seedBase: 5000, world: startTrainWorld, repoGoals: (g) => g.class === 'repo' },
];

const hash = (goals: typeof AB_GOALS): string => createHash('sha256').update(JSON.stringify(goals.map((g) => [g.id, g.class, g.goal]))).digest('hex');
const shown = (a: RepoAttempt, task: { id: string; class: 'lookup' | 'repo'; goal: string; check: (r: any) => { ok: boolean; why: string } }) => {
  const t = scoreTrial(task, a.result);
  const acc = accepted(a);
  const pass = t.outcome === 'pass' && acc;
  return { outcome: t.outcome, why: t.why.slice(0, 160), accepted: acc, pass, false_accept: acc && t.outcome === 'wrong', latency_ms: a.result.latency_ms, tokens: a.result.prompt_tokens + a.result.completion_tokens, tool_calls: a.result.tool_calls, failure: a.result.failure?.kind ?? null, disk_verified: a.disk?.disk_verified ?? null };
};

for (const set of sets) {
  const raw = path.join(outDir, `raw-${set.name}.jsonl`);
  const repo = set.goals.filter(set.repoGoals);
  // 'wx' creates the file or fails if it exists, in one step: a pre-registered run is never repeated or overwritten.
  try { fs.writeFileSync(raw, '', { flag: 'wx' }); } catch { console.error(`${raw} already exists: a pre-registered run is never repeated or overwritten`); process.exit(2); }
  fs.appendFileSync(raw, `${JSON.stringify({ meta: { plan: 'docs/evidence/p3.32-escalation/PLAN.md', set: set.name, goals: repo.length, goals_hash: hash(repo as typeof AB_GOALS), local_model: LOCAL_MODEL, escalation_model: MERCURY, seed: `${set.seedBase} + index in the full ${set.name === 'primary' ? 'AB' : 'TRAIN'} goal list`, max_steps: 8, cap_usd: CAP_USD, commit, started_at: new Date().toISOString() } })}\n`);
  const world = await set.world();
  process.env.KUDBEE_REPO = EVAL_REPO; process.env.KUDBEE_GITHUB_API = world.github.url; process.env.KUDBEE_REPO_ROOT = world.root;
  let n = 0;
  for (const [index, g] of set.goals.entries()) {
    if (!set.repoGoals(g)) continue;
    n += 1;
    const local: LocalChat = { modelCapabilities: clients.modelCapabilities, chatOnce: (m, msgs, o = {}) => clients.chatOnce(m, msgs, { ...o, seed: set.seedBase + index }) };
    const task = { id: g.id, class: g.class, goal: g.goal, check: g.check };
    const hooks = (): ReturnType<typeof lookupHooks>['hooks'] => lookupHooks({ allowedTools: ['repo_search', 'repo_read'] }).hooks;
    const a = await attemptRepo({ model: LOCAL_MODEL, goal: g.goal, chat: local, hooks: hooks(), maxSteps: 8 });
    const row: Record<string, unknown> = { row: true, set: set.name, goal_id: g.id, local: shown(a, task), trigger: repoEscalationReason(g.goal, a), skipped_for_cap: false, escalation: null };
    if (row.trigger) {
      if (spent >= CAP_USD - PER_GOAL_RESERVE_USD) row.skipped_for_cap = true;
      else {
        const e = await attemptRepo({ model: MERCURY, goal: g.goal, chat: mercury, hooks: hooks(), maxSteps: 8 });
        const cost = loopCostUsd(MERCURY, e.result);
        spent += cost;
        row.escalation = { ...shown(e, task), cost_usd: Number(cost.toFixed(6)) };
      }
    }
    const final = (row.escalation ?? row.local) as ReturnType<typeof shown>;
    row.final = { pass: final.pass, false_accept: final.false_accept };
    fs.appendFileSync(raw, `${JSON.stringify(row)}\n`);
    const l = row.local as ReturnType<typeof shown>;
    console.log(`${set.name} ${String(n).padStart(2)}/${repo.length} ${g.id.padEnd(32)} local=${l.pass ? 'PASS' : l.outcome.padEnd(10)} trigger=${row.trigger ? 'yes' : 'no '} final=${final.pass ? 'PASS' : 'fail'} spent=$${spent.toFixed(4)}`);
  }
  await world.close();
}
console.log(`done. Mercury spend (computed from reported tokens): $${spent.toFixed(4)} of the $${CAP_USD} cap`);
process.exit(0);
