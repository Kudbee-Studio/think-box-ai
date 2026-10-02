// Local semantic recall for the Markdown memories (P3.12): embeds every memory with the Think Token model, keeps the vectors in SQLite (memory_embeddings),
// re-embeds a memory only when its text hash changes, and answers "how close is each memory to this query". It never waits for a model that is still loading.
import { createHash } from 'node:crypto';
import { memoryEmbedText, type MemoryStore, type SemanticProvider } from './memory.ts';
import { cosine, type Embedder, type EmbedderState } from './think-token-embed.ts';
import type { SqliteTokenStore } from './think-token-store.ts';

export function createMemorySemantic(deps: { memory: MemoryStore; tokens: SqliteTokenStore; peek: () => Embedder | null; state: () => EmbedderState }): SemanticProvider {
  return {
    async cosines(query, items) {
      const st = deps.state();
      if (st.state === 'off') return { why: 'embeddings off' };
      const embedder = deps.peek();
      if (!embedder) return { why: st.state === 'failed' ? `embedding model failed to load: ${st.error}` : 'model loading' };
      const all = deps.memory.all();
      const have = deps.tokens.memoryEmbeddingHashes(embedder.model);
      const missing = all.filter((m) => have.get(m.id) !== createHash('sha256').update(memoryEmbedText(m)).digest('hex'));
      for (let i = 0; i < missing.length; i += 32) {
        const batch = missing.slice(i, i + 32);
        const vecs = await embedder.embed(batch.map(memoryEmbedText));
        batch.forEach((m, n) => deps.tokens.setMemoryEmbedding(m.id, embedder.model, vecs[n]!, memoryEmbedText(m)));
      }
      if (missing.length) deps.tokens.pruneMemoryEmbeddings(embedder.model, all.map((m) => m.id));
      const [qv] = await embedder.embed([query]);
      const vecs = deps.tokens.memoryEmbeddingsFor(embedder.model);
      const scores = new Map<string, number>();
      for (const m of items) {
        const v = vecs.get(m.id);
        if (v && qv) scores.set(m.id, cosine(qv, v));
      }
      return { model: embedder.model, label: `local-vector (${/minilm/i.test(embedder.model) ? 'MiniLM' : embedder.model})`, scores };
    },
  };
}
