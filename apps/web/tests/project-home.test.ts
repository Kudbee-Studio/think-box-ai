import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildProject } from '../project-home.ts';

const DAY = 86_400_000; const now = Date.UTC(2026, 9, 8, 12, 0, 0);
const active = { name: 'demo', repo: 'acme/demo', tag: 'repo:acme:demo' };
const run = (id: string, repo: string | undefined, over: Record<string, unknown> = {}) => ({ id, repo, goal: `goal ${id}`, status: 'completed', cost_usd: 0.01, files: ['a.ts'], started_at: now - 1000, ...over });

test('with no repository chosen it says how to choose one and shows nothing else', () => {
  const p = buildProject({ active: null, changes: [], runs: [run('1', 'demo')], audit: [], tokens: [], now });
  assert.equal(p.repo, null); assert.match(p.note, /Use for agent/); assert.equal(p.runs.count, 0);
});

test('only runs started on this repository are counted, newest first, with their cost', () => {
  const runs = [run('old', 'demo', { started_at: now - 3 * DAY, cost_usd: 0.02 }), run('other', 'different'), run('none', undefined), run('new', 'demo', { status: 'failed', cost_usd: 0.03 })];
  const p = buildProject({ active, changes: [], runs, audit: [], tokens: [], now });
  assert.equal(p.runs.count, 2); assert.deepEqual(p.runs.recent.map((r) => r.id), ['new', 'old']);
  assert.equal(p.runs.failed, 1); assert.equal(Math.round(p.runs.total_usd * 100), 5); assert.equal(Math.round(p.runs.today_usd * 100), 3);
  assert.equal(p.runs.recent[0].files, 1);
});

test('recent runs are capped at five and goals are shortened', () => {
  const runs = Array.from({ length: 9 }, (_, i) => run(String(i), 'demo', { started_at: now - i * 1000, goal: 'x'.repeat(300) }));
  const p = buildProject({ active, changes: [], runs, audit: [], tokens: [], now });
  assert.equal(p.runs.recent.length, 5); assert.equal(p.runs.count, 9); assert.ok(p.runs.recent[0].goal.length <= 100);
});

test('uncommitted changes are listed (first eight) and trigger the review hint', () => {
  const changes = Array.from({ length: 11 }, (_, i) => ({ path: `f${i}.ts`, status: 'modified' as const }));
  const p = buildProject({ active, changes, runs: [], audit: [], tokens: [], now });
  assert.equal(p.changes.count, 11); assert.equal(p.changes.files.length, 8);
  assert.ok(p.next.some((n) => /Review/.test(n)));
  assert.deepEqual(buildProject({ active, changes: [], runs: [], audit: [], tokens: [], now }).next.filter((n) => /Review/.test(n)), []);
});

test('Think Tokens counts only accepted tokens tagged for this repository, and lists their titles', () => {
  const t = (id: string, tags: string[], status = 'accepted') => ({ id, title: `lesson ${id}`, tags, status });
  const p = buildProject({ active, changes: [], runs: [], audit: [], now, tokens: [t('a', ['repo:acme:demo']), t('b', ['repo:acme:other']), t('c', []), t('d', ['repo:acme:demo'], 'proposed')] });
  assert.equal(p.tokens.repo_scoped, 1); assert.deepEqual(p.tokens.titles, ['lesson a']);
});

test('recent repository decisions come from the audit log, newest first, and nothing else', () => {
  const audit = [
    { ts: 3, kind: 'draft_pr', actor: 'human', summary: 'draft PR opened: https://x/pull/1' },
    { ts: 2, kind: 'approval_resolved', actor: 'dashboard', summary: 'approved' },
    { ts: 1, kind: 'changes_undone', actor: 'human', summary: 'undid a.ts' },
  ];
  const p = buildProject({ active, changes: [], runs: [], audit, tokens: [], now });
  assert.deepEqual(p.events.map((e) => e.kind), ['draft_pr', 'changes_undone']);
});

test('the note admits that runs from before this page existed are not attributed', () => {
  assert.match(buildProject({ active, changes: [], runs: [], audit: [], tokens: [], now }).note, /before/i);
});
