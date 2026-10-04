// Unit tests for routes/runs.ts: the list cache, persistent-history fallback, run detail and token-stats endpoints.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import express from 'express';
import { registerRunsRoutes } from '../routes/runs.ts';
import type { RunRecord, RunStore } from '../runs.ts';
import type { PersistenceLayer } from '../persistence.ts';

const run = (over: Partial<RunRecord>): RunRecord => ({ id: 'r1', session_id: 's1', goal: 'g', status: 'completed', started_at: 1, ended_at: 2, prompt_tokens: 1, completion_tokens: 2, cost_usd: 0.01, files: [], steps: [], ...over } as RunRecord);

let server: http.Server;
let base: string;
before(async () => {
  // A single app whose runs/db can be swapped per test via headers is overkill; mount the union of behaviours.
  const app = express();
  const runs = [run({ id: 'r1', session_id: 's1', goal: 'a' }), run({ id: 'r2', session_id: 's2', goal: 'b' })];
  const runStore = { list: (n: number) => runs.slice(0, n), get: (id: string) => runs.find((r) => r.id === id) } as unknown as RunStore;
  const persistence = {
    listRuns: async (sid: string, n: number) => sid === 'db-session' ? [run({ id: 'd1', session_id: sid, metrics: { tokens_saved_est: 40 } } as unknown as Partial<RunRecord>)] : sid === 'boom' ? Promise.reject(new Error('db down')) : [],
  } as unknown as Pick<PersistenceLayer, 'listRuns'>;
  registerRunsRoutes(app, { runStore, persistence });
  await new Promise<void>((r) => { server = app.listen(0, '127.0.0.1', () => r()); });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
after(() => new Promise<void>((r) => { server.close(() => r()); }));

test('GET /api/runs lists runs without steps and serves the cached copy on a repeat call', async () => {
  const first = await (await fetch(`${base}/api/runs?limit=1`)).json() as { runs: Array<Record<string, unknown>> };
  assert.equal(first.runs.length, 1);
  assert.equal(first.runs[0].steps, undefined);
  assert.equal(first.runs[0].step_count, 0);
  const second = await (await fetch(`${base}/api/runs?limit=1`)).json() as { runs: unknown[] };
  assert.equal(second.runs.length, 1);
});

test('GET /api/runs/:id returns a run or 404', async () => {
  assert.equal((await fetch(`${base}/api/runs/r1`)).status, 200);
  assert.equal((await fetch(`${base}/api/runs/missing`)).status, 404);
});

test('GET /api/runs/history needs a session, prefers the DB and falls back to the JSON store', async () => {
  assert.equal((await fetch(`${base}/api/runs/history`)).status, 400);
  const db = await (await fetch(`${base}/api/runs/history?sessionId=db-session`)).json() as { source: string };
  assert.equal(db.source, 'db');
  const json = await (await fetch(`${base}/api/runs/history?sessionId=json-session`)).json() as { source: string; runs: unknown[] };
  assert.equal(json.source, 'json');
  assert.equal(json.runs.length, 0);
});

test('GET /api/runs/history reports a DB failure as 500', async () => {
  assert.equal((await fetch(`${base}/api/runs/history?sessionId=boom`)).status, 500);
});

test('GET /api/stats/tokens needs a session and aggregates savings chronologically', async () => {
  assert.equal((await fetch(`${base}/api/stats/tokens`)).status, 400);
  const stats = await (await fetch(`${base}/api/stats/tokens?sessionId=db-session`)).json() as { totalTokensSavedEst: number; totalRunsTracked: number };
  assert.equal(stats.totalTokensSavedEst, 40);
  assert.equal(stats.totalRunsTracked, 1);
});

test('GET /api/stats/tokens reports a DB failure as 500', async () => {
  assert.equal((await fetch(`${base}/api/stats/tokens?sessionId=boom`)).status, 500);
});
