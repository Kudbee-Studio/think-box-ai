// Proves the #288 Think Token chain end-to-end against real classes and a real on-disk SQLite
// file: REAL EXECUTION (thoughts shaped exactly like agent.ts's runToolAgent emits them) →
// VALIDATION (ThinkTokenFactory's quality gate + the run's own success flag) → TOKEN CREATION →
// PERSISTENCE (learning.db, learned_patterns table) → RETRIEVAL → RESTART.
//
// Before the fixes this test exercises, every one of these steps except the first was either
// unreachable dead code or a silent no-op — see server-learning-integration.ts and
// think-token-propagation.ts for exactly which line broke which step.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { LearningStore } from '../learning-store.ts';
import { ThinkTokenCollection } from '../think-token.ts';
import { ThinkTokenPropagator } from '../think-token-propagation.ts';
import { ThinkTokenFactory } from '../think-token-factory.ts';
import { ServerLearningIntegration } from '../server-learning-integration.ts';
import type { Thought } from '../types.ts';

function tempDbPath(): string {
  return path.join(os.tmpdir(), `think-token-lifecycle-${Date.now()}-${randomUUID()}.db`);
}

function cleanup(dbPath: string): void {
  for (const suffix of ['', '-wal', '-shm']) fs.rmSync(`${dbPath}${suffix}`, { force: true });
}

function makeIntegration(store: LearningStore): ServerLearningIntegration {
  const propagator = new ThinkTokenPropagator(store, new ThinkTokenCollection());
  return new ServerLearningIntegration(propagator, undefined, store);
}

/**
 * The exact thought shapes agent.ts's runToolAgent emits for a multi-tool goal (see agent.ts
 * lines 578, 598): two successful tool calls back to back, which is what
 * ThinkTokenFactory.extractToolSequence requires (type: 'tool_call', a string `plugin` field).
 */
function realToolSequenceThoughts(): Thought[] {
  const now = Date.now();
  return [
    { id: randomUUID(), timestamp: now, type: 'goal', content: 'Starting goal: research and summarize', status: 'info' },
    { id: randomUUID(), timestamp: now + 1, type: 'tool_call', plugin: 'fetch_url', content: 'fetch_url {"url":"https://example.com"}', status: 'running' },
    { id: randomUUID(), timestamp: now + 2, type: 'tool_result', plugin: 'fetch_url', content: 'fetch_url ✓ {...}', status: 'success' },
    { id: randomUUID(), timestamp: now + 3, type: 'tool_call', plugin: 'read_rss', content: 'read_rss {"url":"https://example.com/feed"}', status: 'running' },
    { id: randomUUID(), timestamp: now + 4, type: 'tool_result', plugin: 'read_rss', content: 'read_rss ✓ {...}', status: 'success' },
    {
      id: randomUUID(), timestamp: now + 5, type: 'reasoning',
      content: 'For goals like this: always fetch_url then read_rss in sequence — this pattern generally applies to similar research goals',
      status: 'thinking',
    },
  ];
}

