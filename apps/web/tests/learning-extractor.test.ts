// Unit tests for learning-extractor.ts: the four pattern extractors, the store writes, the prompt builder and edge cases.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { LearningExtractor } from '../learning-extractor.ts';
import type { LearningStore, LearnedPattern } from '../learning-store.ts';
import type { Thought, MemoryEntry } from '../types.ts';

class FakeStore {
  patterns: LearnedPattern[] = [];
  approaches: Array<{ goal: string; outcome: string }> = [];
  storePattern(p: LearnedPattern): void { this.patterns.push(p); }
  getTopPatterns(limit: number): LearnedPattern[] { return this.patterns.slice(0, limit); }
  getSuccessfulApproaches(_goal: string): Array<{ goal: string; outcome: string }> { return this.approaches; }
}

function extractor(): { ex: LearningExtractor; store: FakeStore } {
  const store = new FakeStore();
  return { ex: new LearningExtractor(store as unknown as LearningStore), store };
}

const t = (over: Partial<Thought>): Thought => ({ id: 't', timestamp: 1, type: 'reasoning', ...over } as Thought);
const mem = (): MemoryEntry[] => [];

test('extractPatternsFromSession writes a tool-sequence, decomposition, recovery and optimization pattern from one session', () => {
  const { ex, store } = extractor();
  const thoughts: Thought[] = [
    t({ type: 'reasoning', content: 'step one: plan' }),
    t({ type: 'plugin_call', plugin: 'read_file' }),
    t({ type: 'plugin_call', plugin: 'write_file' }),
    t({ type: 'plugin_call', plugin: 'list_files' }),
    t({ id: 'e', type: 'plugin_result', status: 'error' }),
    t({ type: 'completion', content: 'retried after the error' }),
  ];
  const ids = ex.extractPatternsFromSession('s1', 'do the thing', thoughts, mem(), 'success');
  assert.equal(ids.length, 4);
  assert.deepEqual(store.patterns.map((p) => p.type).sort(), ['error_recovery', 'goal_approach', 'optimization', 'tool_sequence']);
  const toolPattern = store.patterns.find((p) => p.type === 'tool_sequence')!;
  assert.equal(toolPattern.confidence, 0.9);
  assert.deepEqual(toolPattern.metadata.tools, ['read_file', 'write_file', 'list_files']);
  assert.equal(toolPattern.metadata.toolCount, 3);
});

test('outcome failure and partial set the documented confidences', () => {
  const failure = extractor();
  failure.ex.extractPatternsFromSession('s', 'g', [t({ type: 'plugin_call', plugin: 'a' })], mem(), 'failure');
  assert.equal(failure.store.patterns[0].confidence, 0.2);
  assert.equal(failure.store.patterns[0].failureCount, 1);

  const partial = extractor();
  partial.ex.extractPatternsFromSession('s', 'g', [t({ type: 'plugin_call', plugin: 'a' })], mem(), 'partial');
  assert.equal(partial.store.patterns[0].confidence, 0.5);
});

test('no thoughts yields no patterns', () => {
  const { ex, store } = extractor();
  assert.deepEqual(ex.extractPatternsFromSession('s', 'g', [], mem(), 'success'), []);
  assert.equal(store.patterns.length, 0);
});

test('goal decomposition groups reasoning steps by the last plugin phase', () => {
  const { ex, store } = extractor();
  const thoughts: Thought[] = [
    t({ type: 'reasoning', content: 'step A' }),
    t({ type: 'plugin_call', plugin: 'fetch_url' }),
    t({ type: 'reasoning', content: 'step B' }),
  ];
  ex.extractPatternsFromSession('s', 'g', thoughts, mem(), 'success');
  const decomp = store.patterns.find((p) => p.type === 'goal_approach')!;
  assert.deepEqual(decomp.metadata.phases, ['initial', 'fetch_url']);
  assert.match(decomp.pattern, /initial → fetch_url/);
});

test('optimization flags a long tool chain and excessive reasoning', () => {
  const { ex, store } = extractor();
  const thoughts: Thought[] = [
    t({ type: 'plugin_call', plugin: 'a' }), t({ type: 'plugin_call', plugin: 'b' }), t({ type: 'plugin_call', plugin: 'c' }),
    ...Array.from({ length: 6 }, () => t({ type: 'reasoning', content: 'thinking' })),
  ];
  ex.extractPatternsFromSession('s', 'g', thoughts, mem(), 'success');
  const opt = store.patterns.find((p) => p.type === 'optimization')!;
  assert.equal((opt.metadata.suggestions as string[]).length, 2);
  assert.equal(opt.confidence, 0.6);
});

test('error recovery only records a step when a non-error thought follows', () => {
  const { ex, store } = extractor();
  const thoughts: Thought[] = [
    t({ id: 'e1', type: 'plugin_result', status: 'error', content: 'boom' }),
    t({ type: 'reasoning', content: 'switch approach' }),
    t({ id: 'e2', type: 'plugin_result', status: 'error', content: 'last' }),
  ];
  ex.extractPatternsFromSession('s', 'g', thoughts, mem(), 'success');
  const rec = store.patterns.find((p) => p.type === 'error_recovery')!;
  assert.equal(rec.metadata.errorCount, 2);
  assert.deepEqual(rec.metadata.recovery, ['After plugin_result: switch approach']);
});

test('generateSystemPromptWithLearnings includes approaches and only patterns above 0.5', () => {
  const { ex, store } = extractor();
  store.approaches = [{ goal: 'earlier goal', outcome: 'success' }];
  store.patterns = [
    { id: 'p1', type: 'tool_sequence', pattern: 'high', confidence: 0.8, sourceThoughts: [], firstSeen: 0, lastSeen: 0, successCount: 1, failureCount: 0, metadata: {} },
    { id: 'p2', type: 'tool_sequence', pattern: 'low', confidence: 0.4, sourceThoughts: [], firstSeen: 0, lastSeen: 0, successCount: 0, failureCount: 0, metadata: {} },
  ];
  const prompt = ex.generateSystemPromptWithLearnings('g', 5);
  assert.match(prompt, /Successfully completed similar goals/);
  assert.match(prompt, /earlier goal/);
  assert.match(prompt, /\[80%\] high/);
  assert.doesNotMatch(prompt, /low/);
});

test('generateSystemPromptWithLearnings returns an empty string with nothing stored', () => {
  const { ex } = extractor();
  assert.equal(ex.generateSystemPromptWithLearnings('g'), '');
});
