// kudbEE Persistent Learning Store — Cross-session knowledge persistence

import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DB_PATH = path.join(__dirname, 'learning.db');

export interface LearnedPattern {
  id: string;
  type: 'goal_approach' | 'tool_sequence' | 'error_recovery' | 'optimization';
  pattern: string;
  confidence: number;
  sourceThoughts: string[];
  firstSeen: number;
  lastSeen: number;
  successCount: number;
  failureCount: number;
  metadata: Record<string, unknown>;
}

export interface SessionLearning {
  sessionId: string;
  goal: string;
  thoughts: Array<{
    type: string;
    content: string;
    timestamp: number;
    status: string;
  }>;
  outcome: 'success' | 'failure' | 'partial';
  duration: number;
  patterns: string[];
  metadata: Record<string, unknown>;
}

export class LearningStore {
  private db: Database.Database;

  constructor(dbPath: string = DB_PATH) {
    this.db = new Database(dbPath);
    this.db.pragma('journal_mode = WAL');
    this.initializeTables();
  }

  private initializeTables(): void {
    // Learned patterns table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS learned_patterns (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        pattern TEXT NOT NULL,
        confidence REAL NOT NULL,
        first_seen INTEGER NOT NULL,
        last_seen INTEGER NOT NULL,
        success_count INTEGER DEFAULT 0,
        failure_count INTEGER DEFAULT 0,
        metadata TEXT,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_pattern_type ON learned_patterns(type);
      CREATE INDEX IF NOT EXISTS idx_pattern_confidence ON learned_patterns(confidence DESC);
    `);

    // Session learning history table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS session_learning (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        goal TEXT NOT NULL,
        outcome TEXT NOT NULL,
        duration INTEGER NOT NULL,
        thoughts TEXT NOT NULL,
        patterns TEXT,
        metadata TEXT,
        created_at INTEGER NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_session_goal ON session_learning(goal);
      CREATE INDEX IF NOT EXISTS idx_session_outcome ON session_learning(outcome);
    `);

