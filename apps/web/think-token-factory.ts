// kudbEE Think Token Factory — Quality gate to distinguish capture from learning

import { ThinkToken, ThinkTokenMetadata, ThinkTokenContent } from './think-token.ts';
import { Thought, MemoryEntry } from './types.ts';
import { randomUUID } from 'node:crypto';

/**
 * Think Token Factory creates durable Think Tokens only from HIGH-QUALITY observations.
 *
 * Not all captured data becomes a Think Token:
 * - Capture: Raw observation (500+ thoughts in a session)
 * - Think Token: Structured, evaluable unit (10-20 tokens per session)
 * - Learning: Durable pattern extracted from multiple successful Think Tokens
 *
 * Quality criteria:
 * 1. Actionable (contains specific tools, patterns, or decisions)
 * 2. Repeatable (generalizes beyond single instance)
 * 3. Evaluable (success/failure outcomes are measurable)
 * 4. Reusable (applies to future similar goals)
 */
export class ThinkTokenFactory {
  /**
   * Candidate Think Tokens from a session's thoughts
   */
  static extractCandidates(
    sessionId: string,
    goal: string,
    thoughts: Thought[]
  ): ThinkToken[] {
    const candidates: ThinkToken[] = [];

    // Type 1: Tool sequences (if > 1 tool was used, it's repeatable)
    const toolSequence = this.extractToolSequence(thoughts);
    if (toolSequence && toolSequence.length > 1) {
      const token = this.createToolSequenceToken(sessionId, goal, toolSequence);
      if (this.meetsQualityThreshold(token)) {
        candidates.push(token);
      }
    }

    // Type 2: Error recovery patterns (specific error → specific recovery step)
    const recoveries = this.extractErrorRecoveries(thoughts);
    for (const recovery of recoveries) {
      const token = this.createErrorRecoveryToken(sessionId, goal, recovery);
      if (this.meetsQualityThreshold(token)) {
        candidates.push(token);
      }
    }

    // Type 3: Decision points (when agent chose between options and one worked)
    const decisions = this.extractDecisions(thoughts);
    for (const decision of decisions) {
      const token = this.createDecisionToken(sessionId, goal, decision);
      if (this.meetsQualityThreshold(token)) {
        candidates.push(token);
      }
    }

    // Type 4: Optimization insights (specific improvement found during execution)
    const optimizations = this.extractOptimizations(thoughts);
    for (const opt of optimizations) {
      const token = this.createOptimizationToken(sessionId, goal, opt);
      if (this.meetsQualityThreshold(token)) {
        candidates.push(token);
      }
    }

    return candidates;
  }

  /**
   * Quality gate: only tokens that meet criteria become "real" Think Tokens
   */
  private static meetsQualityThreshold(token: ThinkToken): boolean {
    // Criterion 1: Content must be specific (not vague platitudes)
    if (!this.isSpecific(token.content.text)) {
      return false;
    }

    // Criterion 2: Content must be actionable (contains verbs, tools, patterns)
    if (!this.isActionable(token.content.text)) {
      return false;
    }

    // Criterion 3: Content must be generalizable (not tied to single execution)
    if (!this.isGeneralizable(token.content.text)) {
      return false;
    }

    return true;
  }

  private static isSpecific(text: string): boolean {
    // Generic phrases to reject
    const genericPatterns = [
      /^(I think|it seems|probably|maybe|perhaps)/i,
      /^(just think|I guess|one might say)/i,
      /^(could|might|potentially|presumably)/i
    ];

    return !genericPatterns.some(p => p.test(text));
  }

  private static isActionable(text: string): boolean {
    // Must contain specific verbs, tools, or patterns
    const actionablePatterns = [
      /\b(use|call|execute|run|apply|try)\s+\w+/i,
      /\b(tool|plugin|command|step|approach)\b/i,
      /→|then|next|followed by/i,
      /if.*then|when.*do/i
    ];

    return actionablePatterns.some(p => p.test(text));
  }

  private static isGeneralizable(text: string): boolean {
    // Reject text tied to single instance
    const specificIndicators = [
      /\b(this specific|just now|in this case only)\b/i,
      /\b(once|this time|today)\b/i
    ];

    const generalizing = [
      /\b(always|generally|typically|usually|for.*similar goals)\b/i,
      /\b(pattern|rule|approach|strategy|method)\b/i
    ];

    const hasSpecificBinding = specificIndicators.some(p => p.test(text));
    const hasGeneralizingLanguage = generalizing.some(p => p.test(text));

    return !hasSpecificBinding || hasGeneralizingLanguage;
  }

