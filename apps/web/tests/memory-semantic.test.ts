// ADR 029 P3.12: local vector memory. A fake provider stands in for the MiniLM model; the SQLite storage is the real store.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { MemoryStore, memoryEmbedText, type SemanticProvider } from '../memory.ts';
import { SqliteTokenStore } from '../think-token-store.ts';

const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-memsem-'));
const LOCAL = { KUDBEE_VECTOR_NAMESPACE: 't' } as NodeJS.ProcessEnv;

async function store() {
  const s = new MemoryStore(tmp(), LOCAL);
  await s.write('org', { title: 'Zero byte files', content: 'A blank document has no bytes at all.', tags: ['files'] });
  await s.write('org', { title: 'Feed digests', content: 'Summaries of syndicated feeds cite each headline.', tags: ['rss'] });
  await s.write('org', { title: 'Nested folders', content: 'A deep directory tree is created on demand.', tags: ['files'] });
  await s.write('org', { title: '[SUPERSEDED 2026-10-02] Blank file notes', content: 'Old note about a blank document.', tags: ['superseded'] });
  return s;
}
const provider = (scores: Record<string, number>, why?: string): SemanticProvider => ({
  async cosines(_q, items) {
    if (why) return { why };
    return { model: 'fake', label: 'local-vector (MiniLM)', scores: new Map(items.map((i) => [i.id, scores[i.title] ?? 0])) };
  },
});

test('with vectors: cosine ranks first and is labeled; a lesson sharing no word with the query is found; superseded memories are never returned', async () => {
  const s = await store();
  s.semantic = provider({ 'Zero byte files': 0.6, 'Feed digests': 0.2, 'Nested folders': 0.1, '[SUPERSEDED 2026-10-02] Blank file notes': 0.9 });
  const { hits, backend } = await s.search('something with nothing inside', { topK: 3 });
  assert.equal(backend, 'local-vector (MiniLM)');
  assert.equal(hits[0]!.item.title, 'Zero byte files');
  assert.equal(hits.some((h) => h.item.title.includes('SUPERSEDED')), false);
  assert.equal(hits.some((h) => h.item.title === 'Nested folders'), false, 'below the cosine floor and no keyword match: not recalled');
});

test('BM25 only breaks ties inside a cosine bucket, and exact keyword matches the model scored low still follow the vector hits', async () => {
  const s = await store();
  // both inside one 0.02 bucket: BM25 (the query word "feeds") decides
  s.semantic = provider({ 'Zero byte files': 0.401, 'Feed digests': 0.399, 'Nested folders': 0.05 });
  let r = await s.search('feeds', { topK: 3 });
  assert.equal(r.hits[0]!.item.title, 'Feed digests');
  // far apart: cosine wins even though BM25 prefers the other
  s.semantic = provider({ 'Zero byte files': 0.7, 'Feed digests': 0.3, 'Nested folders': 0.05 });
  r = await s.search('feeds', { topK: 3 });
  assert.equal(r.hits[0]!.item.title, 'Zero byte files');
  assert.equal(r.hits[1]!.item.title, 'Feed digests');
  // a keyword hit below the floor is appended after the vector hits
  s.semantic = provider({ 'Zero byte files': 0.6, 'Feed digests': 0.05, 'Nested folders': 0.05 });
  r = await s.search('feeds', { topK: 3 });
  assert.deepEqual(r.hits.map((h) => h.item.title).slice(0, 2), ['Zero byte files', 'Feed digests']);
});

test('without vectors the label says why (model loading / embeddings off) and ranking is BM25; with no provider at all it is plain local-bm25', async () => {
  const s = await store();
  s.semantic = provider({}, 'model loading');
  let r = await s.search('syndicated feeds headline', { topK: 2 });
  assert.equal(r.backend, 'local-bm25 (model loading)');
  assert.equal(r.hits[0]!.item.title, 'Feed digests');
  s.semantic = provider({}, 'embeddings off');
  assert.equal((await s.search('feeds', { topK: 2 })).backend, 'local-bm25 (embeddings off)');
  s.semantic = undefined;
  assert.equal((await s.search('feeds', { topK: 2 })).backend, 'local-bm25');
});

