// kudbEE layered memory: a folder of Markdown files (source of truth, human-editable) mirrored into a
// vector index for recall. Layers follow AGENTS.md §1.3:
//   session  — live conversation turns inside one socket session (held in AgentSession, not on disk)
//   task     — one episode file per finished run (automatic)
//   org      — lessons/facts the agent or a human chose to keep (unverified until promoted)
//   verified — knowledge a human promoted from org; the only layer treated as ground truth
// Vector backend: Upstash Vector sparse index (BM25-style term vectors computed locally, no embedding API);
// falls back to an in-process BM25 index when Upstash is not configured or unreachable.
import fs from 'fs';
import path from 'path';
import { createHash } from 'node:crypto';
import { freshnessLabel } from './evidence.ts';

export type MemoryLayer = 'task' | 'org' | 'verified';
export const MEMORY_LAYERS: MemoryLayer[] = ['verified', 'org', 'task'];

export interface MemoryItem {
  id: string; // "<layer>/<slug>"
  layer: MemoryLayer;
  title: string;
  tags: string[];
  source: string; // "agent", "human", or "run:<id>"
  created: string;
  updated: string;
  content: string;
  path: string; // relative to memory root
}

/** A memory a human or agent marked out of date: tag `superseded`, or a title starting `[SUPERSEDED`. It stays on disk for history but is never recalled. */
export function isSuperseded(item: Pick<MemoryItem, 'title' | 'tags'>): boolean {
  return item.tags.some((t) => t.toLowerCase() === 'superseded') || /^\s*\[SUPERSEDED/i.test(item.title);
}

/** Duplicate recalls collapse to the newest one: same title and text after whitespace/case normalisation, or, for task episodes, the same goal. */
export function dedupeHits(hits: MemoryHit[]): MemoryHit[] {
  const norm = (s: string): string => s.toLowerCase().replace(/\s+/g, ' ').trim();
  const best = new Map<string, MemoryHit>();
  const order: string[] = [];
  for (const hit of hits) {
    // task episodes of the same goal differ in their recorded outcome and tool details; the goal (title) is what makes them the same question
    const key = hit.item.layer === 'task' ? `task|${norm(hit.item.title)}` : `${hit.item.layer}|${norm(hit.item.title)}|${norm(hit.item.content).slice(0, 400)}`;
    const prior = best.get(key);
    if (!prior) order.push(key);
    if (!prior || hit.item.updated > prior.item.updated) best.set(key, { item: hit.item, score: Math.max(hit.score, prior?.score ?? 0) });
  }
  return order.map((k) => best.get(k)!);
}

/**
 * Local semantic recall (P3.12). The provider (apps/web/server.ts) embeds memories with the same local MiniLM model the Think Tokens use and keeps the
 * vectors in SQLite; it answers "how close is each memory to this query" or says why it cannot (model still loading, embeddings off).
 */
export interface SemanticProvider {
  cosines(query: string, items: MemoryItem[]): Promise<{ model: string; label: string; scores: Map<string, number> } | { why: string }>;
}

/** Cosine below this means "unrelated" (the same floor the Think Token rankers use). */
export const MEMORY_COSINE_FLOOR = 0.15;
/** Cosine buckets of this width; inside a bucket BM25 breaks the tie. Fixed before the eval, as for Think Tokens (P3.8). */
export const MEMORY_COSINE_BUCKET = 0.02;

/** The text that represents a memory for embedding: title and body, without a task episode's unverified answer. */
export function memoryEmbedText(item: Pick<MemoryItem, 'title' | 'content' | 'layer'>): string {
  const body = item.layer === 'task' ? item.content.split(/\n(?:Answer given \(unverified\)|Result):/)[0]! : item.content;
  return `${item.title.replace(/^\s*\[[^\]]*\]\s*/, '')}\n${body}`.replace(/\s+/g, ' ').slice(0, 2000);
}

export interface MemoryHit {
  item: MemoryItem;
  score: number;
}

const STOPWORDS = new Set(
  [
    'a an and are as at be by for from has have i in is it its of on or that the this to was were will with you your we our they their them he she his her not no do does did can could should would into about than then there here what which who when where why how all any each also just only very more most over under after before between if else so such',
    // Instruction verbs and file words appear in almost every goal; matching on them recalls unrelated runs.
    'write wrote written file md txt json remember tell give show make create look find using use based without please short summary current new me my',
  ]
    .join(' ')
    .split(' '),
);

export function tokenize(text: string): string[] {
  return (text.toLowerCase().match(/[a-z0-9][a-z0-9_.-]*[a-z0-9]|[a-z0-9]/g) ?? [])
    .map((token) => (token.length > 4 && token.endsWith('s') && !token.endsWith('ss') ? token.slice(0, -1) : token))
    .filter((token) => token.length > 1 && !STOPWORDS.has(token));
}

/** FNV-1a 32-bit, masked to 31 bits so every index is a valid non-negative sparse dimension. */
function termIndex(term: string): number {
  let hash = 0x811c9dc5;
  // A term is a word; hash at most its first 256 characters so one huge "word" cannot stall a query.
  const length = Math.min(term.length, 256);
  for (let i = 0; i < length; i++) {
    hash ^= term.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0) & 0x7fffffff;
}

function sparseVector(tokens: string[], query: boolean): { indices: number[]; values: number[] } {
  const counts = new Map<number, number>();
  // A query or note can be arbitrarily long; the first 5000 terms are plenty to rank on and bound the work per call.
  const limit = Math.min(tokens.length, 5000);
  for (let i = 0; i < limit; i++) {
    const index = termIndex(tokens[i]!);
    counts.set(index, (counts.get(index) ?? 0) + 1);
  }
  const indices = [...counts.keys()].sort((a, b) => a - b);
  // Documents carry sublinear term frequency; the server applies IDF at query time.
  const values = indices.map((index) => (query ? 1 : 1 + Math.log(counts.get(index) ?? 1)));
  return { indices, values };
}

function slugify(text: string): string {
  const slug = text.slice(0, 400).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60);
  return slug || 'memory';
}

