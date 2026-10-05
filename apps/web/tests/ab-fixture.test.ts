// The A/B goal set is frozen: 30 goals, unique ids, none of the earlier eval wordings, and the engine-checked ones are answerable in the fixture.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EVAL_TASKS } from '../local-eval.ts';
import { AB_GOALS, goalsHash, startAbWorld } from './helpers/ab-fixture.ts';
import { runAbsenceCheck } from '../absence.ts';

test('30 frozen goals, 15 lookup + 15 repo, unique, none reused from the earlier eval', () => {
  assert.equal(AB_GOALS.length, 30);
  assert.equal(AB_GOALS.filter((g) => g.class === 'lookup').length, 15);
  assert.equal(new Set(AB_GOALS.map((g) => g.id)).size, 30);
  const old = new Set(EVAL_TASKS.map((t) => t.goal.toLowerCase()));
  assert.deepEqual(AB_GOALS.filter((g) => old.has(g.goal.toLowerCase())), []);
  assert.match(goalsHash(), /^[0-9a-f]{64}$/);
});
test('in the fixture each untested function really has no test and each tested one does (engine check agrees)', async () => {
  const world = await startAbWorld();
  try {
    const f = (file: string, fn: string, line: number) => ({ found: true, file: `src/${file}.ts`, line, quote: `export function ${fn}(x: number): number {`, claim: `\`${fn}\` has no tests` });
    assert.equal((await runAbsenceCheck(f('billing', 'refundCard', 5), world.root)).contradicted.length, 0);
    assert.ok((await runAbsenceCheck(f('billing', 'chargeCard', 2), world.root)).contradicted.length >= 1);
  } finally { await world.close(); }
});
