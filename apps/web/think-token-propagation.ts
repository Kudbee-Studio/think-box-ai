// kudbEE Think Token Propagation — Distribute validated tokens to workers

import { ThinkToken, ThinkTokenCollection } from './think-token.ts';
import { LearningStore, type LearnedPattern } from './learning-store.ts';
import type { ChatMessage } from './types.ts';

/**
 * Propagation: Making validated Think Tokens available to other workers
 * so they can benefit from experience without independently rediscovering it.
 */
export class ThinkTokenPropagator {
  private store: LearningStore;
  private tokenCollection: ThinkTokenCollection;

  constructor(store: LearningStore, collection: ThinkTokenCollection) {
    this.store = store;
    this.tokenCollection = collection;
  }

  /**
   * Make a newly-minted candidate token reachable by id, so `recordTokenUsage` (and future
   * `getRelevantTokensForGoal` calls) can find it. Without this, a token that was only
   * broadcast and never added here is invisible to every other method on this class.
   */
  addToken(token: ThinkToken): void {
    this.tokenCollection.add(token);
  }

  /**
   * Get relevant Think Tokens for a new worker's goal
   */
  getRelevantTokensForGoal(goal: string, maxTokens: number = 10): ThinkToken[] {
    return this.tokenCollection
      .relevantFor(goal, 90) // Only tokens < 90 days old, with positive signal
      .slice(0, maxTokens);
  }

  /**
   * Inject Think Tokens into worker's system context
   */
  injectTokensIntoSystemPrompt(
    basePrompt: string,
    goal: string,
    maxTokens: number = 5
  ): string {
    const tokens = this.getRelevantTokensForGoal(goal, maxTokens);

    if (tokens.length === 0) {
      return basePrompt;
    }

    let injectedPrompt = basePrompt;
    injectedPrompt += '\n\n## Prior Experience (Think Tokens):\n';
    injectedPrompt += 'The following patterns were learned from previous workers:\n\n';

    tokens.forEach((token, idx) => {
      const confidence = Math.round(token.evaluate() * 100);
      injectedPrompt += `${idx + 1}. [${confidence}% confidence] ${token.content.text}\n`;
      injectedPrompt += `   Type: ${token.content.type} | Used: ${token.metadata.reuseCount} times\n`;
    });

    injectedPrompt += '\nConsider these patterns when planning your approach.\n';

    return injectedPrompt;
  }

  /**
   * Create worker context from Think Tokens
   */
  createWorkerContext(
    workerId: string,
    goal: string,
    baseMessages: ChatMessage[]
  ): {
    enhancedMessages: ChatMessage[];
    injectedTokens: ThinkToken[];
    contextSummary: string;
  } {
    const injectedTokens = this.getRelevantTokensForGoal(goal, 5);

    if (injectedTokens.length === 0) {
      return {
        enhancedMessages: baseMessages,
        injectedTokens: [],
        contextSummary: 'No prior patterns found for this goal type.'
      };
    }

    // Inject tokens into system prompt
    const enhancedSystemMessage = this.injectTokensIntoSystemPrompt(
      baseMessages.find(m => m.role === 'system')?.content || '',
      goal,
      5
    );

    const enhancedMessages = baseMessages.map(m =>
      m.role === 'system' ? { ...m, content: enhancedSystemMessage } : m
    );

    const contextSummary = `Loaded ${injectedTokens.length} relevant prior patterns (avg confidence: ${Math.round(
      (injectedTokens.reduce((sum, t) => sum + t.evaluate(), 0) / injectedTokens.length) * 100
    )}%)`;

    return {
      enhancedMessages,
      injectedTokens,
      contextSummary
    };
  }

