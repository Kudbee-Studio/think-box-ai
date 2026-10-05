// The local worker loop on the repository toolset: look with read-only tools, report ONE finding, judged against what the tools returned.
import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { newRunContext } from '../agent.ts';
import { repoSpec, runLocalToolLoop, type LocalChat } from '../local-tools.ts';
import type { OllamaChatTurn } from '../ollama-client.ts';
import type { RepoEvidence } from '../repo-tools.ts';
import { lookupHooks } from './helpers/lookup-hooks.ts';

let root = '';
before(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), 'repo-loop-'));
  const w = (rel: string, t: string) => { fs.mkdirSync(path.dirname(path.join(root, rel)), { recursive: true }); fs.writeFileSync(path.join(root, rel), t); };
  w('src/alpha.ts', 'export function alpha(x: number): number {\n  return x + 1;\n}\nexport function orphan() {\n  return 7;\n}\n');
  w('tests/alpha.test.ts', 'import { alpha } from "../src/alpha.ts";\ntest("alpha", () => alpha(1));\n');
  w('.env', 'KEY=secret\n');
  process.env.KUDBEE_REPO_ROOT = root;
});
after(() => { delete process.env.KUDBEE_REPO_ROOT; fs.rmSync(root, { recursive: true, force: true }); });

const turn = (o: Partial<OllamaChatTurn>): OllamaChatTurn => ({ content: '', tool_calls: [], prompt_tokens: 10, completion_tokens: 5, latency_ms: 3, ...o });
const nativeCall = (name: string, args: unknown) => turn({ tool_calls: [{ function: { name, arguments: args } }] });
const scripted = (caps: string[], turns: OllamaChatTurn[]) => {
  const requests: Array<{ messages: any[]; tools?: any[]; format?: unknown }> = [];
  const chat: LocalChat = { modelCapabilities: async () => caps, chatOnce: async (_m, messages, o = {}) => { requests.push({ messages: JSON.parse(JSON.stringify(messages)), tools: o.tools as any[], format: o.format }); return turns.shift() ?? turn({ error: 'script exhausted' }); } };
  return { chat, requests };
};
const MODELS = [
  { name: 'qwen2.5:3b', caps: ['tools'], mode: 'native', call: (tool: string, args: object) => nativeCall(tool, args), finish: (f: object) => nativeCall('report_finding', f) },
  { name: 'gemma3:4b', caps: [], mode: 'constrained', call: (tool: string, args: object) => turn({ content: JSON.stringify({ action: 'call', tool, ...args }) }), finish: (f: object) => turn({ content: JSON.stringify({ action: 'finding', finding: f }) }) },
] as const;
const drive = (m: (typeof MODELS)[number], chat: LocalChat, goal = 'Find one function in src that has no test') => {
  const h = lookupHooks({ allowedTools: ['repo_search', 'repo_read'] });
  return runLocalToolLoop<RepoEvidence>({ model: m.name, goal, hooks: h.hooks, context: newRunContext(), chat, repo: null, spec: repoSpec() }).then((result) => ({ result, ...h }));
};
const good = { found: true, file: 'src/alpha.ts', line: 4, quote: 'export function orphan()', claim: 'The function `orphan` has no tests.', absence_search: { query: 'orphan', path: 'tests' } };