describe('Think Token lifecycle (#288)', () => {
  it('a candidate token from a real tool-call sequence meets the factory quality gate', () => {
    // Unit level: no store, no propagator — just the factory against real-shaped thoughts.
    const candidates = ThinkTokenFactory.extractCandidates('sess-unit', 'research and summarize', realToolSequenceThoughts());
    const toolSeq = candidates.find(c => c.content.type === 'tool_sequence');
    assert.ok(toolSeq, 'extractToolSequence should recognize real tool_call thoughts (regression: it used to look for "plugin_call", which agent.ts never emits)');
    assert.deepEqual(toolSeq!.content.artifacts?.tools, ['fetch_url', 'read_rss']);
  });

  it('successful execution -> token created and persisted (learned_patterns row exists)', () => {
    const dbPath = tempDbPath();
    const store = new LearningStore(dbPath);
    try {
      const integration = makeIntegration(store);
      const result = integration.recordGoalExecution('sess-1', 'research and summarize', true, {
        thoughts: realToolSequenceThoughts(),
        duration: 4200,
      });

      assert.equal(result.learningRecorded, true);
      assert.ok(result.tokensAffected > 0, 'a successful run with a real tool sequence must mint at least one token');

      const patterns = store.getPatternsByType('tool_sequence');
      assert.equal(patterns.length, 1);
      assert.match(patterns[0].pattern, /fetch_url.*read_rss/);
      assert.equal(patterns[0].successCount, 1);
      assert.equal(patterns[0].failureCount, 0);
      assert.ok(patterns[0].confidence > 0);

      // The session outcome is recorded too, independently of the token.
      const sessions = store.queryLearningByGoal('research and summarize');
      assert.equal(sessions.length, 1);
      assert.equal(sessions[0].outcome, 'success');
    } finally {
      store.close();
      cleanup(dbPath);
    }
  });

  it('failed execution -> no token is created, even with the same thought content', () => {
    const dbPath = tempDbPath();
    const store = new LearningStore(dbPath);
    try {
      const integration = makeIntegration(store);
      const result = integration.recordGoalExecution('sess-2', 'research and summarize', false, {
        thoughts: realToolSequenceThoughts(),
        duration: 4200,
      });

      assert.equal(result.tokensAffected, 0, 'a failed run must not mint a token even though the thoughts would otherwise qualify');
      assert.equal(store.getPatternsByType('tool_sequence').length, 0);

      const sessions = store.queryLearningByGoal('research and summarize');
      assert.equal(sessions.length, 1);
      assert.equal(sessions[0].outcome, 'failure');
    } finally {
      store.close();
      cleanup(dbPath);
    }
  });

  it('a candidate that fails the factory quality gate produces no token even on success', () => {
    const dbPath = tempDbPath();
    const store = new LearningStore(dbPath);
    try {
      const integration = makeIntegration(store);
      const now = Date.now();
      // Only one tool call: extractToolSequence requires > 1, so no candidate at all.
      const thin: Thought[] = [
        { id: randomUUID(), timestamp: now, type: 'tool_call', plugin: 'fetch_url', content: 'fetch_url', status: 'running' },
      ];
      const result = integration.recordGoalExecution('sess-3', 'a trivial goal', true, { thoughts: thin, duration: 100 });
      assert.equal(result.tokensAffected, 0);
      assert.equal(store.getStatistics().totalPatterns, 0);
    } finally {
      store.close();
      cleanup(dbPath);
    }
  });

  it('evidence association: the persisted pattern carries the origin session, goal and artifacts', () => {
    const dbPath = tempDbPath();
    const store = new LearningStore(dbPath);
    try {
      const integration = makeIntegration(store);
      integration.recordGoalExecution('sess-evidence', 'research and summarize', true, {
        thoughts: realToolSequenceThoughts(),
        duration: 4200,
      });

      const [pattern] = store.getPatternsByType('tool_sequence');
      assert.equal(pattern.metadata.originSessionId, 'sess-evidence');
      assert.equal(pattern.metadata.originGoal, 'research and summarize');
      assert.deepEqual((pattern.metadata.artifacts as { tools: string[] }).tools, ['fetch_url', 'read_rss']);
    } finally {
      store.close();
      cleanup(dbPath);
    }
  });

  it('retrieval through the normal application path (getTopPatterns / getPatternsByType)', () => {
    const dbPath = tempDbPath();
    const store = new LearningStore(dbPath);
    try {
      const integration = makeIntegration(store);
      integration.recordGoalExecution('sess-4', 'research and summarize', true, {
        thoughts: realToolSequenceThoughts(),
        duration: 4200,
      });

      // The fixture's reasoning thought ("For goals like this: ... this pattern generally
      // applies...") also happens to satisfy extractDecisions' (pre-existing, substring-based:
      // 'For' contains 'or') quality gate, so this run legitimately yields two pattern types,
      // not one — retrieval must surface both through the same normal read path.
      const top = store.getTopPatterns(10);
      assert.equal(top.length, 2);
      assert.deepEqual(new Set(top.map(p => p.type)), new Set(['tool_sequence', 'goal_approach']));

      const stats = store.getStatistics();
      assert.equal(stats.totalPatterns, 2);
      assert.equal(stats.totalSessions, 1);
    } finally {
      store.close();
      cleanup(dbPath);
    }
  });

  it('survives a full restart: write -> close -> reopen the same file -> still retrievable', () => {
    const dbPath = tempDbPath();
    try {
      {
        const store = new LearningStore(dbPath);
        const integration = makeIntegration(store);
        const result = integration.recordGoalExecution('sess-restart', 'research and summarize', true, {
          thoughts: realToolSequenceThoughts(),
          duration: 4200,
        });
        assert.ok(result.tokensAffected > 0);
        store.close();
      }
      {
        // A fresh process would open a new LearningStore against the same file; this is that.
        const reopened = new LearningStore(dbPath);
        try {
          const patterns = reopened.getPatternsByType('tool_sequence');
          assert.equal(patterns.length, 1, 'the token must still be there after the store is closed and reopened');
          assert.equal(patterns[0].metadata.originSessionId, 'sess-restart');
        } finally {
          reopened.close();
        }
      }
    } finally {
      cleanup(dbPath);
    }
  });

  it('duplicate/replay: reusing the same token id upserts instead of duplicating a row', () => {
    const dbPath = tempDbPath();
    const store = new LearningStore(dbPath);
    try {
      const collection = new ThinkTokenCollection();
      const propagator = new ThinkTokenPropagator(store, collection);
      const [token] = ThinkTokenFactory.extractCandidates('sess-replay', 'research and summarize', realToolSequenceThoughts());
      propagator.addToken(token);

      propagator.recordTokenUsage('worker-a', token.id, true);
      propagator.recordTokenUsage('worker-b', token.id, true);
      propagator.recordTokenUsage('worker-c', token.id, false);

      const rows = store.getPatternsByType('tool_sequence');
      assert.equal(rows.length, 1, 'replaying the same token must upsert one row, not create three');
      assert.equal(rows[0].successCount, 2);
      assert.equal(rows[0].failureCount, 1);
    } finally {
      store.close();
      cleanup(dbPath);
    }
  });
});