    // Thought artifacts table (for raw thought capture)
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS thought_artifacts (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        type TEXT NOT NULL,
        content TEXT NOT NULL,
        status TEXT,
        timestamp INTEGER NOT NULL,
        extracted_patterns TEXT,
        created_at INTEGER NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_thought_session ON thought_artifacts(session_id);
      CREATE INDEX IF NOT EXISTS idx_thought_type ON thought_artifacts(type);
    `);
  }

  storeSessionLearning(learning: SessionLearning): void {
    const stmt = this.db.prepare(`
      INSERT INTO session_learning (
        id, session_id, goal, outcome, duration, thoughts, patterns, metadata, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    const id = `learning-${learning.sessionId}-${Date.now()}`;
    stmt.run(
      id,
      learning.sessionId,
      learning.goal,
      learning.outcome,
      learning.duration,
      JSON.stringify(learning.thoughts),
      JSON.stringify(learning.patterns),
      JSON.stringify(learning.metadata),
      Date.now()
    );
  }

  storeThoughtArtifact(
    sessionId: string,
    type: string,
    content: string,
    status: string,
    extractedPatterns: string[] = []
  ): void {
    const stmt = this.db.prepare(`
      INSERT INTO thought_artifacts (
        id, session_id, type, content, status, timestamp, extracted_patterns, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);

    const id = `thought-${sessionId}-${Date.now()}`;
    stmt.run(
      id,
      sessionId,
      type,
      content,
      status,
      Date.now(),
      JSON.stringify(extractedPatterns),
      Date.now()
    );
  }

  storePattern(pattern: LearnedPattern): void {
    const existing = this.db.prepare(
      'SELECT * FROM learned_patterns WHERE id = ?'
    ).get(pattern.id);

    const stmt = existing
      ? this.db.prepare(`
          UPDATE learned_patterns SET
            pattern = ?, confidence = ?, last_seen = ?,
            success_count = ?, failure_count = ?, metadata = ?, updated_at = ?
          WHERE id = ?
        `)
      : this.db.prepare(`
          INSERT INTO learned_patterns (
            id, type, pattern, confidence, first_seen, last_seen,
            success_count, failure_count, metadata, created_at, updated_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `);

    if (existing) {
      stmt.run(
        pattern.pattern,
        pattern.confidence,
        pattern.lastSeen,
        pattern.successCount,
        pattern.failureCount,
        JSON.stringify(pattern.metadata),
        Date.now(),
        pattern.id
      );
    } else {
      stmt.run(
        pattern.id,
        pattern.type,
        pattern.pattern,
        pattern.confidence,
        pattern.firstSeen,
        pattern.lastSeen,
        pattern.successCount,
        pattern.failureCount,
        JSON.stringify(pattern.metadata),
        Date.now(),
        Date.now()
      );
    }
  }

  getPatternsByType(type: string, limit: number = 10): LearnedPattern[] {
    const rows = this.db.prepare(`
      SELECT * FROM learned_patterns
      WHERE type = ?
      ORDER BY confidence DESC, success_count DESC
      LIMIT ?
    `).all(type, limit) as any[];

    return rows.map(row => ({
      id: row.id,
      type: row.type,
      pattern: row.pattern,
      confidence: row.confidence,
      sourceThoughts: [],
      firstSeen: row.first_seen,
      lastSeen: row.last_seen,
      successCount: row.success_count,
      failureCount: row.failure_count,
      metadata: JSON.parse(row.metadata || '{}')
    }));
  }

  getTopPatterns(limit: number = 20): LearnedPattern[] {
    const rows = this.db.prepare(`
      SELECT * FROM learned_patterns
      ORDER BY confidence DESC, success_count DESC
      LIMIT ?
    `).all(limit) as any[];

    return rows.map(row => ({
      id: row.id,
      type: row.type,
      pattern: row.pattern,
      confidence: row.confidence,
      sourceThoughts: [],
      firstSeen: row.first_seen,
      lastSeen: row.last_seen,
      successCount: row.success_count,
      failureCount: row.failure_count,
      metadata: JSON.parse(row.metadata || '{}')
    }));
  }

  queryLearningByGoal(goal: string, limit: number = 5): SessionLearning[] {
    const rows = this.db.prepare(`
      SELECT * FROM session_learning
      WHERE goal LIKE ?
      ORDER BY created_at DESC
      LIMIT ?
    `).all(`%${goal}%`, limit) as any[];

    return rows.map(row => ({
      sessionId: row.session_id,
      goal: row.goal,
      outcome: row.outcome,
      duration: row.duration,
      thoughts: JSON.parse(row.thoughts),
      patterns: JSON.parse(row.patterns || '[]'),
      metadata: JSON.parse(row.metadata || '{}')
    }));
  }

  getSuccessfulApproaches(goal: string): SessionLearning[] {
    return this.queryLearningByGoal(goal).filter(l => l.outcome === 'success');
  }

  updatePatternSuccess(patternId: string, success: boolean): void {
    const stmt = this.db.prepare(`
      UPDATE learned_patterns SET
        success_count = success_count + ?,
        failure_count = failure_count + ?,
        confidence = (success_count + ?) * 1.0 / (success_count + failure_count + ?),
        last_seen = ?
      WHERE id = ?
    `);

    const successDelta = success ? 1 : 0;
    const failureDelta = success ? 0 : 1;
    stmt.run(successDelta, failureDelta, successDelta, (successDelta + failureDelta), Date.now(), patternId);
  }

  getStatistics(): {
    totalPatterns: number;
    totalSessions: number;
    avgSuccessRate: number;
    topPattern: LearnedPattern | null;
  } {
    const patterns = this.db.prepare('SELECT COUNT(*) as count FROM learned_patterns').get() as any;
    const sessions = this.db.prepare('SELECT COUNT(*) as count FROM session_learning').get() as any;
    const successRate = this.db.prepare(`
      SELECT SUM(success_count) * 1.0 / (SUM(success_count) + SUM(failure_count)) as rate
      FROM learned_patterns
    `).get() as any;

    const topPattern = this.getTopPatterns(1)[0] || null;

    return {
      totalPatterns: patterns.count,
      totalSessions: sessions.count,
      avgSuccessRate: successRate.rate || 0,
      topPattern
    };
  }

  close(): void {
    this.db.close();
  }
}
