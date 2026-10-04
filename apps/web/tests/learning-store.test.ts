// Unit tests for learning-store.ts against a real (temporary) SQLite database: pattern insert/update, session rows, queries and statistics.
import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { LearningStore, type LearnedPattern } from '../learning-store.ts';

const files: string[] = [];
function store(): LearningStore { const f = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-ls-')), 'learning.db'); files.push(f); return new LearningStore(f); }
after(() => { for (const f of files) fs.rmSync(path.dirname(f), { recursive: true, force: true }); });

const pattern = (id: string, over: Partial<LearnedPattern> = {}): LearnedPattern => ({
  id, type: 'tool_sequence', pattern: `pattern ${id}`, confidence: 0.5, sourceThoughts: [], firstSeen: 1, lastSeen: 1, successCount: 0, failureCount: 0, metadata: { k: 'v' }, ...over,
});

test('storePattern inserts, then updates the same id in place', () => {
  const s = store();
  s.storePattern(pattern('p1', { confidence: 0.4, successCount: 1 }));
  s.storePattern(pattern('p1', { confidence: 0.95, successCount: 5, metadata: { k: 'v2' } }));
  const all = s.getTopPatterns();
  assert.equal(all.length, 1);
  assert.equal(all[0].confidence, 0.95);
  assert.equal(all[0].successCount, 5);
  assert.deepEqual(all[0].metadata, { k: 'v2' });
  s.close();
});

test('getPatternsByType filters and orders by confidence', () => {
  const s = store();
  s.storePattern(pattern('a', { type: 'tool_sequence', confidence: 0.2 }));
  s.storePattern(pattern('b', { type: 'tool_sequence', confidence: 0.8 }));
  s.storePattern(pattern('c', { type: 'optimization', confidence: 0.9 }));
  const tools = s.getPatternsByType('tool_sequence');
  assert.deepEqual(tools.map((p) => p.id), ['b', 'a']);
  assert.equal(s.getPatternsByType('optimization').length, 1);
  s.close();
});

test('storeSessionLearning, queryLearningByGoal and getSuccessfulApproaches round-trip', () => {
  const s = store();
  const base = { sessionId: 's1', duration: 100, thoughts: [{ type: 'reasoning', content: 'x', timestamp: 1, status: 'ok' }], patterns: ['p1'], metadata: { n: 1 } };
  s.storeSessionLearning({ ...base, goal: 'build a bridge', outcome: 'success' });
  s.storeSessionLearning({ ...base, sessionId: 's2', goal: 'build a bridge too', outcome: 'failure' });
  s.storeSessionLearning({ ...base, sessionId: 's3', goal: 'unrelated goal', outcome: 'success' });

  const matches = s.queryLearningByGoal('build a bridge');
  assert.equal(matches.length, 2);
  assert.equal(matches[0].goal.startsWith('build a bridge'), true);
  assert.deepEqual(matches[0].patterns, ['p1']);
  assert.deepEqual(matches[0].metadata, { n: 1 });

  const successful = s.getSuccessfulApproaches('build a bridge');
  assert.equal(successful.length, 1);
  assert.equal(successful[0].sessionId, 's1');
  s.close();
});

test('storeThoughtArtifact persists a thought row without error', () => {
  const s = store();
  assert.doesNotThrow(() => s.storeThoughtArtifact('s1', 'reasoning', 'content', 'ok', ['p1']));
  assert.doesNotThrow(() => s.storeThoughtArtifact('s2', 'plugin_call', 'content', 'error'));
  s.close();
});

test('updatePatternSuccess moves confidence up on success and down on failure', () => {
  const s = store();
  s.storePattern(pattern('p1', { confidence: 0.5 }));
  s.updatePatternSuccess('p1', true);
  assert.equal(s.getTopPatterns()[0].successCount, 1);
  s.updatePatternSuccess('p1', false);
  const after = s.getTopPatterns()[0];
  assert.equal(after.successCount, 1);
  assert.equal(after.failureCount, 1);
  assert.equal(after.confidence, 0.5);
  s.close();
});

test('getStatistics counts patterns and sessions, with a null top pattern when empty', () => {
  const s = store();
  const empty = s.getStatistics();
  assert.equal(empty.totalPatterns, 0);
  assert.equal(empty.totalSessions, 0);
  assert.equal(empty.avgSuccessRate, 0);
  assert.equal(empty.topPattern, null);

  s.storePattern(pattern('p1', { confidence: 0.9, successCount: 3, failureCount: 1 }));
  s.storeSessionLearning({ sessionId: 's', goal: 'g', outcome: 'success', duration: 1, thoughts: [], patterns: [], metadata: {} });
  const stats = s.getStatistics();
  assert.equal(stats.totalPatterns, 1);
  assert.equal(stats.totalSessions, 1);
  assert.equal(stats.avgSuccessRate, 0.75);
  assert.equal(stats.topPattern?.id, 'p1');
  s.close();
});
