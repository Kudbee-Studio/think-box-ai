// The cloud worker-agent registry: Mercury-2 and DeepSeek share one OpenAI-compatible path; only endpoint, key, price and label differ. No real network: a local stub records what each model is sent.
import assert from 'node:assert/strict';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { after, before, beforeEach, test } from 'node:test';
import { CLOUD_MODELS, cloudConfigured, cloudModel, configuredCloudModels, costUsd, inceptionConfigured, isCloudModel, providerOf, runToolAgent, type AgentHooks } from '../agent.ts';
import { defaultAgentModel } from '../cloud-routing.ts';
import { createModelClients } from '../ollama-client.ts';

const KEYS = ['INCEPTION_API_KEY', 'DEEPSEEK_API_KEY', 'XAI_API_KEY', 'INCEPTION_BASE_URL', 'DEEPSEEK_BASE_URL', 'XAI_BASE_URL'] as const;
const saved: Record<string, string | undefined> = {};
before(() => { for (const k of KEYS) saved[k] = process.env[k]; });
beforeEach(() => { for (const k of KEYS) delete process.env[k]; });
after(() => { for (const k of KEYS) { if (saved[k] === undefined) delete process.env[k]; else process.env[k] = saved[k]; } });

interface Seen { url: string; auth: string | undefined; model: string }
async function stub(status = 200): Promise<{ base: string; seen: Seen[]; close: () => Promise<void> }> {
  const seen: Seen[] = [];
  const server = http.createServer((req, res) => {
    let body = ''; req.on('data', (c) => { body += c; });
    req.on('end', () => {
      seen.push({ url: req.url ?? '', auth: req.headers.authorization, model: (JSON.parse(body) as { model: string }).model });
      res.writeHead(status, { 'Content-Type': 'application/json' });
      res.end(status === 200 ? JSON.stringify({ choices: [{ message: { role: 'assistant', content: 'done' } }], usage: { prompt_tokens: 1000, completion_tokens: 500 } }) : 'nope');
    });
  });
  await new Promise<void>((r) => server.listen(0, '127.0.0.1', r));
  return { base: `http://127.0.0.1:${(server.address() as AddressInfo).port}/v1`, seen, close: () => new Promise<void>((r) => server.close(() => r())) };
}
const hooks = (): AgentHooks => ({ signal: new AbortController().signal, workspace: '/tmp', resolvePath: (r: string) => r, onThought: () => {}, onEvent: () => {}, onFilesChanged: () => {}, checkBudget: () => null, approvedDomains: new Set(), requestApproval: async () => true, remember: async () => ({ id: 'x' }), recall: async () => ({ backend: 't', results: [] }), rssFeed: async () => ({ items: [] }) } as unknown as AgentHooks);

test('the registry lists Mercury-2, DeepSeek and xAI, each with its own key and endpoint variables', () => {
  assert.deepEqual(CLOUD_MODELS.map((m) => [m.name, m.provider, m.keyEnv]), [['mercury-2', 'inception', 'INCEPTION_API_KEY'], ['deepseek-flash', 'deepseek', 'DEEPSEEK_API_KEY'], ['grok-4.3', 'xai', 'XAI_API_KEY'], ['grok-4.7', 'xai', 'XAI_API_KEY'], ['grok-build-0.1', 'xai', 'XAI_API_KEY']]);
  assert.ok(isCloudModel('deepseek-flash') && isCloudModel('mercury-2') && isCloudModel('grok-4.3'));
  assert.equal(providerOf('grok-4.3'), 'xai'); assert.equal(cloudModel('grok-4.3')?.vendor, 'xAI');
  assert.ok(!isCloudModel('qwen2.5:1.5b') && !isCloudModel('deepseek-chat'), 'an alias outside the registry is not a registered model');
  assert.equal(cloudModel('deepseek-flash')?.vendor, 'DeepSeek');
  assert.equal(providerOf('deepseek-flash'), 'deepseek'); assert.equal(providerOf('mercury-2'), 'inception'); assert.equal(providerOf('qwen2.5:1.5b'), 'ollama');
});

test('configured models and the default follow which keys are set', () => {
  assert.deepEqual(configuredCloudModels(), []); assert.equal(defaultAgentModel(), null);
  process.env.DEEPSEEK_API_KEY = 'd'; assert.deepEqual(configuredCloudModels().map((m) => m.name), ['deepseek-flash']);
  assert.equal(defaultAgentModel(), 'deepseek-flash'); assert.equal(inceptionConfigured(), false); assert.ok(cloudConfigured('deepseek-flash'));
  process.env.INCEPTION_API_KEY = 'i'; assert.deepEqual(configuredCloudModels().map((m) => m.name), ['mercury-2', 'deepseek-flash']);
  assert.equal(defaultAgentModel(), 'mercury-2', 'Mercury stays the default when both are set');
  process.env.XAI_API_KEY = 'x'; assert.deepEqual(configuredCloudModels().map((m) => m.name), ['mercury-2', 'deepseek-flash', 'grok-4.3', 'grok-4.7', 'grok-build-0.1']);
  delete process.env.INCEPTION_API_KEY; delete process.env.DEEPSEEK_API_KEY; assert.equal(defaultAgentModel(), 'grok-4.3', 'xAI alone is enough');
});

