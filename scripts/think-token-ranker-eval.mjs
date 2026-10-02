// P3.8 ranker comparison on one held-out set: lexical, hybrid, cosine, cosine-tiebreak. Frozen clock, no tuning. Usage:
//   node --experimental-strip-types scripts/think-token-ranker-eval.mjs <seed.db> <goals-module.mjs> [out.json]
// DECISION RULE (fixed before the run): the ranker with the best hit@3 on the decision set becomes the default; on a tie the simpler one wins,
// where the order of simplicity is cosine < cosine-tiebreak < lexical < hybrid. The others stay available through THINKBOX_RETRIEVER.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const [seed, goalsModule, outFile] = process.argv.slice(2);
if (!seed || !goalsModule) throw new Error('usage: think-token-ranker-eval.mjs <seed.db> <goals.mjs> [out.json]');
const { SqliteTokenStore } = await import(pathToFileURL(path.join(root, 'apps/web/think-token-store.ts')).href);
const { getEmbedder, ensureEmbeddings } = await import(pathToFileURL(path.join(root, 'apps/web/think-token-embed.ts')).href);
const { GOALS } = await import(path.resolve(goalsModule));

const NOW = Date.parse(process.env.EVAL_NOW_ISO ?? '2026-10-02T12:00:00Z');
const RANKERS = ['lexical', 'hybrid', 'cosine', 'cosine-tiebreak'];
const tmp = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'tt-rank-')), 'seed.db');
fs.copyFileSync(path.resolve(seed), tmp);
const store = new SqliteTokenStore(tmp);
const embedder = await getEmbedder();
if (!embedder) throw new Error('embedder unavailable');
await ensureEmbeddings(store, embedder);

const related = GOALS.filter((g) => g.related && g.expectedLesson);
const isExpected = (t, slug) => t.evidence_ref === `seed:${slug}`;
const tally = Object.fromEntries(RANKERS.map((r) => [r, { h1: 0, h3: 0 }]));
const perGoal = [];
for (const g of related) {
  const [goalVector] = await embedder.embed([g.goal]);
  const row = { id: g.id, style: g.style, expectedLesson: g.expectedLesson };
  for (const ranker of RANKERS) {
    const top3 = store.retrieve(g.goal, 3, { now: NOW, ranker, goalVector, embedModel: embedder.model });
    const rank = top3.findIndex((t) => isExpected(t, g.expectedLesson));
    if (rank === 0) tally[ranker].h1 += 1;
    if (rank >= 0) tally[ranker].h3 += 1;
    row[ranker] = { rank: rank < 0 ? null : rank + 1, top3: top3.map((t) => t.evidence_ref.replace('seed:', '')) };
  }
  perGoal.push(row);
}
store.close();
const report = { seed: path.basename(seed), goals_module: path.basename(goalsModule), frozen_now: new Date(NOW).toISOString(), embed_model: embedder.model, goals: related.length,
  results: Object.fromEntries(RANKERS.map((r) => [r, { hit_at_1: tally[r].h1, hit_at_3: tally[r].h3 }])), per_goal: perGoal };
const text = `${JSON.stringify(report, null, 2)}\n`;
if (outFile) fs.writeFileSync(outFile, text); else process.stdout.write(text);
console.error(RANKERS.map((r) => `${r} hit@1 ${tally[r].h1}/${related.length} hit@3 ${tally[r].h3}/${related.length}`).join(' | '));