  /**
   * Record worker's use of Think Token and feedback
   */
  recordTokenUsage(
    workerId: string,
    tokenId: string,
    success: boolean,
    context?: Record<string, unknown>
  ): void {
    const token = this.tokenCollection.get(tokenId);
    if (!token) return;

    token.recordUse(success);

    // Persist the token as a durable, evaluable pattern using the existing learning-store
    // mechanism. `storePattern` upserts (it SELECTs first, then INSERTs or UPDATEs), which is
    // required here: `updatePatternSuccess` is UPDATE-only and silently affects zero rows for a
    // pattern id that was never inserted — which every freshly-minted Think Token is, so calling
    // it here never actually persisted anything.
    const pattern: LearnedPattern = {
      id: token.id,
      type: token.content.type,
      pattern: token.content.text,
      confidence: token.evaluate(),
      sourceThoughts: [],
      firstSeen: token.metadata.captureTime,
      lastSeen: token.metadata.lastReused ?? token.metadata.captureTime,
      successCount: token.metadata.successCount,
      failureCount: token.metadata.failureCount,
      metadata: { ...token.metadata, artifacts: token.content.artifacts },
    };
    this.store.storePattern(pattern);

    // Log usage for analytics
    console.log({
      event: 'token_usage',
      workerId,
      tokenId,
      success,
      newConfidence: token.evaluate(),
      context
    });
  }

  /**
   * Get propagation statistics
   */
  getPropagationStats(): {
    totalTokensAvailable: number;
    activeTokens: number;
    averageConfidence: number;
    totalWorkerInteractions: number;
    tokenTypeDistribution: Record<string, number>;
  } {
    const allTokens = this.tokenCollection.export();
    const activeTokens = allTokens.filter(t => t.isRelevant(90)).length;
    const avgConfidence = allTokens.length > 0
      ? allTokens.reduce((sum, t) => sum + t.evaluate(), 0) / allTokens.length
      : 0;

    const totalInteractions = allTokens.reduce((sum, t) => sum + t.metadata.reuseCount, 0);

    const typeDistribution: Record<string, number> = {};
    allTokens.forEach(t => {
      typeDistribution[t.content.type] = (typeDistribution[t.content.type] || 0) + 1;
    });

    return {
      totalTokensAvailable: allTokens.length,
      activeTokens,
      averageConfidence: Math.round(avgConfidence * 100) / 100,
      totalWorkerInteractions: totalInteractions,
      tokenTypeDistribution: typeDistribution
    };
  }

  /**
   * Broadcast token to all workers (via message queue or event system)
   */
  broadcastToken(token: ThinkToken, scope: 'all' | 'similar_goals' = 'similar_goals'): {
    targetWorkers: number;
    broadcastId: string;
  } {
    const broadcastId = `broadcast-${Date.now()}`;

    if (scope === 'all') {
      // In production: publish to message queue (Redis, Kafka, etc.)
      console.log(`[Propagation] Broadcasting token ${token.id} to all workers`);
      return { targetWorkers: -1, broadcastId }; // -1 = all
    } else {
      // Scope to workers with similar goals
      const targets = this.tokenCollection
        .export()
        .filter(t => t.metadata.originGoal.length > 0)
        .length;

      console.log(`[Propagation] Broadcasting token ${token.id} to ${targets} similar workers`);
      return { targetWorkers: targets, broadcastId };
    }
  }

  /**
   * Enable/disable token propagation for A/B testing
   */
  createPropagationVariant(
    enabled: boolean,
    tokenFilter?: (token: ThinkToken) => boolean
  ): {
    variantId: string;
    enabled: boolean;
    config: Record<string, unknown>;
  } {
    const variantId = `variant-${Date.now()}`;

    return {
      variantId,
      enabled,
      config: {
        propagationEnabled: enabled,
        tokenFilter: tokenFilter ? 'custom' : 'default',
        maxTokensPerGoal: 5,
        minConfidenceThreshold: 0.5,
        maxTokenAge: 90 // days
      }
    };
  }
}

/**
 * Integration hooks for server.ts AgentSession
 *
 * Usage in runGoal():
 *
 *   // Before inference
 *   const { enhancedMessages, injectedTokens } = propagator.createWorkerContext(
 *     sessionId, goal, messages
 *   );
 *
 *   // After execution
 *   injectedTokens.forEach(token => {
 *     propagator.recordTokenUsage(sessionId, token.id, outcome === 'success');
 *   });
 */
export function createPropagator(
  store: LearningStore,
  collection: ThinkTokenCollection
): ThinkTokenPropagator {
  return new ThinkTokenPropagator(store, collection);
}
