// BM25 over lesson text for Think Token similarity (ADR 029 P3). Pure functions, no vector DB.
// Similarity is BM25 of one lesson against another, divided by the lesson's score against itself, with IDF taken from
// the whole pool (a two-document IDF would down-weight shared terms, which is backwards for similarity).

const STOP = new Set([
  'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'is', 'are', 'was',
  'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
  'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'this', 'that', 'these', 'those',
  'it', 'its', 'as', 'by', 'from', 'with', 'about', 'into', 'over', 'after', 'before', 'between',
  'if', 'then', 'than', 'so', 'not', 'no', 'yes', 'you', 'we', 'they', 'he', 'she', 'i',
]);

/**
 * Minimum similarity for a `similar` link. Calibrated on 78 pairs of real Mercury lessons (13 tokens, 2026-10-02):
 * see docs/evidence/adr-029-p3.md. 6 of the 78 pairs clear it (max 0.35, median 0.085; re-measured after the tokenizer stopped keeping trailing punctuation); all 6 sit in one create-then-verify cluster of near-duplicate lessons, so links stay sparse. It is a
 * calibration against real data, not a validated cut-off for paraphrase detection.
 */
export const SIMILAR_THRESHOLD = 0.25;

export function tokenize(text: string): string[] {
  return String(text ?? '')
    .toLowerCase()
    .replace(/[^a-z0-9_\-./]+/g, ' ')
    .split(/\s+/)
    .map((t) => t.replace(/^[._\-./]+|[._\-./]+$/g, '')) // 'exist.' and 'exist' are one term
    .filter((t) => t.length >= 2 && !STOP.has(t));
}

interface Bm25Index {
  tf: Map<string, Map<string, number>>;
  len: Map<string, number>;
  df: Map<string, number>;
  avgdl: number;
  N: number;
}

function buildIndex(entries: Array<{ id: string; text: string }>): Bm25Index {
  const tf = new Map<string, Map<string, number>>();
  const len = new Map<string, number>();
  const df = new Map<string, number>();
  let total = 0;
  for (const e of entries) {
    const terms = tokenize(e.text);
    const counts = new Map<string, number>();
    for (const t of terms) counts.set(t, (counts.get(t) ?? 0) + 1);
    tf.set(e.id, counts);
    len.set(e.id, terms.length || 1);
    total += terms.length || 1;
    for (const t of counts.keys()) df.set(t, (df.get(t) ?? 0) + 1);
  }
  return { tf, len, df, avgdl: entries.length ? total / entries.length : 1, N: entries.length };
}

/** BM25 of `query` against document `docId` (k1=1.2, b=0.75, Robertson-Sparck Jones IDF with +0.5 smoothing). */
function score(index: Bm25Index, docId: string, query: string): number {
  const counts = index.tf.get(docId);
  if (!counts) return 0;
  const dl = index.len.get(docId) ?? 1;
  let sum = 0;
  for (const term of new Set(tokenize(query))) {
    const f = counts.get(term) ?? 0;
    if (!f) continue;
    const n = index.df.get(term) ?? 0;
    const idf = Math.log(1 + (index.N - n + 0.5) / (n + 0.5));
    sum += idf * ((f * 2.2) / (f + 1.2 * (0.25 + 0.75 * (dl / index.avgdl))));
  }
  return sum;
}

/**
 * Similarity of `target` to every pool entry, in [0,1]. Each direction is normalized by the text's score against
 * itself, then the two are averaged, so identical text scores 1 and unrelated text scores near 0.
 */
export function similarityToPool(target: { id: string; text: string }, pool: Array<{ id: string; text: string }>): Map<string, number> {
  const out = new Map<string, number>();
  if (!pool.length) return out;
  const index = buildIndex([target, ...pool]);
  const selfT = score(index, target.id, target.text);
  for (const d of pool) {
    const selfD = score(index, d.id, d.text);
    if (!selfT || !selfD) {
      out.set(d.id, 0);
      continue;
    }
    const sim = (score(index, d.id, target.text) / selfT + score(index, target.id, d.text) / selfD) / 2;
    out.set(d.id, Math.max(0, Math.min(1, sim)));
  }
  return out;
}

/** BM25 of a free-text query (a goal) against every pool entry, scaled so the best match is 1. IDF comes from the pool. */
export function rankAgainstQuery(query: string, pool: Array<{ id: string; text: string }>): Map<string, number> {
  const out = new Map<string, number>();
  if (!pool.length) return out;
  const index = buildIndex(pool);
  const raw = pool.map((d) => [d.id, score(index, d.id, query)] as const);
  const max = Math.max(...raw.map(([, v]) => v));
  for (const [id, v] of raw) out.set(id, max > 0 ? v / max : 0);
  return out;
}
