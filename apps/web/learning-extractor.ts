// kudbEE Learning Extractor — Transform observations into durable learning

import { Thought, MemoryEntry } from './types.ts';
import { LearningStore, LearnedPattern } from './learning-store.ts';
import { randomUUID } from 'node:crypto';

export interface ThoughtSequence {
  type: 'goal' | 'reasoning' | 'plugin_call' | 'plugin_result' | 'completion';
  content: string;
  plugins?: string[];
  status: string;
  timestamp: number;
}

export class LearningExtractor {
  private store: LearningStore;

  constructor(store: LearningStore) {
    this.store = store;
  }

  extractPatternsFromSession(
    sessionId: string,
    goal: string,
    thoughts: Thought[],
    memory: MemoryEntry[],
    outcome: 'success' | 'failure' | 'partial'
  ): string[] {
    const patterns: string[] = [];

    // Pattern 1: Tool sequence pattern
    const toolSequence = this.extractToolSequence(thoughts);
    if (toolSequence && toolSequence.length > 0) {
      const patternId = this.storeToolSequencePattern(goal, toolSequence, outcome);
      patterns.push(patternId);
    }

    // Pattern 2: Goal decomposition pattern
    const decomposition = this.extractGoalDecomposition(thoughts);
    if (decomposition) {
      const patternId = this.storeGoalDecompositionPattern(goal, decomposition, outcome);
      patterns.push(patternId);
    }

    // Pattern 3: Error recovery pattern
    const recovery = this.extractErrorRecovery(thoughts, memory);
    if (recovery) {
      const patternId = this.storeErrorRecoveryPattern(goal, recovery, outcome);
      patterns.push(patternId);
    }

    // Pattern 4: Optimization pattern
    const optimization = this.extractOptimization(thoughts);
    if (optimization) {
      const patternId = this.storeOptimizationPattern(goal, optimization, outcome);
      patterns.push(patternId);
    }

    return patterns;
  }

  private extractToolSequence(thoughts: Thought[]): string[] | null {
    const tools: string[] = [];
    for (const thought of thoughts) {
      if (thought.type === 'plugin_call' && typeof thought.plugin === 'string') {
        tools.push(thought.plugin);
      }
    }
    return tools.length > 0 ? tools : null;
  }

  private extractGoalDecomposition(thoughts: Thought[]): Record<string, string[]> | null {
    const steps: Record<string, string[]> = {};
    let currentPhase = 'initial';

    for (const thought of thoughts) {
      if (thought.type === 'reasoning') {
        const content = String(thought.content || '');
        if (content.includes('step')) {
          if (!steps[currentPhase]) steps[currentPhase] = [];
          steps[currentPhase].push(content.substring(0, 100));
        }
      } else if (thought.type === 'plugin_call') {
        currentPhase = String(thought.plugin || 'unknown');
      }
    }

    return Object.keys(steps).length > 0 ? steps : null;
  }

  private extractErrorRecovery(thoughts: Thought[], memory: MemoryEntry[]): Record<string, unknown> | null {
    const errors = thoughts.filter(t => t.status === 'error' || t.type === 'plugin_result' && !t.success);

    if (errors.length === 0) return null;

    const recovery: Record<string, unknown> = {
      errorCount: errors.length,
      errorTypes: [...new Set(errors.map(e => e.type))],
      recoverySteps: []
    };

    for (let i = 0; i < errors.length; i++) {
      const error = errors[i];
      const nextThought = thoughts[thoughts.indexOf(error) + 1];
      if (nextThought && nextThought.type !== 'error') {
        (recovery.recoverySteps as string[]).push(`After ${error.type}: ${nextThought.content}`);
      }
    }

    return recovery;
  }

  private extractOptimization(thoughts: Thought[]): Record<string, unknown> | null {
    const optimizations: Record<string, unknown> = {
      shortcuts: [],
      parallelizable: [],
      cached: []
    };

    const toolSequence = this.extractToolSequence(thoughts);
    if (toolSequence && toolSequence.length > 2) {
      (optimizations.shortcuts as string[]).push(`Chain of ${toolSequence.length} tools could be optimized`);
    }

    const reasoning = thoughts.filter(t => t.type === 'reasoning');
    if (reasoning.length > 5) {
      (optimizations.shortcuts as string[]).push('Excessive reasoning steps - consider pre-planning');
    }

    return (optimizations.shortcuts as string[]).length > 0 ? optimizations : null;
  }

