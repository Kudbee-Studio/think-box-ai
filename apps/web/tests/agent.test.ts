import { test, before, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { startMockInception, say, call, type MockInception } from './helpers/mock-inception.ts';
import type { AgentEvent, AgentHooks } from '../agent.ts';

let mock: MockInception;
let agent: typeof import('../agent.ts');
let workspace: string;

before(async () => {
  mock = await startMockInception();
  // agent.ts reads the base URL at import time, so the env must be set first.
  process.env.INCEPTION_BASE_URL = mock.baseUrl;
  process.env.INCEPTION_API_KEY = 'test-key';
  agent = await import('../agent.ts');
});

after(async () => {
  await mock.close();
});

beforeEach(() => {
  workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-agent-test-'));
});

function makeHooks(overrides: Partial<AgentHooks> = {}) {
  const thoughts: Array<Record<string, unknown>> = [];
  const events: AgentEvent[] = [];
  const remembered: Array<{ title: string; content: string; tags: string[] }> = [];
  const approvals: Array<{ tool: string; reason: string }> = [];
  const hooks: AgentHooks = {
    workspace,
    resolvePath: (rel) => {
      const target = path.resolve(workspace, rel);
      if (!target.startsWith(workspace + path.sep)) throw new Error('Path escapes workspace');
      return target;
    },
    onThought: (t) => thoughts.push(t),
    onEvent: (e) => events.push(e),
    onFilesChanged: () => {},
    signal: new AbortController().signal,
    checkBudget: () => null,
    approvedDomains: new Set(),
    requestApproval: async (tool, _args, reason) => {
      approvals.push({ tool, reason });
      return true;
    },
    remember: async (title, content, tags) => {
      remembered.push({ title, content, tags });
      return { id: `org/${title}` };
    },
    recall: async () => ({ backend: 'test', results: [] }),
    rssFeed: async () => ({ items: [{ title: 'Item', url: 'https://example.test/1' }] }),
    ...overrides,
  };
  return { hooks, thoughts, events, remembered, approvals };
}

const run = (goal: string, hooks: AgentHooks, maxIterations = 8, memoryContext = '') =>
  agent.runToolAgent(goal, 'mercury-2', maxIterations, 0.2, [], hooks, memoryContext);

function toolResults(): Array<Record<string, unknown>> {
  const last = mock.requests.at(-1);
  return (last?.messages ?? []).filter((m) => m.role === 'tool').map((m) => JSON.parse(m.content ?? '{}'));
}

test('plain answer: one step, tokens and cost from usage', async () => {
  mock.script([say('Hello!')]);
  const { hooks, events } = makeHooks();
  const result = await run('Say hello', hooks);
  assert.equal(result.success, true);
  assert.equal(result.result, 'Hello!');
  assert.equal(result.steps, 1);
  assert.equal(result.tokens, 1100);
  assert.equal(result.cost_usd, agent.costUsd('mercury-2', 1000, 100));
  assert.equal(events.length, 1);
  assert.equal(events[0].kind, 'model');
});

test('costUsd uses per-million pricing and is 0 for unknown models', () => {
  assert.equal(agent.costUsd('mercury-2', 1_000_000, 1_000_000), 1.0);
  assert.equal(agent.costUsd('unknown-model', 5000, 5000), 0);
});

test('write_file writes inside the workspace and is traced', async () => {
  mock.script([call('write_file', { path: 'notes/out.md', content: '# hi' }), say('done')]);
  const { hooks, events } = makeHooks();
  const result = await run('write a file', hooks);
  assert.equal(result.success, true);
  assert.equal(fs.readFileSync(path.join(workspace, 'notes/out.md'), 'utf8'), '# hi');
  const tool = events.find((e) => e.kind === 'tool');
  assert.ok(tool && tool.kind === 'tool' && tool.ok && tool.name === 'write_file');
});

test('write_file outside the workspace is rejected as a tool error', async () => {
  mock.script([call('write_file', { path: '../escape.txt', content: 'x' }), say('ok')]);
  const { hooks } = makeHooks();
  await run('escape', hooks);
  assert.equal(fs.existsSync(path.join(workspace, '..', 'escape.txt')), false);
  assert.match(String(toolResults()[0].error), /escapes workspace/);
});

test('overwrite needs approval; denial leaves the file unchanged', async () => {
  fs.writeFileSync(path.join(workspace, 'a.txt'), 'original');
  mock.script([call('write_file', { path: 'a.txt', content: 'new' }), say('ok')]);
  const { hooks, approvals, events } = makeHooks({ requestApproval: async () => false });
  await run('overwrite', hooks);
  assert.equal(fs.readFileSync(path.join(workspace, 'a.txt'), 'utf8'), 'original');
  const tool = events.find((e) => e.kind === 'tool');
  assert.ok(tool && tool.kind === 'tool' && tool.approval === 'denied' && !tool.ok);
  assert.equal(approvals.length, 0); // the override replaced the recording hook
});

test('overwrite proceeds when approved', async () => {
  fs.writeFileSync(path.join(workspace, 'a.txt'), 'original');
  mock.script([call('write_file', { path: 'a.txt', content: 'new' }), say('ok')]);
  const { hooks, approvals } = makeHooks();
  await run('overwrite', hooks);
  assert.equal(fs.readFileSync(path.join(workspace, 'a.txt'), 'utf8'), 'new');
  assert.match(approvals[0].reason, /Overwrites existing file a\.txt/);
});

test('first contact with a domain needs approval once per session', async () => {
  mock.script([call('fetch_url', { url: mock.pageUrl }), call('fetch_url', { url: mock.pageUrl }), say('42')]);
  const { hooks, approvals } = makeHooks();
  const result = await run('fetch twice', hooks);
  assert.equal(result.success, true);
  assert.equal(approvals.length, 1);
  assert.ok(hooks.approvedDomains.has('127.0.0.1'));
  const [first] = toolResults();
  assert.match(String(first.text), /The answer is 42/);
  assert.doesNotMatch(String(first.text), /<p>/, 'HTML tags are stripped');
});

test('fetch_url rejects non-http schemes', async () => {
  mock.script([call('fetch_url', { url: 'file:///etc/passwd' }), say('ok')]);
  const { hooks } = makeHooks();
  await run('read local file via fetch', hooks);
  assert.match(String(toolResults()[0].error), /Only http\(s\) URLs/);
});

test('remember is refused without observed evidence and disabled after two refusals', async () => {
  const note = { title: 'Capital', content: 'Canberra', evidence: 'user said' };
  mock.script([call('remember', note), call('remember', note), call('remember', note), say('not stored')]);
  const { hooks, remembered } = makeHooks();
  const result = await run('Store the capital of Australia in memory', hooks);
  assert.equal(result.success, true);
  assert.equal(remembered.length, 0);
  const errors = toolResults().map((r) => String(r.error));
  assert.match(errors[0], /Refused/);
  assert.match(errors[1], /Refused/);
  assert.match(errors[2], /disabled for the rest of this run/);
});

test('remember does not accept a file the run wrote itself as evidence', async () => {
  mock.script([
    call('write_file', { path: 'fact.txt', content: 'Canberra' }),
    call('read_file', { path: 'fact.txt' }),
    call('remember', { title: 'Capital', content: 'Canberra', evidence: 'fact.txt' }),
    say('not stored'),
  ]);
  const { hooks, remembered } = makeHooks();
  await run('Store the capital of Australia in memory', hooks);
  assert.equal(remembered.length, 0);
});

test('remember is allowed after reading a file that existed before the run', async () => {
  fs.writeFileSync(path.join(workspace, 'source.md'), 'Canberra is the capital.');
  mock.script([
    call('read_file', { path: 'source.md' }),
    call('remember', { title: 'Capital', content: 'Canberra', evidence: 'source.md' }),
    say('stored'),
  ]);
  const { hooks, remembered } = makeHooks();
  await run('Learn the capital from source.md', hooks);
  assert.equal(remembered.length, 1);
  assert.match(remembered[0].content, /Evidence: source\.md/);
});

test('remember is allowed after a fetch, and when the user explicitly asks', async () => {
  mock.script([
    call('fetch_url', { url: mock.pageUrl }),
    call('remember', { title: 'Answer', content: '42', evidence: mock.pageUrl }),
    say('stored'),
  ]);
  const a = makeHooks();
  await run('find the answer', a.hooks);
  assert.equal(a.remembered.length, 1);

  mock.script([call('remember', { title: 'Pref', content: 'Markdown reports', evidence: 'user said' }), say('ok')]);
  const b = makeHooks();
  await run('Remember that I prefer markdown reports', b.hooks);
  assert.equal(b.remembered.length, 1);
});

test('remember requires an evidence argument', async () => {
  mock.script([call('remember', { title: 'Pref', content: 'x' }), say('ok')]);
  const { hooks, remembered } = makeHooks();
  await run('Remember that x', hooks);
  assert.equal(remembered.length, 0);
  assert.match(String(toolResults()[0].error), /evidence/);
});

test('budget exhaustion stops before any model call', async () => {
  mock.script([say('should not be called')]);
  const { hooks } = makeHooks({ checkBudget: () => 'Daily budget of $0.01 reached' });
  const result = await run('anything', hooks);
  assert.equal(result.success, false);
  assert.match(String(result.error), /budget/);
  assert.equal(result.steps, 0);
  assert.equal(mock.requests.length, 0);
});

test('stop aborts the in-flight model request quickly', async () => {
  mock.script([{ content: 'slow', delayMs: 5000 }]);
  const controller = new AbortController();
  const { hooks } = makeHooks({ signal: controller.signal });
  const started = Date.now();
  setTimeout(() => controller.abort(), 100);
  const result = await run('slow goal', hooks);
  assert.equal(result.stopped, true);
  assert.equal(result.success, false);
  assert.ok(Date.now() - started < 2000, 'returned long before the 5 s reply');
});

test('step limit ends a run that never answers', async () => {
  mock.script([call('list_files'), call('list_files'), call('list_files')]);
  const { hooks } = makeHooks();
  const result = await run('loop forever', hooks, 2);
  assert.equal(result.success, false);
  assert.match(String(result.error), /2-step limit/);
  assert.equal(result.steps, 2);
});

test('API errors fail the run with the HTTP status', async () => {
  mock.script([{ status: 500 }]);
  const { hooks } = makeHooks();
  const result = await run('anything', hooks);
  assert.equal(result.success, false);
  assert.match(String(result.error), /Inception API HTTP 500/);
});

test('malformed tool arguments become a tool error, not a crash', async () => {
  mock.script([call('write_file', '{"path": "a.txt", "content": '), say('recovered')]);
  const { hooks } = makeHooks();
  const result = await run('bad json', hooks);
  assert.equal(result.success, true);
  assert.equal(toolResults()[0].ok, false);
});

test('memory context is added to the system prompt', async () => {
  mock.script([say('ok')]);
  const { hooks } = makeHooks();
  await run('anything', hooks, 3, '- [VERIFIED (trust)] Use hnrss.org');
  const system = mock.requests[0].messages[0];
  assert.equal(system.role, 'system');
  assert.match(String(system.content), /Relevant memories:\n- \[VERIFIED \(trust\)\] Use hnrss\.org/);
  const toolNames = (mock.requests[0].tools as Array<{ function: { name: string } }>).map((t) => t.function.name);
  assert.deepEqual(toolNames.sort(), ['algorand', 'fetch_url', 'list_files', 'medication', 'read_file', 'read_rss', 'recall', 'remember', 'write_file']);
});

test('algorand lookups go through the new-domain approval gate', async () => {
  mock.script([call('algorand', { action: 'status', network: 'mainnet' }), say('could not check')]);
  const { hooks, approvals } = makeHooks({
    requestApproval: async (tool, _args, reason) => {
      approvals.push({ tool, reason });
      return false; // deny, so the test never reaches the real network
    },
  });
  await run('What is the Algorand mainnet round?', hooks);
  assert.equal(approvals[0].tool, 'algorand');
  assert.match(approvals[0].reason, /mainnet-api\.algonode\.cloud/);
  assert.match(String(toolResults()[0].error), /Denied/);
});

test('invalid algorand input is rejected before any network call', async () => {
  mock.script([call('algorand', { action: 'account', address: 'not-an-address' }), say('ok')]);
  const { hooks, approvals } = makeHooks();
  await run('check account', hooks);
  assert.equal(approvals.length, 0, 'no approval prompt for input that can never be valid');
  assert.match(String(toolResults()[0].error), /not a valid Algorand address/);
});

// ─── HERMES agent profile: tool-scoped allowlist ──────────────────────────

test('HERMES allowlist is exactly algorand, recall, remember', () => {
  assert.deepEqual(agent.HERMES_ALLOWED_TOOLS.slice().sort(), ['algorand', 'recall', 'remember']);
  assert.equal(agent.AGENT_PROFILES.hermes.allowedTools, agent.HERMES_ALLOWED_TOOLS);
});

test('a HERMES run only offers its allowlisted tools to the model', async () => {
  mock.script([say('ok')]);
  const { hooks } = makeHooks({ allowedTools: agent.HERMES_ALLOWED_TOOLS });
  await run('status check', hooks);
  const toolNames = (mock.requests[0].tools as Array<{ function: { name: string } }>).map((t) => t.function.name);
  assert.deepEqual(toolNames.sort(), ['algorand', 'recall', 'remember']);
});

test('HERMES gets its role context in the system prompt', async () => {
  mock.script([say('ok')]);
  const { hooks } = makeHooks({ allowedTools: agent.HERMES_ALLOWED_TOOLS });
  await run('status check', hooks);
  const system = String(mock.requests[0].messages[0].content);
  assert.match(system, /You are HERMES/);
  assert.match(system, /cannot sign or send anything/);
});

test('a disallowed tool call is rejected before the approval gate, even if the model hallucinates it', async () => {
  // The model is only ever offered algorand/recall/remember (previous test), but nothing stops
  // a compromised or confused model from emitting a tool_call for something else anyway — this
  // is the hard backstop, not just hiding the tool from the function list.
  mock.script([call('write_file', { path: 'x.txt', content: 'nope' }), say('done')]);
  const { hooks, approvals } = makeHooks({ allowedTools: agent.HERMES_ALLOWED_TOOLS });
  await run('write a file anyway', hooks);
  assert.equal(approvals.length, 0, 'never even reaches the approval gate');
  assert.match(String(toolResults()[0].error), /not available to this agent profile/);
});

test('HERMES can still use algorand and remember normally', async () => {
  mock.script([call('algorand', { action: 'status', network: 'testnet' }), say('done')]);
  const { hooks, approvals } = makeHooks({
    allowedTools: agent.HERMES_ALLOWED_TOOLS,
    requestApproval: async (tool, _args, reason) => {
      approvals.push({ tool, reason });
      return false; // deny so the test never reaches the real network; we only care it got this far
    },
  });
  await run('what is the testnet status', hooks);
  assert.equal(approvals.length, 1, 'algorand is allowed, so it reaches the normal approval gate, not the allowlist rejection');
  assert.equal(approvals[0].tool, 'algorand');
});

test('the default (no agentProfile) run is unrestricted, unaffected by HERMES existing', async () => {
  mock.script([call('write_file', { path: 'ok.txt', content: 'hi' }), say('done')]);
  const { hooks } = makeHooks(); // no allowedTools override
  await run('write a file', hooks);
  assert.equal(toolResults()[0].ok, true);
});

// ─── ASCLEPIUS agent profile: medication label research, never a verdict ──

test('ASCLEPIUS allowlist is exactly medication, recall, remember', () => {
  assert.deepEqual(agent.ASCLEPIUS_ALLOWED_TOOLS.slice().sort(), ['medication', 'recall', 'remember']);
  assert.equal(agent.AGENT_PROFILES.asclepius.allowedTools, agent.ASCLEPIUS_ALLOWED_TOOLS);
});

test('an ASCLEPIUS run only offers its allowlisted tools to the model', async () => {
  mock.script([say('ok')]);
  const { hooks } = makeHooks({ allowedTools: agent.ASCLEPIUS_ALLOWED_TOOLS });
  await run('check a drug label', hooks);
  const toolNames = (mock.requests[0].tools as Array<{ function: { name: string } }>).map((t) => t.function.name);
  assert.deepEqual(toolNames.sort(), ['medication', 'recall', 'remember']);
});

test('ASCLEPIUS gets its safety-critical role context in the system prompt', async () => {
  mock.script([say('ok')]);
  const { hooks } = makeHooks({ allowedTools: agent.ASCLEPIUS_ALLOWED_TOOLS });
  await run('check a drug label', hooks);
  const system = String(mock.requests[0].messages[0].content);
  assert.match(system, /You are ASCLEPIUS/);
  assert.match(system, /NEVER tell a user that a combination of medications is "safe"/);
  assert.match(system, /licensed pharmacist or physician/);
});

test('ASCLEPIUS cannot write files even if the model hallucinates the call', async () => {
  mock.script([call('write_file', { path: 'x.txt', content: 'nope' }), say('done')]);
  const { hooks, approvals } = makeHooks({ allowedTools: agent.ASCLEPIUS_ALLOWED_TOOLS });
  await run('write a file anyway', hooks);
  assert.equal(approvals.length, 0);
  assert.match(String(toolResults()[0].error), /not available to this agent profile/);
});

test('ASCLEPIUS can still use medication normally, through the approval gate', async () => {
  mock.script([call('medication', { action: 'lookup', drug: 'warfarin' }), say('done')]);
  const { hooks, approvals } = makeHooks({
    allowedTools: agent.ASCLEPIUS_ALLOWED_TOOLS,
    requestApproval: async (tool, _args, reason) => {
      approvals.push({ tool, reason });
      return false; // deny so the test never reaches the real network
    },
  });
  await run('check warfarin interactions', hooks);
  assert.equal(approvals.length, 1);
  assert.equal(approvals[0].tool, 'medication');
  assert.match(approvals[0].reason, /api\.fda\.gov/);
});

test('invalid medication input is rejected before any network call or approval prompt', async () => {
  mock.script([call('medication', { action: 'compare', drugs: ['only-one'] }), say('ok')]);
  const { hooks, approvals } = makeHooks({ allowedTools: agent.ASCLEPIUS_ALLOWED_TOOLS });
  await run('compare a drug with itself', hooks);
  assert.equal(approvals.length, 0, 'no approval prompt for input that can never be valid');
  assert.match(String(toolResults()[0].error), /2 or more/);
});
