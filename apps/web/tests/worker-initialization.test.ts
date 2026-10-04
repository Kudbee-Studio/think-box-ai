// Unit tests for worker-initialization.ts: prompt injection context, initialization report, A/B variants and behaviour-change detection.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { WorkerInitializer, BehavioralChangeDetector, createWorkerInitializer } from '../worker-initialization.ts';
import type { ThinkTokenPropagator } from '../think-token-propagation.ts';
import type { LearningManager } from '../learning-integration.ts';
import type { AgentSessionConfig } from '../types.ts';

interface Prior { topPatterns: Array<{ confidence: number }>; successfulApproaches: Array<{ goal: string }> }

function make(
  prior: Prior,
  over: { injected?: string; stats?: Record<string, unknown>; tokens?: unknown[] } = {},
): WorkerInitializer {
  const propagator = {
    injectTokensIntoSystemPrompt: () => over.injected ?? 'BASE + tokens',
    getPropagationStats: () => over.stats ?? { injected: 1 },
    getRelevantTokensForGoal: () => over.tokens ?? [],
  };
  const learning = { getPriorExperiences: () => prior };
  return new WorkerInitializer(propagator as unknown as ThinkTokenPropagator, learning as unknown as LearningManager);
}

const config = {} as AgentSessionConfig;

test('initializeWorker injects tokens and reports prior-experience context', () => {
  const w = make(
    { topPatterns: [{ confidence: 0.9 }, { confidence: 0.5 }], successfulApproaches: [{ goal: 'a' }, { goal: 'b' }] },
    { injected: 'BASE + 3 tokens' },
  );
  const result = w.initializeWorker('w1', 'build a thing', config, 'BASE');
  assert.equal(result.enhancedSystemPrompt, 'BASE + 3 tokens');
  assert.equal(result.context.workerId, 'w1');
  assert.equal(result.context.goal, 'build a thing');
  assert.equal(result.context.priorPatternCount, 2);
  assert.equal(result.context.priorSuccessfulApproaches, 2);
  assert.equal(result.context.injectionDetails.highConfidencePatterns, 1);
  assert.equal(result.context.injectionDetails.successRate, 100);
  assert.equal(result.context.injectionDetails.learningSource, 'persistent_think_token_store');
  assert.ok(result.propagationStats);
});

test('initializeWorker reports a zero success rate with no prior approaches', () => {
  const w = make({ topPatterns: [], successfulApproaches: [] });
  const result = w.initializeWorker('w2', 'goal', config, 'BASE');
  assert.equal(result.context.priorPatternCount, 0);
  assert.equal(result.context.injectionDetails.highConfidencePatterns, 0);
  assert.equal(result.context.injectionDetails.successRate, 0);
});

test('createInitializationReport reflects whether any token matched the goal', () => {
  const withTokens = make({ topPatterns: [], successfulApproaches: [] }, { tokens: [{ id: 'TT-1' }, { id: 'TT-2' }] });
  const report = withTokens.createInitializationReport('w3', 'goal', config);
  assert.equal(report.learningInjected, true);
  assert.equal(report.tokenCount, 2);
  assert.equal(report.propagationActive, true);
  assert.equal(report.workerId, 'w3');
  assert.equal(typeof report.timestamp, 'number');

  const none = make({ topPatterns: [], successfulApproaches: [] });
  assert.equal(none.createInitializationReport('w4', 'goal', config).learningInjected, false);
  assert.equal(none.createInitializationReport('w4', 'goal', config).tokenCount, 0);
});

test('createTestVariant builds treatment and control ids', () => {
  const w = make({ topPatterns: [], successfulApproaches: [] });
  assert.deepEqual(w.createTestVariant('exp1'), { testId: 'exp1', variantId: 'exp1-treatment', propagationEnabled: true });
  assert.deepEqual(w.createTestVariant('exp1', true), { testId: 'exp1', variantId: 'exp1-control', propagationEnabled: false });
});

test('createWorkerInitializer returns a WorkerInitializer', () => {
  const w = make({ topPatterns: [], successfulApproaches: [] });
  assert.ok(createWorkerInitializer(
    { injectTokensIntoSystemPrompt: () => '', getPropagationStats: () => ({}), getRelevantTokensForGoal: () => [] } as unknown as ThinkTokenPropagator,
    { getPriorExperiences: () => ({ topPatterns: [], successfulApproaches: [] }) } as unknown as LearningManager,
  ) instanceof WorkerInitializer);
  assert.ok(w instanceof WorkerInitializer);
});

test('detectBehaviorChange reports none when nothing changed', () => {
  const d = new BehavioralChangeDetector();
  const r = d.detectBehaviorChange({ toolSequence: 'a', reasoningSteps: 3 }, { toolSequence: 'a', reasoningSteps: 3 });
  assert.equal(r.changed, false);
  assert.deepEqual(r.changeFactors, []);
  assert.equal(r.impact, 'none');
});

test('detectBehaviorChange reports medium for a single factor and high for two', () => {
  const d = new BehavioralChangeDetector();
  const single = d.detectBehaviorChange({ toolSequence: 'a', reasoningSteps: 4 }, { toolSequence: 'b', reasoningSteps: 4 });
  assert.deepEqual(single.changeFactors, ['tool_sequence']);
  assert.equal(single.impact, 'medium');

  const two = d.detectBehaviorChange(
    { toolSequence: 'a', reasoningSteps: 4, errorRecoveryTime: 100 },
    { toolSequence: 'b', reasoningSteps: 2, errorRecoveryTime: 50 },
  );
  assert.equal(two.changed, true);
  assert.deepEqual(two.changeFactors, ['tool_sequence', 'reasoning_efficiency', 'error_recovery']);
  assert.equal(two.impact, 'high');
});

test('detectBehaviorChange only flags reasoning/error changes when they decrease', () => {
  const d = new BehavioralChangeDetector();
  const r = d.detectBehaviorChange({ reasoningSteps: 2, errorRecoveryTime: 50 }, { reasoningSteps: 5, errorRecoveryTime: 100 });
  assert.equal(r.changed, false);
  assert.equal(r.impact, 'none');
});
