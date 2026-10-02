// Retrieval eval, lexical vs hybrid (BM25 + local embeddings), frozen clock, no tuning. Usage:
//   node --experimental-strip-types scripts/think-token-semantic-eval.mjs <seed.db> <goals-module.mjs> [out.json]
// The seed is copied to a temp file (embeddings are written to the copy, never to the committed seed).
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const [seed, goalsModule, outFile] = process.argv.slice(2);
if (!seed || !goalsModule) throw new Error('usage: think-token-semantic-eval.mjs <seed.db> <goals.mjs> [out.json]');
const { SqliteTokenStore } = await import(pathToFileURL(path.join(root, 'apps/web/think-token-store.ts')).href);
const { getEmbedder, ensureEmbeddings } = await import(pathToFileURL(path.join(root, 'apps/web/think-token-embed.ts')).href);
const { GOALS } = await import(path.resolve(goalsModule));

const NOW = Date.parse(process.env.EVAL_NOW_ISO ?? '2026-10-02T12:00:00Z');
const tmp = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'tt-sem-')), 'seed.db');
fs.copyFileSync(path.resolve(seed), tmp);
const store = new SqliteTokenStore(tmp);
const embedder = await getEmbedder();
if (!embedder) throw new Error('embedder unavailable (is @huggingface/transformers installed and the model reachable?)');
const embedded = await ensureEmbeddings(store, embedder);

const related = GOALS.filter((g) => g.related && g.expectedLesson);
const isExpected = (t, slug) => t.evidence_ref === `seed:${slug}`;
const tally = { lexical: { h1: 0, h3: 0 }, hybrid: { h1: 0, h3: 0 } };
const perGoal = [];
for (const g of related) {
  const [goalVector] = await embedder.embed([g.goal]);
  const row = { id: g.id, expectedLesson: g.expectedLesson };
  for (const [name, opts] of [['lexical', {}], ['hybrid', { goalVector, embedModel: embedder.model }]]) {
    const top3 = store.retrieve(g.goal, 3, { now: NOW, ...opts });
    const rank = top3.findIndex((t) => isExpected(t, g.expectedLesson));
    if (rank === 0) tally[name].h1 += 1;
    if (rank >= 0) tally[name].h3 += 1;
    row[name] = { rank: rank < 0 ? null : rank + 1, top3: top3.map((t) => t.evidence_ref.replace('seed:', '')) };
  }
  perGoal.push(row);
}
store.close();
const report = { seed: path.basename(seed), goals_module: path.basename(goalsModule), frozen_now: new Date(NOW).toISOString(), embed_model: embedder.model, tokens_embedded: embedded, goals: related.length,
  lexical: { hit_at_1: tally.lexical.h1, hit_at_3: tally.lexical.h3 }, hybrid: { hit_at_1: tally.hybrid.h1, hit_at_3: tally.hybrid.h3 }, per_goal: perGoal };
const text = `${JSON.stringify(report, null, 2)}\n`;
if (outFile) fs.writeFileSync(outFile, text); else process.stdout.write(text);
console.error(`lexical hit@1 ${tally.lexical.h1}/${related.length} hit@3 ${tally.lexical.h3}/${related.length} | hybrid hit@1 ${tally.hybrid.h1}/${related.length} hit@3 ${tally.hybrid.h3}/${related.length}`);
