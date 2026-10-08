import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createMessageLimiter, WS_MAX_BYTES } from '../ws-limits.ts';

test('a client may send up to the limit in a window, then is refused until the window passes', () => {
  let t = 0;
  const lim = createMessageLimiter({ max: 3, windowMs: 1000, now: () => t });
  assert.deepEqual([lim(), lim(), lim(), lim()], [true, true, true, false]);
  t = 1001;
  assert.equal(lim(), true);
});

test('each limiter counts separately (one noisy connection does not block another)', () => {
  const a = createMessageLimiter({ max: 1, windowMs: 1000 });
  const b = createMessageLimiter({ max: 1, windowMs: 1000 });
  assert.deepEqual([a(), a(), b()], [true, false, true]);
});

test('the byte cap is 1 MB', () => assert.equal(WS_MAX_BYTES, 1_000_000));

test('KUDBEE_WS_RATE raises the default limit', () => {
  const was = process.env.KUDBEE_WS_RATE;
  process.env.KUDBEE_WS_RATE = '5';
  try { const lim = createMessageLimiter({ windowMs: 1000, now: () => 0 }); assert.deepEqual([1, 2, 3, 4, 5, 6].map(() => lim()), [true, true, true, true, true, false]); } finally { if (was === undefined) delete process.env.KUDBEE_WS_RATE; else process.env.KUDBEE_WS_RATE = was; }
});
