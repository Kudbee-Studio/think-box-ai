import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseOllamaLine } from '../ollama-line.ts';

test('parseOllamaLine parses a good line and skips blank or garbled ones instead of throwing', () => {
  assert.deepEqual(parseOllamaLine('{"message":{"content":"hi"},"done":false}'), { message: { content: 'hi' }, done: false });
  assert.equal(parseOllamaLine(''), null);
  assert.equal(parseOllamaLine('   '), null);
  assert.equal(parseOllamaLine('{"message":{"content":"cut off'), null);
  assert.equal(parseOllamaLine('not json'), null);
});
