// kudbEE Learning Integration — Wire learning into server lifecycle

import { LearningStore } from './learning-store.ts';
import { LearningExtractor } from './learning-extractor.ts';
import type { Thought, MemoryEntry } from './types.ts';

export class LearningManager {
  private store: LearningStore;
  private extractor: LearningExtractor;

  constructor() {
    this.store = new LearningStore();
    this.extractor = new LearningExtractor(this.store);
  }

  /**
   * Called when a session completes to extract and store learning
   */
  async recordSessionCompletion(
    sessionId: string,
    goal: string,
    thoughts: Thought[],
    memory: MemoryEntry[],
    outcome: 'success' | 'failure' | 'partial',
    duration: number
  ): Promise<string[]> {
    try {
      // Extract patterns from this session
      const patterns = this.extractor.extractPatternsFromSession(
        sessionId,
        goal,
        thoughts,
        memory,
        outcome
      );

      // Store the session learning
      this.store.storeSessionLearning({
        sessionId,
        goal,
        thoughts: thoughts.map(t => ({
          type: String(t.type),
          content: String(t.content || ''),
          timestamp: Number(t.timestamp || 0),
          status: String(t.status || 'unknown')
        })),
        outcome,
        duration,
        patterns,
        metadata: {
          thoughtCount: thoughts.length,
          memorySize: memory.length,
          extractedPatternCount: patterns.length
        }
      });

      // Update pattern success/failure tracking
      for (const patternId of patterns) {
        this.store.updatePatternSuccess(patternId, outcome === 'success');
      }

      return patterns;
    } catch (error) {
      console.error('Failed to record session learning:', error);
      return [];
    }
  }

  /**
   * Generate an enhanced system prompt with learnings for a new goal
   */
  generateEnhancedSystemPrompt(goal: string): string {
    const baseSystemPrompt = `You are THINK BOX AI, an intelligent agent.
Use the available plugins to accomplish tasks. Think step by step. Be concise and actionable.

You have access to previous learnings from similar goals.`;

    const learnedInsights = this.extractor.generateSystemPromptWithLearnings(goal, 5);

    return baseSystemPrompt + learnedInsights;
  }

  /**
   * Get relevant prior experiences for a goal
   */
  getPriorExperiences(goal: string) {
    return {
      successfulApproaches: this.store.getSuccessfulApproaches(goal),
      topPatterns: this.store.getTopPatterns(10),
      statistics: this.store.getStatistics()
    };
  }

  /**
   * Export all learnings for backup/analysis
   */
  exportLearnings() {
    return {
      patterns: this.store.getTopPatterns(1000),
      statistics: this.store.getStatistics()
    };
  }

  /**
   * Clean up resources
   */
  close(): void {
    this.store.close();
  }
}

/**
 * Integration hooks for server.ts AgentSession
 *
 * Usage in runGoal():
 *
 *   // At session start
 *   const systemPrompt = learningManager.generateEnhancedSystemPrompt(goal);
 *
 *   // At session end
 *   const outcome = result.success ? 'success' : 'failure';
 *   await learningManager.recordSessionCompletion(
 *     this.id, goal, this.thoughts, this.memory, outcome, duration
 *   );
 */
export function createLearningManager(): LearningManager {
  return new LearningManager();
}
