// Opt-in live run for P3.35 (npm run test:live-token-learning3): the pre-registered plan in docs/evidence/p3.35-confirmation/PLAN.md.
// A full replication of P3.34 (fresh teacher stage, real pipeline, new token set) on 60 fresh held-out goals; no regression stage.
//   Stage 1  Mercury solves the training untested-function goals; each verified success goes through the REAL Think Token pipeline into a FRESH temporary store.
//   Stage 2  qwen2.5:3b on 20 held-out goals, with (B) and without (A) the tokens the real recall retrieves.
// Raw rows are created atomically and never overwritten. The real think-tokens.db is neither read nor written. No key is printed or written.
import Database from 'better-sqlite3';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { TOOLS } from '../../agent.ts';
import { rng } from '../../ab-stats.ts';
import { accepted, attemptRepo, repoEscalationReason, type RepoAttempt } from '../../escalation.ts';
import { scoreTrial } from '../../local-eval.ts';
import { repoSpec, type LocalChat, type LoopSpec } from '../../local-tools.ts';
import type { RepoEvidence } from '../../repo-tools.ts';
import { createMercuryChat, loopCostUsd } from '../../mercury-chat.ts';
import { createModelClients } from '../../ollama-client.ts';
import { processFinishedRun } from '../../think-token-pipeline.ts';
import { createTokenModels } from '../../think-token-model.ts';
import { ensureEmbeddings, getEmbedder } from '../../think-token-embed.ts';
import { SqliteTokenStore, formatTokensForPrompt } from '../../think-token-store.ts';
import { HELD3_GOALS, TRAIN_GOALS, held3GoalsHash, startHeld3World, startTrainWorld } from '../helpers/ab-fixture.ts';
import { EVAL_REPO } from '../helpers/local-eval-fixture.ts';
import { lookupHooks } from '../helpers/lookup-hooks.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
for (const p of [path.resolve(here, '../../.env'), path.resolve(here, '../../../../.env')]) { try { process.loadEnvFile(p); } catch { /* none here */ } }

