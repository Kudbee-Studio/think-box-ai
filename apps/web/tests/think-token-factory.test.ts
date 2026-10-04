// Unit tests for think-token-factory.ts: the four candidate extractors and the specificity/actionability/generalizability quality gate.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ThinkTokenFactory } from '../think-token-factory.ts';
import type { Thought } from '../types.ts';

const t = (o: Record<string, unknown>): Thought => ({ id: 't', timestamp: 1, type: 'reasoning', ...o } as Thought);

test('extractCandidates produces every token type from a rich session', () => {
  const thoughts: Thought[] = [
    t({ type: 'tool_call', plugin: 'read_file' }),
    t({ type: 'tool_call', plugin: 'write_file' }),
    t({ id: 'e', type: 'tool_result', status: 'error', content: 'permission denied here' }),
    t({ type: 'tool_call', plugin: 'chmod' }),
    t({ type: 'reasoning', status: 'thinking', content: 'use approach A or approach B to proceed' }),
    t({ type: 'reasoning', content: 'use fewer steps to run faster' }),
  ];
  const tokens = ThinkTokenFactory.extractCandidates('s', 'build a report', thoughts);
  assert.deepEqual(tokens.map((x) => x.content.type).sort(), ['approach', 'error_recovery', 'optimization', 'tool_sequence']);
  const tool = tokens.find((x) => x.content.type === 'tool_sequence')!;
  assert.match(tool.content.text, /read_file → write_file/);
  assert.equal(tool.metadata.originGoal, 'build a report');
});

test('a single tool call does not qualify as a tool-sequence token', () => {
  const tokens = ThinkTokenFactory.extractCandidates('s', 'g', [t({ type: 'tool_call', plugin: 'only_one' })]);
  assert.equal(tokens.some((x) => x.content.type === 'tool_sequence'), false);
});

test('no thoughts yields no candidates', () => {
  assert.deepEqual(ThinkTokenFactory.extractCandidates('s', 'g', []), []);
});

test('the quality gate rejects a vague decision that is not actionable', () => {
  const tokens = ThinkTokenFactory.extractCandidates('s', 'g', [t({ type: 'reasoning', status: 'thinking', content: 'banana or apple' })]);
  assert.deepEqual(tokens, []);
});

test('the quality gate rejects a decision bound to a single instance', () => {
  const tokens = ThinkTokenFactory.extractCandidates('s', 'g', [t({ type: 'reasoning', status: 'thinking', content: 'use alpha or beta today' })]);
  assert.deepEqual(tokens, []);
});

test('an error is only recovered when a tool call follows it, and only a reasoning status of thinking is a decision', () => {
  const errored = ThinkTokenFactory.extractCandidates('s', 'g', [
    t({ type: 'tool_result', status: 'error', content: 'boom' }),
    t({ type: 'reasoning', content: 'use a different tool' }),
  ]);
  assert.equal(errored.some((x) => x.content.type === 'error_recovery'), false);

  const notThinking = ThinkTokenFactory.extractCandidates('s', 'g', [t({ type: 'reasoning', status: 'done', content: 'use a or b' })]);
  assert.equal(notThinking.some((x) => x.content.type === 'approach'), false);
});