function parseFile(raw: string): { meta: Record<string, string>; body: string } {
  const match = raw.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!match) return { meta: {}, body: raw };
  const meta: Record<string, string> = {};
  for (const line of match[1].split('\n')) {
    const i = line.indexOf(':');
    if (i > 0) meta[line.slice(0, i).trim()] = line.slice(i + 1).trim();
  }
  return { meta, body: match[2].trim() };
}

function serialize(item: MemoryItem): string {
  const oneLine = (value: string) => value.replace(/\s+/g, ' ').trim();
  return `---
id: ${item.id}
layer: ${item.layer}
title: ${oneLine(item.title)}
tags: ${item.tags.map(oneLine).join(', ')}
source: ${oneLine(item.source)}
created: ${item.created}
updated: ${item.updated}
---
${item.content.trim()}
`;
}

const README = `# kudbEE memory

Plain Markdown files are the source of truth; the vector index is a derived copy
that is rebuilt from these files on server start. Edit or delete files freely.

| Folder | Layer | Written by | Trust |
|--------|-------|------------|-------|
| \`task/\` | Task memory | automatically, one episode per finished run | what happened, not advice |
| \`org/\` | Organizational memory | the agent (\`remember\` tool) or a human | unverified until promoted |
| \`verified/\` | Verified knowledge | a human, by promoting from \`org/\` | ground truth for the agent |

Session memory (the live conversation) lives only in the running session.
`;

export class MemoryStore {
  readonly root: string;
  private readonly items = new Map<string, MemoryItem>();
  private docFreq = new Map<string, number>();
  private tokenCache = new Map<string, string[]>();
  private readonly vectorUrl?: string;
  /** True only with KUDBEE_MEMORY_BACKEND=upstash plus its URL and token. Nothing contacts Upstash otherwise (not even the startup sync). */
  private readonly upstashOptIn: boolean;
  private readonly vectorToken?: string;
  readonly namespace: string;
  vectorStatus: { backend: 'upstash-sparse' | 'local-bm25'; ok: boolean; synced: number; error?: string } = {
    backend: 'local-bm25',
    ok: true,
    synced: 0,
  };

