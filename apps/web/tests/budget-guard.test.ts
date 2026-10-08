// Spend limits: the daily and per-run budgets stop a run with a plain message, a daily 80% warning is raised once per day, and both are off unless set.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { BudgetGuard, budgetConfig, formatUsd } from '../budget-guard.ts';

const guard = (cfg: { daily: number; run: number }, today: { v: number }, events: string[], now = () => Date.parse('2026-10-07T12:00:00')): BudgetGuard =>
  new BudgetGuard(cfg, { costToday: () => today.v, now, onWarn: (m) => events.push(`warn:${m}`), onStop: (m, id) => events.push(`stop:${id}:${m}`) });

test('configuration: unset, zero, negative and junk values mean off', () => {
  assert.deepEqual(budgetConfig({}), { daily: 0, run: 0 });
  assert.deepEqual(budgetConfig({ KUDBEE_DAILY_BUDGET_USD: '5', KUDBEE_RUN_BUDGET_USD: '0.25' }), { daily: 5, run: 0.25 });
  assert.deepEqual(budgetConfig({ KUDBEE_DAILY_BUDGET_USD: '-1', KUDBEE_RUN_BUDGET_USD: 'abc' }), { daily: 0, run: 0 });
});

test('the daily message is the one the dashboard already shows', () => {
  assert.equal(formatUsd(0.005), '$0.0050'); assert.equal(formatUsd(5), '$5.00');
  const events: string[] = []; const g = guard({ daily: 0.01, run: 0 }, { v: 0.01 }, events);
  assert.equal(g.check(0, 'r1'), 'Daily budget of $0.01 reached (KUDBEE_DAILY_BUDGET_USD)');
});

test('off means off: nothing stops and nothing warns', () => {
  const events: string[] = []; const g = guard({ daily: 0, run: 0 }, { v: 999 }, events);
  assert.equal(g.check(999, 'r'), null); assert.deepEqual(events, []);
});

test('a per-run cap stops that run only, and the daily budget is checked first', () => {
  const events: string[] = []; const today = { v: 0.1 };
  const g = guard({ daily: 5, run: 0.25 }, today, events);
  assert.equal(g.check(0.24, 'a'), null); assert.equal(g.check(0.25, 'a'), 'Run budget of $0.25 reached (KUDBEE_RUN_BUDGET_USD)'); assert.equal(g.check(0.01, 'b'), null);
  today.v = 5; assert.match(String(g.check(0.25, 'a')), /^Daily budget/);
});

test('stopping is reported once per run and limit, not once per call', () => {
  const events: string[] = []; const g = guard({ daily: 0, run: 0.1 }, { v: 0 }, events);
  g.check(0.2, 'a'); g.check(0.3, 'a'); g.check(0.2, 'b');
  assert.deepEqual(events, ['stop:a:Run budget of $0.10 reached (KUDBEE_RUN_BUDGET_USD)', 'stop:b:Run budget of $0.10 reached (KUDBEE_RUN_BUDGET_USD)']);
});

test('80% of the daily budget warns once per day, not before, not at the limit, and again the next day', () => {
  const events: string[] = []; const today = { v: 0 }; let clock = Date.parse('2026-10-07T12:00:00');
  const g = guard({ daily: 10, run: 0 }, today, events, () => clock);
  today.v = 7.9; g.check(0, 'r'); assert.deepEqual(events, []);
  today.v = 8; g.check(0, 'r'); g.check(0, 'r'); assert.deepEqual(events, ['warn:80% of the daily budget is used: $8.00 of $10.00']);
  clock = Date.parse('2026-10-08T09:00:00'); today.v = 8.5; g.check(0, 'r'); assert.equal(events.length, 2);
  today.v = 10; assert.match(String(g.check(0, 'r')), /^Daily budget/); assert.equal(events.filter((e) => e.startsWith('warn')).length, 2);
});
