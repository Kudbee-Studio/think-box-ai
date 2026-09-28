// kudbEE Persistent Memory Backbone
// Survives process restart via SQLite + Node

import Database from 'better-sqlite3';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';

export interface DashboardState {
  sessionId: string;
  panelState?: Record<string, any>;
  viewState?: Record<string, any>;
  settings?: Record<string, any>;
  lastUpdate: number;
  createdAt: number;
}

export interface RunMetadata {
  runId: string;
  sessionId: string;
  goal: string;
  status: 'running' | 'completed' | 'failed' | 'stopped';
  startTime: number;
  endTime?: number;
  metrics?: Record<string, any>;
  files?: string[];
  createdAt: number;
}

export interface MemoryNote {
  id: string;
  sessionId: string;
  layer: 'session' | 'task' | 'org' | 'verified';
  title: string;
  content: string;
  evidence?: Record<string, any>;
  createdAt: number;
  updatedAt: number;
}

export class PersistenceLayer {
  private db: Database.Database;
  private dbPath: string;

  constructor(dbDir?: string) {
    const dir = dbDir || path.join(os.homedir(), '.kudbee', 'data');
    fs.mkdirSync(dir, { recursive: true });
    this.dbPath = path.join(dir, 'kudbee.db');

    this.db = new Database(this.dbPath);
    this.db.pragma('journal_mode = WAL');
    this.initSchema();
  }

  private initSchema(): void {
    // Dashboard state: KPIs, panel positions, selected model, etc
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS dashboard_state (
        sessionId TEXT PRIMARY KEY,
        panelState TEXT,
        viewState TEXT,
        settings TEXT,
        lastUpdate INTEGER NOT NULL,
        createdAt INTEGER NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_dashboard_lastUpdate
        ON dashboard_state(lastUpdate DESC);
    `);

    // Run metadata: persisted from each goal run
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS run_metadata (
        runId TEXT PRIMARY KEY,
        sessionId TEXT NOT NULL,
        goal TEXT NOT NULL,
        status TEXT NOT NULL,
        startTime INTEGER NOT NULL,
        endTime INTEGER,
        metrics TEXT,
        files TEXT,
        createdAt INTEGER NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_run_session ON run_metadata(sessionId);
      CREATE INDEX IF NOT EXISTS idx_run_status ON run_metadata(status);
      CREATE INDEX IF NOT EXISTS idx_run_created ON run_metadata(createdAt DESC);
    `);

    // Memory notes: org/verified knowledge + task episodes
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS memory_notes (
        id TEXT PRIMARY KEY,
        sessionId TEXT NOT NULL,
        layer TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT,
        evidence TEXT,
        createdAt INTEGER NOT NULL,
        updatedAt INTEGER NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_memory_layer ON memory_notes(layer);
      CREATE INDEX IF NOT EXISTS idx_memory_session ON memory_notes(sessionId);
      CREATE INDEX IF NOT EXISTS idx_memory_created ON memory_notes(createdAt DESC);
    `);
  }

  // ── Dashboard State ──

  async saveDashboardState(state: DashboardState): Promise<void> {
    const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO dashboard_state
      (sessionId, panelState, viewState, settings, lastUpdate, createdAt)
      VALUES (?, ?, ?, ?, ?, COALESCE(
        (SELECT createdAt FROM dashboard_state WHERE sessionId = ?),
        ?
      ))
    `);

    const now = Date.now();
    stmt.run(
      state.sessionId,
      state.panelState ? JSON.stringify(state.panelState) : null,
      state.viewState ? JSON.stringify(state.viewState) : null,
      state.settings ? JSON.stringify(state.settings) : null,
      now,
      state.sessionId,
      now
    );
  }

  async restoreDashboardState(sessionId: string): Promise<DashboardState | null> {
    const stmt = this.db.prepare(
      'SELECT * FROM dashboard_state WHERE sessionId = ?'
    );
    const row = stmt.get(sessionId) as any;

    if (!row) return null;

    return {
      sessionId: row.sessionId,
      panelState: row.panelState ? JSON.parse(row.panelState) : undefined,
      viewState: row.viewState ? JSON.parse(row.viewState) : undefined,
      settings: row.settings ? JSON.parse(row.settings) : undefined,
      lastUpdate: row.lastUpdate,
      createdAt: row.createdAt
    };
  }

  // ── Run Metadata ──

