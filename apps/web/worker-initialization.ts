// kudbEE Worker Initialization — Activate Think Token propagation on worker startup

import { ThinkTokenPropagator } from './think-token-propagation.ts';
import { LearningManager } from './learning-integration.ts';
import type { AgentSessionConfig, ChatMessage } from './types.ts';

/**
 * Worker Initialization: Set up new worker with Think Token context
 * This bridges the gap between stored learning and active execution
 */
export class WorkerInitializer {
  private propagator: ThinkTokenPropagator;
  private learningManager: LearningManager;

  constructor(propagator: ThinkTokenPropagator, learningManager: LearningManager) {
    this.propagator = propagator;
    this.learningManager = learningManager;
  }

  /**
   * Initialize worker with prior learning context
   */
  initializeWorker(
    workerId: string,
    goal: string,
    config: AgentSessionConfig,
    baseSystemPrompt: string
  ): {
    enhancedSystemPrompt: string;
    context: {
      workerId: string;
      goal: string;
      priorPatternCount: number;
      priorSuccessfulApproaches: number;
      injectionDetails: Record<string, unknown>;
    };
    propagationStats: Record<string, unknown>;
  } {
    // Step 1: Get relevant prior patterns from learning store
    const priorExperiences = this.learningManager.getPriorExperiences(goal);

    // Step 2: Inject Think Tokens into system prompt
    const enhancedSystemPrompt = this.propagator.injectTokensIntoSystemPrompt(
      baseSystemPrompt,
      goal,
      5 // Top 5 tokens
    );

    // Step 3: Gather initialization context
    const context = {
      workerId,
      goal,
      priorPatternCount: priorExperiences.topPatterns.length,
      priorSuccessfulApproaches: priorExperiences.successfulApproaches.length,
      injectionDetails: {
        highConfidencePatterns: priorExperiences.topPatterns
          .filter(p => p.confidence > 0.7)
          .length,
        successRate: this.calculateSuccessRate(priorExperiences.successfulApproaches),
        learningSource: 'persistent_think_token_store'
      }
    };

    return {
      enhancedSystemPrompt,
      context,
      propagationStats: this.propagator.getPropagationStats()
    };
  }

  /**
   * Create initialization report for observability
   */
  createInitializationReport(
    workerId: string,
    goal: string,
    config: AgentSessionConfig
  ): {
    timestamp: number;
    workerId: string;
    goal: string;
    learningInjected: boolean;
    tokenCount: number;
    propagationActive: boolean;
  } {
    const tokens = this.propagator.getRelevantTokensForGoal(goal, 100);

    return {
      timestamp: Date.now(),
      workerId,
      goal,
      learningInjected: tokens.length > 0,
      tokenCount: tokens.length,
      propagationActive: true
    };
  }

  /**
   * Calculate success rate from prior experiences
   */
  private calculateSuccessRate(successfulApproaches: any[]): number {
    if (successfulApproaches.length === 0) return 0;
    return (successfulApproaches.length / Math.max(1, successfulApproaches.length)) * 100;
  }

  /**
   * Enable/disable Think Token propagation for A/B testing
   */
  createTestVariant(
    testId: string,
    control: boolean = false
  ): {
    testId: string;
    variantId: string;
    propagationEnabled: boolean;
  } {
    return {
      testId,
      variantId: `${testId}-${control ? 'control' : 'treatment'}`,
      propagationEnabled: !control
    };
  }
}

/**
 * Integration pattern for server.ts AgentSession.constructor()
 *
 * Usage:
 *
 *   constructor(id: string, config: SessionConfigInput = {}) {
 *     this.id = id;
 *     this.config = { ... };
 *
 *     // NEW: Initialize with Think Token context
 *     const initializer = new WorkerInitializer(propagator, learningManager);
 *     const initResult = initializer.initializeWorker(
 *       id,
 *       currentGoal,
 *       this.config,
 *       baseSystemPrompt
 *     );
 *
 *     this.systemPrompt = initResult.enhancedSystemPrompt;
 *     this.context = initResult.context;
 *   }
 */
export function createWorkerInitializer(
  propagator: ThinkTokenPropagator,
  learningManager: LearningManager
): WorkerInitializer {
  return new WorkerInitializer(propagator, learningManager);
}

/**
 * Behavioral change detection after worker uses Think Tokens
 */
export class BehavioralChangeDetector {
  /**
   * Compare worker behavior before/after Think Token injection
   */
  detectBehaviorChange(
    beforeContext: Record<string, unknown>,
    afterContext: Record<string, unknown>
  ): {
    changed: boolean;
    changeFactors: string[];
    impact: 'high' | 'medium' | 'low' | 'none';
  } {
    const changes: string[] = [];

    // Check if tool sequence changed
    if (
      beforeContext.toolSequence !== afterContext.toolSequence &&
      afterContext.toolSequence
    ) {
      changes.push('tool_sequence');
    }

    // Check if reasoning patterns changed
    if (
      beforeContext.reasoningSteps !== afterContext.reasoningSteps &&
      (afterContext.reasoningSteps as number) < (beforeContext.reasoningSteps as number)
    ) {
      changes.push('reasoning_efficiency');
    }

    // Check if error recovery improved
    if (
      beforeContext.errorRecoveryTime &&
      afterContext.errorRecoveryTime &&
      (afterContext.errorRecoveryTime as number) < (beforeContext.errorRecoveryTime as number)
    ) {
      changes.push('error_recovery');
    }

    const impactLevel = changes.length >= 2 ? 'high' : changes.length === 1 ? 'medium' : 'none';

    return {
      changed: changes.length > 0,
      changeFactors: changes,
      impact: impactLevel as 'high' | 'medium' | 'low' | 'none'
    };
  }
}
