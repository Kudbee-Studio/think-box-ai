// Direct tests for modules extracted from server.ts: config-patch, mcp-skills and ollama-client. They were only reachable through the
// running server before; now each has its own contract. The Ollama/Janus client talks to a local mock HTTP server (no external network).
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { MAX_AGENT_ITERATIONS, sanitizeConfigPatch } from '../config-patch.ts';
import { filterSkills, groupSkillsByCategory } from '../mcp-skills.ts';
import { createModelClients } from '../ollama-client.ts';
import type { OllamaTokenMessage } from '../types.ts';

test('config patch: valid values pass through and are trimmed; the documented bounds are exact', () => {
  assert.deepEqual(sanitizeConfigPatch({ model: '  mercury-2  ', provider: 'inception', maxIterations: 1, temperature: 0 }), { model: 'mercury-2', provider: 'inception', maxIterations: 1, temperature: 0 });
  assert.deepEqual(sanitizeConfigPatch({ maxIterations: MAX_AGENT_ITERATIONS, temperature: 2, provider: 'ollama' }), { maxIterations: 50, temperature: 2, provider: 'ollama' });
  assert.deepEqual(sanitizeConfigPatch({}), {});
  assert.equal(MAX_AGENT_ITERATIONS, 50);
});

test('config patch: every invalid shape throws a specific message and nothing is partially applied', () => {
  const bad: Array<[unknown, RegExp]> = [
    [null, /config must be an object/], [[], /config must be an object/], ['x', /config must be an object/],
    [{ model: '' }, /model must be a model name/], [{ model: '   ' }, /model must be a model name/], [{ model: 'm'.repeat(101) }, /model must be a model name/], [{ model: 7 }, /model must be a model name/],
    [{ provider: 'openai' }, /provider must be inception or ollama/],
    [{ maxIterations: 0 }, /maxIterations must be an integer from 1 to 50/], [{ maxIterations: 51 }, /1 to 50/], [{ maxIterations: 2.5 }, /1 to 50/], [{ maxIterations: '5' }, /1 to 50/],
    [{ temperature: -0.1 }, /temperature must be from 0 to 2/], [{ temperature: 2.1 }, /0 to 2/], [{ temperature: NaN }, /0 to 2/], [{ temperature: Infinity }, /0 to 2/], [{ temperature: '1' }, /0 to 2/],
    [{ apiKey: 'x' }, /unknown config key: apiKey/], [{ model: 'ok', __proto__: undefined, constructor: 1 }, /unknown config key: constructor/],
  ];
  for (const [input, message] of bad) assert.throws(() => sanitizeConfigPatch(input), message, JSON.stringify(input));
  assert.throws(() => sanitizeConfigPatch({ model: 'fine', temperature: 9 }), /temperature/, 'a good key next to a bad one still rejects the patch');
});

const skills = [
  { name: 'github', repo: 'r/github', description: 'Work with Git repositories', category: 'Developer', tags: ['git', 'prs'], capabilities: [] },
  { name: 'postgres', repo: 'r/pg', description: 'SQL queries', category: 'Data', tags: ['sql'], capabilities: [] },
  { name: 'sqlite', repo: 'r/sq', description: 'Local SQL database', category: 'Data', tags: [], capabilities: [] },
  { name: 'misc', repo: 'r/m', description: '', category: '', tags: [], capabilities: [] },
];

test('mcp skills: grouped by category (blank category is "Other") and filtered by name, description or tag, case-insensitively', () => {
  const groups = groupSkillsByCategory(skills);
  assert.deepEqual(Object.keys(groups).sort(), ['Data', 'Developer', 'Other']);
  assert.equal(groups.Data.length, 2);
  assert.equal(groups.Other[0].name, 'misc');
  assert.deepEqual(groupSkillsByCategory([]), {});

  assert.equal(filterSkills(skills, '').length, 4, 'no query returns everything');
  assert.deepEqual(filterSkills(skills, 'GITHUB').map((s) => s.name), ['github'], 'by name');
  assert.deepEqual(filterSkills(skills, 'sql').map((s) => s.name), ['postgres', 'sqlite'], 'by description and tag');
  assert.deepEqual(filterSkills(skills, 'prs').map((s) => s.name), ['github'], 'by tag');
  assert.deepEqual(filterSkills(skills, 'zzz'), []);
});

