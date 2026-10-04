// Unit tests for think-token-propagation.ts: retrieval slicing, prompt/context injection, usage recording, stats, broadcast and A/B variants.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ThinkTokenPropagator, createPropagator } from '../think-token-propagation.ts';
import type { ThinkToken, ThinkTokenCollection } from '../think-token.ts';
import type { LearningStore, LearnedPattern } from '../learning-store.ts';

interface Meta { reuseCount: number; captureTime: number; lastReused?: number; successCount: number; failureCount: number; originGoal: string }
interface FakeToken { id: string; content: { text: string; type: string; artifacts: unknown[] }; metadata: Meta; evaluate(): number; recordUse(s: boolean): void; isRelevant(d: number): boolean }

function token(id: string, over: Partial<FakeToken> = {}): FakeToken {
  const t: FakeToken = {
    id,
    content: { text: `lesson ${id}`, type: 'tool_sequence', artifacts: [] },
    metadata: { reuseCount: 0, captureTime: 1000, successCount: 0, failureCount: 0, originGoal: 'goal' },
    evaluate: () => 0.8,
    recordUse(success: boolean) { this.metadata.reuseCount++; this.metadata.successCount += success ? 1 : 0; this.metadata.failureCount += success ? 0 : 1; if (success) this.metadata.lastReused = 2000; },
    isRelevant: () => true,
  };
  return { ...t, ...over };
}

class FakeCollection {
  tokens: FakeToken[] = [];
  add(t: FakeToken): void { this.tokens.push(t); }
  get(id: string): FakeToken | undefined { return this.tokens.find((t) => t.id === id); }
  relevantFor(_goal: string, days: number): FakeToken[] { return this.tokens.filter((t) => t.isRelevant(days)); }
  export(): FakeToken[] { return this.tokens; }
}

function build(tokens: FakeToken[] = []): { p: ThinkTokenPropagator; c: FakeCollection; saved: LearnedPattern[] } {
  const c = new FakeCollection();
  c.tokens = tokens;
  const saved: LearnedPattern[] = [];
  const store = { storePattern: (x: LearnedPattern) => saved.push(x) } as unknown as LearningStore;
  return { p: new ThinkTokenPropagator(store, c as unknown as ThinkTokenCollection), c, saved };
}

test('addToken makes a token visible and getRelevantTokensForGoal slices to the limit', () => {
  const { p, c } = build();
  p.addToken(token('TT-1') as unknown as ThinkToken);
  p.addToken(token('TT-2') as unknown as ThinkToken);
  assert.equal(c.tokens.length, 2);
  assert.equal(p.getRelevantTokensForGoal('g', 1).length, 1);
  assert.equal(p.getRelevantTokensForGoal('g').length, 2);
});

test('injectTokensIntoSystemPrompt returns the base prompt unchanged with no tokens', () => {
  const { p } = build();
  assert.equal(p.injectTokensIntoSystemPrompt('BASE', 'g'), 'BASE');
});

test('injectTokensIntoSystemPrompt lists each token with confidence, type and reuse count', () => {
  const { p } = build([token('TT-1')]);
  const out = p.injectTokensIntoSystemPrompt('BASE', 'g', 5);
  assert.match(out, /Prior Experience \(Think Tokens\)/);
  assert.match(out, /1\. \[80% confidence\] lesson TT-1/);
  assert.match(out, /Type: tool_sequence \| Used: 0 times/);
});

