// Think Token health: counts over the saved tokens (used, waiting, stale, finished runs), honest about being observational; same numbers in the CLI and the dashboard message.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { formatTokenHealth, tokenHealth } from '../think-token-health.ts';
import type { ApiToken } from '../think-token-reader.ts';

const NOW = Date.parse('2026-10-07T12:00:00Z'); const DAY = 86_400_000;
const tok = (over: Partial<ApiToken>): ApiToken => ({ id: 'TT-000001', legacy_id: null, kind: 'lesson', title: 'A lesson', content: 'x', tags: [], status: 'accepted', score: 0.8, score_breakdown: {} as never, source_run_id: 'r', evidence_ref: 'e', extractor: 'mercury' as never, extract_model: null, challenge: { verdict: null, reason: null, model: null, meta: {} as never }, uses: 0, last_used_at: null, success_runs: 0, failed_runs: 0, thumbs_up: 0, thumbs_down: 0, seen_count: 1, created_at: NOW - DAY, used_by: [] as never, receipt: null, links: [], ...over });

test('an empty store has all zeros and no ids', () => {
  const h = tokenHealth([], NOW);
  assert.equal(h.total, 0); assert.equal(h.accepted, 0); assert.deepEqual(h.top_used, []); assert.deepEqual(h.stale_ids, []);
});

test('used, recently used, waiting and stale accepted tokens are counted apart; other statuses only in by_status', () => {
  const tokens = [
    tok({ id: 'TT-000001', uses: 5, last_used_at: NOW - DAY, success_runs: 4, failed_runs: 1, created_at: NOW - 3 * DAY }),
    tok({ id: 'TT-000002', uses: 2, last_used_at: NOW - 40 * DAY, success_runs: 2, created_at: NOW - 60 * DAY }),
    tok({ id: 'TT-000003', uses: 0, created_at: NOW - 10 * DAY }),
    tok({ id: 'TT-000004', uses: 0, created_at: NOW - 50 * DAY }),
    tok({ id: 'TT-000005', uses: 0, created_at: NOW - 2 * DAY }),
    tok({ id: 'TT-000006', status: 'rejected', uses: 9, success_runs: 9 }),
  ];
  const h = tokenHealth(tokens, NOW);
  assert.deepEqual([h.total, h.accepted, h.used, h.used_7d, h.waiting, h.stale], [6, 5, 2, 1, 1, 2]);
  assert.deepEqual(h.by_status, { accepted: 5, rejected: 1 });
  assert.deepEqual([h.runs_finished, h.runs_failed], [6, 1], 'a rejected token never counts');
  assert.deepEqual(h.stale_ids, ['TT-000002', 'TT-000004']);
  assert.deepEqual(h.top_used.map((t) => t.id), ['TT-000001', 'TT-000002']);
});

test('thumbs and challenge verdicts are totalled over every token', () => {
  const h = tokenHealth([tok({ thumbs_up: 2, challenge: { verdict: 'pass', reason: null, model: null, meta: {} as never } }), tok({ status: 'rejected', thumbs_down: 1, challenge: { verdict: 'fail', reason: null, model: null, meta: {} as never } })], NOW);
  assert.deepEqual([h.thumbs_up, h.thumbs_down, h.challenge_pass, h.challenge_fail], [2, 1, 1, 1]);
});

test('the text form states the counts and says it is not a measurement of benefit', () => {
  const text = formatTokenHealth(tokenHealth([tok({ uses: 3, last_used_at: NOW - DAY, success_runs: 3, created_at: NOW - 40 * DAY }), tok({ id: 'TT-000002', created_at: NOW - 90 * DAY })], NOW));
  assert.match(text, /2 saved, 2 accepted \(0 learned in one repository/); assert.match(text, /used by a run: 1 of 2/); assert.match(text, /most used:\n\s+TT-000001  3x/); assert.match(text, /to re-check: TT-000002/); assert.match(text, /measured by the A\/B experiments/);
});

test('accepted tokens learned in one repository are counted as repository-scoped', () => {
  const h = tokenHealth([tok({ tags: ['repo:acme:demo', 'lesson'] }), tok({ id: 'TT-000002' }), tok({ id: 'TT-000003', status: 'rejected', tags: ['repo:acme:demo'] })], NOW);
  assert.equal(h.repo_scoped, 1);
});