test('grok-4.3 and deepseek-flash have a price, so a budget can count it; an unknown model still costs nothing', () => {
  const usd = costUsd('deepseek-flash', 1_000_000, 1_000_000);
  assert.ok(usd > 0 && usd >= costUsd('mercury-2', 1_000_000, 1_000_000), 'the estimate is not below Mercury');
  assert.ok(costUsd('grok-4.3', 1_000_000, 1_000_000) > 0);
  assert.equal(costUsd('some-unknown-model', 1000, 1000), 0);
});

test('deepseek-flash is sent to the DeepSeek endpoint with the DeepSeek key, and cost is counted', async () => {
  const s = await stub(); process.env.DEEPSEEK_BASE_URL = s.base; process.env.DEEPSEEK_API_KEY = 'ds-secret'; process.env.INCEPTION_API_KEY = 'inc-secret';
  try {
    const r = await runToolAgent('say done', 'deepseek-flash', 3, 0, [], hooks(), '');
    assert.equal(r.success, true);
    assert.deepEqual(s.seen.map((x) => [x.url, x.auth, x.model]), [['/v1/chat/completions', 'Bearer ds-secret', 'deepseek-flash']]);
    assert.ok(r.cost_usd > 0);
  } finally { await s.close(); }
});

test('grok-4.3 is sent to the xAI endpoint with the xAI key', async () => {
  const s = await stub(); process.env.XAI_BASE_URL = s.base; process.env.XAI_API_KEY = 'xai-secret'; process.env.INCEPTION_API_KEY = 'inc-secret';
  try {
    const r = await runToolAgent('say done', 'grok-4.3', 3, 0, [], hooks(), '');
    assert.equal(r.success, true);
    assert.deepEqual(s.seen.map((x) => [x.auth, x.model]), [['Bearer xai-secret', 'grok-4.3']]);
    assert.ok(r.cost_usd > 0);
  } finally { await s.close(); }
  delete process.env.XAI_API_KEY;
  assert.equal((await runToolAgent('x', 'grok-4.3', 2, 0, [], hooks(), '')).error, 'XAI_API_KEY is not set in .env');
});

test('mercury-2 still uses the Inception endpoint and key, and an unregistered name falls back to them', async () => {
  const s = await stub(); process.env.INCEPTION_BASE_URL = s.base; process.env.INCEPTION_API_KEY = 'inc-secret'; process.env.DEEPSEEK_API_KEY = 'ds-secret';
  try {
    await runToolAgent('x', 'mercury-2', 2, 0, [], hooks(), ''); await runToolAgent('x', 'deepseek-chat', 2, 0, [], hooks(), '');
    assert.deepEqual(s.seen.map((x) => [x.auth, x.model]), [['Bearer inc-secret', 'mercury-2'], ['Bearer inc-secret', 'deepseek-chat']]);
  } finally { await s.close(); }
});

test('a missing key names the right variable, and an HTTP error names the right vendor', async () => {
  const none = await runToolAgent('x', 'deepseek-flash', 2, 0, [], hooks(), '');
  assert.equal(none.success, false); assert.match(String(none.error), /DEEPSEEK_API_KEY is not set/);
  const s = await stub(500); process.env.DEEPSEEK_BASE_URL = s.base; process.env.DEEPSEEK_API_KEY = 'k';
  try { const r = await runToolAgent('x', 'deepseek-flash', 2, 0, [], hooks(), ''); assert.match(String(r.error), /^DeepSeek API HTTP 500/); } finally { await s.close(); }
});

test('the dashboard model list shows each configured cloud model as a worker agent', async () => {
  const clients = createModelClients({ ollamaBaseUrl: 'http://127.0.0.1:9', janusBaseUrl: 'http://127.0.0.1:9', janusEnabled: () => false });
  assert.deepEqual((await clients.listModels().catch(() => [])).filter((m) => (m as { agent?: boolean }).agent), []);
  process.env.DEEPSEEK_API_KEY = 'd'; process.env.INCEPTION_API_KEY = 'i'; process.env.XAI_API_KEY = 'x';
  const list = (await clients.listModels()) as Array<{ name: string; provider: string; vendor?: string; agent?: boolean }>;
  assert.deepEqual(list.filter((m) => m.agent).map((m) => [m.name, m.provider, m.vendor]), [['mercury-2', 'inception', 'Inception'], ['deepseek-flash', 'deepseek', 'DeepSeek'], ['grok-4.3', 'xai', 'xAI'], ['grok-4.7', 'xai', 'xAI'], ['grok-build-0.1', 'xai', 'xAI']]);
});
