// Cloud model ranking from measured runs, and failover when a provider fails before doing anything. No real network: local stubs stand in for each provider.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import path from 'node:path';
import { after, before, beforeEach, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import type { AgentHooks, AgentRunResult } from '../agent.ts';
import { CLOUD_MEASUREMENTS, MEASUREMENT_ALIASES, defaultAgentModel, estCostPerTask, isProviderFailure, rankCloudModels, runToolAgentWithFailover, type CloudMeasurement } from '../cloud-routing.ts';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const KEYS = ['INCEPTION_API_KEY', 'DEEPSEEK_API_KEY', 'XAI_API_KEY', 'INCEPTION_BASE_URL', 'DEEPSEEK_BASE_URL', 'XAI_BASE_URL', 'KUDBEE_CLOUD_ROUTING', 'KUDBEE_CLOUD_FAILOVER'] as const;
const saved: Record<string, string | undefined> = {};
before(() => { for (const k of KEYS) saved[k] = process.env[k]; });
beforeEach(() => { for (const k of KEYS) delete process.env[k]; });
after(() => { for (const k of KEYS) { if (saved[k] === undefined) delete process.env[k]; else process.env[k] = saved[k]; } });

test('the measurement table is exactly what the evidence files say (provenance)', () => {
  const median = (xs: number[]): number => { const s = [...xs].sort((a, b) => a - b); return s.length % 2 ? s[(s.length - 1) / 2]! : (s[s.length / 2 - 1]! + s[s.length / 2]!) / 2; };
  type Row = { model: string; category: string; wall_ms: number; tokens: number; cost_usd: number };
  const load = (files: string[], model: string): Row[] => files.flatMap((src) => (JSON.parse(fs.readFileSync(path.join(repoRoot, src), 'utf8')) as { rows: Row[] }).rows.filter((r) => (MEASUREMENT_ALIASES[r.model] ?? r.model) === model));
  for (const m of CLOUD_MEASUREMENTS) {
    const pooled = load(m.sources, m.model);
    assert.equal(pooled.length, m.tasks, `${m.model} tasks`);
    assert.equal(pooled.filter((r) => r.category === 'success').length, m.success, `${m.model} success`);
    const cost = load(m.cost_sources, m.model);
    assert.equal(cost.length, 27, `${m.model} P3.57 rows`);
    assert.equal(Math.round(median(cost.map((r) => r.cost_usd)) * 1e6) / 1e6, m.median_usd, `${m.model} median usd`);
    assert.equal(Math.round(median(cost.map((r) => r.wall_ms))), m.median_ms, `${m.model} median ms`);
    assert.equal(Math.round(median(cost.map((r) => r.tokens))), m.median_tokens, `${m.model} median tokens`);
    assert.ok(m.cost_sources.every((c) => m.sources.includes(c)), 'cost sources are among the sources');
  }
});

test('ranking: eligible models by measured cost per task: Mercury, DeepSeek, grok-build-0.1, grok-4.3, grok-4.7', () => {
  const r = rankCloudModels(['grok-4.7', 'grok-4.3', 'grok-build-0.1', 'deepseek-flash', 'mercury-2']);
  assert.deepEqual(r.map((x) => x.model), ['mercury-2', 'deepseek-flash', 'grok-build-0.1', 'grok-4.3', 'grok-4.7']);
  assert.match(r[0]!.reason, /64\/66 verified fixes.*\$0\.0021 per task \(tokens at the provider price list\)/);
  assert.match(r[3]!.reason, /\(provider-billed\)/); assert.match(r[1]!.reason, /\(tokens at an estimated price\)/);
  const c = (m: string) => estCostPerTask(CLOUD_MEASUREMENTS.find((x) => x.model === m)!);
  assert.ok(c('mercury-2') < c('deepseek-flash') && c('deepseek-flash') < c('grok-build-0.1') && c('grok-build-0.1') < c('grok-4.3') && c('grok-4.3') < c('grok-4.7'));
});

test('ranking: a model below the rule or never measured goes after the qualified ones, and says so', () => {
  const table: CloudMeasurement[] = [{ model: 'mercury-2', tasks: 10, success: 10, median_usd: 0.001, median_ms: 1, median_tokens: 1000, cost_basis: 'provider-billed', sources: [], cost_sources: [] }, { model: 'deepseek-flash', tasks: 30, success: 20, median_usd: 0.001, median_ms: 1, median_tokens: 1000, cost_basis: 'provider-billed', sources: [], cost_sources: [] }, { model: 'grok-4.3', tasks: 30, success: 30, median_usd: 0.001, median_ms: 9000, median_tokens: 1000, cost_basis: 'provider-billed', sources: [], cost_sources: [] }];
  const r = rankCloudModels(['mercury-2', 'deepseek-flash', 'grok-4.3', 'newcomer'], table);
  assert.deepEqual(r.map((x) => x.model), ['grok-4.3', 'mercury-2', 'deepseek-flash', 'newcomer']);
  assert.match(r[1]!.reason, /below the 90% over 20 tasks rule/); assert.match(r[3]!.reason, /never measured/);
  assert.deepEqual(rankCloudModels([], table), []);
});

test('the default agent model is the best-ranked configured one, and routing can be turned off', () => {
  assert.equal(defaultAgentModel(), null);
  process.env.XAI_API_KEY = 'x'; assert.equal(defaultAgentModel(), 'grok-build-0.1', 'the cheapest measured xAI model');
  process.env.DEEPSEEK_API_KEY = 'd'; assert.equal(defaultAgentModel(), 'deepseek-flash', 'cheaper than xAI');
  process.env.INCEPTION_API_KEY = 'i'; assert.equal(defaultAgentModel(), 'mercury-2');
  assert.equal(defaultAgentModel({ KUDBEE_CLOUD_ROUTING: 'off' }), 'mercury-2', 'registry order');
});

test('which errors count as the provider failing', () => {
  for (const e of ['Inception API HTTP 402: no credit', 'DeepSeek API HTTP 429: slow down', 'xAI API HTTP 503: x', 'TypeError: fetch failed', 'The operation was aborted due to timeout', 'DEEPSEEK_API_KEY is not set in .env']) assert.ok(isProviderFailure(e), e);
  for (const e of ['Inception API HTTP 400: bad request', 'Step limit reached', 'tool failed', undefined]) assert.ok(!isProviderFailure(e), String(e));
});

interface Seen { auth?: string; model: string }
async function stub(status: number): Promise<{ base: string; seen: Seen[]; close: () => Promise<void> }> {
  const seen: Seen[] = [];
  const server = http.createServer((req, res) => {
    let body = ''; req.on('data', (c) => { body += c; });
    req.on('end', () => { seen.push({ auth: req.headers.authorization, model: (JSON.parse(body) as { model: string }).model }); res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(status === 200 ? JSON.stringify({ choices: [{ message: { role: 'assistant', content: 'done' } }], usage: { prompt_tokens: 100, completion_tokens: 20 } }) : 'provider says no'); });
  });
  await new Promise<void>((r) => server.listen(0, '127.0.0.1', r));
  return { base: `http://127.0.0.1:${(server.address() as AddressInfo).port}/v1`, seen, close: () => new Promise<void>((r) => server.close(() => r())) };
}
const mkHooks = (thoughts: Array<Record<string, unknown>>, signal = new AbortController().signal): AgentHooks => ({ signal, workspace: '/tmp', resolvePath: (r: string) => r, onThought: (t: Record<string, unknown>) => { thoughts.push(t); }, onEvent: () => {}, onFilesChanged: () => {}, checkBudget: () => null, approvedDomains: new Set(), requestApproval: async () => true, remember: async () => ({ id: 'x' }), recall: async () => ({ backend: 't', results: [] }), rssFeed: async () => ({ items: [] }) } as unknown as AgentHooks);

test('failover: Mercury is out of credit, so the same goal runs on DeepSeek, announced, and the result names the model used', async () => {
  const a = await stub(402); const b = await stub(200);
  process.env.INCEPTION_BASE_URL = a.base; process.env.DEEPSEEK_BASE_URL = b.base; process.env.INCEPTION_API_KEY = 'i'; process.env.DEEPSEEK_API_KEY = 'd';
  const thoughts: Array<Record<string, unknown>> = [];
  try {
    const r = await runToolAgentWithFailover('say done', 'mercury-2', 3, 0, [], mkHooks(thoughts));
    assert.equal(r.success, true); assert.equal(r.model_used, 'deepseek-flash');
    assert.deepEqual(a.seen.map((s) => s.model), ['mercury-2']); assert.deepEqual(b.seen.map((s) => [s.auth, s.model]), [['Bearer d', 'deepseek-flash']]);
    const note = thoughts.find((t) => t.type === 'routing');
    assert.match(String(note?.content), /mercury-2 failed before doing anything.*retrying the same goal on deepseek-flash/);
    assert.ok(r.cost_usd > 0);
  } finally { await a.close(); await b.close(); }
});

test('failover: no change when the first model works, when failover is off, or when the error is not the provider', async () => {
  const ok = await stub(200); const bad = await stub(402); const other = await stub(400);
  process.env.INCEPTION_API_KEY = 'i'; process.env.DEEPSEEK_API_KEY = 'd'; process.env.INCEPTION_BASE_URL = ok.base; process.env.DEEPSEEK_BASE_URL = bad.base;
  try {
    const first = await runToolAgentWithFailover('x', 'mercury-2', 2, 0, [], mkHooks([]));
    assert.equal(first.success, true); assert.equal(first.model_used, undefined); assert.equal(bad.seen.length, 0);
    process.env.INCEPTION_BASE_URL = bad.base; process.env.DEEPSEEK_BASE_URL = ok.base; process.env.KUDBEE_CLOUD_FAILOVER = 'off';
    const off = await runToolAgentWithFailover('x', 'mercury-2', 2, 0, [], mkHooks([]));
    assert.equal(off.success, false); assert.match(String(off.error), /Inception API HTTP 402/); assert.equal(ok.seen.length, 1, 'only the first success call above');
    delete process.env.KUDBEE_CLOUD_FAILOVER; process.env.INCEPTION_BASE_URL = other.base;
    const notProvider = await runToolAgentWithFailover('x', 'mercury-2', 2, 0, [], mkHooks([]));
    assert.equal(notProvider.success, false); assert.match(String(notProvider.error), /HTTP 400/); assert.equal(ok.seen.length, 1);
  } finally { await ok.close(); await bad.close(); await other.close(); }
});

test('failover: every provider failing returns the first error with what the fallbacks said; a stop is never retried', async () => {
  const a = await stub(402); const b = await stub(429);
  process.env.INCEPTION_BASE_URL = a.base; process.env.DEEPSEEK_BASE_URL = b.base; process.env.INCEPTION_API_KEY = 'i'; process.env.DEEPSEEK_API_KEY = 'd';
  try {
    const r = await runToolAgentWithFailover('x', 'mercury-2', 2, 0, [], mkHooks([]));
    assert.equal(r.success, false); assert.match(String(r.error), /^Inception API HTTP 402.*no fallback worked: deepseek-flash: DeepSeek API HTTP 429/);
    const ac = new AbortController(); ac.abort();
    const stopped: AgentRunResult = await runToolAgentWithFailover('x', 'mercury-2', 2, 0, [], mkHooks([], ac.signal));
    assert.equal(stopped.stopped, true); assert.equal(a.seen.length, 1, 'the aborted run made no new call');
  } finally { await a.close(); await b.close(); }
});

test('failover: no other model configured says so', async () => {
  const a = await stub(402); process.env.INCEPTION_BASE_URL = a.base; process.env.INCEPTION_API_KEY = 'i';
  try { const r = await runToolAgentWithFailover('x', 'mercury-2', 2, 0, [], mkHooks([])); assert.match(String(r.error), /no fallback worked: none configured/); } finally { await a.close(); }
});