test('createWorkerContext reports no patterns, or enhances the system message and summarises confidence', () => {
  const none = build();
  const empty = none.p.createWorkerContext('w', 'g', [{ role: 'system', content: 'SYS' }, { role: 'user', content: 'U' }]);
  assert.equal(empty.injectedTokens.length, 0);
  assert.match(empty.contextSummary, /No prior patterns/);
  assert.deepEqual(empty.enhancedMessages, [{ role: 'system', content: 'SYS' }, { role: 'user', content: 'U' }]);

  const some = build([token('TT-1'), token('TT-2')]);
  const ctx = some.p.createWorkerContext('w', 'g', [{ role: 'system', content: 'SYS' }, { role: 'user', content: 'U' }]);
  assert.equal(ctx.injectedTokens.length, 2);
  assert.match(ctx.enhancedMessages[0].content, /Prior Experience/);
  assert.equal(ctx.enhancedMessages[1].content, 'U');
  assert.match(ctx.contextSummary, /Loaded 2 relevant prior patterns \(avg confidence: 80%\)/);
});

test('recordTokenUsage ignores an unknown id and persists a known one with its mapped type', () => {
  const { p, saved } = build([token('TT-1'), token('TT-2', { content: { text: 'approach', type: 'approach', artifacts: [] } })]);
  assert.doesNotThrow(() => p.recordTokenUsage('w', 'missing', true));
  assert.equal(saved.length, 0);

  p.recordTokenUsage('w', 'TT-1', true, { note: 'x' });
  p.recordTokenUsage('w', 'TT-2', true);
  assert.equal(saved.length, 2);
  assert.equal(saved[0].id, 'TT-1');
  assert.equal(saved[0].type, 'tool_sequence');
  assert.equal(saved[0].successCount, 1);
  assert.equal(saved[0].metadata.contentType, 'tool_sequence');
  assert.equal(saved[1].type, 'goal_approach', 'approach maps onto goal_approach');
  assert.equal((saved[0].metadata as { note?: string }).note, undefined, 'store metadata comes from the token, not the caller context');
});

test('getPropagationStats is empty-safe and aggregates tokens once present', () => {
  const empty = build();
  assert.deepEqual(empty.p.getPropagationStats(), { totalTokensAvailable: 0, activeTokens: 0, averageConfidence: 0, totalWorkerInteractions: 0, tokenTypeDistribution: {} });

  const t1 = token('TT-1');
  const t2 = token('TT-2', { content: { text: 'x', type: 'optimization', artifacts: [] }, evaluate: () => 0.5 });
  t1.metadata.reuseCount = 2;
  const { p } = build([t1, t2]);
  const stats = p.getPropagationStats();
  assert.equal(stats.totalTokensAvailable, 2);
  assert.equal(stats.activeTokens, 2);
  assert.equal(stats.averageConfidence, 0.65);
  assert.equal(stats.totalWorkerInteractions, 2);
  assert.deepEqual(stats.tokenTypeDistribution, { tool_sequence: 1, optimization: 1 });
});

test('broadcastToken scopes to all or to tokens with an origin goal', () => {
  const { p } = build([token('TT-1'), token('TT-2', { metadata: { reuseCount: 0, captureTime: 1, successCount: 0, failureCount: 0, originGoal: '' } })]);
  assert.deepEqual(Object.keys(p.broadcastToken(token('TT-1') as unknown as ThinkToken, 'all')), ['targetWorkers', 'broadcastId']);
  assert.equal(p.broadcastToken(token('TT-1') as unknown as ThinkToken, 'all').targetWorkers, -1);
  assert.equal(p.broadcastToken(token('TT-1') as unknown as ThinkToken).targetWorkers, 1);
});

test('createPropagationVariant marks a custom or default filter and createPropagator builds an instance', () => {
  const { p } = build();
  const custom = p.createPropagationVariant(true, () => true);
  assert.equal(custom.enabled, true);
  assert.equal(custom.config.tokenFilter, 'custom');
  assert.equal(custom.config.propagationEnabled, true);
  const def = p.createPropagationVariant(false);
  assert.equal(def.config.tokenFilter, 'default');
  assert.equal(def.config.propagationEnabled, false);
  assert.ok(createPropagator({} as LearningStore, new FakeCollection() as unknown as ThinkTokenCollection) instanceof ThinkTokenPropagator);
});
