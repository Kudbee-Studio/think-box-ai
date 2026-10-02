// The 100-cell Think Token (ADR 029, decision accepted 2026-10-02): the canonical per-token model. Ten rows of ten named cells, every cell a documented field
// read from REAL stored data (the token row, its ledger receipts, links, embeddings and retrieval text). A cell whose data does not exist for this token is
// `empty`, never filled with a stand-in. The 54-sticker Rubik's cube (6 faces x 9) is a VIEW: `projectTo54` folds the 100 cells onto 54 stickers.
// Pure: no I/O, no clock except the `now` passed in, same inputs give the same cells.
import type { ThinkTokenLink, ThinkTokenRow } from './think-token-store.ts';

export const CELL_COUNT = 100;
export const ROWS = ['identity', 'lesson', 'provenance', 'challenge', 'score', 'usage', 'links', 'lifecycle', 'health', 'propagation'] as const;
export type CubeRow = (typeof ROWS)[number];

/** What the store gathers for one token; everything the cells are computed from. */
export interface CubeInputs {
  row: ThinkTokenRow;
  links: ThinkTokenLink[];
  /** Ledger receipts for this token by action (the `cells` bookkeeping action excluded), with first/last timestamps and the rejected-decision count. */
  ledger: { byAction: Record<string, number>; total: number; rejected: number; firstTs: number | null; lastTs: number | null };
  /** Statuses of the tokens this one is linked to, by id. */
  neighborStatus: Record<string, string>;
  embeddingModel: string | null;
  whenToUse: { text: string; source: string } | null;
  /** Names of the failure modes the lesson text itself warns about (see `lessonFailureModes`). */
  failureModes: string[];
}

export interface Cell {
  index: number;
  row: CubeRow;
  col: number;
  key: string;
  label: string;
  /** Where the value comes from: table.column or a computation over stored rows. */
  source: string;
  /** What the cell means and how it is read. */
  doc: string;
  /** 0..1 intensity for drawing; null when empty. */
  value: number | null;
  /** The value as text; "empty" when there is no data for this token. */
  display: string;
  empty: boolean;
}

type Compute = (i: CubeInputs, now: number) => { value: number | null; display: string };
interface Def { key: string; label: string; source: string; doc: string; compute: Compute }

const DAY = 86_400_000;
const clamp01 = (n: number): number => Math.max(0, Math.min(1, n));
const EMPTY = { value: null, display: 'empty' } as const;
const flag = (b: boolean): { value: number; display: string } => ({ value: b ? 1 : 0, display: b ? 'yes' : 'no' });
const count = (n: number, full: number): { value: number; display: string } => ({ value: clamp01(n / full), display: String(n) });
const days = (ms: number): number => Math.max(0, Math.floor(ms / DAY));
const present = (s: string | null | undefined, v = 1): { value: number | null; display: string } => (s ? { value: v, display: s.length > 40 ? `${s.slice(0, 39)}…` : s } : EMPTY);
const num = (n: number | undefined | null, digits = 3): { value: number | null; display: string } => (typeof n === 'number' && Number.isFinite(n) ? { value: clamp01(n), display: String(Math.round(n * 10 ** digits) / 10 ** digits) } : EMPTY);
const ms = (n: number | undefined, full: number): { value: number | null; display: string } => (typeof n === 'number' ? { value: clamp01(n / full), display: `${n} ms` } : EMPTY);
const toks = (n: number | undefined, full: number): { value: number | null; display: string } => (typeof n === 'number' ? { value: clamp01(n / full), display: `${n} tokens` } : EMPTY);
const STATUS_VALUE: Record<string, number> = { accepted: 1, challenged: 0.6, scored: 0.5, extracted: 0.4, candidate: 0.3, rejected: 0.1, retired: 0.1 };
const bd = (i: CubeInputs) => i.row.score_breakdown;
const act = (i: CubeInputs, a: string): number => i.ledger.byAction[a] ?? 0;
const linkCount = (i: CubeInputs, kind: string): number => i.links.filter((l) => l.kind === kind).length;
const mergedAway = (i: CubeInputs): boolean => i.links.some((l) => l.kind === 'merged_into' && l.from_id === i.row.id);
const mode = (name: string): Compute => (i) => flag(i.failureModes.includes(name));

