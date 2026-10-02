// ADR 029 P3.6: local embeddings stored in SQLite, hybrid ranking, schema v3 with an automatic backup. Hermetic: a fake embedder
// stands in for the ONNX model (the real model is exercised by scripts/think-token-semantic-eval.mjs, which needs a download).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import Database from 'better-sqlite3';
import { SqliteTokenStore, SCHEMA_VERSION, type TokenDraft } from '../think-token-store.ts';
import { blobToVector, cosine, embedText, ensureEmbeddings, getEmbedder, resetEmbedder, vectorToBlob, type Embedder } from '../think-token-embed.ts';

const okW = <T extends { ok: boolean }>(r: T): Extract<T, { ok: true }> => { assert.equal(r.ok, true, JSON.stringify(r)); return r as Extract<T, { ok: true }>; };
const accept = (store: SqliteTokenStore, d: Partial<TokenDraft> & { title: string; content: string }): string => {
  const id = okW(store.write({ source_run_id: 'r', kind: 'lesson', tags: [], evidence_ref: 'x', extractor: 'mercury', extract_model: 'm', ...d }, 't')).id;
  okW(store.advance(id, 'extracted', 't'));
  okW(store.advance(id, 'scored', 't'));
  okW(store.advance(id, 'challenged', 't', { challenge: { verdict: 'pass', reason: 'ok', model: 'm' } }));
  okW(store.advance(id, 'accepted', 't'));
  return id;
};

/** A tiny deterministic "semantic" embedder: words map to concept axes, so synonyms land on the same axis. */
const CONCEPTS: Record<string, number> = { empty: 0, blank: 0, nothing: 0, zero: 0, headline: 1, rss: 1, feed: 1, digest: 1, folder: 2, directory: 2, nested: 2, subfolder: 2 };
function fakeEmbedder(): Embedder & { calls: number } {
  const e = {
    model: 'fake-model', calls: 0,
    async embed(texts: string[]) {
      e.calls += texts.length;
      return texts.map((t) => {
        const v = new Float32Array(8);
        for (const w of t.toLowerCase().match(/[a-z]+/g) ?? []) v[CONCEPTS[w] ?? 7] += CONCEPTS[w] === undefined ? 0.05 : 1;
        const n = Math.hypot(...v) || 1;
        return v.map((x) => x / n);
      });
    },
  };
  return e;
}

test('vectors round-trip through a BLOB unchanged, and cosine of unit vectors is the dot product', () => {
  const v = Float32Array.from([0.25, -0.5, 0.75, 0.125]);
  assert.deepEqual([...blobToVector(vectorToBlob(v))], [...v]);
  assert.ok(Math.abs(cosine(Float32Array.from([1, 0]), Float32Array.from([0.6, 0.8])) - 0.6) < 1e-6);
  assert.equal(embedText({ title: '[lesson:x] Real title', content: 'body' }), 'Real title\nbody', 'a leading [tag] is not embedded');
});

test('ensureEmbeddings embeds accepted tokens once, re-embeds when the text changes, and skips non-accepted tokens', async () => {
  const store = new SqliteTokenStore();
  const a = accept(store, { title: 'Blank file', content: 'An empty document has zero bytes.' });
  okW(store.write({ source_run_id: 'r2', kind: 'lesson', title: 'Candidate', content: 'Never embedded.', tags: [], evidence_ref: 'x' }, 't'));
  const emb = fakeEmbedder();
  assert.equal(await ensureEmbeddings(store, emb), 1);
  assert.equal(await ensureEmbeddings(store, emb), 0, 'nothing missing the second time');
  assert.equal(emb.calls, 1);
  assert.equal(store.embeddingsFor('fake-model').size, 1);
  assert.equal(store.embeddingsFor('other-model').size, 0, 'vectors are per model');
  store.handle.prepare('UPDATE think_tokens SET content = ? WHERE id = ?').run('A changed body about feeds.', a);
  assert.equal(await ensureEmbeddings(store, emb), 1, 'changed text is re-embedded');
  store.close();
});

