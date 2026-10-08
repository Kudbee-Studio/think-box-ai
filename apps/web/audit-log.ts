// A tamper-evident audit log (Layer 1): who decided what, and what it cost. One append-only SQLite file; every row carries the hash of the row before it,
// so an edited, deleted or reordered row breaks the chain and `chainStatus()` says where. It records facts about decisions, never file contents or secrets:
// tool arguments are summarised (names, lengths, a short redacted start) and everything passes through the same secret redaction as Think Tokens.
// Identity: the dashboard has no login yet, so the actor is the CHANNEL ("dashboard", "timeout", "local-token"), not a person. When accounts exist the actor becomes the user.
import { createHash } from 'node:crypto';
import Database from 'better-sqlite3';
import { redact } from './think-token-store.ts';

export type AuditKind = 'approval_requested' | 'approval_resolved' | 'run_finished' | 'agent_repo_changed' | 'changes_undone' | 'draft_pr';
export interface AuditEvent { seq: number; ts: number; kind: AuditKind; actor: string; run_id: string | null; summary: string; detail: Record<string, unknown>; prev_hash: string; hash: string }
/** `head` is the hash of the newest row: note it down elsewhere and a later cut of the end of the log shows up as a head you cannot reach (the chain alone cannot prove nothing was cut off the end). */
export interface AuditVerdict { ok: boolean; entries: number; head?: string; broken_at?: number; reason?: string }

const GENESIS = '0'.repeat(64);
const SUMMARY_MAX = 300;
const DETAIL_MAX = 2000;

/** Tool arguments reduced to what an auditor needs: the names, the sizes, and a short redacted start of text values. */
export function summarizeArgs(args: unknown): Record<string, unknown> {
  if (args === null || typeof args !== 'object') return {};
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(args as Record<string, unknown>).slice(0, 12)) {
    if (typeof value === 'string') out[key] = value.length > 80 ? `${redact(value.slice(0, 80))}… (${value.length} chars)` : redact(value);
    else if (Array.isArray(value)) out[key] = `[${value.length} items]`;
    else if (value !== null && typeof value === 'object') out[key] = '{…}';
    else out[key] = value;
  }
  return out;
}

const clip = (text: string, max: number): string => (text.length > max ? `${text.slice(0, max - 1)}…` : text);
const hashOf = (prev: string, row: { ts: number; kind: string; actor: string; run_id: string | null; summary: string; detail: string }): string =>
  createHash('sha256').update(JSON.stringify([prev, row.ts, row.kind, row.actor, row.run_id, row.summary, row.detail])).digest('hex');

export class AuditLog {
  private readonly db: Database.Database;
  private last: string;

  constructor(file: string = ':memory:') {
    this.db = new Database(file);
    this.db.pragma('journal_mode = WAL');
    this.db.exec(`CREATE TABLE IF NOT EXISTS audit_events (
      seq INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, kind TEXT NOT NULL, actor TEXT NOT NULL, run_id TEXT,
      summary TEXT NOT NULL, detail TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL)`);
    this.last = (this.db.prepare('SELECT hash FROM audit_events ORDER BY seq DESC LIMIT 1').get() as { hash: string } | undefined)?.hash ?? GENESIS;
  }

  /** Append one event. Never throws: an audit failure must not stop the thing being audited (it is reported once on stderr). */
  record(kind: AuditKind, actor: string, summary: string, detail: Record<string, unknown> = {}, runId: string | null = null, now: number = Date.now()): AuditEvent | null {
    try {
      const row = { ts: now, kind, actor: clip(redact(actor), 60), run_id: runId, summary: clip(redact(summary), SUMMARY_MAX), detail: clip(redact(JSON.stringify(detail)), DETAIL_MAX) };
      const hash = hashOf(this.last, row);
      const info = this.db.prepare('INSERT INTO audit_events (ts, kind, actor, run_id, summary, detail, prev_hash, hash) VALUES (?,?,?,?,?,?,?,?)').run(row.ts, row.kind, row.actor, row.run_id, row.summary, row.detail, this.last, hash);
      const event = { seq: Number(info.lastInsertRowid), ts: row.ts, kind, actor: row.actor, run_id: runId, summary: row.summary, detail: detailOf(row.detail), prev_hash: this.last, hash };
      this.last = hash;
      return event;
    } catch (err) {
      console.error(`audit log write failed: ${err instanceof Error ? err.message : err}`);
      return null;
    }
  }

  /** Newest first. */
  list(opts: { limit?: number; kind?: string; run_id?: string; since?: number } = {}): AuditEvent[] {
    const where: string[] = []; const params: unknown[] = [];
    if (opts.kind) { where.push('kind = ?'); params.push(opts.kind); }
    if (opts.run_id) { where.push('run_id = ?'); params.push(opts.run_id); }
    if (opts.since) { where.push('ts >= ?'); params.push(opts.since); }
    const limit = Math.max(1, Math.min(Math.floor(opts.limit ?? 100), 1000));
    const rows = this.db.prepare(`SELECT * FROM audit_events ${where.length ? `WHERE ${where.join(' AND ')}` : ''} ORDER BY seq DESC LIMIT ?`).all(...params, limit) as Array<Omit<AuditEvent, 'detail'> & { detail: string }>;
    return rows.map((r) => ({ ...r, detail: detailOf(r.detail) }));
  }

  /** Walk the whole chain: every row must point at the hash of the one before and hash to its own stored hash. */
  chainStatus(): AuditVerdict {
    const rows = this.db.prepare('SELECT * FROM audit_events ORDER BY seq ASC').all() as Array<{ seq: number; ts: number; kind: string; actor: string; run_id: string | null; summary: string; detail: string; prev_hash: string; hash: string }>;
    let prev = GENESIS; let n = 0;
    for (const r of rows) {
      if (r.prev_hash !== prev) return { ok: false, entries: n, broken_at: r.seq, reason: 'a row before this one was removed, inserted or reordered' };
      if (hashOf(prev, r) !== r.hash) return { ok: false, entries: n, broken_at: r.seq, reason: 'this row was changed after it was written' };
      prev = r.hash; n++;
    }
    return { ok: true, entries: n, head: prev };
  }

  close(): void { this.db.close(); }
}

function detailOf(text: string): Record<string, unknown> {
  try { const v = JSON.parse(text); return v !== null && typeof v === 'object' ? v as Record<string, unknown> : {}; } catch { return { truncated: true }; }
}