const DEFS: Def[] = [
  // ── identity ──
  { key: 'id', label: 'Permanent id', source: 'think_tokens.id', doc: 'The TT-id, allocated in the insert transaction and never reused.', compute: (i) => ({ value: 1, display: i.row.id }) },
  { key: 'seq', label: 'Sequence number', source: 'think_tokens.seq', doc: 'Allocation order; drawn relative to 1000.', compute: (i) => count(i.row.seq, 1000) },
  { key: 'kind', label: 'Kind', source: 'think_tokens.kind', doc: 'lesson, fix or tool_pattern.', compute: (i) => ({ value: 1, display: i.row.kind }) },
  { key: 'status', label: 'Status', source: 'think_tokens.status', doc: 'Lifecycle status; brighter the closer to accepted.', compute: (i) => ({ value: STATUS_VALUE[i.row.status] ?? 0, display: i.row.status }) },
  { key: 'extractor', label: 'Extractor', source: 'think_tokens.extractor', doc: 'mercury or local model, or the deterministic template (never auto-accepted).', compute: (i) => ({ value: i.row.extractor === 'template' ? 0.3 : 1, display: i.row.extractor }) },
  { key: 'extract_model', label: 'Extraction model', source: 'think_tokens.extract_model', doc: 'The model that wrote the lesson.', compute: (i) => present(i.row.extract_model) },
  { key: 'source_run', label: 'Source run', source: 'think_tokens.source_run_id', doc: 'The run this lesson came from (first 8 characters).', compute: (i) => present(i.row.source_run_id?.slice(0, 8)) },
  { key: 'evidence_ref', label: 'Evidence reference', source: 'think_tokens.evidence_ref', doc: 'Where the evidence for the lesson lives (for example run:<id>).', compute: (i) => present(i.row.evidence_ref) },
  { key: 'legacy_id', label: 'Legacy id', source: 'think_tokens.legacy_id', doc: 'The pre-v2 tt_<hash> id, if the token was migrated.', compute: (i) => present(i.row.legacy_id) },
  { key: 'age_days', label: 'Age', source: 'now - think_tokens.created_at', doc: 'Days since creation; drawn relative to 90 days.', compute: (i, now) => count(days(now - i.row.created_at), 90) },
  // ── lesson ──
  { key: 'title_len', label: 'Title length', source: 'length(think_tokens.title)', doc: 'Characters in the title (limit 120).', compute: (i) => count(i.row.title.length, 120) },
  { key: 'content_len', label: 'Lesson length', source: 'length(think_tokens.content)', doc: 'Characters in the lesson (limit 600).', compute: (i) => count(i.row.content.length, 600) },
  { key: 'tags', label: 'Tags', source: 'think_tokens.tags', doc: 'Number of tags (limit 8).', compute: (i) => count(i.row.tags.length, 8) },
  { key: 'tool_tags', label: 'Tool tags', source: 'think_tokens.tags (tool:*)', doc: 'Tags naming a tool the lesson is about; these drive same_tool links.', compute: (i) => count(i.row.tags.filter((t) => t.startsWith('tool:')).length, 4) },
  { key: 'mode_missing', label: 'Warns: missing thing', source: 'lesson text vs FAILURE_MODES', doc: 'The lesson text warns about a missing file or resource (ENOENT, not found).', compute: mode('missing') },
  { key: 'mode_modify', label: 'Warns: modify existing', source: 'lesson text vs FAILURE_MODES', doc: 'The lesson text is about appending or overwriting existing content.', compute: mode('modify') },
  { key: 'mode_path', label: 'Warns: path rules', source: 'lesson text vs FAILURE_MODES', doc: 'The lesson text is about invalid or escaping paths.', compute: mode('path') },
  { key: 'mode_encoding', label: 'Warns: bytes/encoding', source: 'lesson text vs FAILURE_MODES', doc: 'The lesson text is about byte counts or character encoding.', compute: mode('encoding') },
  { key: 'mode_listing', label: 'Warns: listing/folders', source: 'lesson text vs FAILURE_MODES', doc: 'The lesson text is about folder listings or subdirectories.', compute: mode('listing') },
  { key: 'has_when_to_use', label: 'Trigger text', source: 'think_token_retrieval_text', doc: 'Whether a plain-words "when to use" text exists (it is embedded with the lesson).', compute: (i) => flag(Boolean(i.whenToUse)) },
  // ── provenance ──
  { key: 'extract_latency', label: 'Extraction latency', source: 'think_tokens.extract_meta.latency_ms', doc: 'Model latency for the extraction call; drawn relative to 5 s.', compute: (i) => ms(i.row.extract_meta.latency_ms, 5000) },
  { key: 'extract_tokens_in', label: 'Extraction tokens in', source: 'think_tokens.extract_meta.tokens_in', doc: 'Prompt tokens of the extraction call.', compute: (i) => toks(i.row.extract_meta.tokens_in, 2000) },
  { key: 'extract_tokens_out', label: 'Extraction tokens out', source: 'think_tokens.extract_meta.tokens_out', doc: 'Completion tokens of the extraction call.', compute: (i) => toks(i.row.extract_meta.tokens_out, 1000) },
  { key: 'seen_count', label: 'Times extracted', source: 'think_tokens.seen_count', doc: 'How often extraction produced this same lesson (dedupe sightings).', compute: (i) => count(i.row.seen_count, 5) },
  { key: 'when_to_use_source', label: 'Trigger text author', source: 'think_token_retrieval_text.source', doc: 'The model that wrote the trigger text.', compute: (i) => present(i.whenToUse?.source) },
  { key: 'when_to_use_len', label: 'Trigger text length', source: 'length(think_token_retrieval_text.text)', doc: 'Characters in the trigger text (limit 400).', compute: (i) => (i.whenToUse ? count(i.whenToUse.text.length, 400) : EMPTY) },
  { key: 'embedded', label: 'Embedded', source: 'think_token_embeddings', doc: 'Whether a local vector exists for this token.', compute: (i) => flag(i.embeddingModel !== null) },
  { key: 'embedding_model', label: 'Embedding model', source: 'think_token_embeddings.model', doc: 'The model that produced the stored vector.', compute: (i) => present(i.embeddingModel) },
  { key: 'model_written', label: 'Model-written', source: 'think_tokens.extractor', doc: 'The lesson was written by a model (not the deterministic template).', compute: (i) => flag(i.row.extractor !== 'template') },
  { key: 'ledger_writes', label: 'Write receipts', source: 'think_token_ledger (action=write)', doc: 'Ledger entries for writing this token (including dedupe sightings).', compute: (i) => count(act(i, 'write'), 5) },
  // ── challenge ──
  { key: 'challenge_verdict', label: 'Challenge verdict', source: 'think_tokens.challenge_verdict', doc: 'pass or fail, once the challenge ran.', compute: (i) => (i.row.challenge.verdict ? { value: i.row.challenge.verdict === 'pass' ? 1 : 0, display: i.row.challenge.verdict } : EMPTY) },
  { key: 'challenge_model', label: 'Challenge model', source: 'think_tokens.challenge_model', doc: 'The model (or deterministic check) that judged the lesson.', compute: (i) => present(i.row.challenge.model) },
  { key: 'challenge_reason_len', label: 'Challenge reason length', source: 'length(think_tokens.challenge_reason)', doc: 'Characters in the stored reason.', compute: (i) => (i.row.challenge.reason ? count(i.row.challenge.reason.length, 300) : EMPTY) },
  { key: 'challenge_latency', label: 'Challenge latency', source: 'think_tokens.challenge_meta.latency_ms', doc: 'Model latency for the challenge call.', compute: (i) => ms(i.row.challenge.meta.latency_ms, 5000) },
  { key: 'challenge_tokens_in', label: 'Challenge tokens in', source: 'think_tokens.challenge_meta.tokens_in', doc: 'Prompt tokens of the challenge call.', compute: (i) => toks(i.row.challenge.meta.tokens_in, 2000) },
  { key: 'challenge_tokens_out', label: 'Challenge tokens out', source: 'think_tokens.challenge_meta.tokens_out', doc: 'Completion tokens of the challenge call.', compute: (i) => toks(i.row.challenge.meta.tokens_out, 1000) },
  { key: 'transitions', label: 'Lifecycle steps', source: 'think_token_ledger (action=transition)', doc: 'Receipted lifecycle transitions (candidate -> ... -> accepted/rejected).', compute: (i) => count(act(i, 'transition'), 6) },
  { key: 'reached_challenge', label: 'Reached challenge', source: 'think_tokens.status / challenge_verdict', doc: 'The token has a challenge verdict.', compute: (i) => flag(i.row.challenge.verdict !== null) },
  { key: 'accepted_flag', label: 'Accepted', source: 'think_tokens.status', doc: 'Status is accepted.', compute: (i) => flag(i.row.status === 'accepted') },
  { key: 'rejected_flag', label: 'Rejected', source: 'think_tokens.status', doc: 'Status is rejected.', compute: (i) => flag(i.row.status === 'rejected') },
  // ── score ──
  { key: 'usefulness', label: 'Usefulness', source: 'score_breakdown.components.usefulness', doc: '(wins + 1) / (wins + losses + 2); weight 0.45.', compute: (i) => num(bd(i).components.usefulness) },
  { key: 'recency', label: 'Recency', source: 'score_breakdown.components.recency', doc: 'Half-life 30 days from the last use or creation; weight 0.20.', compute: (i) => num(bd(i).components.recency) },
  { key: 'reuse', label: 'Reuse', source: 'score_breakdown.components.reuse', doc: 'log2(1 + uses) / log2(11); weight 0.15.', compute: (i) => num(bd(i).components.reuse) },
  { key: 'feedback', label: 'Feedback', source: 'score_breakdown.components.feedback', doc: '(thumbs up + 1) / (votes + 2); weight 0.20.', compute: (i) => num(bd(i).components.feedback) },
  { key: 'base_score', label: 'Weighted base', source: 'sum of score_breakdown.weighted', doc: 'The four weighted parts added up, before propagation.', compute: (i) => num(bd(i).weighted.usefulness + bd(i).weighted.recency + bd(i).weighted.reuse + bd(i).weighted.feedback) },
  { key: 'propagation_bonus', label: 'Propagation bonus', source: 'score_breakdown.propagation_bonus', doc: 'min(0.10, 0.02 x sum of the last 12 credits).', compute: (i) => (bd(i).propagation_bonus === undefined ? EMPTY : num(bd(i).propagation_bonus! / 0.1)) },
  { key: 'propagation_credits', label: 'Credits held', source: 'score_breakdown.propagation', doc: 'Credits from linked tokens that were used (window of 12).', compute: (i) => count(bd(i).propagation?.length ?? 0, 12) },
  { key: 'score', label: 'Score', source: 'think_tokens.score', doc: 'The stored score (base plus bonus).', compute: (i) => num(i.row.score) },
  { key: 'score_age_days', label: 'Score age basis', source: 'score_breakdown.inputs.age_days', doc: 'The age in days the recency part was computed with.', compute: (i) => count(Math.floor(bd(i).inputs.age_days), 90) },
  { key: 'last_used_age', label: 'Since last use', source: 'now - think_tokens.last_used_at', doc: 'Days since a run last used this token; empty if never used.', compute: (i, now) => (i.row.last_used_at === null ? EMPTY : count(days(now - i.row.last_used_at), 90)) },
  // ── usage ──
  { key: 'uses', label: 'Uses', source: 'think_tokens.uses', doc: 'Runs that were given this token as planner context.', compute: (i) => count(i.row.uses, 20) },
  { key: 'distinct_runs', label: 'Runs seen', source: 'think_token_uses', doc: 'Distinct runs in the use log (latest 20 kept).', compute: (i) => count(i.row.used_by?.length ?? 0, 20) },
  { key: 'success_runs', label: 'Wins', source: 'think_tokens.success_runs', doc: 'Used-in runs that succeeded.', compute: (i) => count(i.row.success_runs, 10) },
  { key: 'failed_runs', label: 'Losses', source: 'think_tokens.failed_runs', doc: 'Used-in runs that failed.', compute: (i) => count(i.row.failed_runs, 10) },
  { key: 'win_rate', label: 'Win rate', source: 'success_runs / (success_runs + failed_runs)', doc: 'Share of judged uses that succeeded; empty until a use has an outcome.', compute: (i) => (i.row.success_runs + i.row.failed_runs ? num(i.row.success_runs / (i.row.success_runs + i.row.failed_runs)) : EMPTY) },
  { key: 'thumbs_up', label: 'Thumbs up', source: 'think_tokens.thumbs_up', doc: 'Founder thumbs up.', compute: (i) => count(i.row.thumbs_up, 5) },
  { key: 'thumbs_down', label: 'Thumbs down', source: 'think_tokens.thumbs_down', doc: 'Founder thumbs down.', compute: (i) => count(i.row.thumbs_down, 5) },
  { key: 'uses_7d', label: 'Uses, last 7 days', source: 'think_token_uses.used_at', doc: 'Uses recorded in the last week (from the latest 20).', compute: (i, now) => count((i.row.used_by ?? []).filter((u) => now - u.used_at < 7 * DAY).length, 10) },
  { key: 'ledger_uses', label: 'Use receipts', source: 'think_token_ledger (action=use)', doc: 'Ledger entries for use.', compute: (i) => count(act(i, 'use'), 20) },
  { key: 'ledger_outcomes', label: 'Outcome receipts', source: 'think_token_ledger (action=outcome)', doc: 'Ledger entries for recorded outcomes.', compute: (i) => count(act(i, 'outcome'), 20) },
  // ── links ──
  { key: 'links_total', label: 'Links', source: 'think_token_links', doc: 'All links to or from this token.', compute: (i) => count(i.links.length, 12) },
  { key: 'link_same_tool', label: 'same_tool links', source: 'think_token_links (kind=same_tool)', doc: 'Links through a shared, rare tool tag.', compute: (i) => count(linkCount(i, 'same_tool'), 8) },
  { key: 'link_similar', label: 'similar links', source: 'think_token_links (kind=similar)', doc: 'Links through similar lesson text.', compute: (i) => count(linkCount(i, 'similar'), 8) },
  { key: 'link_co_used', label: 'co_used links', source: 'think_token_links (kind=co_used)', doc: 'Links to tokens used in the same run.', compute: (i) => count(linkCount(i, 'co_used'), 8) },
  { key: 'merged_into', label: 'Merged into', source: 'think_token_links (merged_into, from this token)', doc: 'This token was merged into a better one as a near-duplicate.', compute: (i) => { const l = i.links.find((x) => x.kind === 'merged_into' && x.from_id === i.row.id); return l ? { value: 1, display: l.to_id } : EMPTY; } },
  { key: 'merged_from', label: 'Absorbed duplicates', source: 'think_token_links (merged_into, to this token)', doc: 'Near-duplicates merged into this token.', compute: (i) => count(i.links.filter((l) => l.kind === 'merged_into' && l.to_id === i.row.id).length, 5) },
  { key: 'strongest_weight', label: 'Strongest link', source: 'max(think_token_links.weight)', doc: 'Weight of the strongest link; empty without links.', compute: (i) => (i.links.length ? num(Math.max(...i.links.map((l) => l.weight))) : EMPTY) },
  { key: 'strongest_kind', label: 'Strongest link kind', source: 'think_token_links.kind', doc: 'Kind of the strongest link.', compute: (i) => { const top = [...i.links].sort((a, b) => b.weight - a.weight)[0]; return top ? { value: 1, display: top.kind } : EMPTY; } },
  { key: 'neighbors_accepted', label: 'Accepted neighbors', source: 'think_tokens.status of linked tokens', doc: 'Linked tokens that are accepted.', compute: (i) => count(Object.values(i.neighborStatus).filter((s) => s === 'accepted').length, 8) },
  { key: 'neighbors', label: 'Distinct neighbors', source: 'think_token_links', doc: 'Distinct tokens linked to this one.', compute: (i) => count(Object.keys(i.neighborStatus).length, 12) },
  // ── lifecycle (ledger) ──
  { key: 'receipts', label: 'Receipts', source: 'think_token_ledger', doc: 'All ledger entries mentioning this token (cell bookkeeping excluded).', compute: (i) => count(i.ledger.total, 40) },
  { key: 'feedback_receipts', label: 'Feedback receipts', source: 'think_token_ledger (action=feedback)', doc: 'Receipted thumbs.', compute: (i) => count(act(i, 'feedback'), 10) },
  { key: 'propagate_receipts', label: 'Propagation receipts', source: 'think_token_ledger (action=propagate)', doc: 'Credits received from linked tokens.', compute: (i) => count(act(i, 'propagate'), 20) },
  { key: 'merge_receipts', label: 'Merge receipts', source: 'think_token_ledger (action=merge)', doc: 'Receipted merges.', compute: (i) => count(act(i, 'merge'), 3) },
  { key: 'link_receipts', label: 'Link receipts', source: 'think_token_ledger (action=link_*)', doc: 'Receipted link creations and updates.', compute: (i) => count(act(i, 'link_create') + act(i, 'link_update'), 20) },
  { key: 'resighted', label: 'Extracted again', source: 'think_tokens.seen_count', doc: 'Extraction produced this same lesson more than once (a dedupe sighting).', compute: (i) => flag(i.row.seen_count > 1) },
  { key: 'first_receipt_age', label: 'Oldest receipt', source: 'min(think_token_ledger.ts)', doc: 'Days since the first receipt.', compute: (i, now) => (i.ledger.firstTs === null ? EMPTY : count(days(now - i.ledger.firstTs), 90)) },
  { key: 'last_receipt_age', label: 'Newest receipt', source: 'max(think_token_ledger.ts)', doc: 'Days since the latest receipt.', compute: (i, now) => (i.ledger.lastTs === null ? EMPTY : count(days(now - i.ledger.lastTs), 90)) },
  { key: 'rejected_decisions', label: 'Refused actions', source: 'think_token_ledger (decision=rejected)', doc: 'Receipted refusals that mention this token.', compute: (i) => count(i.ledger.rejected, 5) },
  { key: 'status_changes', label: 'Status changes', source: 'think_token_ledger (set_status)', doc: 'Receipted operator accept/retire actions.', compute: (i) => count(act(i, 'set_status'), 3) },
  // ── health ──
  { key: 'is_accepted', label: 'Accepted', source: 'think_tokens.status', doc: 'Eligible to be shown to the planner.', compute: (i) => flag(i.row.status === 'accepted') },
  { key: 'is_retrievable', label: 'Retrievable', source: 'status + think_token_embeddings', doc: 'Accepted and embedded, so cosine retrieval can find it.', compute: (i) => flag(i.row.status === 'accepted' && i.embeddingModel !== null) },
  { key: 'is_retired', label: 'Retired', source: 'think_tokens.status', doc: 'Retired by an operator or by a merge.', compute: (i) => flag(i.row.status === 'retired') },
  { key: 'is_merged_away', label: 'Merged away', source: 'think_token_links', doc: 'Retired as a near-duplicate of another token.', compute: (i) => flag(mergedAway(i)) },
  { key: 'is_template', label: 'Template only', source: 'think_tokens.extractor', doc: 'Written by the deterministic template, so it can only be a candidate.', compute: (i) => flag(i.row.extractor === 'template') },
  { key: 'is_stale_unused', label: 'Stale and unused', source: 'age and uses', doc: 'Older than 30 days and never used.', compute: (i, now) => flag(i.row.uses === 0 && now - i.row.created_at > 30 * DAY) },
  { key: 'challenge_passed', label: 'Challenge passed', source: 'think_tokens.challenge_verdict', doc: 'The challenge verdict is pass.', compute: (i) => flag(i.row.challenge.verdict === 'pass') },
  { key: 'has_feedback', label: 'Has feedback', source: 'think_tokens.thumbs_*', doc: 'At least one thumb was given.', compute: (i) => flag(i.row.thumbs_up + i.row.thumbs_down > 0) },
  { key: 'never_used', label: 'Never used', source: 'think_tokens.uses', doc: 'No run has been given this token yet.', compute: (i) => flag(i.row.uses === 0) },
  { key: 'in_progress', label: 'In the pipeline', source: 'think_tokens.status', doc: 'Not yet at a final status (candidate, extracted, scored or challenged).', compute: (i) => flag(['candidate', 'extracted', 'scored', 'challenged'].includes(i.row.status)) },
];

