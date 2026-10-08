import assert from 'node:assert/strict';
import { test } from 'node:test';
import { setupSteps } from '../setup-status.ts';

const none = { env: {}, ollamaReachable: false, runs: 0 };
const step = (r: ReturnType<typeof setupSteps>, id: string) => r.steps.find((s) => s.id === id)!;

test('a fresh install is not ready and the first step says exactly what to set', () => {
  const r = setupSteps(none);
  assert.equal(r.ready, false);
  assert.equal(step(r, 'model').done, false);
  assert.match(step(r, 'model').hint, /INCEPTION_API_KEY|DEEPSEEK_API_KEY|XAI_API_KEY|Ollama/);
  assert.equal(step(r, 'first-goal').done, false);
});

test('any one model source makes it ready: a cloud key or a reachable local Ollama', () => {
  for (const env of [{ INCEPTION_API_KEY: 'k' }, { DEEPSEEK_API_KEY: 'k' }, { XAI_API_KEY: 'k' }]) assert.equal(setupSteps({ ...none, env }).ready, true);
  assert.equal(setupSteps({ ...none, ollamaReachable: true }).ready, true);
  assert.equal(setupSteps({ ...none, env: { INCEPTION_API_KEY: '   ' } }).ready, false, 'a blank key is not a key');
});

test('a placeholder key from the example file does not count', () => {
  assert.equal(setupSteps({ ...none, env: { INCEPTION_API_KEY: 'sk-your-key-here' } }).ready, false);
});

test('first goal is done once any run exists; the spend limit step reads the budget variable; neither blocks ready', () => {
  const r = setupSteps({ env: { INCEPTION_API_KEY: 'k', KUDBEE_DAILY_BUDGET_USD: '2' }, ollamaReachable: false, runs: 3 });
  assert.equal(step(r, 'first-goal').done, true);
  assert.equal(step(r, 'spend-limit').done, true);
  assert.equal(setupSteps({ env: { INCEPTION_API_KEY: 'k' }, ollamaReachable: false, runs: 0 }).ready, true);
  assert.equal(step(setupSteps({ env: { INCEPTION_API_KEY: 'k', KUDBEE_DAILY_BUDGET_USD: '0' }, ollamaReachable: false, runs: 0 }), 'spend-limit').done, false);
});

test('the result never contains a key value', () => {
  assert.ok(!JSON.stringify(setupSteps({ env: { INCEPTION_API_KEY: 'sk-live-secret1234567890' }, ollamaReachable: false, runs: 0 })).includes('secret1234567890'));
});
