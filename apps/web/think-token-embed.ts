// Local sentence embeddings for Think Token retrieval (ADR 029 P3.6). CPU only, no API key: a small ONNX model
// (default Xenova/all-MiniLM-L6-v2, ~23 MB, downloaded once from the Hugging Face hub into a local cache and then used offline).
// Vectors are stored in SQLite (think_token_embeddings); there is no vector database (ADR 026). If the library or the model is
// unavailable the embedder is null and retrieval falls back to the lexical ranker, so nothing depends on this module being present.
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const DEFAULT_EMBED_MODEL = 'Xenova/all-MiniLM-L6-v2';

export interface Embedder {
  model: string;
  embed(texts: string[]): Promise<Float32Array[]>;
}

type Env = Record<string, string | undefined>;

/** The text that represents a lesson: title and body (without a leading `[tag]` marker), plus its retrieval text (`when_to_use`) when it has one. */
export function embedText(t: { title: string; content: string; when_to_use?: string | null }): string {
  const base = `${t.title.replace(/^\s*\[[^\]]*\]\s*/, '')}\n${t.content}`;
  return (t.when_to_use ? `${base}\nUseful when: ${t.when_to_use}` : base).slice(0, 2400);
}

export function cosine(a: Float32Array, b: Float32Array): number {
  const n = Math.min(a.length, b.length);
  let dot = 0;
  for (let i = 0; i < n; i++) dot += a[i]! * b[i]!;
  return dot; // vectors are L2-normalized by the embedder
}

export function vectorToBlob(v: Float32Array): Buffer {
  return Buffer.from(v.buffer, v.byteOffset, v.byteLength);
}

export function blobToVector(b: Buffer): Float32Array {
  const copy = new Uint8Array(b.byteLength);
  copy.set(b);
  return new Float32Array(copy.buffer);
}

let cached: Promise<Embedder | null> | null = null;
let loaded: Embedder | null = null;
let loadError: string | null = null;

export type EmbedderState = { state: 'off' } | { state: 'loading' } | { state: 'ready'; model: string } | { state: 'failed'; error: string };

/** Why embeddings are or are not available, for the thought stream and logs. */
export function embedderState(env: Env = process.env): EmbedderState {
  if (env.THINKBOX_EMBEDDINGS === 'off' || env.THINKBOX_EMBEDDINGS === '0') return { state: 'off' };
  if (loaded) return { state: 'ready', model: loaded.model };
  if (loadError) return { state: 'failed', error: loadError };
  return { state: 'loading' };
}

/** The embedder, or null when disabled (`THINKBOX_EMBEDDINGS=off`) or when the library/model cannot be loaded. Loaded once per process. */
export function getEmbedder(env: Env = process.env): Promise<Embedder | null> {
  if (env.THINKBOX_EMBEDDINGS === 'off' || env.THINKBOX_EMBEDDINGS === '0') return Promise.resolve(null);
  cached ??= load(env)
    .then((e) => (loaded = e))
    .catch((err) => {
      loadError = (err instanceof Error ? err.message : String(err)).replace(/\s+/g, ' ').slice(0, 200);
      console.warn(`[think-token] embedding model could not be loaded: ${loadError}; retrieval stays lexical`);
      return null;
    });
  return cached;
}

/**
 * The embedder if it has already finished loading, else null. The first call starts the load in the background, so a request never waits for a model
 * download: until it is ready, retrieval is lexical.
 */
export function peekEmbedder(env: Env = process.env): Embedder | null {
  void getEmbedder(env);
  return loaded;
}

/** Test helper: forget the loaded model. */
export function resetEmbedder(): void {
  cached = null;
  loaded = null;
  loadError = null;
}

async function load(env: Env): Promise<Embedder | null> {
  const lib = await import('@huggingface/transformers');
  const model = env.THINKBOX_EMBED_MODEL || DEFAULT_EMBED_MODEL;
  lib.env.cacheDir = env.THINKBOX_EMBED_CACHE || path.join(env.KUDBEE_DATA_DIR || path.join(path.dirname(fileURLToPath(import.meta.url)), 'data'), 'models');
  const extractor = await lib.pipeline('feature-extraction', model, { dtype: 'q8' });
  return {
    model,
    async embed(texts) {
      if (!texts.length) return [];
      const out = await extractor(texts, { pooling: 'mean', normalize: true });
      const dim = out.dims[out.dims.length - 1] as number;
      const data = out.data as Float32Array;
      return texts.map((_, i) => Float32Array.from(data.subarray(i * dim, (i + 1) * dim)));
    },
  };
}

/** Structural view of the store used here, so this module does not import it. */
export interface EmbeddingStore {
  listMissingEmbeddings(model: string): Array<{ id: string; title: string; content: string; when_to_use?: string }>;
  setEmbedding(tokenId: string, model: string, vector: Float32Array, text: string): void;
}

/** Embed every accepted token that has no current vector for this model. Returns how many were embedded. */
export async function ensureEmbeddings(store: EmbeddingStore, embedder: Embedder): Promise<number> {
  const missing = store.listMissingEmbeddings(embedder.model);
  if (!missing.length) return 0;
  const vectors = await embedder.embed(missing.map(embedText));
  missing.forEach((t, i) => store.setEmbedding(t.id, embedder.model, vectors[i]!, embedText(t)));
  return missing.length;
}
