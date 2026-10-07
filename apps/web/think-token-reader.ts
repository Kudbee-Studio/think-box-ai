// The ONE place that reads Think Tokens for display (ADR 029, CLI/dashboard parity). The server's WebSocket
// handler, the `kudbee tokens` CLI commands and the tests all go through this module, so a token shows the same
// id, title, lesson, status, score breakdown, run id and ledger receipt everywhere. Layer 1: read-only, no network.
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { tokenHealth, type TokenHealth } from './think-token-health.ts';
import { CELL_COUNT, projectTo54, type Cell, type Sticker } from './think-token-cube.ts';
import { SqliteTokenStore, normalizeTokenId, type ListOptions, type Receipt, type ScoreBreakdown, type ThinkTokenLink, type ThinkTokenRow, type TokenStatus } from './think-token-store.ts';

const here = path.dirname(fileURLToPath(import.meta.url));

/** Same rule the server uses: KUDBEE_THINK_TOKEN_DB, else <KUDBEE_DATA_DIR or apps/web/data>/think-tokens.db. */
export function thinkTokenDbPath(env: Record<string, string | undefined> = process.env): string {
  if (env.KUDBEE_THINK_TOKEN_DB) return env.KUDBEE_THINK_TOKEN_DB;
  return path.join(env.KUDBEE_DATA_DIR || path.join(here, 'data'), 'think-tokens.db');
}

export interface ApiToken {
  id: string;
  legacy_id: string | null;
  kind: ThinkTokenRow['kind'];
  title: string;
  /** The lesson text. */
  content: string;
  tags: string[];
  status: TokenStatus;
  score: number;
  score_breakdown: ScoreBreakdown;
  source_run_id: string;
  evidence_ref: string;
  extractor: ThinkTokenRow['extractor'];
  extract_model: string | null;
  challenge: ThinkTokenRow['challenge'];
  uses: number;
  last_used_at: number | null;
  success_runs: number;
  failed_runs: number;
  thumbs_up: number;
  thumbs_down: number;
  seen_count: number;
  created_at: number;
  used_by: NonNullable<ThinkTokenRow['used_by']>;
  /** Latest ledger receipt that mentions this token. */
  receipt: Receipt | null;
  /** P3 relationship links (same reader for CLI + dashboard). */
  links: ThinkTokenLink[];
}

/** The single projection of a stored row to what clients see. Nothing else formats a token. */
export function toApiToken(row: ThinkTokenRow, store?: SqliteTokenStore): ApiToken {
  return {
    id: row.id,
    legacy_id: row.legacy_id,
    kind: row.kind,
    title: row.title,
    content: row.content,
    tags: row.tags,
    status: row.status,
    score: row.score,
    score_breakdown: row.score_breakdown,
    source_run_id: row.source_run_id,
    evidence_ref: row.evidence_ref,
    extractor: row.extractor,
    extract_model: row.extract_model,
    challenge: row.challenge,
    uses: row.uses,
    last_used_at: row.last_used_at,
    success_runs: row.success_runs,
    failed_runs: row.failed_runs,
    thumbs_up: row.thumbs_up,
    thumbs_down: row.thumbs_down,
    seen_count: row.seen_count,
    created_at: row.created_at,
    used_by: row.used_by ?? [],
    receipt: row.latest_receipt ?? row.receipts?.[row.receipts.length - 1] ?? null,
    links: store ? store.listLinks(row.id) : [],
  };
}

export function readTokens(store: SqliteTokenStore, opts: ListOptions = {}): ApiToken[] {
  return store.list(opts).map((row) => toApiToken(row, store));
}

/** Counts over every saved token (see think-token-health.ts). */
export function readHealth(store: SqliteTokenStore): TokenHealth {
  return tokenHealth(readTokens(store, { limit: 5000 }));
}

export function readToken(store: SqliteTokenStore, idLike: string): ApiToken | null {
  const row = store.get(idLike);
  return row ? toApiToken(row, store) : null;
}

/** Read-only handle on the same database the server writes. Throws a readable error if there is nothing yet. */
export function openTokenReader(env: Record<string, string | undefined> = process.env): SqliteTokenStore {
  return SqliteTokenStore.openReadOnly(thinkTokenDbPath(env));
}

const clip = (text: string, max: number): string => (text.length > max ? `${text.slice(0, max - 1)}…` : text);

/** One line per token, for `kudbee tokens list`. */
export function formatTokenLine(t: ApiToken): string {
  const model = t.extractor === 'template' ? 'template' : (t.extract_model ?? t.extractor);
  return `${t.id}  ${t.status.padEnd(10)} ${t.score.toFixed(3)}  ${t.kind.padEnd(12)} ${clip(t.title, 60)}  [${model}]`;
}

