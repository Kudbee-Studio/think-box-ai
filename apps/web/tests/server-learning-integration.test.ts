// Regression test for the #300 typecheck fix: `LearningStore.recordSessionCompletion` was
// called but never implemented (TS2339). Fixed by routing `recordGoalExecution` through the
// store's real, already-implemented `storeSessionLearning` instead. Nothing in the codebase
// calls `ServerLearningIntegration`/`recordGoalExecution` today (grepped for it — dead code),
// so this is the only test coverage this path has ever had.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { LearningStore } from '../learning-store.ts';
import { ThinkTokenPropagator } from '../think-token-propagation.ts';
import { ThinkTokenCollection } from '../think-token.ts';
import { WorkerInitializer } from '../worker-initialization.ts';
import { LearningManager } from '../learning-integration.ts';
import { ServerLearningIntegration } from '../server-learning-integration.ts';

function makeIntegration(store: LearningStore): ServerLearningIntegration {
  const propagator = new ThinkTokenPropagator(store, new ThinkTokenCollection());
  const initializer = new WorkerInitializer(propagator, new LearningManager());
  return new ServerLearningIntegration(propagator, initializer, store);
}

test('recordGoalExecution stores session learning via the real store method (valid input)', () => {
  const dbPath = path.join(os.tmpdir(), `learning-test-${Date.now()}-${Math.random().toString(36).slice(2)}.db`);
  const store = new LearningStore(dbPath);
  try {
    const integration = makeIntegration(store);

    const result = integration.recordGoalExecution('sess-1', 'write a haiku about the sea', true, { thoughts: [] });

    assert.equal(result.learningRecorded, true);
    assert.equal(result.tokensAffected, 0); // no thoughts -> no Think Token candidates

    const stored = store.queryLearningByGoal('write a haiku about the sea');
    assert.equal(stored.length, 1, 'storeSessionLearning should have written one row');
    assert.equal(stored[0].sessionId, 'sess-1');
    assert.equal(stored[0].outcome, 'success');
    assert.deepEqual(stored[0].thoughts, []);
  } finally {
    store.close();
    fs.rmSync(dbPath, { force: true });
    fs.rmSync(`${dbPath}-wal`, { force: true });
    fs.rmSync(`${dbPath}-shm`, { force: true });
  }
});

test('recordGoalExecution records a failed outcome (success=false)', () => {
  const dbPath = path.join(os.tmpdir(), `learning-test-${Date.now()}-${Math.random().toString(36).slice(2)}.db`);
  const store = new LearningStore(dbPath);
  try {
    const integration = makeIntegration(store);
    integration.recordGoalExecution('sess-2', 'a goal that failed', false, { thoughts: [] });

    const stored = store.queryLearningByGoal('a goal that failed');
    assert.equal(stored.length, 1);
    assert.equal(stored[0].outcome, 'failure');
  } finally {
    store.close();
    fs.rmSync(dbPath, { force: true });
    fs.rmSync(`${dbPath}-wal`, { force: true });
    fs.rmSync(`${dbPath}-shm`, { force: true });
  }
});

test('recordGoalExecution propagates the store error instead of swallowing it (error path)', () => {
  const dbPath = path.join(os.tmpdir(), `learning-test-${Date.now()}-${Math.random().toString(36).slice(2)}.db`);
  const store = new LearningStore(dbPath);
  const integration = makeIntegration(store);
  store.close(); // force the underlying better-sqlite3 call to fail

  assert.throws(() => integration.recordGoalExecution('sess-3', 'goal after close', true, { thoughts: [] }));

  fs.rmSync(dbPath, { force: true });
  fs.rmSync(`${dbPath}-wal`, { force: true });
  fs.rmSync(`${dbPath}-shm`, { force: true });
});