  constructor(root: string, env: NodeJS.ProcessEnv = process.env) {
    this.root = root;
    this.vectorUrl = env.UPSTASH_VECTOR_REST_URL?.replace(/\/+$/, '');
    this.vectorToken = env.UPSTASH_VECTOR_REST_TOKEN;
    this.namespace = env.KUDBEE_VECTOR_NAMESPACE || 'kudbee-memory';
    // Local is the default. The Upstash adapter stays in the code but is used only when asked for explicitly: KUDBEE_MEMORY_BACKEND=upstash (and its URL and token).
    this.upstashOptIn = env.KUDBEE_MEMORY_BACKEND === 'upstash' && Boolean(this.vectorUrl && this.vectorToken);
    if (this.upstashOptIn) this.vectorStatus = { backend: 'upstash-sparse', ok: false, synced: 0 };
    for (const layer of MEMORY_LAYERS) fs.mkdirSync(path.join(root, layer), { recursive: true });
    const readme = path.join(root, 'README.md');
    try {
      fs.writeFileSync(readme, README, { flag: 'wx' });
    } catch (err) {
      if ((err as NodeJS.ErrnoException).code !== 'EEXIST') throw err;
    }
    this.loadAll();
  }

  /** Set by the server: local vectors for recall. Without it (or while the model loads) recall is BM25 and says so. */
  semantic?: SemanticProvider;

  all(): MemoryItem[] {
    return [...this.items.values()];
  }

  get usesUpstash(): boolean {
    return this.vectorStatus.backend === 'upstash-sparse';
  }

  private loadAll(): void {
    this.items.clear();
    for (const layer of MEMORY_LAYERS) {
      for (const file of fs.readdirSync(path.join(this.root, layer))) {
        if (!file.endsWith('.md')) continue;
        const rel = `${layer}/${file}`;
        const { meta, body } = parseFile(fs.readFileSync(path.join(this.root, rel), 'utf8'));
        const id = `${layer}/${file.slice(0, -3)}`;
        const stat = fs.statSync(path.join(this.root, rel));
        this.items.set(id, {
          id,
          layer,
          title: meta.title || file.slice(0, -3),
          tags: (meta.tags || '').split(',').map((t) => t.trim()).filter(Boolean),
          source: meta.source || 'human',
          created: meta.created || stat.birthtime.toISOString(),
          updated: meta.updated || stat.mtime.toISOString(),
          content: body,
          path: rel,
        });
      }
    }
    this.rebuildStats();
  }

  private rebuildStats(): void {
    this.tokenCache = new Map([...this.items.values()].map((item) => [item.id, this.itemTokens(item)]));
    this.docFreq = new Map();
    for (const tokens of this.tokenCache.values()) {
      for (const token of new Set(tokens)) this.docFreq.set(token, (this.docFreq.get(token) ?? 0) + 1);
    }
  }

  private itemTokens(item: MemoryItem): string[] {
    // Title and tags count twice: they are the densest description of the memory.
    const head = `${item.title} ${item.tags.join(' ')}`;
    return tokenize(`${head} ${head} ${item.content}`);
  }

