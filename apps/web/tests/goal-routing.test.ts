// Which goals a plain local chat can answer, and which must go to the worker agent.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { isComplexGoal, needsToolsOrLiveData } from '../goal-routing.ts';

describe('needsToolsOrLiveData', () => {
  it('lets plain knowledge and chat goals stay on the local model', () => {
    for (const goal of [
      'What is 2 plus 2? Answer in one short sentence.',
      'Say hi',
      'Say hello in Spanish.',
      'Name the capital of France in one word.',
      'What colour is the sky on a clear day? One word.',
      'What can you do with machine learning?',
      'Explain what a hash map is in two sentences.',
      'Tell me a short joke.',
      'Translate "good morning" into German.',
    ]) assert.equal(needsToolsOrLiveData(goal), null, goal);
  });

  it('sends repository, live-state, date, file, web, action, image and system goals to the worker agent, with a reason', () => {
    const cases: Array<[string, RegExp]> = [
      ['WHAT PR ARE WE ON', /pull requests|repository/],
      ['what PR are we working on?', /pull requests|repository/],
      ['How many open issues are there?', /pull requests|repository/],
      ['Is the server up right now?', /live state/],
      ['What is the weather today?', /current date|recent events/],
      ['What is the latest news about Mars?', /current date|recent events/],
      ['Summarize https://example.com/page', /file|URL|website/],
      ['What is in config.json?', /file|URL|website/],
      ['List my files', /file|URL|website|action/],
      ['Download the report and email it to me', /action/],
      ['Generate an image of a dog', /image/],
      ['Which Think Tokens do you remember?', /system|memory/],
      ['What did you learn in TT-000007?', /system|memory/],
    ];
    for (const [goal, why] of cases) {
      const reason = needsToolsOrLiveData(goal);
      assert.ok(reason, `${goal} should need tools or live data`);
      assert.match(reason!, why, goal);
    }
  });

  it('handles empty, non-string and hostile input', () => {
    assert.equal(needsToolsOrLiveData(''), null);
    assert.equal(needsToolsOrLiveData(undefined as unknown as string), null);
    assert.equal(needsToolsOrLiveData(null as unknown as string), null);
    assert.equal(needsToolsOrLiveData('a'.repeat(100_000)), null);
    assert.doesNotThrow(() => needsToolsOrLiveData('((((((((((((((((((((((((((((((('));
  });
});

describe('isComplexGoal (the CLI rule)', () => {
  it('keeps the old rule: complexity words, long goals and code', () => {
    assert.ok(isComplexGoal('Write a function that sorts numbers'));
    assert.ok(isComplexGoal('Analyze this'));
    assert.ok(isComplexGoal('x'.repeat(151)));
    assert.ok(isComplexGoal('```js\nconsole.log(1)\n```'));
  });
  it('and now also treats tool or live-data goals as complex, so the CLI and the server agree', () => {
    assert.ok(isComplexGoal('WHAT PR ARE WE ON'));
    assert.ok(!isComplexGoal('What is 2 plus 2?'));
    assert.ok(!isComplexGoal('Say hi'));
  });
});