  private static extractToolSequence(thoughts: Thought[]): string[] | null {
    const tools: string[] = [];
    for (const thought of thoughts) {
      if (thought.type === 'plugin_call' && typeof thought.plugin === 'string') {
        tools.push(thought.plugin);
      }
    }
    return tools.length > 1 ? tools : null;
  }

  private static extractErrorRecoveries(
    thoughts: Thought[]
  ): Array<{ error: string; recovery: string }> {
    const recoveries: Array<{ error: string; recovery: string }> = [];

    for (let i = 0; i < thoughts.length - 1; i++) {
      const current = thoughts[i];
      const next = thoughts[i + 1];

      if (current.status === 'error' && next.type === 'plugin_call') {
        recoveries.push({
          error: String(current.content || ''),
          recovery: `Use ${next.plugin} to recover`
        });
      }
    }

    return recoveries;
  }

  private static extractDecisions(
    thoughts: Thought[]
  ): Array<{ decision: string; outcome: string }> {
    const decisions: Array<{ decision: string; outcome: string }> = [];

    for (const thought of thoughts) {
      if (thought.type === 'reasoning' && thought.status === 'thinking') {
        const content = String(thought.content || '');
        if (content.includes('or') || content.includes('vs')) {
          decisions.push({
            decision: content,
            outcome: 'considered'
          });
        }
      }
    }

    return decisions;
  }

  private static extractOptimizations(
    thoughts: Thought[]
  ): Array<{ optimization: string; impact: string }> {
    const optimizations: Array<{ optimization: string; impact: string }> = [];

    for (const thought of thoughts) {
      if (thought.type === 'reasoning') {
        const content = String(thought.content || '');
        if (content.includes('optimize') || content.includes('faster') || content.includes('simpler')) {
          optimizations.push({
            optimization: content,
            impact: 'observed'
          });
        }
      }
    }

    return optimizations;
  }

  private static createToolSequenceToken(
    sessionId: string,
    goal: string,
    tools: string[]
  ): ThinkToken {
    const metadata: ThinkTokenMetadata = {
      originSessionId: sessionId,
      originGoal: goal,
      captureTime: Date.now(),
      reuseCount: 0,
      successCount: 0,
      failureCount: 0
    };

    const content: ThinkTokenContent = {
      type: 'tool_sequence',
      text: `For goals like "${goal}": use ${tools.join(' → ')} in sequence`,
      artifacts: { tools }
    };

    return new ThinkToken(`token-tools-${randomUUID()}`, content, metadata, 0.6);
  }

  private static createErrorRecoveryToken(
    sessionId: string,
    goal: string,
    recovery: { error: string; recovery: string }
  ): ThinkToken {
    const metadata: ThinkTokenMetadata = {
      originSessionId: sessionId,
      originGoal: goal,
      captureTime: Date.now(),
      reuseCount: 0,
      successCount: 0,
      failureCount: 0
    };

    const content: ThinkTokenContent = {
      type: 'error_recovery',
      text: `When encountering "${recovery.error.substring(0, 50)}...": ${recovery.recovery}`,
      artifacts: { error: recovery.error, recovery: recovery.recovery }
    };

    return new ThinkToken(`token-recovery-${randomUUID()}`, content, metadata, 0.5);
  }

  private static createDecisionToken(
    sessionId: string,
    goal: string,
    decision: { decision: string; outcome: string }
  ): ThinkToken {
    const metadata: ThinkTokenMetadata = {
      originSessionId: sessionId,
      originGoal: goal,
      captureTime: Date.now(),
      reuseCount: 0,
      successCount: 0,
      failureCount: 0
    };

    const content: ThinkTokenContent = {
      type: 'approach',
      text: `For "${goal}": ${decision.decision.substring(0, 100)}...`,
      artifacts: { decision: decision.decision }
    };

    return new ThinkToken(`token-decision-${randomUUID()}`, content, metadata, 0.5);
  }

  private static createOptimizationToken(
    sessionId: string,
    goal: string,
    opt: { optimization: string; impact: string }
  ): ThinkToken {
    const metadata: ThinkTokenMetadata = {
      originSessionId: sessionId,
      originGoal: goal,
      captureTime: Date.now(),
      reuseCount: 0,
      successCount: 0,
      failureCount: 0
    };

    const content: ThinkTokenContent = {
      type: 'optimization',
      text: `Optimization for "${goal}": ${opt.optimization.substring(0, 100)}...`,
      artifacts: { optimization: opt.optimization }
    };

    return new ThinkToken(`token-opt-${randomUUID()}`, content, metadata, 0.4);
  }
}