/** Row 9: the ten newest propagation credits, one cell each (empty when fewer exist). */
const CREDIT_SLOTS = 10;
function creditDefs(): Def[] {
  return Array.from({ length: CREDIT_SLOTS }, (_, n) => ({
    key: `credit_${n + 1}`,
    label: `Credit ${n + 1} (newest first)`,
    source: 'score_breakdown.propagation',
    doc: 'A credit this token earned because a linked token was used: which token, link kind and weight.',
    compute: (i: CubeInputs) => {
      const credits = [...(bd(i).propagation ?? [])].reverse();
      const c = credits[n];
      return c ? { value: clamp01(c.credit), display: `${c.from_id} ${c.kind} ${Math.round(c.weight * 100) / 100}` } : EMPTY;
    },
  }));
}

const ALL_DEFS: Def[] = [...DEFS, ...creditDefs()];
if (ALL_DEFS.length !== CELL_COUNT) throw new Error(`the cube must have exactly ${CELL_COUNT} cells, has ${ALL_DEFS.length}`);

/** The documented cell layout: what each of the 100 cells is, without any token data. */
export const CELL_DEFS: ReadonlyArray<Omit<Cell, 'value' | 'display' | 'empty'>> = ALL_DEFS.map((d, index) => ({ index, row: ROWS[Math.floor(index / 10)]!, col: index % 10, key: d.key, label: d.label, source: d.source, doc: d.doc }));

