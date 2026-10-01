// The ONE place that reads Think Tokens for display (ADR 029, CLI/dashboard parity). The server's WebSocket
// handler, the `kudbee tokens` CLI commands and the tests all go through this module, so a token shows the same
// id, title, lesson, status, score breakdown, run id and ledger receipt everywhere. Layer 1: read-only, no network.
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { SqliteTokenStore, normalizeTokenId, type ListOptions, type Receipt, type ScoreBreakdown, type ThinkTokenRow, type TokenStatus } from './think-token-store.ts';

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
}

/** The single projection of a stored row to what clients see. Nothing else formats a token. */
export function toApiToken(row: ThinkTokenRow): ApiToken {
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
  };
}

export function readTokens(store: SqliteTokenStore, opts: ListOptions = {}): ApiToken[] {
  return store.list(opts).map(toApiToken);
}

export function readToken(store: SqliteTokenStore, idLike: string): ApiToken | null {
  const row = store.get(idLike);
  return row ? toApiToken(row) : null;
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
  return lines.join('\n');
}

export { normalizeTokenId };