/** Full text for `kudbee tokens show <id>`; contains every field the dashboard card shows. */
export function formatTokenDetail(t: ApiToken): string {
  const b = t.score_breakdown;
  const lines = [
    `${t.id}${t.legacy_id ? `  (was ${t.legacy_id})` : ''}  ${t.status}  ${t.kind}`,
    `title:     ${t.title}`,
    `lesson:    ${t.content}`,
    `tags:      ${t.tags.join(', ') || '(none)'}`,
    `run:       ${t.source_run_id}   evidence: ${t.evidence_ref}`,
    `extractor: ${t.extractor}${t.extract_model ? ` (${t.extract_model})` : ''}`,
    t.challenge.verdict
      ? `challenge:  ${t.challenge.verdict} by ${t.challenge.model ?? 'unknown'} - ${t.challenge.reason ?? ''}`
      : 'challenge:  none yet',
    `score:     ${t.score.toFixed(4)} = ${b.formula}`,
    `  usefulness ${b.components.usefulness} x ${b.weights.usefulness} = ${b.weighted.usefulness}  (success ${b.inputs.success_runs}, failed ${b.inputs.failed_runs})`,
    `  recency    ${b.components.recency} x ${b.weights.recency} = ${b.weighted.recency}  (age ${b.inputs.age_days} days, half-life ${b.inputs.half_life_days})`,
    `  reuse      ${b.components.reuse} x ${b.weights.reuse} = ${b.weighted.reuse}  (uses ${b.inputs.uses})`,
    `  feedback   ${b.components.feedback} x ${b.weights.feedback} = ${b.weighted.feedback}  (up ${b.inputs.thumbs_up}, down ${b.inputs.thumbs_down})`,
    `uses:      ${t.uses}${t.used_by.length ? `   by runs ${t.used_by.map((u) => u.run_id.slice(0, 8)).join(', ')}` : ''}   seen ${t.seen_count}x`,
    `receipt:   ${t.receipt ? `${t.receipt.receipt_id} (${t.receipt.action}, ${t.receipt.decision}, ledger seq ${t.receipt.seq})` : 'none'}`,
  ];
  if (t.links?.length) {
    lines.push(`links:     ${t.links.length}`);
    for (const L of t.links) {
      const other = L.from_id === t.id ? L.to_id : L.from_id;
      const dir = L.from_id === t.id ? '→' : '←';
      lines.push(`  - ${L.kind} ${dir} ${other} w=${L.weight.toFixed(2)} ${L.evidence}`);
    }
  } else {
    lines.push('links:     (none)');
  }
  return lines.join('\n');
}

export { normalizeTokenId };

/** Links for one token — CLI `tokens links` and dashboard panel share this. */
export function readTokenLinks(store: SqliteTokenStore, idLike: string): ThinkTokenLink[] {
  const id = normalizeTokenId(idLike);
  if (!id) return [];
  const row = store.get(id);
  if (!row) return [];
  return store.listLinks(row.id);
}


export interface ApiCube {
  id: string;
  cells: Cell[];
  stickers: Sticker[];
  /** Newest first. */
  events: Array<{ ts: number; cause: string; key: string; before: string | null; after: string; ledger_seq: number | null }>;
  /** Keys of the cells changed by the latest recorded cause (what pulses in the views). */
  last_change: { cause: string; ts: number; keys: string[] } | null;
  filled: number;
}

/** The 100 cells, the 54-sticker view and the recent cell changes: one projection for the CLI (`kudbee token cube`) and the dashboard. */
export function readTokenCube(store: SqliteTokenStore, idLike: string, now: number = Date.now()): ApiCube | null {
  const id = normalizeTokenId(idLike);
  if (!id) return null;
  const cells = store.cubeCells(id, now);
  if (!cells) return null;
  const events = store.cellEvents(id, 200);
  const latest = events[0];
  const last_change = latest ? { cause: latest.cause, ts: latest.ts, keys: events.filter((e) => e.ts === latest.ts && e.cause === latest.cause).map((e) => e.key) } : null;
  return {
    id: store.get(id)!.id,
    cells,
    stickers: projectTo54(cells),
    events: events.slice(0, 60).map((e) => ({ ts: e.ts, cause: e.cause, key: e.key, before: e.before, after: e.after, ledger_seq: e.ledger_seq })),
    last_change,
    filled: cells.filter((c) => !c.empty).length,
  };
}

/** ASCII grid of the 100 cells for the terminal: ten rows of ten, with the changed cells marked. */
export function formatCubeGrid(cube: ApiCube): string {
  const changed = new Set(cube.last_change?.keys ?? []);
  const shade = (v: number | null): string => (v === null ? '·' : v >= 0.75 ? '█' : v >= 0.5 ? '▓' : v >= 0.25 ? '▒' : v > 0 ? '░' : ' ');
  const rows: string[] = [`${cube.id}: ${cube.filled}/${CELL_COUNT} cells filled (· = empty, no data)`];
  for (let r = 0; r < 10; r++) {
    const row = cube.cells.slice(r * 10, r * 10 + 10);
    rows.push(`  ${row[0]!.row.padEnd(11)} ${row.map((c) => `${changed.has(c.key) ? '*' : ' '}${shade(c.value)}`).join(' ')}`);
  }
  if (cube.last_change) rows.push(`  * changed by "${cube.last_change.cause}" at ${new Date(cube.last_change.ts).toISOString()}: ${cube.last_change.keys.join(', ')}`);
  else rows.push('  (no cell changes recorded yet)');
  return rows.join('\n');
}