  private async vectorRequest(route: string, body?: unknown, method = 'POST'): Promise<any> {
    const response = await fetch(`${this.vectorUrl}/${route}`, {
      method,
      headers: { Authorization: `Bearer ${this.vectorToken}`, 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(8000),
    });
    const data = (await response.json().catch(() => ({}))) as { result?: unknown; error?: string };
    if (!response.ok || data.error) throw new Error(`Upstash Vector ${route}: HTTP ${response.status} ${data.error ?? ''}`.trim());
    return data.result;
  }

  private vectorRecord(item: MemoryItem): Record<string, unknown> {
    return {
      id: item.id,
      sparseVector: sparseVector(this.tokenCache.get(item.id) ?? this.itemTokens(item), false),
      metadata: { layer: item.layer, title: item.title, path: item.path, updated: item.updated },
    };
  }

  /** Upserts every file into the vector index; called at boot so the index always matches the folder. */
  async syncVectors(): Promise<void> {
    if (!this.upstashOptIn || !this.vectorUrl || !this.vectorToken) return;
    try {
      const all = [...this.items.values()];
      const batches = [];
      for (let i = 0; i < all.length; i += 100) {
        batches.push(this.vectorRequest(`upsert/${this.namespace}`, all.slice(i, i + 100).map((item) => this.vectorRecord(item))));
      }
      // Parallelize batch uploads (up to 3 concurrent requests) instead of sequential
      for (let i = 0; i < batches.length; i += 3) {
        await Promise.all(batches.slice(i, i + 3));
      }
      this.vectorStatus = { backend: 'upstash-sparse', ok: true, synced: all.length };
    } catch (err) {
      this.vectorStatus = { backend: 'upstash-sparse', ok: false, synced: 0, error: err instanceof Error ? err.message : String(err) };
    }
  }

  list(layer?: MemoryLayer, limit = 100): MemoryItem[] {
    return [...this.items.values()]
      .filter((item) => !layer || item.layer === layer)
      .sort((a, b) => b.updated.localeCompare(a.updated))
      .slice(0, limit);
  }

  get(id: string): MemoryItem | undefined {
    return this.items.get(id);
  }

  counts(): Record<MemoryLayer, number> {
    const counts = { task: 0, org: 0, verified: 0 };
    for (const item of this.items.values()) counts[item.layer] += 1;
    return counts;
  }

  async write(layer: MemoryLayer, input: { title: string; content: string; tags?: string[]; source?: string; slug?: string }): Promise<MemoryItem> {
    // The type says MemoryLayer, but callers pass request data; the layer becomes a directory name, so check it at runtime.
    if (!MEMORY_LAYERS.includes(layer)) throw new Error(`Unknown memory layer '${String(layer).slice(0, 40)}'`);
    const now = new Date().toISOString();
    let slug = input.slug ? slugify(input.slug) : slugify(input.title);
    // A new title that collides with an existing file gets a short content hash instead of overwriting it.
    if (!input.slug && this.items.has(`${layer}/${slug}`)) {
      slug = `${slug}-${createHash('sha256').update(input.content + now).digest('hex').slice(0, 6)}`;
    }
    const id = `${layer}/${slug}`;
    const existing = this.items.get(id);
    const item: MemoryItem = {
      id,
      layer,
      title: input.title.trim().slice(0, 200) || slug,
      tags: (input.tags ?? []).map((t) => t.trim()).filter(Boolean).slice(0, 12),
      source: input.source ?? 'human',
      created: existing?.created ?? now,
      updated: now,
      content: input.content.slice(0, 20000),
      path: `${id}.md`,
    };
    await fs.promises.writeFile(path.join(this.root, item.path), serialize(item), 'utf8');
    this.items.set(id, item);
    this.rebuildStats();
    if (this.usesUpstash) {
      try {
        await this.vectorRequest(`upsert/${this.namespace}`, [this.vectorRecord(item)]);
        this.vectorStatus = { ...this.vectorStatus, ok: true, synced: this.vectorStatus.synced + (existing ? 0 : 1), error: undefined };
      } catch (err) {
        this.vectorStatus = { ...this.vectorStatus, ok: false, error: err instanceof Error ? err.message : String(err) };
      }
    }
    return item;
  }

  async remove(id: string): Promise<boolean> {
    const item = this.items.get(id);
    if (!item) return false;
    await fs.promises.rm(path.join(this.root, item.path), { force: true });
    this.items.delete(id);
    this.rebuildStats();
    if (this.usesUpstash) {
      try {
        await this.vectorRequest(`delete/${this.namespace}`, [id], 'DELETE');
      } catch (err) {
        this.vectorStatus = { ...this.vectorStatus, ok: false, error: err instanceof Error ? err.message : String(err) };
      }
    }
    return true;
  }

  /** Human-only: copies an org memory into verified knowledge and removes the unverified copy. */
  async promote(id: string, reviewer = 'human'): Promise<MemoryItem> {
    const item = this.items.get(id);
    if (!item) throw new Error(`Memory not found: ${id}`);
    if (item.layer !== 'org') throw new Error('Only org memories can be promoted to verified');
    const promoted = await this.write('verified', {
      title: item.title,
      content: item.content,
      tags: item.tags,
      source: `${item.source}; promoted by ${reviewer} ${new Date().toISOString().slice(0, 10)}`,
      slug: id.slice('org/'.length),
    });
    await this.remove(id);
    return promoted;
  }

  private localSearch(query: string, layers: MemoryLayer[], topK: number): MemoryHit[] {
    const terms = [...new Set(tokenize(query))];
    if (!terms.length) return [];
    const n = this.items.size;
    const avgLen = [...this.tokenCache.values()].reduce((sum, t) => sum + t.length, 0) / Math.max(1, n);
    const hits: MemoryHit[] = [];
    for (const item of this.items.values()) {
      if (!layers.includes(item.layer)) continue;
      const tokens = this.tokenCache.get(item.id) ?? [];
      let score = 0;
      for (const term of terms) {
        const tf = tokens.filter((token) => token === term).length;
        if (!tf) continue;
        const df = this.docFreq.get(term) ?? 0;
        const idf = Math.log(1 + (n - df + 0.5) / (df + 0.5));
        score += (idf * tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * (tokens.length / Math.max(1, avgLen))));
      }
      if (score > 0) hits.push({ item, score });
    }
    return hits.sort((a, b) => b.score - a.score).slice(0, topK);
  }