  private storeToolSequencePattern(goal: string, tools: string[], outcome: 'success' | 'failure' | 'partial'): string {
    const patternId = `pattern-tool-${tools.join('-')}-${Date.now()}`;
    const confidence = outcome === 'success' ? 0.9 : outcome === 'partial' ? 0.5 : 0.2;

    const pattern: LearnedPattern = {
      id: patternId,
      type: 'tool_sequence',
      pattern: `Use tools in order: ${tools.join(' → ')} for goals like "${goal}"`,
      confidence,
      sourceThoughts: [],
      firstSeen: Date.now(),
      lastSeen: Date.now(),
      successCount: outcome === 'success' ? 1 : 0,
      failureCount: outcome === 'failure' ? 1 : 0,
      metadata: {
        goal,
        tools,
        outcome,
        toolCount: tools.length
      }
    };

    this.store.storePattern(pattern);
    return patternId;
  }

  private storeGoalDecompositionPattern(
    goal: string,
    decomposition: Record<string, string[]>,
    outcome: 'success' | 'failure' | 'partial'
  ): string {
    const patternId = `pattern-decomp-${goal.substring(0, 20)}-${Date.now()}`;
    const confidence = outcome === 'success' ? 0.85 : 0.3;

    const pattern: LearnedPattern = {
      id: patternId,
      type: 'goal_approach',
      pattern: `Break "${goal}" into phases: ${Object.keys(decomposition).join(' → ')}`,
      confidence,
      sourceThoughts: [],
      firstSeen: Date.now(),
      lastSeen: Date.now(),
      successCount: outcome === 'success' ? 1 : 0,
      failureCount: outcome === 'failure' ? 1 : 0,
      metadata: {
        goal,
        phases: Object.keys(decomposition),
        outcome
      }
    };

    this.store.storePattern(pattern);
    return patternId;
  }

  private storeErrorRecoveryPattern(
    goal: string,
    recovery: Record<string, unknown>,
    outcome: 'success' | 'failure' | 'partial'
  ): string {
    const patternId = `pattern-recovery-${randomUUID()}`;
    const confidence = outcome === 'success' ? 0.7 : 0.2;

    const pattern: LearnedPattern = {
      id: patternId,
      type: 'error_recovery',
      pattern: `For goals like "${goal}": if errors occur, apply recovery steps ${JSON.stringify(recovery.recoverySteps)}`,
      confidence,
      sourceThoughts: [],
      firstSeen: Date.now(),
      lastSeen: Date.now(),
      successCount: outcome === 'success' ? 1 : 0,
      failureCount: outcome === 'failure' ? 1 : 0,
      metadata: {
        goal,
        errorCount: recovery.errorCount,
        recovery: recovery.recoverySteps,
        outcome
      }
    };

    this.store.storePattern(pattern);
    return patternId;
  }

  private storeOptimizationPattern(
    goal: string,
    optimization: Record<string, unknown>,
    outcome: 'success' | 'failure' | 'partial'
  ): string {
    const patternId = `pattern-opt-${randomUUID()}`;
    const confidence = 0.6;

    const pattern: LearnedPattern = {
      id: patternId,
      type: 'optimization',
      pattern: `Optimize goals like "${goal}": ${JSON.stringify(optimization.shortcuts)}`,
      confidence,
      sourceThoughts: [],
      firstSeen: Date.now(),
      lastSeen: Date.now(),
      successCount: 0,
      failureCount: 0,
      metadata: {
        goal,
        suggestions: optimization.shortcuts,
        outcome
      }
    };

    this.store.storePattern(pattern);
    return patternId;
  }

  generateSystemPromptWithLearnings(goal: string, topN: number = 5): string {
    const patterns = this.store.getTopPatterns(topN);
    const goalSpecific = this.store.queryLearningByGoal(goal, 3);
    const successfulApproaches = this.store.getSuccessfulApproaches(goal);

    let prompt = '';

    if (successfulApproaches.length > 0) {
      prompt += `\n## Successfully completed similar goals:\n`;
      successfulApproaches.forEach(approach => {
        prompt += `- Goal: "${approach.goal}" (${approach.outcome})\n`;
      });
    }

    if (patterns.length > 0) {
      prompt += `\n## Learned patterns to consider:\n`;
      patterns.forEach(p => {
        if (p.confidence > 0.5) {
          prompt += `- [${(p.confidence * 100).toFixed(0)}%] ${p.pattern}\n`;
        }
      });
    }

    return prompt;
  }
}
