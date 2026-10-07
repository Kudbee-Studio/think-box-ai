// What a new customer sees: a short help that leads with plain-English goals, a welcome, and a model list that states what is measured and what is not.
import assert from 'node:assert/strict';
import test from 'node:test';
import { CLOUD_MEASUREMENTS } from '../cloud-measurements.ts';
import { MODELS_PRIVACY_NOTE, cloudModelNote, localModelNote, quickHelp, welcome } from '../cli-help.ts';

const plain = { bold: (s: string) => s, dim: (s: string) => s, cyan: (s: string) => s, yellow: (s: string) => s, green: (s: string) => s };

test('the short help leads with plain-English goals, lists a handful of everyday commands, and points at /help all', () => {
  const h = quickHelp(plain);
  assert.match(h, /Just type a goal in plain English/); assert.match(h, /Read https:\/\/hnrss\.org\/frontpage/);
  for (const cmd of ['/models', '/model NAME', '/files', '/runs', '/stop', '/help all', '/quit']) assert.ok(h.includes(cmd), cmd);
  assert.ok(h.split('\n').length <= 24, 'short enough to read at a glance');
  for (const jargon of ['Think Token', 'Convoy', 'HERMES', 'Upstash', 'BM25', 'Mayor']) assert.ok(!h.includes(jargon), `no internal word: ${jargon}`);
  assert.match(h, /asks you first/);
});

test('the welcome names the session, model and address and says how to get help', () => {
  const w = welcome(plain, { session: 'abcd1234', model: 'mercury-2', host: 'http://127.0.0.1:3000' });
  assert.match(w, /session abcd1234 · model mercury-2 · http:\/\/127\.0\.0\.1:3000/); assert.match(w, /\/help/); assert.match(w, /asks you first/);
});

test('a measured cloud model shows its verified fixes, cost per task and time; an estimated price says so; an unmeasured one says "not measured yet"', () => {
  assert.equal(cloudModelNote('mercury-2', 'inception'), '[inception] 64/66 verified fixes · about $0.0021 per task · 2.6 s median');
  assert.match(cloudModelNote('deepseek-flash', 'deepseek'), /66\/66 verified fixes · about \$0\.0028 per task \(estimated price\) · 5\.4 s median/);
  assert.match(cloudModelNote('deepseek-chat', 'deepseek'), /66\/66/, 'the experiment alias resolves to the registered model');
  assert.equal(cloudModelNote('some-new-model', 'acme'), '[acme] cloud agent · not measured yet');
  assert.equal(cloudModelNote('x', undefined, []), '[cloud] cloud agent · not measured yet');
  for (const m of CLOUD_MEASUREMENTS) assert.ok(cloudModelNote(m.model, 'p').includes(`${m.success}/${m.tasks}`), m.model);
});

test('local models say they stay on the machine, and the privacy note is plain', () => {
  assert.match(localModelNote('ollama'), /runs on your machine · nothing leaves it/);
  assert.match(MODELS_PRIVACY_NOTE, /Cloud agents send your goal/);
});