for (const m of MODELS) {
  describe(`${m.name} (${m.mode}) investigating the repository`, () => {
    it('reads, searches for absence, reports, and the finding is GROUNDED', async () => {
      const { chat, requests } = scripted(m.caps as unknown as string[], [m.call('repo_read', { path: 'src/alpha.ts', start: 1, end: 6 }), m.call('repo_search', { query: 'orphan', path: 'tests' }), m.finish(good)]);
      const { result, approvals, events } = await drive(m, chat);
      assert.equal(result.success, true, JSON.stringify(result.failure));
      assert.equal(result.mode, m.mode);
      assert.equal(result.tool_calls, 2);
      assert.equal(result.grounding?.status, 'GROUNDED', JSON.stringify(result.grounding?.unsupported));
      assert.equal(result.finding?.file, 'src/alpha.ts');
      assert.deepEqual(result.evidence.map((e) => e.tool), ['repo_read', 'repo_search']);
      assert.equal(approvals.length, 0, 'read-only tools need no per-call approval (the convoy was approved)');
      assert.equal(events.filter((e) => e.kind === 'tool').length, 2, 'both went through the governed path');
      // nothing to report before anything was looked at: the report option is withheld on the first turn and offered afterwards
      if (m.mode === 'native') {
        assert.deepEqual(requests[0]!.tools!.map((t) => t.function.name), ['repo_search', 'repo_read']);
        assert.deepEqual(requests[1]!.tools!.map((t) => t.function.name), ['repo_search', 'repo_read', 'report_finding']);
      } else {
        assert.deepEqual((requests[0]!.format as any).properties.action.enum, ['call']);
        assert.deepEqual((requests[1]!.format as any).properties.action.enum, ['call', 'finding']);
      }
      assert.match(JSON.stringify(requests[1]!.messages), /src\/alpha\.ts lines 1-6 of 7/);
    });
    it('a fabricated line, quote or file is GROUNDING FAILED, not a success', async () => {
      for (const bad of [{ ...good, line: 5 }, { ...good, quote: 'export function missing()' }, { ...good, file: 'src/nope.ts' }]) {
        const { chat } = scripted(m.caps as unknown as string[], [m.call('repo_read', { path: 'src/alpha.ts', start: 1, end: 6 }), m.call('repo_search', { query: 'orphan', path: 'tests' }), m.finish(bad), m.finish(bad)]);
        const { result } = await drive(m, chat);
        assert.equal(result.success, true);
        assert.equal(result.grounding?.status, 'GROUNDING FAILED', JSON.stringify(bad));
      }
    });
    it('one round of feedback: an unsupported absence claim is sent back, the model runs the missing search, and the second report is GROUNDED', async () => {
      const { chat, requests } = scripted(m.caps as unknown as string[], [m.call('repo_read', { path: 'src/alpha.ts', start: 1, end: 6 }), m.finish({ ...good, absence_search: undefined }), m.call('repo_search', { query: 'orphan', path: 'tests' }), m.finish(good)]);
      const { result } = await drive(m, chat);
      assert.equal(result.success, true, JSON.stringify(result.failure));
      assert.equal(result.grounding?.status, 'GROUNDED');
      assert.deepEqual(result.steps.map((s) => s.outcome), ['tool_ok', 'malformed', 'tool_ok', 'answer']);
      assert.match(result.steps[1]!.error!, /not grounded: absence/);
      assert.match(JSON.stringify(requests[2]!.messages), /not accepted because these claims are not supported/);
    });
    it('a second ungrounded report is returned as GROUNDING FAILED, not retried forever', async () => {
      const { chat } = scripted(m.caps as unknown as string[], [m.call('repo_read', { path: 'src/alpha.ts', start: 1, end: 6 }), m.finish({ ...good, absence_search: undefined }), m.finish({ ...good, absence_search: undefined })]);
      const { result } = await drive(m, chat);
      assert.equal(result.success, true);
      assert.equal(result.grounding?.status, 'GROUNDING FAILED');
      assert.equal(result.steps.filter((s) => s.outcome === 'malformed').length, 1);
    });
    it('a claim of absence without the search that proves it fails', async () => {
      const { chat } = scripted(m.caps as unknown as string[], [m.call('repo_read', { path: 'src/alpha.ts', start: 1, end: 6 }), m.finish({ ...good, absence_search: undefined }), m.finish({ ...good, absence_search: undefined })]);
      const { result } = await drive(m, chat);
      assert.equal(result.grounding?.status, 'GROUNDING FAILED');
      assert.ok(result.grounding!.unsupported.some((u) => u.kind === 'absence'));
    });
    it('"nothing worth reporting" after looking is an honest result', async () => {
      const { chat } = scripted(m.caps as unknown as string[], [m.call('repo_read', { path: 'src/alpha.ts' }), m.finish({ found: false, reason: 'every exported function is exercised' })]);
      const { result } = await drive(m, chat);
      assert.equal(result.success, true);
      assert.equal(result.finding?.found, false);
      assert.equal(result.grounding?.status, 'GROUNDED');
    });
    it('a finding with no looking at all is a failure', async () => {
      const { chat } = scripted(m.caps as unknown as string[], [m.finish(good)]);
      const { result } = await drive(m, chat);
      assert.equal(result.success, false);
      assert.equal(result.failure?.kind, 'no_tool_call');
    });
    it('forbidden paths are refused before anything runs (one repair, then a classified failure)', async () => {
      const { chat } = scripted(m.caps as unknown as string[], [m.call('repo_read', { path: '.env' }), m.call('repo_read', { path: '../../etc/passwd.ts' })]);
      const { result, events } = await drive(m, chat);
      assert.equal(result.success, false);
      assert.equal(result.failure?.kind, 'malformed_tool_request');
      assert.equal(events.filter((e) => e.kind === 'tool').length, 0, 'nothing reached the tool');
    });
    it('a malformed report is repaired once', async () => {
      const { chat, requests } = scripted(m.caps as unknown as string[], [m.call('repo_read', { path: 'src/alpha.ts', start: 1, end: 6 }), m.call('repo_search', { query: 'orphan', path: 'tests' }), m.finish({ found: true, file: 'src/alpha.ts' }), m.finish(good)]);
      const { result } = await drive(m, chat);
      assert.equal(result.success, true);
      assert.deepEqual(result.steps.map((s) => s.outcome), ['tool_ok', 'tool_ok', 'malformed', 'answer']);
      assert.match(JSON.stringify(requests[3]!.messages), /That report was invalid: the finding is malformed/);
    });
    it('a missing file is a tool failure with its reason', async () => {
      const { chat } = scripted(m.caps as unknown as string[], [m.call('repo_read', { path: 'src/missing.ts' }), m.finish(good)]);
      const { result } = await drive(m, chat);
      assert.equal(result.failure?.kind, 'tool_failed');
      assert.match(result.failure!.message, /not found/);
    });
  });
}
describe('the spec rejects tools it does not own', () => {
  it('native: live_lookup or an invented tool is malformed in a repo investigation', async () => {
    const { chat } = scripted(['tools'], [nativeCall('live_lookup', { recipe: 'latest_pr' }), nativeCall('rm_rf', {})]);
    const { result } = await drive(MODELS[0], chat);
    assert.equal(result.failure?.kind, 'malformed_tool_request');
    assert.match(result.steps[0]!.error!, /unknown tool "live_lookup"/);
  });
});
