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
  const keyed = await get({ runCount: () => 2, ollamaBaseUrl: 'http://127.0.0.1:9', env: { XAI_API_KEY: 'xai-secret-1234567890' } });
  assert.equal(keyed.ready, true); assert.equal(keyed.steps.find((s) => s.id === 'first-goal')?.done, true);
  assert.ok(!JSON.stringify(keyed).includes('secret-1234567890'));
});

test('a reachable Ollama counts as a model', async () => {
  const fake = http.createServer((_q, r) => r.end('{"models":[]}')); const port = await listen(fake);
  try { assert.equal((await get({ runCount: () => 0, ollamaBaseUrl: `http://127.0.0.1:${port}`, env: {} })).ready, true); } finally { fake.close(); }
});