/** token -> 100 cells. Total (always 100), pure and stable: the same inputs and `now` give the same cells. */
export function buildCells(inputs: CubeInputs, now: number): Cell[] {
  return ALL_DEFS.map((d, index) => {
    const { value, display } = d.compute(inputs, now);
    return { ...CELL_DEFS[index]!, value, display, empty: value === null };
  });
}

/** Cells whose value or display differs between two snapshots, by key. */
export function diffCells(before: Array<Pick<Cell, 'key' | 'value' | 'display'>> | null, after: Cell[]): Array<{ key: string; before: string | null; after: string; before_value: number | null; after_value: number | null }> {
  const prev = new Map((before ?? []).map((c) => [c.key, c]));
  const out = [];
  for (const c of after) {
    const p = prev.get(c.key);
    if (!p ? !c.empty : p.display !== c.display || p.value !== c.value) out.push({ key: c.key, before: p?.display ?? null, after: c.display, before_value: p?.value ?? null, after_value: c.value });
  }
  return out;
}

// ─── The 54-sticker VIEW ────────────────────────────────────────

export const FACES = ['U', 'R', 'F', 'D', 'L', 'B'] as const;
export const STICKERS_PER_FACE = 9;
export const STICKER_COUNT = FACES.length * STICKERS_PER_FACE;

