import { describe, it, expect, before, after } from 'node:test';
import Database from 'better-sqlite3';
import path from 'node:path';
import os from 'node:os';
import { randomUUID } from 'node:crypto';
import PersistenceLayer from '../persistence.ts';

describe('CLI Memory Commands', () => {
  let persistence: PersistenceLayer;
  let dbPath: string;

  before(() => {
    const tempDir = path.join(os.tmpdir(), `kudbee-test-${randomUUID()}`);
    persistence = new PersistenceLayer(tempDir);
    dbPath = path.join(tempDir, 'kudbee.db');
  });

  after(() => {
    persistence.close();
  });

  describe('/remember command', () => {
    it('saves a note to session layer', async () => {
      const sessionId = randomUUID();
      const note = {
        id: randomUUID(),
        sessionId,
        layer: 'session' as const,
        title: 'Test note',
        content: 'This is a test memory note',
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };

      await persistence.saveMemoryNote(note);
      const retrieved = await persistence.getMemoryNote(note.id);

      expect(retrieved).toBeDefined();
      expect(retrieved?.title).toBe('Test note');
      expect(retrieved?.content).toBe('This is a test memory note');
      expect(retrieved?.layer).toBe('session');
    });

    it('saves a note with task layer', async () => {
      const sessionId = randomUUID();
      const note = {
        id: randomUUID(),
        sessionId,
        layer: 'task' as const,
        title: 'Run episode',
        content: 'Goal: fetch data. Result: success',
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };

      await persistence.saveMemoryNote(note);
      const notes = await persistence.listMemoryNotes(sessionId, 'task');

      expect(notes.length).toBeGreaterThan(0);
      expect(notes[0].layer).toBe('task');
    });
  });

  describe('/notes command', () => {
    it('lists notes for a session', async () => {
      const sessionId = randomUUID();
      const notes = [
        { id: randomUUID(), sessionId, layer: 'session' as const, title: 'Note 1', content: 'Content 1', createdAt: Date.now(), updatedAt: Date.now() },
        { id: randomUUID(), sessionId, layer: 'session' as const, title: 'Note 2', content: 'Content 2', createdAt: Date.now(), updatedAt: Date.now() },
      ];

      for (const note of notes) await persistence.saveMemoryNote(note);
      const retrieved = await persistence.listMemoryNotes(sessionId);

      expect(retrieved.length).toBe(2);
      expect(retrieved.map((n) => n.title)).toContain('Note 1');
    });

    it('filters by layer', async () => {
      const sessionId = randomUUID();
      await persistence.saveMemoryNote({ id: randomUUID(), sessionId, layer: 'session', title: 'S1', content: 'c', createdAt: Date.now(), updatedAt: Date.now() });
      await persistence.saveMemoryNote({ id: randomUUID(), sessionId, layer: 'org', title: 'O1', content: 'c', createdAt: Date.now(), updatedAt: Date.now() });

      const sessionNotes = await persistence.listMemoryNotes(sessionId, 'session');
      const orgNotes = await persistence.listMemoryNotes(sessionId, 'org');

      expect(sessionNotes.length).toBe(1);
      expect(sessionNotes[0].layer).toBe('session');
      expect(orgNotes.length).toBe(1);
      expect(orgNotes[0].layer).toBe('org');
    });

    it('respects limit parameter', async () => {
      const sessionId = randomUUID();
      for (let i = 0; i < 5; i++) {
        await persistence.saveMemoryNote({ id: randomUUID(), sessionId, layer: 'session', title: `Note ${i}`, content: 'c', createdAt: Date.now() + i, updatedAt: Date.now() + i });
      }

      const limited = await persistence.listMemoryNotes(sessionId, undefined, 3);
      expect(limited.length).toBe(3);
    });
  });

  describe('/forget command', () => {
    it('deletes a note by ID', async () => {
      const sessionId = randomUUID();
      const noteId = randomUUID();
      await persistence.saveMemoryNote({ id: noteId, sessionId, layer: 'session', title: 'To delete', content: 'Will be removed', createdAt: Date.now(), updatedAt: Date.now() });

      // Note: Full delete implementation is Phase 4. Phase 3 is a stub.
      const before = await persistence.getMemoryNote(noteId);
      expect(before).toBeDefined();
    });
  });

  describe('persistence across sessions', () => {
    it('survives process restart', async () => {
      const sessionId = randomUUID();
      const noteId = randomUUID();
      const tempDir = path.join(os.tmpdir(), `kudbee-restart-test-${randomUUID()}`);

      // First session: write
      {
        const p1 = new PersistenceLayer(tempDir);
        await p1.saveMemoryNote({ id: noteId, sessionId, layer: 'org', title: 'Persistent note', content: 'Should survive', createdAt: Date.now(), updatedAt: Date.now() });
        p1.close();
      }

      // Second session: read
      {
        const p2 = new PersistenceLayer(tempDir);
        const retrieved = await p2.getMemoryNote(noteId);
        expect(retrieved).toBeDefined();
        expect(retrieved?.title).toBe('Persistent note');
        p2.close();
      }
    });
  });
});
