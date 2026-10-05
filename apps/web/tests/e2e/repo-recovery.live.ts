// P3.26 live check (npm run test:live-repo-recovery -- <model>): the 10 untested-function TRAINING goals with empty-reply recovery on.
// Plan: docs/evidence/p3.26-empty-reply/PLAN.md. One JSON row per run is appended to live-<model>.jsonl; nothing is edited afterwards.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { newRunContext } from '../../agent.ts';
import { scoreTrial } from '../../local-eval.ts';
import { repoSpec, runLocalToolLoop, type LocalChat } from '../../local-tools.ts';
import { createModelClients } from '../../ollama-client.ts';
import { EVAL_REPO } from '../helpers/local-eval-fixture.ts';
import { TRAIN_GOALS, startTrainWorld, trainGoalsHash } from '../helpers/ab-fixture.ts';
import { lookupHooks } from '../helpers/lookup-hooks.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
const model = process.argv.slice(2).find((a) => !a.startsWith('--')) ?? 'qwen2.5:3b';
const outDir = path.resolve(here, '../../../../docs/evidence/p3.26-empty-reply');
fs.mkdirSync(outDir, { recursive: true });
const out = path.join(outDir, `live-${model.replace(/[^\w.-]/g, '-')}.jsonl`);
fs.writeFileSync(out, JSON.stringify({ meta: { plan: 'docs/evidence/p3.26-empty-reply/PLAN.md', model, train_goals_hash: trainGoalsHash(), seeds: '5000 + goal index', started_at: new Date().toISOString() } }) + '\n');
const world = await startTrainWorld();
process.env.KUDBEE_REPO = EVAL_REPO; process.env.KUDBEE_GITHUB_API = world.github.url; process.env.KUDBEE_REPO_ROOT = world.root;
const clients = createModelClients({ ollamaBaseUrl: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434', janusBaseUrl: 'http://127.0.0.1:9', janusEnabled: () => false });
let pass = 0; let n = 0;
for (const [i, g] of TRAIN_GOALS.entries()) {
  if (!g.id.startsWith('train-untested-')) continue;
  const chat: LocalChat = { modelCapabilities: clients.modelCapabilities, chatOnce: (m, msgs, o = {}) => clients.chatOnce(m, msgs, { ...o, seed: 5000 + i }) };
  const h = lookupHooks({ allowedTools: ['repo_search', 'repo_read'] });
  const result = await runLocalToolLoop({ model, goal: g.goal, hooks: h.hooks, context: newRunContext(), chat, repo: null, spec: repoSpec(), maxSteps: 4 });
  const t = scoreTrial({ id: g.id, class: g.class, goal: g.goal, check: g.check }, result);
  if (t.outcome === 'pass') pass += 1; n += 1;
  fs.appendFileSync(out, JSON.stringify({ row: true, goal_id: g.id, outcome: t.outcome, why: t.why, latency_ms: t.latency_ms, tool_calls: t.tool_calls, recovery: result.recovery ?? null, absence: result.absence ?? null, failure: result.failure?.kind ?? null, steps: result.steps.map((s) => s.outcome) }) + '\n');
  console.log(`${n}/10 ${g.id.padEnd(30)} ${t.outcome.padEnd(10)} recovery=${result.recovery ? `${result.recovery.path}${result.recovery.recovered_by ? '(recovered)' : ''}` : 'none'} ${t.why.slice(0, 70)}`);
}
console.log(`passed ${pass}/${n}`);
await world.close();
process.exit(0);