// ─── Ollama / Janus client against a mock server ─────────────
let mock: http.Server;
let base = '';
let janusOn = false;
let chatRequests: Array<{ model: string; messages: unknown; stream: boolean }> = [];
let mode: 'ok' | 'nobody' | 'drop' | 'janus-error' | 'notfound' | 'errline' | 'nonewline' = 'ok';
before(async () => {
  mock = http.createServer((req, res) => {
    let body = '';
    req.on('data', (c) => { body += c; });
    req.on('end', () => {
      if (req.url === '/api/tags') { res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify({ models: [{ name: 'qwen2.5:1.5b', size: 1 }, { name: 'llama3' }] })); return; }
      if (req.url === '/api/chat') {
        chatRequests.push(JSON.parse(body));
        if (mode === 'nobody') { res.statusCode = 200; res.end(); return; }
        if (mode === 'notfound') { res.statusCode = 404; res.end('{"error":"model \'x\' not found"}'); return; }
        if (mode === 'errline') { res.end('{"message":{"content":"a"}}\n{"error":"out of memory"}\n'); return; }
        if (mode === 'nonewline') { res.end('{"message":{"content":"ok"}}\n{"done":true,"eval_count":1}'); return; }
        if (mode === 'drop') { res.write('{"message":{"content":"par"}}\n'); setTimeout(() => res.destroy(), 40); return; }
        res.write('{"message":{"content":"Hel"}}\n{"message":{"content":"lo"}}\n');
        res.write('not json at all\n');
        res.end('{"done":true,"eval_count":2}\n');
        return;
      }
      if (req.url === '/analyze' || req.url === '/generate') {
        res.setHeader('Content-Type', 'application/json');
        if (mode === 'janus-error') { res.statusCode = 422; res.end(JSON.stringify({ detail: 'bad image' })); return; }
        res.end(JSON.stringify({ echoed: JSON.parse(body).prompt ?? 'none', via: req.url }));
        return;
      }
      res.statusCode = 404; res.end('{}');
    });
  });
  await new Promise<void>((r) => mock.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${(mock.address() as AddressInfo).port}`;
});
after(() => { mock.close(); });

const clients = (over: Partial<{ ollamaBaseUrl: string; janusBaseUrl: string }> = {}) => createModelClients({ ollamaBaseUrl: base, janusBaseUrl: base, janusEnabled: () => janusOn, ...over });

test('ollama client: models are listed with provider "ollama"; an unreachable Ollama is an empty list, not an error', async () => {
  const c = clients();
  const models = await c.listOllamaModels();
  assert.deepEqual(models.map((m) => [m.name, m.provider]), [['qwen2.5:1.5b', 'ollama'], ['llama3', 'ollama']]);
  assert.deepEqual(await clients({ ollamaBaseUrl: 'http://127.0.0.1:9' }).listOllamaModels(), []);
});

test('ollama client: listModels puts the cloud worker models first only when Inception is configured', async () => {
  const had = process.env.INCEPTION_API_KEY;
  try {
    process.env.INCEPTION_API_KEY = '';
    const local = await clients().listModels();
    assert.ok(local.every((m) => m.provider === 'ollama'));
    process.env.INCEPTION_API_KEY = 'test-key';
    const both = await clients().listModels();
    assert.equal(both[0].provider, 'inception');
    assert.equal(both[0].agent, true);
    assert.equal(both.at(-1)?.provider, 'ollama');
  } finally {
    if (had === undefined) delete process.env.INCEPTION_API_KEY; else process.env.INCEPTION_API_KEY = had;
  }
});

async function stream(c: ReturnType<typeof clients>, model = 'qwen2.5:1.5b') {
  const tokens: string[] = []; const done: OllamaTokenMessage[] = [];
  await c.streamOllama(model, [{ role: 'user', content: 'hi' }] as never, (t) => tokens.push(t), (d) => done.push(d));
  return { tokens, done };
}

test('ollama client: a streamed chat delivers tokens in order, skips malformed lines, and signals done once with the stats', async () => {
  chatRequests = []; mode = 'ok';
  const { tokens, done } = await stream(clients());
  assert.deepEqual(tokens, ['Hel', 'lo']);
  assert.equal(done.length, 1);
  assert.equal(done[0].done, true);
  assert.equal(chatRequests[0].model, 'qwen2.5:1.5b');
  assert.equal(chatRequests[0].stream, true);
  assert.deepEqual(chatRequests[0].messages, [{ role: 'user', content: 'hi' }]);
});

test('ollama client: every failure is reported through the callbacks (an error token and an error result), never thrown', async () => {
  mode = 'nobody';
  const empty = await stream(clients());
  assert.match(empty.tokens.join(''), /\[Error: Ollama ended the response without finishing it\]/);
  assert.equal(empty.done.length, 1);
  assert.match(String(empty.done[0].error), /without finishing/);

  mode = 'notfound';
  const missing = await stream(clients());
  assert.match(missing.tokens.join(''), /Ollama returned HTTP 404: model 'x' not found/);
  assert.match(String(missing.done[0].error), /HTTP 404: model 'x' not found/, 'the status and Ollama\'s own reason are kept');

  mode = 'errline';
  const midStream = await stream(clients());
  assert.equal(midStream.tokens[0], 'a', 'tokens before the error are delivered');
  assert.match(midStream.done.at(-1)?.error ?? '', /out of memory/);

  mode = 'ok';
  const down = await stream(clients({ ollamaBaseUrl: 'http://127.0.0.1:9' }));
  assert.match(down.tokens[0], /^\[Error: /);
  assert.ok(down.done[0].error);

  mode = 'drop';
  const dropped = await stream(clients());
  assert.equal(dropped.tokens[0], 'par', 'tokens before the connection dropped were delivered');
  assert.ok(dropped.done.at(-1)?.error, 'the drop is reported');
  mode = 'ok';
});

test('ollama client: a final line without a trailing newline is still processed (the done marker is not lost)', async () => {
  mode = 'nonewline';
  const r = await stream(clients());
  assert.deepEqual(r.tokens, ['ok']);
  assert.equal(r.done.length, 1);
  assert.equal(r.done[0].error, undefined);
  mode = 'ok';
});

test('janus client: refuses while disabled; when enabled posts the payload and returns the JSON; a service error carries its detail', async () => {
  janusOn = false;
  await assert.rejects(clients().requestJanus('analyze', { prompt: 'x' }), /Janus image service is disabled/);
  janusOn = true;
  assert.deepEqual(await clients().requestJanus('generate', { prompt: 'a cat' }), { echoed: 'a cat', via: '/generate' });
  assert.deepEqual(await clients().requestJanus('analyze', { prompt: 'p' }), { echoed: 'p', via: '/analyze' });
  mode = 'janus-error';
  await assert.rejects(clients().requestJanus('analyze', {}), /bad image/);
  mode = 'ok'; janusOn = false;
});