  /**
   * Hybrid recall: Upstash sparse vectors (durable, shared) merged with the in-process BM25 index.
   * Upstash indexes upserts asynchronously, so a memory written seconds ago may not be queryable there
   * yet; the local index sees it immediately. Scores are max-normalised per backend and summed.
   */
  async search(query: string, options: { layers?: MemoryLayer[]; topK?: number } = {}): Promise<{ hits: MemoryHit[]; backend: string }> {
    const topK = Math.min(Math.max(options.topK ?? 5, 1), 25);
    const layers = options.layers?.length ? options.layers : MEMORY_LAYERS;
    // Explicit opt-in to the Upstash backend keeps its own path; everything else is local.
    if (this.usesUpstash) {
      const raw = await this.searchRaw(query, { ...options, topK: Math.min(topK * 2, 25) });
      return { hits: dedupeHits(raw.hits.filter((hit) => !isSuperseded(hit.item))).slice(0, topK), backend: raw.backend };
    }
    const eligible = this.all().filter((item) => layers.includes(item.layer) && !isSuperseded(item));
    const semantic = this.semantic ? await this.semantic.cosines(query, eligible).catch((err) => ({ why: `embedding error: ${err instanceof Error ? err.message.slice(0, 60) : 'error'}` })) : { why: 'no embedder' };
    const bm25 = new Map(this.localSearch(query, layers, 1000).map((h) => [h.item.id, h.score]));
    if ('scores' in semantic) {
      // Cosine first (buckets of 0.02), BM25 only breaks ties inside a bucket; then BM25-only matches (an exact keyword the model scored low) follow.
      const byCosine = eligible
        .map((item) => ({ item, cos: semantic.scores.get(item.id) ?? -1, bm: bm25.get(item.id) ?? 0 }))
        .filter((e) => e.cos >= MEMORY_COSINE_FLOOR)
        .sort((a, b) => Math.round(b.cos / MEMORY_COSINE_BUCKET) - Math.round(a.cos / MEMORY_COSINE_BUCKET) || b.bm - a.bm || b.cos - a.cos);
      const taken = new Set(byCosine.map((e) => e.item.id));
      const rest = [...bm25.entries()].filter(([id]) => !taken.has(id) && this.items.get(id) && layers.includes(this.items.get(id)!.layer) && !isSuperseded(this.items.get(id)!)).sort((a, b) => b[1] - a[1]);
      const hits: MemoryHit[] = [...byCosine.map((e) => ({ item: e.item, score: e.cos })), ...rest.map(([id, score]) => ({ item: this.items.get(id)!, score }))];
      return { hits: dedupeHits(hits).slice(0, topK), backend: semantic.label };
    }
    const hits = eligible.filter((item) => bm25.has(item.id)).map((item) => ({ item, score: bm25.get(item.id)! })).sort((a, b) => b.score - a.score);
    return { hits: dedupeHits(hits).slice(0, topK), backend: this.semantic ? `local-bm25 (${semantic.why})` : 'local-bm25' };
  }

