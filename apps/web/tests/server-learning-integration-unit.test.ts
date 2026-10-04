// Unit tests for server-learning-integration.ts: context enhancement, goal-execution recording (success mints tokens, failure does not),
// behaviour detection and stats — using a real LearningStore on a temporary database and a real token collection.
import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { LearningStore } from '../learning-store.ts';
import { ThinkTokenCollection } from '../think-token.ts';
import { ThinkTokenPropagator } from '../think-token-propagation.ts';
import { ServerLearningIntegration, createServerLearningIntegration } from '../server-learning-integration.ts';
import type { Thought } from '../types.ts';

const files: string[] = [];
function build(): ServerLearningIntegration {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-sli-'));
  const db = path.join(dir, 'learning.db');
  files.push(dir);
  const store = new LearningStore(db);
  return new ServerLearningIntegration(new ThinkTokenPropagator(store, new ThinkTokenCollection()), undefined, store);
}
after(() => { for (const d of files) fs.rmSync(d, { recursive: true, force: true }); });

const toolCalls: Thought[] = [
  { id: 'a', timestamp: 1, type: 'tool_call', plugin: 'read_file' },
  { id: 'b', timestamp: 2, type: 'tool_call', plugin: 'write_file' },
] as Thought[];

test('enhanceSessionContext reports no injection when there are no prior tokens', () => {
  const integration = build();
  const out = integration.enhanceSessionContext('s', 'a unique goal', 'BASE', [{ role: 'system', content: 'SYS' }]);
  assert.equal(out.contextInjection.injectedTokenCount, 0);
  assert.equal(out.contextInjection.propagationActive, false);
  assert.deepEqual(out.tokens, []);
  assert.equal(out.enhancedSystemPrompt, 'BASE');
});

test('a failed goal is recorded but mints no tokens', () => {
  const integration = build();
  const result = integration.recordGoalExecution('s', 'failing goal', false, { thoughts: toolCalls, duration: 5 });
  assert.equal(result.learningRecorded, true);
  assert.equal(result.tokensAffected, 0);
  assert.match(result.behavioralImpact, /Tokens: 0/);
});

test('a successful goal mints tokens that later enhance a matching session', () => {
  const integration = build();
  const result = integration.recordGoalExecution('s', 'build a report', true, { thoughts: toolCalls, duration: 5 });
  assert.equal(result.learningRecorded, true);
  assert.ok(result.tokensAffected >= 1, 'the tool-sequence candidate was minted');
  assert.equal(integration.getPropagationStats().totalTokensAvailable >= 1, true);

  const enhanced = integration.enhanceSessionContext('s2', 'build a report', 'BASE', [{ role: 'system', content: 'SYS' }, { role: 'user', content: 'U' }]);
  assert.equal(enhanced.contextInjection.propagationActive, true);
  assert.ok(enhanced.tokens.length >= 1);
  assert.match(enhanced.enhancedSystemPrompt, /Prior Experience/);
});

test('detectBehaviorChange and createServerLearningIntegration delegate', () => {
  const integration = build();
  assert.equal(integration.detectBehaviorChange({ reasoningSteps: 3 }, { reasoningSteps: 3 }).changed, false);
  assert.equal(integration.detectBehaviorChange({ toolSequence: 'a' }, { toolSequence: 'b' }).changed, true);
  const made = createServerLearningIntegration(new ThinkTokenPropagator(new LearningStore(path.join(files[0], 'x.db')), new ThinkTokenCollection()), undefined as never, new LearningStore(path.join(files[0], 'y.db')));
  assert.ok(made instanceof ServerLearningIntegration);
});