/** Cell i maps to sticker i for i < 54 and folds onto sticker i - 54 for i >= 54: every cell lands on exactly one sticker, every sticker has 1 or 2 cells. */
export function stickerOfCell(cell: number): number {
  if (!Number.isInteger(cell) || cell < 0 || cell >= CELL_COUNT) throw new RangeError(`cell out of range: ${cell}`);
  return cell < STICKER_COUNT ? cell : cell - STICKER_COUNT;
}

export interface Sticker { sticker: number; face: (typeof FACES)[number]; position: number; cells: number[]; value: number | null; empty: boolean }

/** 100 cells -> 54 stickers (6 faces x 9). A sticker shows the brightest of its cells; it is empty only when all its cells are. */
export function projectTo54(cells: Cell[]): Sticker[] {
  const stickers: Sticker[] = Array.from({ length: STICKER_COUNT }, (_, s) => ({ sticker: s, face: FACES[Math.floor(s / STICKERS_PER_FACE)]!, position: s % STICKERS_PER_FACE, cells: [], value: null, empty: true }));
  for (const c of cells) {
    const st = stickers[stickerOfCell(c.index)]!;
    st.cells.push(c.index);
    if (c.value !== null) { st.value = Math.max(st.value ?? 0, c.value); st.empty = false; }
  }
  return stickers;
}

// ─── Reading the lesson text for failure modes (the lesson side of the lexicon used by retrieval) ───

const LESSON_MODES: Array<{ name: string; cues: string[] }> = [
  { name: 'missing', cues: ['enoent', 'missing', 'not exist', 'no such', 'not found'] },
  { name: 'modify', cues: ['append', 'overwrit', 'increment', 'read_file first', 'reading it', 'modif'] },
  { name: 'path', cues: ['..', 'invalid workspace path', 'workspace-relative', 'escape'] },
  { name: 'encoding', cues: ['bytes', 'utf-8', 'non-ascii', 'characters'] },
  { name: 'listing', cues: ['subfolder', 'prefix', 'no path argument', 'accepts no'] },
];

export function lessonFailureModes(text: string): string[] {
  const t = text.toLowerCase();
  return LESSON_MODES.filter((m) => m.cues.some((c) => t.includes(c))).map((m) => m.name);
}
