import { test, describe, beforeEach, afterEach } from 'node:test';
import { strictEqual, deepStrictEqual, ok } from 'node:assert';
import PersistenceLayer from '../persistence.ts';
import type { DashboardState, RunMetadata, MemoryNote } from '../persistence.ts';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';

describe('PersistenceLayer', () => {
  let db: PersistenceLayer;
  let testDbDir: string;

  beforeEach(() => {
    testDbDir = path.join(os.tmpdir(), `kudbee-test-${Date.now()}`);
    db = new PersistenceLayer(testDbDir);
  });

  afterEach(() => {
    db.close();
    if (fs.existsSync(testDbDir)) {
      fs.rmSync(testDbDir, { recursive: true });
    }
  });

  describe('Dashboard State', () => {
    test('saves and restores dashboard state', async () => {
      const state: DashboardState = {
        sessionId: 'test-session-1',
        panelState: { 'left-sidebar': { open: true, scroll: 42 } },
        viewState: { activeTab: 'metrics' },
        settings: { theme: 'dark' },
        lastUpdate: Date.now(),
        createdAt: Date.now()
      };

      await db.saveDashboardState(state);
      const restored = await db.restoreDashboardState('test-session-1');

      ok(restored);
      strictEqual(restored.sessionId, 'test-session-1');
      deepStrictEqual(restored.panelState, state.panelState);
      deepStrictEqual(restored.viewState, state.viewState);
    });

    test('returns null for non-existent session', async () => {
      const restored = await db.restoreDashboardState('nonexistent');
      strictEqual(restored, null);
    });

    test('updates existing state', async () => {
      const state1: DashboardState = {
        sessionId: 'test-session-2',
        settings: { theme: 'dark' },
        lastUpdate: Date.now(),
        createdAt: Date.now()
      };

      await db.saveDashboardState(state1);

      const state2: DashboardState = {
        ...state1,
        settings: { theme: 'light' },
        lastUpdate: Date.now()
      };

      await db.saveDashboardState(state2);
      const restored = await db.restoreDashboardState('test-session-2');

      ok(restored);
      strictEqual(restored.settings?.theme, 'light');
    });
  });

  describe('Run Metadata', () => {
    test('saves and retrieves run metadata', async () => {
      const run: RunMetadata = {
        runId: 'run-123',
        sessionId: 'session-1',
        goal: 'Write a hello world',
        status: 'completed',
        startTime: 1000,
        endTime: 2000,
        metrics: { tokens: 150, cost: 0.001 },
        files: ['hello.ts'],
        createdAt: 1000
      };

      await db.saveRunMetadata(run);
      const restored = await db.getRunMetadata('run-123');

      ok(restored);
      strictEqual(restored.goal, 'Write a hello world');
      strictEqual(restored.status, 'completed');
      deepStrictEqual(restored.metrics, { tokens: 150, cost: 0.001 });
    });

    test('lists runs for a session', async () => {
      const run1: RunMetadata = {
        runId: 'run-1',
        sessionId: 'session-1',
        goal: 'First goal',
        status: 'completed',
        startTime: 1000,
        createdAt: 1000
      };

      const run2: RunMetadata = {
        runId: 'run-2',
        sessionId: 'session-1',
        goal: 'Second goal',
        status: 'completed',
        startTime: 2000,
        createdAt: 2000
      };

      await db.saveRunMetadata(run1);
      await db.saveRunMetadata(run2);

      const runs = await db.listRuns('session-1', 10);
      strictEqual(runs.length, 2);
      // Should be in reverse chronological order
      strictEqual(runs[0].runId, 'run-2');
      strictEqual(runs[1].runId, 'run-1');
    });

    test('limits run list', async () => {
      for (let i = 0; i < 5; i++) {
        const run: RunMetadata = {
          runId: `run-${i}`,
          sessionId: 'session-1',
          goal: `Goal ${i}`,
          status: 'completed',
          startTime: i * 1000,
          createdAt: i * 1000
        };
        await db.saveRunMetadata(run);
      }

      const runs = await db.listRuns('session-1', 3);
      strictEqual(runs.length, 3);
    });
  });

  describe('Memory Notes', () => {
    test('saves and retrieves memory note', async () => {
      const note: MemoryNote = {
        id: 'note-1',
        sessionId: 'session-1',
        layer: 'org',
        title: 'Python Tips',
        content: 'Use list comprehensions',
        evidence: { source: 'fetch_url', timestamp: Date.now() },
        createdAt: Date.now(),
        updatedAt: Date.now()
      };

      await db.saveMemoryNote(note);
      const restored = await db.getMemoryNote('note-1');

      ok(restored);
      strictEqual(restored.title, 'Python Tips');
      strictEqual(restored.layer, 'org');
      deepStrictEqual(restored.evidence, note.evidence);
    });

    test('lists notes by layer', async () => {
      const orgNote: MemoryNote = {
        id: 'org-1',
        sessionId: 'session-1',
        layer: 'org',
        title: 'Org Note',
        content: 'Content',
        createdAt: Date.now(),
        updatedAt: Date.now()
      };

      const verifiedNote: MemoryNote = {
        id: 'verified-1',
        sessionId: 'session-1',
        layer: 'verified',
        title: 'Verified Fact',
        content: 'Fact',
        createdAt: Date.now(),
        updatedAt: Date.now()
      };

      await db.saveMemoryNote(orgNote);
      await db.saveMemoryNote(verifiedNote);

      const orgNotes = await db.listMemoryNotes('session-1', 'org');
      const verifiedNotes = await db.listMemoryNotes('session-1', 'verified');

      strictEqual(orgNotes.length, 1);
      strictEqual(verifiedNotes.length, 1);
      strictEqual(orgNotes[0].layer, 'org');
      strictEqual(verifiedNotes[0].layer, 'verified');
    });

    test('updates memory note', async () => {
      const note: MemoryNote = {
        id: 'note-1',
        sessionId: 'session-1',
        layer: 'org',
        title: 'Original',
        content: 'Original content',
        createdAt: Date.now(),
        updatedAt: Date.now()
      };

      await db.saveMemoryNote(note);

      const updated: MemoryNote = {
        ...note,
        title: 'Updated',
        content: 'Updated content',
        updatedAt: Date.now()
      };

      await db.saveMemoryNote(updated);
      const restored = await db.getMemoryNote('note-1');

      ok(restored);
      strictEqual(restored.title, 'Updated');
      strictEqual(restored.content, 'Updated content');
    });
  });

  describe('Persistence across restarts', () => {
    test('data survives database close and reopen', async () => {
      const state: DashboardState = {
        sessionId: 'persistent-test',
        settings: { theme: 'dark' },
        lastUpdate: Date.now(),
        createdAt: Date.now()
      };

      await db.saveDashboardState(state);
      db.close();

      // Reopen same database
      const db2 = new PersistenceLayer(testDbDir);
      const restored = await db2.restoreDashboardState('persistent-test');
      db2.close();

      ok(restored);
      strictEqual(restored.settings?.theme, 'dark');
    });
  });

  describe('Stats', () => {
    test('reports database statistics', async () => {
      const run: RunMetadata = {
        runId: 'run-1',
        sessionId: 'session-1',
        goal: 'Test',
        status: 'completed',
        startTime: Date.now(),
        createdAt: Date.now()
      };

      const note: MemoryNote = {
        id: 'note-1',
        sessionId: 'session-1',
        layer: 'org',
        title: 'Note',
        content: 'Content',
        createdAt: Date.now(),
        updatedAt: Date.now()
      };

      await db.saveRunMetadata(run);
      await db.saveMemoryNote(note);

      const stats = db.getStats();
      ok(stats.dbSize > 0);
      strictEqual(stats.runs, 1);
      strictEqual(stats.notes, 1);
    });
  });
});
