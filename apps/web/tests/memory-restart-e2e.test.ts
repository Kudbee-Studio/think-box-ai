import { describe, it, before, after } from 'node:test';
import { expect } from './test-helpers.ts';
import path from 'node:path';
import os from 'os';
import { randomUUID } from 'node:crypto';
import PersistenceLayer from '../persistence.ts';

describe('Memory Restart Proof (E2E)', () => {
  const tempDbDir = path.join(os.tmpdir(), `kudbee-e2e-restart-${randomUUID()}`);

  after(() => {
    // Cleanup is optional; temp dirs can be left for inspection
  });

  it('survives full restart: write → close → reopen → verify', async () => {
    const sessionId = randomUUID();
    const runId = randomUUID();

    // STEP 1: First session — write memory and run metadata
    {
      const p1 = new PersistenceLayer(tempDbDir);

      // Save a memory note (task layer)
      await p1.saveMemoryNote({
        id: randomUUID(),
        sessionId,
        layer: 'task',
        title: 'Run episode #1',
        content: 'Goal: fetch data. Result: completed successfully.',
        createdAt: Date.now(),
        updatedAt: Date.now(),
      });

      // Save run metadata
      await p1.saveRunMetadata({
        runId,
        sessionId,
        goal: 'Fetch API data',
        status: 'completed',
        startTime: Date.now() - 10000,
        endTime: Date.now(),
        metrics: {
          tokens: 1500,
          cost_usd: 0.0042,
          duration_ms: 10000,
        },
        files: ['output.json'],
        createdAt: Date.now() - 10000,
      });

      // Save dashboard state
      await p1.saveDashboardState({
        sessionId,
        panelState: { selectedRun: runId },
        settings: { theme: 'dark', model: 'mercury-2' },
        lastUpdate: Date.now(),
        createdAt: Date.now(),
      });

      p1.close();
    }

    // STEP 2: Simulate restart — open a new persistence instance
    {
      const p2 = new PersistenceLayer(tempDbDir);

      // Verify memory note survived
      const notes = await p2.listMemoryNotes(sessionId, 'task');
      expect(notes.length).toBeGreaterThan(0);
      expect(notes[0].title).toBe('Run episode #1');

      // Verify run metadata survived
      const run = await p2.getRunMetadata(runId);
      expect(run).toBeDefined();
      expect(run?.goal).toBe('Fetch API data');
      expect(run?.status).toBe('completed');
      expect(run?.metrics?.tokens).toBe(1500);

      // Verify dashboard state survived
      const dash = await p2.restoreDashboardState(sessionId);
      expect(dash).toBeDefined();
      expect(dash?.panelState?.selectedRun).toBe(runId);
      expect(dash?.settings?.model).toBe('mercury-2');

      p2.close();
    }

    // STEP 3: Verify data is still there after another restart
    {
      const p3 = new PersistenceLayer(tempDbDir);
      const run2 = await p3.getRunMetadata(runId);
      expect(run2?.goal).toBe('Fetch API data');
      p3.close();
    }
  });

  it('handles multiple sessions independently', async () => {
    const session1 = randomUUID();
    const session2 = randomUUID();

    // Write to both sessions
    {
      const p = new PersistenceLayer(tempDbDir);

      await p.saveMemoryNote({ id: randomUUID(), sessionId: session1, layer: 'session', title: 'S1', content: 'Content 1', createdAt: Date.now(), updatedAt: Date.now() });
      await p.saveMemoryNote({ id: randomUUID(), sessionId: session2, layer: 'session', title: 'S2', content: 'Content 2', createdAt: Date.now(), updatedAt: Date.now() });

      p.close();
    }

    // Read and verify isolation
    {
      const p = new PersistenceLayer(tempDbDir);
      const notes1 = await p.listMemoryNotes(session1);
      const notes2 = await p.listMemoryNotes(session2);

      expect(notes1.length).toBe(1);
      expect(notes2.length).toBe(1);
      expect(notes1[0].title).toBe('S1');
      expect(notes2[0].title).toBe('S2');

      p.close();
    }
  });

  it('run history aggregates correctly on restart', async () => {
    const sessionId = randomUUID();

    // Write multiple runs
    {
      const p = new PersistenceLayer(tempDbDir);
      for (let i = 0; i < 3; i++) {
        await p.saveRunMetadata({
          runId: randomUUID(),
          sessionId,
          goal: `Goal ${i}`,
          status: 'completed',
          startTime: Date.now() - (3 - i) * 5000,
          endTime: Date.now(),
          metrics: { tokens: 100 * (i + 1), cost_usd: 0.001 * (i + 1) },
          files: [],
          createdAt: Date.now() - (3 - i) * 5000,
        });
      }
      p.close();
    }

    // Read all runs after restart
    {
      const p = new PersistenceLayer(tempDbDir);
      const runs = await p.listRuns(sessionId, 50);
      expect(runs.length).toBe(3);
      expect(runs[0].goal).toMatch(/Goal \d/);
      p.close();
    }
  });
});
