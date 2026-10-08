import assert from 'node:assert/strict';
import http from 'node:http';
import { test } from 'node:test';
import express from 'express';
import { registerSetupRoute } from '../routes/setup.ts';

const listen = (s: http.Server): Promise<number> => new Promise((r) => s.listen(0, '127.0.0.1', () => r((s.address() as { port: number }).port)));
async function get(deps: Parameters<typeof registerSetupRoute>[1]) {
  const app = express(); registerSetupRoute(app, deps);
  const s = http.createServer(app); const port = await listen(s);
  try { return await (await fetch(`http://127.0.0.1:${port}/api/setup`)).json() as { ready: boolean; steps: Array<{ id: string; done: boolean }> }; } finally { s.close(); }
}

test('with no key and no Ollama the route says not ready; a key makes it ready; no key value is returned', async () => {
  const none = await get({ runCount: () => 0, ollamaBaseUrl: 'http://127.0.0.1:9', env: {} });
  assert.equal(none.ready, false);
  const keyed = await get({ runCount: () => 2, ollamaBaseUrl: 'http://127.0.0.1:9', env: { XAI_API_KEY: 'xai-secret-1234567890' } }); // secret-scan:ignore (fixture)
  assert.equal(keyed.ready, true); assert.equal(keyed.steps.find((s) => s.id === 'first-goal')?.done, true);
  assert.ok(!JSON.stringify(keyed).includes('secret-1234567890'));
});

test('a reachable Ollama counts as a model', async () => {
  const fake = http.createServer((_q, r) => r.end('{"models":[]}')); const port = await listen(fake);
  try { assert.equal((await get({ runCount: () => 0, ollamaBaseUrl: `http://127.0.0.1:${port}`, env: {} })).ready, true); } finally { fake.close(); }
});

test('POST /api/notify/test reports the result of the test message', async () => {
  const app = express(); registerSetupRoute(app, { runCount: () => 0, ollamaBaseUrl: 'http://127.0.0.1:9', env: {}, sendTest: async () => ({ ok: false, error: 'No webhook is set (KUDBEE_NOTIFY_WEBHOOK)' }) });
  const bad = http.createServer(app); const p1 = await listen(bad);
  try { const r = await fetch(`http://127.0.0.1:${p1}/api/notify/test`, { method: 'POST' }); assert.equal(r.status, 400); assert.match((await r.json() as { error: string }).error, /No webhook/); } finally { bad.close(); }
  const app2 = express(); registerSetupRoute(app2, { runCount: () => 0, ollamaBaseUrl: 'http://127.0.0.1:9', env: {}, sendTest: async () => ({ ok: true }) });
  const good = http.createServer(app2); const p2 = await listen(good);
  try { const r = await fetch(`http://127.0.0.1:${p2}/api/notify/test`, { method: 'POST' }); assert.equal(r.status, 200); } finally { good.close(); }
});
