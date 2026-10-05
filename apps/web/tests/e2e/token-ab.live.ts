// Opt-in real-model A/B (npm run test:live-token-ab3 -- <model>): the pre-registered plan in docs/evidence/p3.24-ab/PLAN.md.
// Arms: A no token, engine absence search off | B tokens retrieved by the real recall | C tokens + engine absence search. Appends one JSON row per trial to
// docs/evidence/p3.24-ab/raw-<model>.jsonl (resumable; nothing is edited afterwards). Analysis is token-ab-report.ts, from those rows only.
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import Database from 'better-sqlite3';
import { createHash } from 'node:crypto';
import { newRunContext, TOOLS } from '../../agent.ts';
import { scoreTrial } from '../../local-eval.ts';
import { lookupSpec, repoSpec, runLocalToolLoop, type LoopSpec, type LocalChat } from '../../local-tools.ts';
import { createModelClients } from '../../ollama-client.ts';
import { rng } from '../../ab-stats.ts';
import { ensureEmbeddings, getEmbedder } from '../../think-token-embed.ts';
import { thinkTokenDbPath } from '../../think-token-reader.ts';
import { SqliteTokenStore, formatTokensForPrompt } from '../../think-token-store.ts';
import { EVAL_REPO } from '../helpers/local-eval-fixture.ts';
import { AB_GOALS, goalsHash, startAbWorld } from '../helpers/ab-fixture.ts';
import { lookupHooks } from '../helpers/lookup-hooks.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
const model = process.argv.slice(2).find((a) => !a.startsWith('--')) ?? 'qwen2.5:3b';
const outDir = path.resolve(here, '../../../../docs/evidence/p3.24-ab');
const rawPath = path.join(outDir, `raw-${model.replace(/[^\w.-]/g, '-')}.jsonl`);
fs.mkdirSync(outDir, { recursive: true });

// a COPY of the real token store: retrieval and embeddings never touch the original
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'p324-ab-'));
const copy = path.join(tmp, 'think-tokens.db');
const src = new Database(thinkTokenDbPath(), { readonly: true }); src.exec(`VACUUM INTO '${copy.replace(/'/g, "''")}'`); src.close();
process.env.KUDBEE_THINK_TOKEN_DB = copy;
const store = new SqliteTokenStore(copy);
const accepted = store.list({ status: 'accepted', limit: 500 });
const embedder = await getEmbedder();
if (!embedder) throw new Error('the embedding model could not be loaded, so the real (semantic) recall cannot be used; refusing to fall back to lexical');
await ensureEmbeddings(store, embedder);
const storeMeta = { accepted: accepted.length, ids: accepted.map((t) => t.id).sort(), content_sha256: createHash('sha256').update(JSON.stringify(accepted.map((t) => [t.id, t.title, t.content]).sort())).digest('hex'), embed_model: embedder.model };

const world = await startAbWorld();
process.env.KUDBEE_REPO = EVAL_REPO; process.env.KUDBEE_GITHUB_API = world.github.url; process.env.KUDBEE_REPO_ROOT = world.root;
const clients = createModelClients({ ollamaBaseUrl: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434', janusBaseUrl: 'http://127.0.0.1:9', janusEnabled: () => false });
const commit = execFileSync('git', ['rev-parse', '--short', 'HEAD']).toString().trim();

type Arm = 'A' | 'B' | 'C';
const withTokens = <E>(spec: LoopSpec<E>, block: string): LoopSpec<E> => block ? { ...spec, system: `${spec.system}\n\n${block}`, constrainedSystem: `${spec.constrainedSystem}\n\n${block}` } : spec;

// retrieval once per goal (B and C see the same tokens)
const retrieved = new Map<string, { ids: string[]; block: string }>();
for (const g of AB_GOALS) {
  const [goalVector] = await embedder.embed([g.goal]);
  const rows = store.retrieve(g.goal, 3, { knownTools: TOOLS.map((t) => t.function.name), goalVector, embedModel: embedder.model });
  retrieved.set(g.id, { ids: rows.map((r) => r.id), block: formatTokensForPrompt(rows) });
}
const coverage = AB_GOALS.filter((g) => retrieved.get(g.id)!.ids.length > 0).length;
console.log(`retrieval: ${coverage}/${AB_GOALS.length} goals retrieved at least one token (store: ${storeMeta.accepted} accepted)`);

const done = new Set<string>();
if (fs.existsSync(rawPath)) for (const l of fs.readFileSync(rawPath, 'utf8').split('\n').filter(Boolean)) { const r = JSON.parse(l); if (r.row) done.add(`${r.arm}|${r.goal_id}`); }
if (!fs.existsSync(rawPath) || !fs.readFileSync(rawPath, 'utf8').includes('"meta"')) fs.appendFileSync(rawPath, JSON.stringify({ meta: { plan: 'docs/evidence/p3.24-ab/PLAN.md', model, goals_hash: goalsHash(), goals: AB_GOALS.length, store: storeMeta, retrieval_coverage: coverage, commit, started_at: new Date().toISOString(), seeds: 'seed = 1000 + goal index', temperature: 0 } }) + '\n');

const order = AB_GOALS.flatMap((g, i) => (['A', 'B', 'C'] as Arm[]).map((arm) => ({ g, i, arm }))).filter((x) => !done.has(`${x.arm}|${x.g.id}`));
const rand = rng(20261005); for (let i = order.length - 1; i > 0; i -= 1) { const j = Math.floor(rand() * (i + 1)); [order[i], order[j]] = [order[j]!, order[i]!]; }
let n = 0;
for (const { g, i, arm } of order) {
  const seed = 1000 + i;
  const chat: LocalChat = { modelCapabilities: clients.modelCapabilities, chatOnce: (m, msgs, o = {}) => clients.chatOnce(m, msgs, { ...o, seed }) };
  const tok = retrieved.get(g.id)!;
  const block = arm === 'A' ? '' : tok.block;
  const h = lookupHooks(g.class === 'repo' ? { allowedTools: ['repo_search', 'repo_read'] } : {});
  const result = g.class === 'repo'
    ? await runLocalToolLoop({ model, goal: g.goal, hooks: h.hooks, context: newRunContext(), chat, repo: null, spec: withTokens(repoSpec({ engineAbsence: arm === 'C' }), block), maxSteps: 4 })
    : await runLocalToolLoop({ model, goal: g.goal, hooks: h.hooks, context: newRunContext(), chat, repo: EVAL_REPO, spec: withTokens(lookupSpec(EVAL_REPO), block), maxSteps: 3 });
  const t = scoreTrial({ id: g.id, class: g.class, goal: g.goal, check: g.check }, result);
  const row = { row: true, arm, goal_id: g.id, class: g.class, seed, tokens_retrieved: arm === 'A' ? [] : tok.ids, outcome: t.outcome, grounded: t.outcome === 'pass' || t.outcome === 'wrong', pass: t.outcome === 'pass', why: t.why, latency_ms: t.latency_ms, tool_calls: t.tool_calls, tokens: t.tokens, mode: t.mode, ...(result.absence ? { absence: result.absence } : {}), finished_at: new Date().toISOString() };
  fs.appendFileSync(rawPath, JSON.stringify(row) + '\n');
  n += 1;
  console.log(`[${n}/${order.length}] ${arm} ${g.id.padEnd(24)} ${t.outcome.padEnd(10)} ${String(t.latency_ms).padStart(6)}ms ${t.why.slice(0, 70)}`);
}
await world.close(); fs.rmSync(tmp, { recursive: true, force: true });
console.log(`done: ${rawPath}`);
process.exit(0);
