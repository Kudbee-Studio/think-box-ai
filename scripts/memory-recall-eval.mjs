// P3.12 memory recall eval: BM25 vs local vectors (MiniLM) on a hermetic corpus and 10 paraphrased queries whose expected memories were committed before the run.
// Rule (fixed beforehand, same as P3.8 for tokens): cosine first (buckets of 0.02), BM25 only breaks ties, BM25-only matches follow. Run once, no tuning.
//   node --experimental-strip-types scripts/memory-recall-eval.mjs <out.json>
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ev = path.join(root, 'docs/evidence/adr-029-p3');
const imp = (f) => import(pathToFileURL(path.join(root, 'apps/web', f)).href);
const { MemoryStore } = await imp('memory.ts');
const { createMemorySemantic } = await imp('memory-semantic.ts');
const { SqliteTokenStore } = await imp('think-token-store.ts');
const { getEmbedder, embedderState } = await imp('think-token-embed.ts');
const corpus = JSON.parse(fs.readFileSync(path.join(ev, 'p312-memory-eval-corpus.json'), 'utf8')).memories;
const queries = JSON.parse(fs.readFileSync(path.join(ev, 'p312-memory-eval-queries.json'), 'utf8')).queries;

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'mem-eval-'));
const memory = new MemoryStore(path.join(dir, 'memory'), { KUDBEE_VECTOR_NAMESPACE: 'eval' });
for (const m of corpus) await memory.write(m.layer, { title: m.title, content: m.content, slug: m.slug, tags: [] });
const tokens = new SqliteTokenStore(path.join(dir, 'eval.db'));
const embedder = await getEmbedder();
if (!embedder) throw new Error('embedder unavailable');
const semantic = createMemorySemantic({ memory, tokens, peek: () => embedder, state: embedderState });

const tally = { 'local-bm25': { h1: 0, h3: 0 }, 'local-vector': { h1: 0, h3: 0 } };
const rows = [];
for (const q of queries) {
  const row = { id: q.id, expected: q.expected };
  for (const [name, provider] of [['local-bm25', undefined], ['local-vector', semantic]]) {
    memory.semantic = provider;
    const { hits, backend } = await memory.search(q.query, { topK: 3 });
    const ids = hits.map((h) => h.item.id);
    const rank = ids.indexOf(q.expected);
    if (rank === 0) tally[name].h1 += 1;
    if (rank >= 0) tally[name].h3 += 1;
    row[name] = { rank: rank < 0 ? null : rank + 1, backend, top3: ids };
  }
  rows.push(row);
}
tokens.close();
const report = { corpus_size: corpus.length, queries: queries.length, model: embedder.model, results: Object.fromEntries(Object.entries(tally).map(([k, v]) => [k, { hit_at_1: v.h1, hit_at_3: v.h3 }])), per_query: rows };
fs.writeFileSync(process.argv[2], `${JSON.stringify(report, null, 2)}\n`);
console.log(Object.entries(tally).map(([k, v]) => `${k} hit@1 ${v.h1}/${queries.length} hit@3 ${v.h3}/${queries.length}`).join(' | '));