  private async searchRaw(query: string, options: { layers?: MemoryLayer[]; topK?: number } = {}): Promise<{ hits: MemoryHit[]; backend: string }> {
    const layers = options.layers?.length ? options.layers : MEMORY_LAYERS;
    const topK = Math.min(Math.max(options.topK ?? 5, 1), 25);
    const local = this.localSearch(query, layers, topK * 2);
    if (!this.usesUpstash) return { hits: local.slice(0, topK), backend: 'local-bm25' };

    let remote: MemoryHit[] = [];
    const vector = sparseVector(tokenize(query), true);
    if (vector.indices.length) {
      try {
        const filter = layers.length < MEMORY_LAYERS.length ? layers.map((layer) => `layer = '${layer}'`).join(' OR ') : undefined;
        const result = (await this.vectorRequest(`query/${this.namespace}`, {
          sparseVector: vector,
          topK: topK * 2,
          includeMetadata: false,
          weightingStrategy: 'IDF',
          ...(filter ? { filter } : {}),
        })) as Array<{ id: string; score: number }>;
        this.vectorStatus = { ...this.vectorStatus, ok: true, error: undefined };
        remote = result
          .map((row) => ({ item: this.items.get(row.id), score: row.score }))
          .filter((hit): hit is MemoryHit => Boolean(hit.item));
      } catch (err) {
        this.vectorStatus = { ...this.vectorStatus, ok: false, error: err instanceof Error ? err.message : String(err) };
        return { hits: local.slice(0, topK), backend: 'local-bm25 (vector offline)' };
      }
    }

    const merged = new Map<string, MemoryHit>();
    for (const list of [remote, local]) {
      const max = Math.max(...list.map((hit) => hit.score), 1e-9);
      for (const hit of list) {
        const prior = merged.get(hit.item.id);
        merged.set(hit.item.id, { item: hit.item, score: (prior?.score ?? 0) + hit.score / max });
      }
    }
    const hits = [...merged.values()].sort((a, b) => b.score - a.score).slice(0, topK);
    return { hits, backend: 'hybrid (upstash-sparse + local-bm25)' };
  }

  /** Compact context block for the agent's system prompt; verified knowledge is labelled as such. */
  static formatForPrompt(hits: MemoryHit[], now: number = Date.now(), liveFlags?: Map<string, boolean>): string {
    if (!hits.length) return '';
    const label: Record<MemoryLayer, string> = {
      verified: 'VERIFIED (trust)',
      org: 'ORG (unverified note, has evidence)',
      task: 'PAST RUN (history only — its answer is not evidence)',
    };
    // Past answers are left out of task episodes: feeding an unverified answer back in lets a guess
    // reinforce itself run after run. The facts of the run (goal, outcome, tools, files) stay.
    const body = (item: MemoryItem) =>
      (item.layer === 'task' ? item.content.split(/\n(?:Answer given \(unverified\)|Result):/)[0] : item.content).replace(/\s+/g, ' ').slice(0, 500);
    return hits.map(({ item }) => `- [${label[item.layer]}] ${item.title} (${item.id}, updated ${freshnessLabel(item.updated, `${item.title} ${item.content}`, now, liveFlags?.get(item.id))})\n  ${body(item)}`).join('\n');
  }
}
