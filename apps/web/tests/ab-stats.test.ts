import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fisherExact, pairedBootstrap, percentile, rng, wilson } from '../ab-stats.ts';

test('Fisher exact matches independently enumerated values', () => {
  assert.ok(Math.abs(fisherExact(8, 2, 1, 5) - 0.03496503496503497) < 1e-9);
  assert.ok(Math.abs(fisherExact(12, 18, 21, 9) - 0.036992395940511104) < 1e-9);
  assert.equal(fisherExact(5, 5, 5, 5), 1);
  assert.ok(fisherExact(0, 10, 10, 0) < 1e-4);
});
test('paired bootstrap is deterministic, centred on the observed difference, and brackets a clear effect', () => {
  const x = Array.from({ length: 30 }, (_, i) => (i < 10 ? 1 : 0));
  const y = Array.from({ length: 30 }, (_, i) => (i < 22 ? 1 : 0));
  const a = pairedBootstrap(x, y); const b = pairedBootstrap(x, y);
  assert.deepEqual(a, b);
  assert.ok(Math.abs(a.diff - 0.4) < 1e-9);
  assert.ok(a.lo > 0.1 && a.hi < 0.7, JSON.stringify(a));
});
test('no difference gives an interval that contains zero; mismatched samples are refused', () => {
  const z = Array.from({ length: 30 }, (_, i) => i % 2);
  const r = pairedBootstrap(z, z);
  assert.equal(r.diff, 0); assert.equal(r.lo, 0); assert.equal(r.hi, 0);
  const noisy = pairedBootstrap(z, z.map((v, i) => (i % 6 === 0 ? 1 - v : v)));
  assert.ok(noisy.lo <= 0 && noisy.hi >= 0 || Math.abs(noisy.diff) < 0.2);
  assert.throws(() => pairedBootstrap([1], [1, 0]));
});
test('wilson, percentile and the seeded generator behave', () => {
  const w = wilson(15, 30); assert.ok(w.lo < 0.5 && w.hi > 0.5 && w.lo > 0.3 && w.hi < 0.7);
  assert.deepEqual(wilson(0, 0), { lo: 0, hi: 0 });
  assert.equal(percentile([5, 1, 3, 2, 4], 0.5), 3);
  assert.equal(percentile([], 0.5), 0);
  const r1 = rng(7); const r2 = rng(7);
  assert.deepEqual([r1(), r1(), r1()], [r2(), r2(), r2()]);
});
