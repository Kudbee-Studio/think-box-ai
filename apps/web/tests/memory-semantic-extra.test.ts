// Unit tests for memory-semantic.ts: the embeddings-off/loading/failed guards, batch re-embedding, pruning and scoring.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createMemorySemantic } from '../memory-semantic.ts';
import type { MemoryStore, MemoryItem } from '../memory.ts';
import type { Embedder, EmbedderState } from '../think-token-embed.ts';
import type { SqliteTokenStore } from '../think-token-store.ts';

function item(i: number): MemoryItem {
  return { id: `task/m${i}`, layer: 'task', title: `m${i}`, tags: [], source: 'test', created: '2026-01-01', updated: '2026-01-01', content: `body ${i}`, path: `task/m${i}.md` };
}

function deps(over: { state: EmbedderState; embedder?: Embedder | null; items: MemoryItem[] }) {
  const stored = new Map<string, Float32Array>();
  const hashes = new Map<string, string>();
  let setCalls = 0;
  let pruneCalls = 0;
  const tokens = {
    memoryEmbeddingHashes: () => new Map(hashes),
    setMemoryEmbedding: (id: string, _model: string, vector: Float32Array, text: string) => { setCalls++; stored.set(id, vector); hashes.set(id, createHash('sha256').update(text).digest('hex')); },
    memoryEmbeddingsFor: () => new Map(stored),
    pruneMemoryEmbeddings: () => { pruneCalls++; return 0; },
  } as unknown as SqliteTokenStore;
  const store = { all: () => over.items } as unknown as MemoryStore;
  const counts = { set: () => setCalls, prune: () => pruneCalls };
  return {
    deps: { memory: store, tokens, peek: () => over.embedder ?? null, state: () => over.state },
    counts,
  };
}

const embedder = (model = 'Xenova/all-MiniLM-L6-v2'): Embedder => ({
  model,
  async embed(texts: string[]) { return texts.map(() => Float32Array.from([1, 0])); },
});

test('cosines stops early when embeddings are off, loading or failed', async () => {
  const off = deps({ state: { state: 'off' }, items: [] });
  assert.deepEqual(await createMemorySemantic(off.deps).cosines('q', []), { why: 'embeddings off' });

  const loading = deps({ state: { state: 'loading' }, items: [] });
  assert.deepEqual(await createMemorySemantic(loading.deps).cosines('q', []), { why: 'model loading' });

  const failed = deps({ state: { state: 'failed', error: 'boom' }, items: [] });
  assert.deepEqual(await createMemorySemantic(failed.deps).cosines('q', []), { why: 'embedding model failed to load: boom' });
});

test('cosines embeds missing memories in batches, prunes and scores every item', async () => {
  const items = Array.from({ length: 40 }, (_, i) => item(i));
  const d = deps({ state: { state: 'ready', model: 'Xenova/all-MiniLM-L6-v2' }, embedder: embedder(), items });
  const result = await createMemorySemantic(d.deps).cosines('query', items);
  assert.ok('model' in result && 'scores' in result);
  if ('model' in result) {
    assert.equal(result.model, 'Xenova/all-MiniLM-L6-v2');
    assert.equal(result.label, 'local-vector (MiniLM)');
    assert.equal(result.scores.size, 40);
    assert.equal(result.scores.get('task/m0'), 1);
  }
  assert.equal(d.counts.set(), 40, 'every missing memory was embedded once');
  assert.equal(d.counts.prune(), 1, 'prune ran because some memories were missing');
});

test('cosines does not re-embed or prune when every hash already matches', async () => {
  const items = [item(0), item(1)];
  const d = deps({ state: { state: 'ready', model: 'm' }, embedder: embedder('m'), items });
  const provider = createMemorySemantic(d.deps);
  await provider.cosines('query', items);
  const setAfterFirst = d.counts.set();
  const pruneAfterFirst = d.counts.prune();
  await provider.cosines('query', items);
  assert.equal(d.counts.set(), setAfterFirst, 'second pass embeds nothing new');
  assert.equal(d.counts.prune(), pruneAfterFirst, 'second pass does not prune');
});

test('cosines labels a non-MiniLM model with its raw name', async () => {
  const items = [item(0)];
  const d = deps({ state: { state: 'ready', model: 'custom-embed-1' }, embedder: embedder('custom-embed-1'), items });
  const result = await createMemorySemantic(d.deps).cosines('query', items);
  if ('label' in result) assert.equal(result.label, 'local-vector (custom-embed-1)');
});