test('Upstash is opt-in: with its URL and token set but no KUDBEE_MEMORY_BACKEND=upstash, recall and writes never contact it', async () => {
  let contacted = 0;
  const srv = http.createServer((_req, res) => { contacted += 1; res.writeHead(200, { 'Content-Type': 'application/json' }); res.end('{"result":[]}'); });
  await new Promise<void>((r) => srv.listen(0, '127.0.0.1', r));
  try {
    const env = { UPSTASH_VECTOR_REST_URL: `http://127.0.0.1:${(srv.address() as AddressInfo).port}`, UPSTASH_VECTOR_REST_TOKEN: 'x' } as NodeJS.ProcessEnv;
    const s = new MemoryStore(tmp(), env);
    await s.syncVectors();
    await s.write('org', { title: 'Feed digests', content: 'Summaries of feeds.' });
    const r = await s.search('feeds', { topK: 2 });
    assert.equal(r.backend, 'local-bm25');
    assert.equal(s.usesUpstash, false);
    assert.equal(contacted, 0, 'no request reached the vector service');
    assert.equal(new MemoryStore(tmp(), { ...env, KUDBEE_MEMORY_BACKEND: 'upstash' } as NodeJS.ProcessEnv).usesUpstash, true, 'explicit opt-in still works');
  } finally { srv.close(); }
});

test('memory embeddings live in SQLite: stored per model, re-embedded only when the text hash changes, pruned when a memory is gone', () => {
  const t = new SqliteTokenStore();
  const item = { title: 'Feed digests', content: 'Summaries of feeds.', layer: 'org' as const };
  const text = memoryEmbedText(item);
  t.setMemoryEmbedding('org/feed-digests', 'm', Float32Array.from([0.5, 0.25]), text);
  assert.deepEqual([...t.memoryEmbeddingsFor('m').get('org/feed-digests')!], [0.5, 0.25]);
  assert.equal(t.memoryEmbeddingsFor('other').size, 0);
  const hash = t.memoryEmbeddingHashes('m').get('org/feed-digests')!;
  assert.notEqual(hash, '');
  t.setMemoryEmbedding('org/feed-digests', 'm', Float32Array.from([0.5, 0.25]), memoryEmbedText({ ...item, content: 'Changed body.' }));
  assert.notEqual(t.memoryEmbeddingHashes('m').get('org/feed-digests'), hash, 'changed text changes the stored hash, so it is re-embedded');
  t.setMemoryEmbedding('org/gone', 'm', Float32Array.from([1, 0]), 'x');
  assert.equal(t.pruneMemoryEmbeddings('m', ['org/feed-digests']), 1);
  assert.deepEqual([...t.memoryEmbeddingsFor('m').keys()], ['org/feed-digests']);
  assert.equal(memoryEmbedText({ title: 'T', layer: 'task', content: 'Goal: g\nOutcome: ok\nAnswer given (unverified):\nA guess' }), 'T Goal: g Outcome: ok', 'a task episode embeds without its unverified answer');
  t.close();
});

test('P3.12 eval queries are paraphrases: each shares at most one distinctive word with its expected memory', async () => {
  const { tokenize } = await import('../think-token-bm25.ts');
  const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '../../../docs/evidence/adr-029-p3');
  const corpus = JSON.parse(fs.readFileSync(path.join(root, 'p312-memory-eval-corpus.json'), 'utf8')).memories as Array<{ layer: string; slug: string; title: string; content: string }>;
  const queries = JSON.parse(fs.readFileSync(path.join(root, 'p312-memory-eval-queries.json'), 'utf8')).queries as Array<{ id: string; query: string; expected: string }>;
  assert.equal(queries.length, 10);
  const COMMON = new Set(['which', 'what', 'where', 'does', 'with', 'from', 'that', 'this', 'when', 'have', 'been', 'were', 'into', 'about', 'there', 'their', 'user', 'every']);
  for (const q of queries) {
    const m = corpus.find((c) => `${c.layer}/${c.slug}` === q.expected);
    assert.ok(m, `${q.id}: expected memory exists`);
    const words = new Set(tokenize(`${m!.title} ${m!.content}`).filter((w) => w.length >= 4 && !COMMON.has(w)));
    const shared = [...new Set(tokenize(q.query))].filter((w) => w.length >= 4 && !COMMON.has(w) && words.has(w));
    assert.ok(shared.length <= 1, `${q.id} shares ${shared.join(', ')}`);
  }
});
