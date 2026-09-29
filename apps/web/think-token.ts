// kudbEE Think Token — Durable, structured unit of reasoning

export interface ThinkTokenMetadata {
  originSessionId: string;
  originGoal: string;
  originTask?: string;
  captureTime: number;
  evaluationScore?: number;
  reuseCount: number;
  successCount: number;
  failureCount: number;
  lastReused?: number;
}

export interface ThinkTokenContent {
  type: 'reasoning' | 'approach' | 'error_recovery' | 'tool_sequence' | 'optimization' | 'pattern';
  text: string;
  artifacts?: Record<string, unknown>;
}

/**
 * Think Token: A durable, structured unit of reasoning or execution experience
 * captured from a Think Box interaction that can be retained, evaluated, retrieved,
 * and reused to improve a future Think Job.
 */
export class ThinkToken {
  readonly id: string;
  readonly content: ThinkTokenContent;
  readonly metadata: ThinkTokenMetadata;
  readonly embeddings?: number[]; // For semantic search
  readonly confidence: number; // 0-1, based on success history

  constructor(
    id: string,
    content: ThinkTokenContent,
    metadata: ThinkTokenMetadata,
    confidence: number = 0.5
  ) {
    this.id = id;
    this.content = content;
    this.metadata = metadata;
    this.confidence = Math.min(1, Math.max(0, confidence));
  }

  /**
   * Evaluate this token's usefulness based on success/failure history
   */
  evaluate(): number {
    const total = this.metadata.successCount + this.metadata.failureCount;
    if (total === 0) return 0.5; // Neutral if never reused

    const successRate = this.metadata.successCount / total;
    const reuseBonus = Math.min(1, this.metadata.reuseCount / 10); // Normalize reuse bonus

    return (successRate * 0.7) + (reuseBonus * 0.3);
  }

  /**
   * Mark this token as having been used
   */
  recordUse(success: boolean): void {
    this.metadata.reuseCount++;
    this.metadata.lastReused = Date.now();

    if (success) {
      this.metadata.successCount++;
    } else {
      this.metadata.failureCount++;
    }
  }

  /**
   * Check if token is still relevant (not too stale, has positive feedback)
   */
  isRelevant(maxAgeDays: number = 90): boolean {
    const ageMs = Date.now() - this.metadata.captureTime;
    const ageDays = ageMs / (1000 * 60 * 60 * 24);

    if (ageDays > maxAgeDays) return false;

    // Token is relevant if:
    // 1. Never used (new), OR
    // 2. More successes than failures, OR
    // 3. Has been reused multiple times
    const total = this.metadata.successCount + this.metadata.failureCount;
    if (total === 0) return true;

    const successRate = this.metadata.successCount / total;
    const frequentlyReused = this.metadata.reuseCount > 5;

    return successRate > 0.5 || frequentlyReused;
  }

  /**
   * Serialize for storage
   */
  toJSON() {
    return {
      id: this.id,
      content: this.content,
      metadata: this.metadata,
      confidence: this.confidence
    };
  }

  /**
   * Deserialize from storage
   */
  static fromJSON(data: any): ThinkToken {
    return new ThinkToken(
      data.id,
      data.content,
      data.metadata,
      data.confidence
    );
  }
}

/**
 * Think Token Collection — Enables batch operations
 */
export class ThinkTokenCollection {
  private tokens: Map<string, ThinkToken> = new Map();

  add(token: ThinkToken): void {
    this.tokens.set(token.id, token);
  }

  get(id: string): ThinkToken | undefined {
    return this.tokens.get(id);
  }

  byType(type: string): ThinkToken[] {
    return Array.from(this.tokens.values()).filter(t => t.content.type === type);
  }

  byGoal(goal: string): ThinkToken[] {
    return Array.from(this.tokens.values()).filter(
      t => t.metadata.originGoal.includes(goal)
    );
  }

  relevantFor(goal: string, maxAge: number = 90): ThinkToken[] {
    return this.byGoal(goal)
      .filter(t => t.isRelevant(maxAge))
      .sort((a, b) => b.evaluate() - a.evaluate());
  }

  topByConfidence(n: number = 10): ThinkToken[] {
    return Array.from(this.tokens.values())
      .sort((a, b) => b.evaluate() - a.evaluate())
      .slice(0, n);
  }

  recordUse(tokenId: string, success: boolean): void {
    const token = this.tokens.get(tokenId);
    if (token) {
      token.recordUse(success);
    }
  }

  size(): number {
    return this.tokens.size;
  }

  export(): ThinkToken[] {
    return Array.from(this.tokens.values());
  }
}
