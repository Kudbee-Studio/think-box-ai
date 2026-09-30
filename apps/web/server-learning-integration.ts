// kudbEE Server-side Learning Integration
// Wires Think Token propagation into AgentSession lifecycle

import { ThinkTokenPropagator } from './think-token-propagation.ts';
import { WorkerInitializer, BehavioralChangeDetector } from './worker-initialization.ts';
import { LearningStore, type SessionLearning } from './learning-store.ts';
import { ThinkTokenFactory } from './think-token-factory.ts';
import type { AgentSession } from './server.ts';
import type { ChatMessage } from './types.ts';

/**
 * ServerLearningIntegration hooks Think Token propagation into the agent runtime.
 * This is the energy core that makes experience compound across workers.
 */
export class ServerLearningIntegration {
  private propagator: ThinkTokenPropagator;
  private initializer: WorkerInitializer | undefined;
  private behaviorDetector: BehavioralChangeDetector;
  private store: LearningStore;

  constructor(propagator: ThinkTokenPropagator, initializer: WorkerInitializer | undefined, store: LearningStore) {
    this.propagator = propagator;
    this.initializer = initializer;
    this.behaviorDetector = new BehavioralChangeDetector();
    this.store = store;
  }

  /**
   * Hook into AgentSession.constructor() — inject prior learning context
   */
  enhanceSessionContext(
    sessionId: string,
    goal: string,
    baseSystemPrompt: string,
    messages: ChatMessage[]
  ): {
    enhancedSystemPrompt: string;
    contextInjection: Record<string, unknown>;
    tokens: Array<Record<string, unknown>>;
  } {
    // Step 1: Get relevant prior patterns
    const { enhancedMessages, injectedTokens, contextSummary } = this.propagator.createWorkerContext(
      sessionId,
      goal,
      messages
    );

    // Step 2: Inject tokens into system prompt
    const enhancedSystemPrompt = this.propagator.injectTokensIntoSystemPrompt(
      baseSystemPrompt,
      goal,
      5
    );

    return {
      enhancedSystemPrompt,
      contextInjection: {
        goal,
        injectedTokenCount: injectedTokens.length,
        contextSummary,
        propagationActive: injectedTokens.length > 0
      },
      tokens: injectedTokens.map(t => t.toJSON())
    };
  }

  /**
   * Hook into AgentSession.runGoal() — record execution and propagate learning
   */
  recordGoalExecution(
    sessionId: string,
    goal: string,
    success: boolean,
    executionContext: Record<string, unknown>
  ): {
    learningRecorded: boolean;
    tokensAffected: number;
    behavioralImpact: string;
  } {
    // Step 1: Record goal completion for learning store.
    // `LearningStore` has no `recordSessionCompletion` method — it was never implemented; the
    // store's real method for this is `storeSessionLearning`.
    this.store.storeSessionLearning({
      sessionId,
      goal,
      thoughts: (executionContext.thoughts as SessionLearning['thoughts']) || [],
      outcome: success ? 'success' : 'failure',
      duration: (executionContext.duration as number) ?? 0,
      patterns: [],
      metadata: executionContext,
    });

    let tokensAffected = 0;

    // Step 2: Only a successful execution can mint a Think Token. A failed goal still gets its
    // session recorded above (for later analysis) but produces no token — the factory's own
    // quality gate (specific/actionable/generalizable) is a second, independent filter on top of
    // this, not a replacement for it.
    if (success) {
      const thoughts = executionContext.thoughts || [];
      const candidates = ThinkTokenFactory.extractCandidates(sessionId, goal, thoughts as any[]);

      // Step 3: For each candidate, make it reachable, then persist its usage.
      candidates.forEach(token => {
        // `addToken` must happen before `recordTokenUsage`, which looks the token up by id in
        // the propagator's own collection and silently no-ops if it isn't there — which, before
        // this fix, every freshly-created candidate always was.
        this.propagator.addToken(token);

        this.propagator.broadcastToken(token, 'similar_goals');

        // Record that this token was used; this is also what persists it (see
        // ThinkTokenPropagator.recordTokenUsage -> LearningStore.storePattern).
        this.propagator.recordTokenUsage(sessionId, token.id, success);
        tokensAffected++;
      });
    }

    // Step 4: Get propagation stats for dashboard
    const stats = this.propagator.getPropagationStats();

    return {
      learningRecorded: true,
      tokensAffected,
      behavioralImpact: `Tokens: ${stats.totalTokensAvailable}, Interactions: ${stats.totalWorkerInteractions}`
    };
  }

  /**
   * Detect behavioral changes when tokens are injected
   */
  detectBehaviorChange(
    beforeContext: Record<string, unknown>,
    afterContext: Record<string, unknown>
  ): {
    changed: boolean;
    changeFactors: string[];
    impact: 'high' | 'medium' | 'low' | 'none';
  } {
    return this.behaviorDetector.detectBehaviorChange(beforeContext, afterContext);
  }

  /**
   * Export propagation statistics for dashboard
   */
  getPropagationStats() {
    return this.propagator.getPropagationStats();
  }
}

/**
 * Integration pattern for server.ts
 *
 * In server.ts AgentSession class:
 *
 *   export class AgentSession {
 *     private learningIntegration: ServerLearningIntegration;
 *
 *     constructor(id: string, config: SessionConfigInput = {}) {
 *       this.id = id;
 *       // ... existing setup ...
 *
 *       // NEW: Initialize learning integration
 *       this.learningIntegration = new ServerLearningIntegration(
 *         globalPropagator,
 *         globalInitializer,
 *         globalLearningStore
 *       );
 *
 *       // Enhance system prompt with prior learning
 *       const enhanced = this.learningIntegration.enhanceSessionContext(
 *         id,
 *         this.currentGoal || '',
 *         this.systemPrompt,
 *         this.messages
 *       );
 *
 *       this.systemPrompt = enhanced.enhancedSystemPrompt;
 *       this.contextInjection = enhanced.contextInjection;
 *     }
 *
 *     async runGoal(goal: string): Promise<unknown> {
 *       const beforeContext = { reasoningSteps: this.thoughts.length };
 *
 *       // ... existing execution ...
 *       const result = await this.executeGoal(goal);
 *
 *       const afterContext = {
 *         reasoningSteps: this.thoughts.length,
 *         toolSequence: this.tools,
 *         errorRecoveryTime: this.recoveryMs
 *       };
 *
 *       // Record learning
 *       const learning = this.learningIntegration.recordGoalExecution(
 *         this.id,
 *         goal,
 *         result.success,
 *         { thoughts: this.thoughts, tools: this.tools }
 *       );
 *
 *       // Detect behavioral changes
 *       const behavior = this.learningIntegration.detectBehaviorChange(
 *         beforeContext,
 *         afterContext
 *       );
 *
 *       // Emit events for dashboard
 *       this.emit('propagation:stats', this.learningIntegration.getPropagationStats());
 *       if (behavior.changed) {
 *         this.emit('behavior:changed', { factors: behavior.changeFactors, impact: behavior.impact });
 *       }
 *
 *       return result;
 *     }
 *   }
 */

export function createServerLearningIntegration(
  propagator: ThinkTokenPropagator,
  initializer: WorkerInitializer,
  store: LearningStore
): ServerLearningIntegration {
  return new ServerLearningIntegration(propagator, initializer, store);
}
