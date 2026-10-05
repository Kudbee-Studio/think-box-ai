// P3.25 stage 1 (npm run test:live-repo-harvest -- <model>): real repository-investigation runs on TRAINING goals, then the REAL Think Token pipeline
// (extract -> deterministic checks -> challenge) on every run that passed. Local models only (no Mercury, no network). Writes the token store to a
// temp file and the full account of what happened to docs/evidence/p3.25-repo-tokens/harvest-<model>.json. The challenge verdict is whatever the
// local model says; this script does not override it.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { newRunContext } from '../../agent.ts';
import { scoreTrial } from '../../local-eval.ts';
import { repoSpec, runLocalToolLoop, type LocalChat } from '../../local-tools.ts';
import { createModelClients } from '../../ollama-client.ts';
import { processFinishedRun } from '../../think-token-pipeline.ts';
import { createLocalCaller } from '../../think-token-model.ts';
import { DEFAULT_KNOWN_TOOLS, SqliteTokenStore } from '../../think-token-store.ts';
import { EVAL_REPO } from '../helpers/local-eval-fixture.ts';
import { TRAIN_GOALS, startTrainWorld, trainGoalsHash } from '../helpers/ab-fixture.ts';
import { lookupHooks } from '../helpers/lookup-hooks.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
const model = process.argv.slice(2).find((a) => !a.startsWith('--')) ?? 'qwen2.5:3b';
const outDir = path.resolve(here, '../../../../docs/evidence/p3.25-repo-tokens');
fs.mkdirSync(outDir, { recursive: true });
process.env.THINKBOX_LOCAL_MODEL = model;
const dbPath = process.env.P325_STORE ?? path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'p325-')), 'think-tokens.db');
const store = new SqliteTokenStore(dbPath);
const world = await startTrainWorld();
process.env.KUDBEE_REPO = EVAL_REPO; process.env.KUDBEE_GITHUB_API = world.github.url; process.env.KUDBEE_REPO_ROOT = world.root;
const clients = createModelClients({ ollamaBaseUrl: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434', janusBaseUrl: 'http://127.0.0.1:9', janusEnabled: () => false });
const deps = { store, models: { mercury: async () => { throw new Error('mercury disabled: local-only experiment'); }, local: createLocalCaller(process.env) }, knownTools: [...DEFAULT_KNOWN_TOOLS, 'repo_search', 'repo_read'], env: { ...process.env, THINKBOX_TOKEN_MODEL_CALLS_PER_DAY: '1000' } };

const runs: unknown[] = [];
for (const [i, g] of TRAIN_GOALS.entries()) {
  const chat: LocalChat = { modelCapabilities: clients.modelCapabilities, chatOnce: (m, msgs, o = {}) => clients.chatOnce(m, msgs, { ...o, seed: 5000 + i }) };
  const h = lookupHooks({ allowedTools: ['repo_search', 'repo_read'] });
  const result = await runLocalToolLoop({ model, goal: g.goal, hooks: h.hooks, context: newRunContext(), chat, repo: null, spec: repoSpec(), maxSteps: 4 });
  const t = scoreTrial({ id: g.id, class: g.class, goal: g.goal, check: g.check }, result);
  const runId = `train-${i}`;
  const answer = result.finding?.found ? `${result.finding.file}:${result.finding.line} - ${result.finding.claim}` : `No finding: ${result.finding?.reason ?? ''}`;
  let pipeline: unknown = null;
  if (t.outcome === 'pass') {
    const r = await processFinishedRun(deps, { id: runId, goal: g.goal, success: true, steps: h.events as never, result: answer }, 'p3.25-harvest');
    pipeline = { tokens: r.tokens.map((x) => ({ id: x.id, status: x.status, title: x.title, content: x.content, challenge: x.challenge })), dropped: r.dropped, model_calls: r.model_calls };
  }
  runs.push({ goal_id: g.id, outcome: t.outcome, why: t.why, pipeline });
  console.log(`${String(i + 1).padStart(2)}/${TRAIN_GOALS.length} ${g.id.padEnd(34)} ${t.outcome.padEnd(10)} ${pipeline ? JSON.stringify((pipeline as { tokens: Array<{ status: string }>; dropped: unknown[] }).tokens.map((x) => x.status)) + ` dropped=${(pipeline as { dropped: unknown[] }).dropped.length}` : ''}`);
}
const counts = (s: string) => store.list({ status: s as never, limit: 500 }).length;
const summary = { model, train_goals_hash: trainGoalsHash(), runs: runs.length, passed: runs.filter((r) => (r as { outcome: string }).outcome === 'pass').length, tokens: Object.fromEntries(['candidate', 'extracted', 'scored', 'challenged', 'accepted', 'rejected'].map((s) => [s, counts(s)])), store: dbPath };
fs.writeFileSync(path.join(outDir, `harvest-${model.replace(/[^\w.-]/g, '-')}.json`), JSON.stringify({ summary, runs }, null, 2) + '\n');
console.log(JSON.stringify(summary));
await world.close();
process.exit(0);