test('hybrid ranking finds a lesson that shares no words with the goal; lexical ranking does not; the lexical flag forces the old ranker', async () => {
  const store = new SqliteTokenStore();
  const target = accept(store, { title: 'Zero-byte documents', content: 'Writing a blank document creates a zero length file.' });
  accept(store, { title: 'Feed digests', content: 'Summaries of syndicated feeds should cite each headline.' });
  accept(store, { title: 'Nested folders', content: 'A deep directory tree is created on demand.' });
  const emb = fakeEmbedder();
  await ensureEmbeddings(store, emb);
  const goal = 'Make something with nothing inside.'; // synonym of the target, no shared distinctive word
  const [goalVector] = await emb.embed([goal]);
  const now = Date.now();
  assert.equal(store.retrieve(goal, 3, { now })[0]?.id, undefined, 'lexical: nothing matches');
  assert.equal(store.retrieve(goal, 3, { now, goalVector, embedModel: 'fake-model' })[0]!.id, target, 'hybrid: the synonym lesson is first');
  process.env.THINKBOX_RETRIEVER = 'lexical';
  try { assert.equal(store.retrieve(goal, 3, { now, goalVector, embedModel: 'fake-model' }).length, 0, 'the flag restores the old ranker'); } finally { delete process.env.THINKBOX_RETRIEVER; }
  assert.deepEqual(store.retrieve(goal, 3, { now, goalVector, embedModel: 'no-vectors-for-this-model' }).map((t) => t.id), [], 'a model with no stored vectors falls back to lexical');
  store.close();
});

test('hybrid ranking is deterministic under a frozen clock', async () => {
  const store = new SqliteTokenStore();
  accept(store, { title: 'Feed digests', content: 'Summaries of syndicated feeds cite each headline.' });
  accept(store, { title: 'Blank files', content: 'An empty document has zero bytes.' });
  const emb = fakeEmbedder();
  await ensureEmbeddings(store, emb);
  const [goalVector] = await emb.embed(['a digest of headlines']);
  const run = () => store.retrieve('a digest of headlines', 3, { now: 1_800_000_000_000, goalVector, embedModel: 'fake-model' }).map((t) => [t.id, t.score]);
  assert.deepEqual(run(), run());
  store.close();
});

test('schema v3: a v2 database gets a consistent backup before it migrates, and nothing is lost; a current or in-memory database makes no backup', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-v3-'));
  const file = path.join(dir, 'think-tokens.db');
  const first = new SqliteTokenStore(file);
  accept(first, { title: 'Kept lesson', content: 'This row must survive the migration.' });
  first.close();
  // rewind to schema v2: drop the embeddings table and the version
  const raw = new Database(file);
  raw.exec('DROP TABLE think_token_embeddings');
  raw.pragma('user_version = 2');
  raw.close();
  const backups = () => fs.readdirSync(dir).filter((f) => f.includes('.bak-pre-v3-'));
  assert.deepEqual(backups(), []);
  const migrated = new SqliteTokenStore(file);
  assert.equal(migrated.handle.pragma('user_version', { simple: true }), SCHEMA_VERSION);
  assert.equal(migrated.list({ status: 'accepted' }).length, 1);
  migrated.close();
  assert.equal(backups().length, 1, 'one backup next to the database');
  const copy = new Database(path.join(dir, backups()[0]!), { readonly: true });
  assert.equal(copy.pragma('user_version', { simple: true }), 2, 'the backup is the pre-migration state');
  assert.equal((copy.prepare('SELECT COUNT(*) n FROM think_tokens').get() as { n: number }).n, 1);
  assert.equal(copy.pragma('integrity_check', { simple: true }), 'ok');
  copy.close();
  new SqliteTokenStore(file).close();
  assert.equal(backups().length, 1, 'already current: no second backup');
  new SqliteTokenStore().close(); // :memory: never writes a file
});

test('the embedder is optional: THINKBOX_EMBEDDINGS=off gives null without loading anything', async () => {
  resetEmbedder();
  assert.equal(await getEmbedder({ THINKBOX_EMBEDDINGS: 'off' }), null);
  resetEmbedder();
});
