import assert from 'node:assert/strict';
import http from 'node:http';
import { test } from 'node:test';
import express from 'express';
import { registerActiveRepoRoutes } from '../routes/active-repo.ts';

const listen = (s: http.Server): Promise<number> => new Promise((r) => s.listen(0, '127.0.0.1', () => r((s.address() as { port: number }).port)));

test('GET /api/project answers for the chosen repository, and for none', async () => {
  let chosen: { name: string; root: string; repo: string | null; } | null = null;
  const manager = { active: () => chosen, list: () => [], tag: () => 'repo:acme:demo', set() {}, clear() {} } as any;
  const app = express();
  registerActiveRepoRoutes(app, { manager, profileId: () => 'p', isHuman: () => true, project: { runs: () => [{ id: 'r', repo: 'demo', goal: 'g', status: 'completed', cost_usd: 0.5, files: [], started_at: Date.now() }], audit: () => [], tokens: () => [] } });
  const s = http.createServer(app); const port = await listen(s);
  try {
    const none = await (await fetch(`http://127.0.0.1:${port}/api/project`)).json() as any;
    assert.equal(none.repo, null);
    chosen = { name: 'demo', root: '/nonexistent/path', repo: 'acme/demo' };
    const some = await (await fetch(`http://127.0.0.1:${port}/api/project`)).json() as any;
    assert.equal(some.repo.name, 'demo'); assert.equal(some.runs.count, 1); assert.equal(some.runs.total_usd, 0.5);
    assert.equal(some.changes.count, 0, 'an unreadable repository folder shows no changes instead of an error');
  } finally { s.close(); }
});
