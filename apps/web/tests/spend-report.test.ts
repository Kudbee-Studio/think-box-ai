// The spend report: totals for today, the last 7 days and all time; per day, per model and per profile; honest zeros.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { formatSpendReport, spendReport, type SpendRun } from '../spend-report.ts';

const NOW = new Date(2026, 9, 7, 15, 0, 0).getTime(); const DAY = 86_400_000;
const run = (daysAgo: number, cost: number, model: string, profile = 'p1'): SpendRun => ({ cost_usd: cost, started_at: NOW - daysAgo * DAY - 3600_000, model, profile_id: profile });

test('an empty history is all zeros', () => {
  const r = spendReport([], { now: NOW });
  assert.deepEqual([r.runs, r.today_usd, r.last_7d_usd, r.all_time_usd, r.by_day, r.by_model, r.by_profile], [0, 0, 0, 0, [], [], []]);
});

test('totals cover today, the last 7 days (today and the 6 days before) and all time', () => {
  const r = spendReport([run(0, 1, 'a'), run(3, 2, 'a'), run(6, 4, 'b'), run(7, 8, 'b'), run(30, 16, 'b')], { now: NOW });
  assert.deepEqual([r.today_usd, r.last_7d_usd, r.all_time_usd, r.runs], [1, 7, 31, 5]);
});

test('per model: most expensive first, with runs and the average cost per run; a missing model is "unknown"', () => {
  const r = spendReport([run(0, 3, 'a'), run(0, 1, 'a'), run(0, 10, 'b'), { cost_usd: 0.5, started_at: NOW }], { now: NOW });
  assert.deepEqual(r.by_model.map((m) => [m.model, m.runs, m.cost_usd, m.avg_cost_usd]), [['b', 1, 10, 10], ['a', 2, 4, 2], ['unknown', 1, 0.5, 0.5]]);
});

test('per profile uses the given names; per day lists the last 14 days newest first', () => {
  const r = spendReport([run(0, 1, 'a', 'p1'), run(1, 2, 'a', 'p2'), run(20, 5, 'a', 'p2')], { now: NOW, names: { p1: 'Alice' } });
  assert.deepEqual(r.by_profile.map((p) => [p.profile, p.name, p.cost_usd]), [['p2', undefined, 7], ['p1', 'Alice', 1]]);
  assert.deepEqual(r.by_day.map((d) => d.cost_usd), [1, 2]); assert.ok(r.by_day[0]!.day > r.by_day[1]!.day);
});

test('the text report names the totals and each group', () => {
  const text = formatSpendReport(spendReport([run(0, 0.5, 'mercury-2', 'p1')], { now: NOW, names: { p1: 'kudbee' } }));
  assert.match(text, /today \$0\.50/); assert.match(text, /mercury-2 +1 runs +\$0\.50/); assert.match(text, /kudbee +1 runs/);
});
