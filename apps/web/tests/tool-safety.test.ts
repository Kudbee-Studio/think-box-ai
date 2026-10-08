// Safe by default: every tool the agent can call is classified by what it can do to the machine, and each class is proven to be gated. A new tool without a class fails this test,
// so nobody can add a tool that writes, reaches the network or runs code without saying how a human stays in control.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { startMockInception, type MockInception } from './helpers/mock-inception.ts';
import type { AgentHooks } from '../agent.ts';

type Effect = 'read-local' | 'write-local' | 'network' | 'memory-write' | 'exec' | 'proposal';
/** What each tool can do, and how it is gated. Add every new tool here. */
const CLASS: Record<string, { effect: Effect; sample: Record<string, unknown>; coveredBy?: string }> = {
  list_files: { effect: 'read-local', sample: {} },
  read_file: { effect: 'read-local', sample: { path: '../../etc/passwd' } },
  repo_search: { effect: 'read-local', sample: { query: 'x', path: '../../..' } },
  repo_read: { effect: 'read-local', sample: { path: '../../../etc/passwd', start: 1, end: 5 } },
  recall: { effect: 'read-local', sample: { query: 'anything' } },
  write_file: { effect: 'write-local', sample: { path: 'existing.txt', content: 'overwritten' } },
  remember: { effect: 'memory-write', sample: { title: 't', content: 'c', evidence: 'e' } },
  fetch_url: { effect: 'network', sample: { url: 'http://127.0.0.1:9/x' } },
  read_rss: { effect: 'network', sample: { url: 'http://127.0.0.1:9/feed' } },
  live_lookup: { effect: 'network', sample: { kind: 'open_prs' } },
  algorand: { effect: 'network', sample: { action: 'status' } },
  medication: { effect: 'network', sample: { action: 'lookup', drug: 'aspirin' } },
  // Opt-in tools (not offered to a run unless its profile names them): their gates have their own tests, named here so that a change to either shows up in this list.
  run_checks: { effect: 'exec', sample: {}, coveredBy: 'run-checks-tool.test.ts' },
  propose_change: { effect: 'proposal', sample: {}, coveredBy: 'draft-pr-server.test.ts' },
};

let mock: MockInception; let agent: typeof import('../agent.ts'); let workspace = ''; let fetchCalls: string[] = []; const realFetch = globalThis.fetch;
before(async () => {
  mock = await startMockInception(); process.env.INCEPTION_BASE_URL = mock.baseUrl; process.env.INCEPTION_API_KEY = 'test-key'; agent = await import('../agent.ts');
  workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-tool-safety-')); fs.writeFileSync(path.join(workspace, 'existing.txt'), 'original');
});
after(async () => { globalThis.fetch = realFetch; await mock.close(); fs.rmSync(workspace, { recursive: true, force: true }); });

function hooks(answer: boolean, spied: { rss: number; remembered: number; asked: string[] }): AgentHooks {
  return {
    workspace, resolvePath: (rel: string) => { const t = path.resolve(workspace, rel); if (t !== workspace && !t.startsWith(workspace + path.sep)) throw new Error('Path escapes workspace'); return t; },
    onThought: () => {}, onEvent: () => {}, onFilesChanged: () => {}, signal: new AbortController().signal, checkBudget: () => null, approvedDomains: new Set(),
    requestApproval: async (tool: string) => { spied.asked.push(tool); return answer; },
    remember: async () => { spied.remembered += 1; return {}; }, recall: async () => ({ backend: 'test', results: [] }), rssFeed: async () => { spied.rss += 1; return {}; },
  } as AgentHooks;
}

test('every tool is classified, and nothing classified is missing from the tool list', () => {
  const names = agent.TOOLS.map((t: { function: { name: string } }) => t.function.name).sort();
  assert.deepEqual(names.filter((n: string) => !CLASS[n]), [], 'a tool has no safety class: add it to CLASS in tests/tool-safety.test.ts and show how it is gated');
  assert.deepEqual(Object.keys(CLASS).filter((n) => !names.includes(n)), [], 'a classified tool no longer exists');
});

for (const [name, { effect, sample }] of Object.entries(CLASS)) {
  if (effect === 'network') {
    test(`${name} (network): when the human says no, nothing leaves the machine`, async () => {
      fetchCalls = []; globalThis.fetch = ((url: unknown, ...rest: unknown[]) => { fetchCalls.push(String(url)); return realFetch(url as string, ...(rest as [RequestInit])); }) as typeof fetch;
      const spied = { rss: 0, remembered: 0, asked: [] as string[] };
      try { await agent.runGovernedTool(name, sample, hooks(false, spied), agent.newRunContext(), 1); } finally { globalThis.fetch = realFetch; }
      assert.deepEqual(spied.asked, [name], `${name} must ask a human before its first request to a new host`);
      assert.deepEqual(fetchCalls, [], `${name} made a network call after a denial`); assert.equal(spied.rss, 0);
    });
  }
}

test('write_file: overwriting an existing file asks first; a denial leaves the file as it was', async () => {
  const spied = { rss: 0, remembered: 0, asked: [] as string[] };
  const r = await agent.runGovernedTool('write_file', CLASS.write_file!.sample, hooks(false, spied), agent.newRunContext(), 1);
  assert.equal(r.output.ok, false); assert.deepEqual(spied.asked, ['write_file']); assert.equal(fs.readFileSync(path.join(workspace, 'existing.txt'), 'utf8'), 'original');
});

test('read tools cannot leave the workspace or the repository', async () => {
  for (const name of ['read_file', 'repo_search', 'repo_read']) {
    const spied = { rss: 0, remembered: 0, asked: [] as string[] };
    const r = await agent.runGovernedTool(name, CLASS[name]!.sample, hooks(true, spied), agent.newRunContext(), 1);
    assert.equal(r.output.ok, false, `${name} read outside its folder`);
  }
});

test('remember with no evidence from this run is refused without asking anyone', async () => {
  const spied = { rss: 0, remembered: 0, asked: [] as string[] };
  const r = await agent.runGovernedTool('remember', CLASS.remember!.sample, hooks(true, spied), agent.newRunContext(), 1);
  assert.equal(r.output.ok, false); assert.equal(spied.remembered, 0);
});

test('opt-in tools: their own gate tests exist, and they are not offered to a run by default', () => {
  for (const [name, c] of Object.entries(CLASS)) if (c.coveredBy) assert.ok(fs.existsSync(path.join(path.dirname(new URL(import.meta.url).pathname), c.coveredBy)), `${name}: ${c.coveredBy} is missing`);
  for (const name of ['run_checks', 'propose_change', 'repo_search', 'repo_read']) assert.ok(agent.OPT_IN_TOOLS.has(name), `${name} must stay opt-in`);
});
