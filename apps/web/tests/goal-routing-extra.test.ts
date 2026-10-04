// Unit tests for goal-routing.ts: the seven live-data reasons, complexity, local confidence and answer grounding.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { needsToolsOrLiveData, isComplexGoal, localConfidence, groundAnswer } from '../goal-routing.ts';

test('needsToolsOrLiveData names the matching reason for each category', () => {
  assert.match(needsToolsOrLiveData('what prs are open')!, /repository or its pull requests/);
  assert.match(needsToolsOrLiveData('is it running')!, /live state/);
  assert.match(needsToolsOrLiveData('what is the latest news')!, /current date, time or recent events/);
  assert.match(needsToolsOrLiveData('read notes.md')!, /file, folder, workspace, URL/);
  assert.match(needsToolsOrLiveData('install the package')!, /take an action/);
  assert.match(needsToolsOrLiveData('draw me a logo')!, /image/);
  assert.match(needsToolsOrLiveData('what think tokens are saved')!, /this system/);
});

test('needsToolsOrLiveData returns null for a plain knowledge question and tolerates empty input', () => {
  assert.equal(needsToolsOrLiveData('what is 2 plus 2'), null);
  assert.equal(needsToolsOrLiveData(''), null);
  assert.equal(needsToolsOrLiveData(undefined as unknown as string), null);
});

test('isComplexGoal is true for a complexity keyword, a long goal or a live-data goal', () => {
  assert.equal(isComplexGoal('write a function that adds'), true);
  assert.equal(isComplexGoal('x'.repeat(151)), true);
  assert.equal(isComplexGoal('what is the latest news'), true);
  assert.equal(isComplexGoal('2+2'), false);
});

test('localConfidence scores a known recipe, an unknown live goal, knowledge, complexity and the default', () => {
  assert.equal(localConfidence('what pr is open'), 75);
  assert.equal(localConfidence('is it running'), 25);
  assert.equal(localConfidence('explain gravity'), 90);
  assert.equal(localConfidence('refactor the module'), 30);
  assert.equal(localConfidence('banana'), 70);
});

test('groundAnswer requires a cited fact only when evidence is present', () => {
  assert.deepEqual(groundAnswer('The value is 42', ['42']), { ok: true });
  assert.deepEqual(groundAnswer('anything at all', []), { ok: true });
  const ungrounded = groundAnswer('I am not sure', ['42']);
  assert.equal(ungrounded.ok, false);
  assert.match(ungrounded.why!, /did not cite/);
});
