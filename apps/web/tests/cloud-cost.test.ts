// Cost accounting for cloud models: reasoning tokens are counted, and the provider's own billed cost (xAI reports it in ticks of 1e-10 USD) beats any price estimate.
import assert from 'node:assert/strict';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { after, before, beforeEach, test } from 'node:test';
import type { AgentHooks } from '../agent.ts';
import { runToolAgent } from '../agent.ts';
import { MODEL_PRICING, costUsd } from '../cloud-models.ts';

const KEYS = ['XAI_API_KEY', 'XAI_BASE_URL', 'INCEPTION_API_KEY', 'INCEPTION_BASE_URL'] as const;
const saved: Record<string, string | undefined> = {};
before(() => { for (const k of KEYS) saved[k] = process.env[k]; });
beforeEach(() => { for (const k of KEYS) delete process.env[k]; });
after(() => { for (const k of KEYS) { if (saved[k] === undefined) delete process.env[k]; else process.env[k] = saved[k]; } });

async function stub(usage: Record<string, unknown>): Promise<{ base: string; close: () => Promise<void> }> {
  const server = http.createServer((req, res) => { req.resume(); req.on('end', () => { res.writeHead(200, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ choices: [{ message: { role: 'assistant', content: 'done' } }], usage })); }); });
  await new Promise<void>((r) => server.listen(0, '127.0.0.1', r));
  return { base: `http://127.0.0.1:${(server.address() as AddressInfo).port}/v1`, close: () => new Promise<void>((r) => server.close(() => r())) };
}
const hooks = (events: Array<Record<string, unknown>> = []): AgentHooks => ({ signal: new AbortController().signal, workspace: '/tmp', resolvePath: (r: string) => r, onThought: () => {}, onEvent: (e: unknown) => { events.push(e as Record<string, unknown>); }, onFilesChanged: () => {}, checkBudget: () => null, approvedDomains: new Set(), requestApproval: async () => true, remember: async () => ({ id: 'x' }), recall: async () => ({ backend: 't', results: [] }), rssFeed: async () => ({ items: [] }) } as unknown as AgentHooks);

test('the xAI prices reproduce xAI\'s own billed cost for real recorded calls', () => {
  // Recorded grok-4.3 calls: [uncached prompt, cached prompt, output + reasoning tokens, cost_in_usd_ticks]. Cached input is billed at $0.20 per million.
  for (const [uncached, cached, out, ticks] of [[69, 128, 173, 5443500], [353, 128, 437, 15593500], [79, 128, 192, 6043500], [521, 128, 383, 16343500], [70, 128, 217, 6556000]] as const) {
    const usd = (uncached * MODEL_PRICING['grok-4.3']!.input + cached * 0.2 + out * MODEL_PRICING['grok-4.3']!.output) / 1e6;
    assert.ok(Math.abs(usd - ticks / 1e10) < 1e-9, `${uncached}/${cached}/${out}: ${usd} vs ${ticks / 1e10}`);
  }
  // grok-build-0.1: 75 uncached + 128 cached + 196 output (1 + 195 reasoning) tokens billed 4926000 ticks.
  assert.ok(Math.abs((75 * MODEL_PRICING['grok-build-0.1']!.input + 128 * 0.2 + 196 * MODEL_PRICING['grok-build-0.1']!.output) / 1e6 - 4926000 / 1e10) < 1e-9);
  assert.equal(costUsd('grok-4.3', 1_000_000, 1_000_000), 3.75);
});

test('a billed cost from the provider is used as is, and reasoning tokens are counted as output', async () => {
  const s = await stub({ prompt_tokens: 209, completion_tokens: 1, completion_tokens_details: { reasoning_tokens: 330 }, cost_in_usd_ticks: 8871500 });
  process.env.XAI_BASE_URL = s.base; process.env.XAI_API_KEY = 'k'; const events: Array<Record<string, unknown>> = [];
  try {
    const r = await runToolAgent('say done', 'grok-4.3', 2, 0, [], hooks(events), '');
    assert.equal(r.success, true);
    assert.equal(r.cost_usd, 8871500 / 1e10);
    assert.equal(r.completion_tokens, 331); assert.equal(r.tokens, 209 + 331);
    assert.equal(events.find((e) => e.kind === 'model')?.cost_usd, 8871500 / 1e10);
  } finally { await s.close(); }
});

test('without a billed cost the price is applied to the tokens INCLUDING reasoning tokens', async () => {
  const s = await stub({ prompt_tokens: 1000, completion_tokens: 100, completion_tokens_details: { reasoning_tokens: 900 } });
  process.env.XAI_BASE_URL = s.base; process.env.XAI_API_KEY = 'k';
  try {
    const r = await runToolAgent('x', 'grok-4.3', 2, 0, [], hooks(), '');
    assert.equal(r.cost_usd, costUsd('grok-4.3', 1000, 1000)); assert.equal(r.completion_tokens, 1000);
  } finally { await s.close(); }
});

test('a nonsense billed cost is ignored, and a provider that reports neither field behaves as before', async () => {
  for (const ticks of [-5, 'abc', null]) {
    const s = await stub({ prompt_tokens: 1000, completion_tokens: 200, cost_in_usd_ticks: ticks });
    process.env.INCEPTION_BASE_URL = s.base; process.env.INCEPTION_API_KEY = 'k';
    try { const r = await runToolAgent('x', 'mercury-2', 2, 0, [], hooks(), ''); assert.equal(r.cost_usd, costUsd('mercury-2', 1000, 200), String(ticks)); assert.equal(r.completion_tokens, 200); } finally { await s.close(); }
  }
});
