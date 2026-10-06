import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createMercuryChat, loopCostUsd, toOpenAiMessages } from '../mercury-chat.ts';

const history = [
  { role: 'system', content: 'sys' },
  { role: 'user', content: 'goal' },
  { role: 'assistant', content: '', tool_calls: [{ function: { name: 'repo_read', arguments: { path: 'src/a.ts' } } }] },
  { role: 'tool', tool_name: 'repo_read', content: 'FACTS' },
  { role: 'assistant', content: 'thinking', tool_calls: [{ function: { name: 'report_finding', arguments: '{"found":false}' } }] },
  { role: 'tool', tool_name: 'report_finding', content: 'REJECTED' },
  { role: 'user', content: 'try again' },
];

test('the loop history becomes OpenAI messages: call ids, JSON-text arguments, each tool reply answers the call before it', () => {
  const m = toOpenAiMessages(history);
  assert.deepEqual(m[2], { role: 'assistant', content: null, tool_calls: [{ id: 'call_1', type: 'function', function: { name: 'repo_read', arguments: '{"path":"src/a.ts"}' } }] });
  assert.deepEqual(m[3], { role: 'tool', tool_call_id: 'call_1', content: 'FACTS' });
  assert.equal((m[4] as any).content, 'thinking');
  assert.equal((m[4] as any).tool_calls[0].function.arguments, '{"found":false}', 'text arguments are kept as they are');
  assert.deepEqual(m[5], { role: 'tool', tool_call_id: 'call_2', content: 'REJECTED' });
  assert.deepEqual(m[0], { role: 'system', content: 'sys' });
  assert.deepEqual(m[6], { role: 'user', content: 'try again' });
  // a tool reply with no call before it, and a call with no arguments, are tolerated rather than crashing
  assert.equal((toOpenAiMessages([{ role: 'tool', content: 'x' }])[0] as any).tool_call_id, 'call_0');
  assert.equal((toOpenAiMessages([{ role: 'assistant', tool_calls: [{ function: { name: 'x' } }] }])[0] as any).tool_calls[0].function.arguments, '{}');
});

const okFetch = (body: unknown, seen: { url?: string; init?: RequestInit } = {}): typeof fetch => (async (url: any, init: any) => { seen.url = String(url); seen.init = init; return new Response(JSON.stringify(body), { status: 200 }); }) as typeof fetch;
const chatWith = (fetchImpl: typeof fetch, key: string | null = 'k-test') => createMercuryChat({ apiKey: () => key ?? undefined, baseUrl: () => 'http://127.0.0.1:1/v1', fetchImpl });

test('a tool call comes back in the loop\'s shape: first call only, arguments kept as text, token counts from usage', async () => {
  const seen: { url?: string; init?: RequestInit } = {};
  const chat = chatWith(okFetch({ choices: [{ message: { content: null, tool_calls: [{ function: { name: 'repo_read', arguments: '{"path":"a"}' } }, { function: { name: 'repo_search', arguments: '{}' } }] } }], usage: { prompt_tokens: 120, completion_tokens: 30 } }, seen));
  const t = await chat.chatOnce('mercury-2', [{ role: 'user', content: 'g' }], { tools: [{ type: 'function', function: { name: 'repo_read' } }] });
  assert.deepEqual(t.tool_calls, [{ function: { name: 'repo_read', arguments: '{"path":"a"}' } }]);
  assert.equal(t.content, ''); assert.equal(t.prompt_tokens, 120); assert.equal(t.completion_tokens, 30); assert.equal(t.error, undefined);
  assert.equal(seen.url, 'http://127.0.0.1:1/v1/chat/completions');
  const body = JSON.parse(String(seen.init!.body));
  assert.equal(body.model, 'mercury-2'); assert.equal(body.temperature, 0); assert.equal(body.tools.length, 1);
  assert.equal((seen.init!.headers as Record<string, string>).Authorization, 'Bearer k-test');
  assert.deepEqual(await chat.modelCapabilities('mercury-2'), ['tools']);
});

test('a plain answer, a missing key, an HTTP error, no choices and a network failure are each an explicit result, never a crash', async () => {
  const plain = await chatWith(okFetch({ choices: [{ message: { content: 'done' } }] })).chatOnce('m', []);
  assert.equal(plain.content, 'done'); assert.deepEqual(plain.tool_calls, []); assert.equal(plain.prompt_tokens, 0);
  const noTools = chatWith(okFetch({ choices: [{ message: { content: 'x', tool_calls: [{ function: { name: 'a' } }] } }] }));
  assert.equal((await noTools.chatOnce('m', [])).tool_calls[0]!.function!.arguments, '{}');
  assert.match((await chatWith(okFetch({}), null).chatOnce('m', [])).error!, /INCEPTION_API_KEY is not set/);
  assert.match((await chatWith((async () => new Response('out of credit', { status: 402 })) as typeof fetch).chatOnce('m', [])).error!, /HTTP 402: out of credit/);
  assert.match((await chatWith(okFetch({ choices: [] })).chatOnce('m', [])).error!, /no choices/);
  assert.match((await chatWith((async () => { throw new Error('connect ECONNREFUSED'); }) as typeof fetch).chatOnce('m', [], { signal: new AbortController().signal })).error!, /ECONNREFUSED/);
  assert.match((await chatWith((async () => { throw 'plain string'; }) as typeof fetch).chatOnce('m', [])).error!, /plain string/);
});

test('the key never appears in an error', async () => {
  const t = await chatWith((async () => new Response('bad', { status: 401 })) as typeof fetch, 'sk-secret-123').chatOnce('m', []);
  assert.doesNotMatch(JSON.stringify(t), /sk-secret-123/);
});

test('spend is computed from the reported tokens at the model\'s price; an unpriced model costs 0', () => {
  assert.equal(Math.round(loopCostUsd('mercury-2', { prompt_tokens: 1_000_000, completion_tokens: 1_000_000 }) * 100) / 100, 1);
  assert.equal(loopCostUsd('qwen2.5:3b', { prompt_tokens: 5000, completion_tokens: 500 }), 0);
});

test('defaults come from the environment when not injected', async () => {
  const keep = { k: process.env.INCEPTION_API_KEY, u: process.env.INCEPTION_BASE_URL };
  delete process.env.INCEPTION_API_KEY;
  try {
    assert.match((await createMercuryChat().chatOnce('m', [])).error!, /not set/);
    process.env.INCEPTION_API_KEY = 'k'; process.env.INCEPTION_BASE_URL = 'http://127.0.0.1:1/v1';
    assert.ok((await createMercuryChat().chatOnce('m', [], { timeoutMs: 500 })).error, 'a closed local port is an error result');
  } finally {
    if (keep.k === undefined) delete process.env.INCEPTION_API_KEY; else process.env.INCEPTION_API_KEY = keep.k;
    if (keep.u === undefined) delete process.env.INCEPTION_BASE_URL; else process.env.INCEPTION_BASE_URL = keep.u;
  }
});