const LOCAL_MODEL = 'qwen2.5:3b';
const MERCURY = 'mercury-2';
const CAP_USD = 0.5;
const outDir = path.resolve(here, '../../../../docs/evidence/p3.35-confirmation');
fs.mkdirSync(outDir, { recursive: true });
const create = (name: string): string => {
  const f = path.join(outDir, name);
  try { fs.writeFileSync(f, '', { flag: 'wx' }); } catch { console.error(`${f} already exists: a pre-registered run is never repeated or overwritten`); process.exit(2); }
  return f;
};
if (!process.env.INCEPTION_API_KEY || !process.env.INCEPTION_API_KEY_2) { console.error('INCEPTION_API_KEY and INCEPTION_API_KEY_2 must both be set (.env); nothing was run'); process.exit(2); }
const commit = execFileSync('git', ['rev-parse', '--short=8', 'HEAD'], { encoding: 'utf8' }).trim();
const teacherPath = create('raw-teacher.jsonl');
const abPath = create('raw-ab.jsonl');
const note = (f: string, o: unknown): void => fs.appendFileSync(f, `${JSON.stringify(o)}\n`);

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'p334-'));
const dbFile = path.join(tmp, 'think-tokens.db');
process.env.KUDBEE_THINK_TOKEN_DB = dbFile;
const store = new SqliteTokenStore(dbFile);
const models = { mercury: createTokenModels(process.env).mercury, local: null };
if (!models.mercury) { console.error('the Mercury token caller is not configured; nothing was run'); process.exit(2); }
const knownTools = TOOLS.map((t) => t.function.name);
const mercury = createMercuryChat();
const clients = createModelClients({ ollamaBaseUrl: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434', janusBaseUrl: 'http://127.0.0.1:9', janusEnabled: () => false });
let laneSpend = 0; let pipelineSpend = 0;

const outcomeOf = (a: RepoAttempt, g: { id: string; class: 'lookup' | 'repo'; goal: string; check: (r: any) => { ok: boolean; why: string } }) => {
  const t = scoreTrial(g, a.result); const acc = accepted(a);
  return { outcome: t.outcome, why: t.why.slice(0, 160), accepted: acc, pass: t.outcome === 'pass' && acc, false_accept: acc && t.outcome === 'wrong', latency_ms: a.result.latency_ms, tool_calls: a.result.tool_calls, tokens: a.result.prompt_tokens + a.result.completion_tokens, failure: a.result.failure?.kind ?? null, tool_retries: a.result.tool_retries ?? 0 };
};

// ── Stage 1: teacher ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
const train = await startTrainWorld();
process.env.KUDBEE_REPO = EVAL_REPO; process.env.KUDBEE_GITHUB_API = train.github.url; process.env.KUDBEE_REPO_ROOT = train.root;
const teacherGoals = TRAIN_GOALS.filter((g) => g.id.startsWith('train-untested-'));
note(teacherPath, { meta: { plan: 'docs/evidence/p3.35-confirmation/PLAN.md', stage: 'teacher', model: MERCURY, goals: teacherGoals.length, commit, started_at: new Date().toISOString() } });
for (const g of teacherGoals) {
  const h = lookupHooks({ allowedTools: ['repo_search', 'repo_read'] });
  const a = await attemptRepo({ model: MERCURY, goal: g.goal, chat: mercury, hooks: h.hooks, maxSteps: 8 });
  const cost = loopCostUsd(MERCURY, a.result); laneSpend += cost;
  const o = outcomeOf(a, g);
  const row: Record<string, unknown> = { row: true, goal_id: g.id, ...o, cost_usd: Number(cost.toFixed(6)), fed_to_pipeline: false, tokens: [] };
  if (o.pass && laneSpend + pipelineSpend < CAP_USD) {
    const f = a.result.finding!;
    const run = { id: `p335-${g.id}`, goal: g.goal, success: true, steps: h.events, files: [] as string[], result: `${f.file}:${f.line} - ${f.claim}` };
    const before = new Set(store.list({ limit: 500 }).map((t) => t.id));
    const res = await processFinishedRun({ store, models, knownTools }, run, 'p3.35-teacher');
    row.fed_to_pipeline = true;
    pipelineSpend += store.modelUsage(run.id).reduce((t, u) => t + (u.tokens_in * 0.25 + u.tokens_out * 0.75) / 1e6, 0);
    row.pipeline = { tokens: res.tokens.map((t) => ({ id: t.id, status: t.status, duplicate: Boolean(t.duplicate) })), dropped: res.dropped.map((d) => ({ title: d.title, reasons: d.reasons })), model_calls: res.model_calls };
    row.new_token_ids = store.list({ limit: 500 }).map((t) => t.id).filter((id) => !before.has(id));
  }
  note(teacherPath, row);
  console.log(`teacher ${g.id.padEnd(26)} ${o.pass ? 'PASS' : o.outcome.padEnd(10)} fed=${row.fed_to_pipeline} accepted_so_far=${store.list({ status: 'accepted', limit: 500 }).length}`);
}
await train.close();

const acceptedRows = store.list({ status: 'accepted', limit: 500 });
const poolUsd = pipelineSpend;
const retrievalText = ((): Record<string, string> => { try { const d = new Database(dbFile, { readonly: true }); const r = d.prepare('SELECT token_id, text FROM think_token_retrieval_text').all() as Array<{ token_id: string; text: string }>; d.close(); return Object.fromEntries(r.map((x) => [x.token_id, x.text])); } catch { return {}; } })();
const tokenDump = store.list({ limit: 500 }).map((t) => ({ id: t.id, kind: t.kind, status: t.status, title: t.title, content: t.content, tags: t.tags, extractor: t.extractor, extract_model: t.extract_model, source_run_id: t.source_run_id, challenge: t.challenge, retrieval_text: retrievalText[t.id] ?? null }));
fs.writeFileSync(path.join(outDir, 'tokens.json'), `${JSON.stringify({ note: 'every token the pipeline wrote from the Mercury teacher runs, with the status the pipeline gave it, its challenge verdict and its retrieval text; none written or edited by hand. Together with the pipeline code this is enough to rebuild the set.', accepted: acceptedRows.length, tokens: tokenDump }, null, 2)}\n`);
const mercuryAccepted = acceptedRows.filter((t) => t.extract_model === MERCURY).length;
console.log(`stage 1 done: ${acceptedRows.length} accepted token(s) (${mercuryAccepted} written by ${MERCURY}); lane spend $${laneSpend.toFixed(4)}`);
note(teacherPath, { summary: true, accepted: acceptedRows.length, accepted_by_mercury: mercuryAccepted, lane_spend_usd: Number(laneSpend.toFixed(6)), pipeline_spend_usd_estimate: Number(poolUsd.toFixed(6)) });
if (mercuryAccepted < 2) {
  note(abPath, { meta: { plan: 'docs/evidence/p3.35-confirmation/PLAN.md', stage: 'primary', skipped: 'teacher guard: fewer than 2 tokens accepted from Mercury runs', commit } });
  console.log('teacher guard failed: stage 2 not run (pre-registered: UNPROVEN, no tokens produced)');
  process.exit(0);
}

// ── Stages 2 and 3: A/B on held-out goals (primary: fresh; regression: the P3.33 goals) ─────────────────────────────────────────────────────
const embedder = await getEmbedder();
if (!embedder) { console.error('the embedding model could not be loaded, so the real (semantic) recall cannot be used; refusing to fall back to lexical'); process.exit(2); }
await ensureEmbeddings(store, embedder);
const withTokens = (spec: LoopSpec<RepoEvidence>, block: string): LoopSpec<RepoEvidence> => (block ? { ...spec, system: `${spec.system}\n\n${block}`, constrainedSystem: `${spec.constrainedSystem}\n\n${block}` } : spec);
const tokenHash = createHash('sha256').update(JSON.stringify(acceptedRows.map((t) => [t.id, t.title, t.content]).sort())).digest('hex');
type Arm = 'A' | 'B';

async function abStage(name: string, file: string, goals: typeof HELD3_GOALS, hash: string, seedBase: number, orderSeed: number, world: typeof startHeld3World): Promise<void> {
  const retrieved = new Map<string, { ids: string[]; block: string }>();
  for (const g of goals) {
    const [goalVector] = await embedder!.embed([g.goal]);
    const rows = store.retrieve(g.goal, 3, { knownTools, goalVector, embedModel: embedder!.model });
    retrieved.set(g.id, { ids: rows.map((r) => r.id), block: formatTokensForPrompt(rows) });
  }
  const coverage = goals.filter((g) => retrieved.get(g.id)!.ids.length > 0).length;
  console.log(`${name}: retrieval ${coverage}/${goals.length} goals retrieved at least one token`);
  note(file, { meta: { plan: 'docs/evidence/p3.35-confirmation/PLAN.md', stage: name, local_model: LOCAL_MODEL, goals: goals.length, goals_hash: hash, seed: `${seedBase} + goal index`, max_steps: 8, retrieval_coverage: coverage, accepted_tokens: acceptedRows.map((t) => t.id).sort(), tokens_sha256: tokenHash, embed_model: embedder!.model, commit, started_at: new Date().toISOString() } });
  const w = await world();
  process.env.KUDBEE_REPO_ROOT = w.root; process.env.KUDBEE_GITHUB_API = w.github.url;
  const order = goals.flatMap((g, i) => (['A', 'B'] as Arm[]).map((arm) => ({ g, i, arm })));
  const rand = rng(orderSeed); for (let i = order.length - 1; i > 0; i -= 1) { const j = Math.floor(rand() * (i + 1)); [order[i], order[j]] = [order[j]!, order[i]!]; }
  let n = 0;
  for (const { g, i, arm } of order) {
    const seed = seedBase + i;
    const chat: LocalChat = { modelCapabilities: clients.modelCapabilities, chatOnce: (m, msgs, o = {}) => clients.chatOnce(m, msgs, { ...o, seed }) };
    const tok = retrieved.get(g.id)!;
    const h = lookupHooks({ allowedTools: ['repo_search', 'repo_read'] });
    const a = await attemptRepo({ model: LOCAL_MODEL, goal: g.goal, chat, hooks: h.hooks, maxSteps: 8, spec: withTokens(repoSpec(), arm === 'A' ? '' : tok.block) });
    const o = outcomeOf(a, g);
    note(file, { row: true, arm, goal_id: g.id, seed, tokens_retrieved: arm === 'A' ? [] : tok.ids, ...o, would_escalate: repoEscalationReason(g.goal, a) !== null, steps: a.result.steps.map((s) => s.outcome), recovery: a.result.recovery?.path ?? null, finished_at: new Date().toISOString() });
    n += 1;
    console.log(`${name} [${n}/${order.length}] ${arm} ${g.id.padEnd(30)} ${o.pass ? 'PASS' : o.outcome.padEnd(10)} retries=${o.tool_retries} ${String(o.latency_ms).padStart(6)}ms ${o.why.slice(0, 50)}`);
  }
  await w.close();
}

await abStage('primary', abPath, HELD3_GOALS, held3GoalsHash(), 11000, 20261009, startHeld3World);
fs.rmSync(tmp, { recursive: true, force: true });
console.log(`done. Mercury lane spend $${laneSpend.toFixed(4)} + pipeline estimate $${poolUsd.toFixed(4)} (cap $${CAP_USD})`);
process.exit(0);