  async saveRunMetadata(run: RunMetadata): Promise<void> {
    const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO run_metadata
      (runId, sessionId, goal, status, startTime, endTime, metrics, files, createdAt)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(
      run.runId,
      run.sessionId,
      run.goal,
      run.status,
      run.startTime,
      run.endTime || null,
      run.metrics ? JSON.stringify(run.metrics) : null,
      run.files ? JSON.stringify(run.files) : null,
      run.createdAt || Date.now()
    );
  }

  async getRunMetadata(runId: string): Promise<RunMetadata | null> {
    const stmt = this.db.prepare('SELECT * FROM run_metadata WHERE runId = ?');
    const row = stmt.get(runId) as any;

    if (!row) return null;

    return {
      runId: row.runId,
      sessionId: row.sessionId,
      goal: row.goal,
      status: row.status,
      startTime: row.startTime,
      endTime: row.endTime,
      metrics: row.metrics ? JSON.parse(row.metrics) : undefined,
      files: row.files ? JSON.parse(row.files) : undefined,
      createdAt: row.createdAt
    };
  }

  async listRuns(sessionId: string, limit = 50): Promise<RunMetadata[]> {
    const stmt = this.db.prepare(`
      SELECT * FROM run_metadata
      WHERE sessionId = ?
      ORDER BY createdAt DESC
      LIMIT ?
    `);

    const rows = stmt.all(sessionId, limit) as any[];
    return rows.map((row) => ({
      runId: row.runId,
      sessionId: row.sessionId,
      goal: row.goal,
      status: row.status,
      startTime: row.startTime,
      endTime: row.endTime,
      metrics: row.metrics ? JSON.parse(row.metrics) : undefined,
      files: row.files ? JSON.parse(row.files) : undefined,
      createdAt: row.createdAt
    }));
  }

  // ── Memory Notes ──

  async saveMemoryNote(note: MemoryNote): Promise<void> {
    const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO memory_notes
      (id, sessionId, layer, title, content, evidence, createdAt, updatedAt)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(
      note.id,
      note.sessionId,
      note.layer,
      note.title,
      note.content,
      note.evidence ? JSON.stringify(note.evidence) : null,
      note.createdAt || Date.now(),
      note.updatedAt || Date.now()
    );
  }

  async getMemoryNote(id: string): Promise<MemoryNote | null> {
    const stmt = this.db.prepare('SELECT * FROM memory_notes WHERE id = ?');
    const row = stmt.get(id) as any;

    if (!row) return null;

    return {
      id: row.id,
      sessionId: row.sessionId,
      layer: row.layer,
      title: row.title,
      content: row.content,
      evidence: row.evidence ? JSON.parse(row.evidence) : undefined,
      createdAt: row.createdAt,
      updatedAt: row.updatedAt
    };
  }

  async listMemoryNotes(sessionId: string, layer?: string, limit = 100): Promise<MemoryNote[]> {
    let stmt;
    const params = [sessionId, limit];

    if (layer) {
      stmt = this.db.prepare(`
        SELECT * FROM memory_notes
        WHERE sessionId = ? AND layer = ?
        ORDER BY updatedAt DESC
        LIMIT ?
      `);
      params.splice(1, 0, layer);
    } else {
      stmt = this.db.prepare(`
        SELECT * FROM memory_notes
        WHERE sessionId = ?
        ORDER BY updatedAt DESC
        LIMIT ?
      `);
    }

    const rows = stmt.all(...params) as any[];
    return rows.map((row) => ({
      id: row.id,
      sessionId: row.sessionId,
      layer: row.layer,
      title: row.title,
      content: row.content,
      evidence: row.evidence ? JSON.parse(row.evidence) : undefined,
      createdAt: row.createdAt,
      updatedAt: row.updatedAt
    }));
  }

  // ── Maintenance ──

  close(): void {
    this.db.close();
  }

  vacuum(): void {
    this.db.exec('VACUUM;');
  }

  getStats(): { dbSize: number; runs: number; notes: number } {
    const stat = fs.statSync(this.dbPath);
    const runs = this.db.prepare('SELECT COUNT(*) as count FROM run_metadata').get() as any;
    const notes = this.db.prepare('SELECT COUNT(*) as count FROM memory_notes').get() as any;

    return {
      dbSize: stat.size,
      runs: runs.count,
      notes: notes.count
    };
  }
}

export default PersistenceLayer;
