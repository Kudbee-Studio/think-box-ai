// How healthy the saved Think Tokens are, from what is already recorded (no model, no network, read-only). One module for the dashboard card and `kudbee tokens health`.
// It is OBSERVATIONAL: "runs that used a token and finished" says nothing about whether they would have finished without it. That is measured by the A/B experiments, not here.
import type { ApiToken } from './think-token-reader.ts';
import { repoTagOf } from './think-token-repo.ts';

const DAY = 86_400_000;
export const STALE_DAYS = 30;
export const WAITING_DAYS = 7;

export interface TokenHealth {
  total: number;
  by_status: Record<string, number>;
  accepted: number;
  /** Accepted tokens used by at least one run. */
  used: number;
  /** Accepted tokens used in the last 7 days. */
  used_7d: number;
  /** Accepted, never used, and older than 7 days: nothing has needed them yet. */
  waiting: number;
  /** Accepted and not used for 30 days (or never used and older than 30 days): re-check or retire. */
  stale: number;
  /** Runs that used an accepted token, split by how they ended (a run that used two tokens counts twice). */
  runs_finished: number;
  runs_failed: number;
  /** Accepted tokens learned in one repository (they are recalled only there). */
  repo_scoped: number;
  thumbs_up: number;
  thumbs_down: number;
  challenge_pass: number;
  challenge_fail: number;
  top_used: Array<{ id: string; title: string; uses: number; success_runs: number; failed_runs: number }>;
  stale_ids: string[];
  note: string;
}

export function tokenHealth(tokens: ApiToken[], now: number = Date.now()): TokenHealth {
  const by_status: Record<string, number> = {};
  for (const t of tokens) by_status[t.status] = (by_status[t.status] ?? 0) + 1;
  const accepted = tokens.filter((t) => t.status === 'accepted');
  const stale = accepted.filter((t) => (t.last_used_at ?? t.created_at) < now - STALE_DAYS * DAY);
  return {
    total: tokens.length,
    by_status,
    accepted: accepted.length,
    used: accepted.filter((t) => t.uses > 0).length,
    used_7d: accepted.filter((t) => t.last_used_at !== null && t.last_used_at >= now - 7 * DAY).length,
    waiting: accepted.filter((t) => t.uses === 0 && t.created_at < now - WAITING_DAYS * DAY && t.created_at >= now - STALE_DAYS * DAY).length,
    stale: stale.length,
    runs_finished: accepted.reduce((n, t) => n + t.success_runs, 0),
    runs_failed: accepted.reduce((n, t) => n + t.failed_runs, 0),
    repo_scoped: accepted.filter((t) => repoTagOf(t.tags) !== null).length,
    thumbs_up: tokens.reduce((n, t) => n + t.thumbs_up, 0),
    thumbs_down: tokens.reduce((n, t) => n + t.thumbs_down, 0),
    challenge_pass: tokens.filter((t) => t.challenge.verdict === 'pass').length,
    challenge_fail: tokens.filter((t) => t.challenge.verdict === 'fail').length,
    top_used: [...accepted].sort((a, b) => b.uses - a.uses || a.id.localeCompare(b.id)).filter((t) => t.uses > 0).slice(0, 5)
      .map((t) => ({ id: t.id, title: t.title, uses: t.uses, success_runs: t.success_runs, failed_runs: t.failed_runs })),
    stale_ids: stale.map((t) => t.id).slice(0, 20),
    note: 'Counts only. Whether tokens make runs better is measured by the A/B experiments, not by this card.',
  };
}

/** The same numbers as plain lines, for the CLI. */
export function formatTokenHealth(h: TokenHealth): string {
  const lines = [
    `Think Tokens: ${h.total} saved, ${h.accepted} accepted (${h.repo_scoped} learned in one repository, the rest general)`,
    `  used by a run: ${h.used} of ${h.accepted}   used in the last 7 days: ${h.used_7d}   waiting (not needed yet): ${h.waiting}   stale (30+ days): ${h.stale}`,
    `  runs that used a token: ${h.runs_finished} finished, ${h.runs_failed} did not   thumbs: ${h.thumbs_up} up, ${h.thumbs_down} down   challenge: ${h.challenge_pass} passed, ${h.challenge_fail} failed`,
  ];
  if (h.top_used.length) { lines.push('  most used:'); for (const t of h.top_used) lines.push(`    ${t.id}  ${t.uses}x (${t.success_runs} finished, ${t.failed_runs} not)  ${t.title}`); }
  if (h.stale_ids.length) lines.push(`  to re-check: ${h.stale_ids.join(', ')}`);
  lines.push(`  ${h.note}`);
  return lines.join('\n');
}
