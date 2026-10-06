// SIMULATE with a LOCAL patch worker (P3.48): a local model proposes exact text edits through the same governed tools (repo_search, repo_read, propose_change), a human approves the
// sandbox run, the sandbox verifies, and the result is built by code. Models are scripted (native tool calls like Qwen, constrained JSON like Gemma), so each case is deterministic;
// the repository, the governed tools, the sandbox and the approval gate are real. The fixture repository has a genuinely failing test.
import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { newRunContext, type AgentRunResult } from '../agent.ts';
import { executeConvoy, type RunnerDeps } from '../convoy-runner.ts';
import { ConvoyStore } from '../convoy.ts';
import { patchSpec, runLocalToolLoop, type LocalChat } from '../local-tools.ts';
import { evaluatePolicy, planConvoy } from '../mayor.ts';
import type { OllamaChatTurn } from '../ollama-client.ts';
import { RunStore, type RunRecord } from '../runs.ts';
import { probeSandbox } from '../scratch-runner.ts';
import { lookupHooks } from './helpers/lookup-hooks.ts';

const realTmp = process.env.TMPDIR; let privateTmp = ''; let repo = ''; let sha = ''; const savedRoot = process.env.KUDBEE_REPO_ROOT;
const probe = await (async () => { privateTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'local-sim-tests-')); process.env.TMPDIR = privateTmp; return probeSandbox(); })();
const skip = probe.ok ? false : `no proven sandbox here: ${(probe as { reason: string }).reason}`;
const git = (...a: string[]): string => execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', ...a], { cwd: repo, encoding: 'utf8' }).trim();
const GREETER = "function greet(name) {\n  return 'helo ' + name;\n}\nmodule.exports = { greet };\n";
const FIX = [{ path: 'apps/web/src/greeter.js', find: "'helo '", replace: "'hello '" }];

before(() => {
  repo = fs.mkdtempSync(path.join(os.tmpdir(), 'local-sim-fixture-'));
  const w = (rel: string, text: string): void => { fs.mkdirSync(path.dirname(path.join(repo, rel)), { recursive: true }); fs.writeFileSync(path.join(repo, rel), text); };
  w('apps/web/package.json', JSON.stringify({ name: 'fixture', scripts: { test: 'node --test "tests/*.test.js"', lint: 'node -e "0"' } }));
  w('apps/web/src/greeter.js', GREETER);
  w('apps/web/tests/greeter.test.js', "const { test } = require('node:test'); const assert = require('node:assert'); const { greet } = require('../src/greeter.js');\ntest('greets', () => assert.equal(greet('x'), 'hello x'));\n");
  w('apps/web/.gitignore', 'node_modules\n'); fs.mkdirSync(path.join(repo, 'apps/web/node_modules'), { recursive: true });
  git('init', '-q', '-b', 'main'); git('add', '-A'); git('commit', '-qm', 'fixture: the greeting test fails'); sha = git('rev-parse', 'HEAD');
  process.env.KUDBEE_REPO_ROOT = repo;
});
after(async () => {
  await new Promise((r) => setTimeout(r, 500));
  if (savedRoot === undefined) delete process.env.KUDBEE_REPO_ROOT; else process.env.KUDBEE_REPO_ROOT = savedRoot;
  if (realTmp === undefined) delete process.env.TMPDIR; else process.env.TMPDIR = realTmp;
  fs.rmSync(repo, { recursive: true, force: true }); fs.rmSync(privateTmp, { recursive: true, force: true });
});

const turn = (o: Partial<OllamaChatTurn>): OllamaChatTurn => ({ content: '', tool_calls: [], prompt_tokens: 20, completion_tokens: 8, latency_ms: 5, ...o });
const nativeCall = (name: string, args: unknown) => turn({ tool_calls: [{ function: { name, arguments: args } }] });
const jsonTurn = (body: unknown) => turn({ content: JSON.stringify(body) });
/** A scripted local model: replays `turns` in order and records every request it was sent. */
function scripted(capabilities: string[], turns: OllamaChatTurn[]) {
  const requests: Array<{ messages: any[]; tools?: unknown[]; format?: unknown; timeoutMs?: number }> = [];
  const chat: LocalChat = { modelCapabilities: async () => capabilities, chatOnce: async (_m, messages, opts = {}) => { requests.push({ messages: JSON.parse(JSON.stringify(messages)), tools: opts.tools, format: opts.format, timeoutMs: opts.timeoutMs }); return turns.shift() ?? turn({ error: 'script exhausted' }); } };
  return { chat, requests, left: () => turns.length };
}
const MODELS = [
  { name: 'qwen2.5:3b', caps: ['completion', 'tools'], mode: 'native' as const, call: (tool: string, args: Record<string, unknown>) => nativeCall(tool, args), answer: (text: string) => turn({ content: text }) },
  { name: 'gemma3:4b', caps: ['completion', 'vision'], mode: 'constrained' as const, call: (tool: string, args: Record<string, unknown>) => jsonTurn({ action: 'call', tool, ...args }), answer: (text: string) => jsonTurn({ action: 'answer', answer: text }) },
];
const TOOLS = ['list_files', 'read_file', 'repo_search', 'repo_read', 'propose_change', 'run_checks', 'live_lookup'];

describe('the local patch loop (no sandbox needed)', () => {
  const drive = (model: string, chat: LocalChat, goal = 'Fix the typo in the greeting so the greeting test passes', allowedTools = ['repo_search', 'repo_read', 'propose_change']) => {
    const h = lookupHooks({ scratchRef: sha, allowedTools });
    return runLocalToolLoop({ model, goal, hooks: h.hooks, context: newRunContext(), chat, repo: null, spec: patchSpec(sha), maxSteps: 8 }).then((result) => ({ result, ...h }));
  };
  for (const m of MODELS) {
    it(`${m.name} (${m.mode}): reads, proposes, and the loop ends THE MOMENT the proposal is accepted (no final text turn is needed or asked for)`, async () => {
      const s = scripted(m.caps, [m.call('repo_read', { path: 'apps/web/src/greeter.js', start: 1, end: 5 }), m.call('propose_change', { edits: FIX, summary: 'Fixes the typo.' }), m.answer('SHOULD NEVER BE ASKED FOR')]);
      const { result } = await drive(m.name, s.chat);
      assert.equal(result.success, true, JSON.stringify(result.failure)); assert.equal(result.mode, m.mode); assert.equal(result.answer, 'Fixes the typo.'); assert.equal(result.tool_calls, 2);
      assert.equal(s.left(), 1, 'the third scripted turn was never requested');
      const proposal = result.evidence.find((e) => e.tool === 'propose_change')!; assert.ok(proposal && 'patch' in proposal); assert.equal(proposal.ref, sha); assert.deepEqual(proposal.files, ['apps/web/src/greeter.js']); assert.match(proposal.patch, /^diff --git a\/apps\/web\/src\/greeter\.js/);
      assert.match(s.requests[0]!.messages[0].content, new RegExp(`pinned to commit ${sha.slice(0, 12)}`));
      if (m.mode === 'native') assert.deepEqual((s.requests[0]!.tools as any[]).map((t) => t.function.name), ['repo_search', 'repo_read', 'propose_change']); else assert.ok(s.requests[0]!.format);
    });
    it(`${m.name}: a bad edit is handed back as an error and the model fixes it (the proposal that counts is the corrected one)`, async () => {
      const s = scripted(m.caps, [m.call('repo_read', { path: 'apps/web/src/greeter.js' }), m.call('propose_change', { edits: [{ path: 'apps/web/src/greeter.js', find: "'hello '", replace: "'hullo '" }], summary: 'wrong' }), m.call('propose_change', { edits: FIX, summary: 'Fixed.' })]);
      const { result } = await drive(m.name, s.chat);
      assert.equal(result.success, true, JSON.stringify(result.failure)); assert.equal(result.tool_retries, 1); assert.equal(result.answer, 'Fixed.');
      assert.ok(result.steps.some((x) => x.outcome === 'tool_failed' && /propose_change: .*the text to find is not in the file/.test(String(x.error))), JSON.stringify(result.steps.map((x) => [x.outcome, x.error])));
      assert.match(JSON.stringify(s.requests[2]!.messages), /propose_change: /, 'the error text went back to the model');
      const last = result.evidence.at(-1)!; assert.ok(last.tool === 'propose_change'); assert.match(last.patch, /\+  return 'hello '/);
    });
    it(`${m.name}: answering after reading WITHOUT proposing is refused once, then fails: nothing is invented`, async () => {
      const s = scripted(m.caps, [m.call('repo_read', { path: 'apps/web/src/greeter.js' }), m.answer('I think the typo is on line 2.'), m.answer('Still just talking.')]);
      const { result } = await drive(m.name, s.chat);
      assert.equal(result.success, false); assert.equal(result.failure?.kind, 'malformed_tool_request'); assert.match(String(result.failure?.message), /you have not proposed a change/);
      assert.ok(!result.evidence.some((e) => e.tool === 'propose_change'));
    });
    it(`${m.name}: a tool outside the allowlist is never run, and a model that answers without looking at all fails explicitly`, async () => {
      const denied = scripted(m.caps, [m.call('write_file', { path: 'x.txt', content: 'x' }), m.call('write_file', { path: 'x.txt', content: 'x' })]);
      const a = await drive(m.name, denied.chat); assert.equal(a.result.success, false); assert.equal(a.result.failure?.kind, 'malformed_tool_request'); assert.equal(a.approvals.length, 0);
      assert.equal(fs.existsSync(path.join(repo, 'x.txt')), false);
      const talk = scripted(m.caps, [m.answer('Just change line 2.'), m.answer('Really, just change line 2.')]);
      const b = await drive(m.name, talk.chat); assert.equal(b.result.success, false); assert.equal(b.result.failure?.kind, 'no_tool_call'); assert.equal(talk.requests.length, 2, 'one nudge, then it fails explicitly');
    });
  }
  it('the prompts steer a small model: never guess a path, start with a search for a word from the goal; and the constrained prompt has NO example values to copy (run 1: smollm2 sent "optional folder" and "..." back verbatim)', () => {
    const spec = patchSpec(sha);
    for (const text of [spec.system, spec.constrainedSystem]) { assert.match(text, /Never guess a path/); assert.match(text, /Start by calling repo_search with a word from the goal/); assert.match(text, new RegExp(sha.slice(0, 12))); }
    assert.doesNotMatch(spec.constrainedSystem, /optional folder|"\.\.\."|exact old text|new text"|\{"action"/, 'no JSON template to echo back');
    assert.match(spec.constrainedSystem, /Leave out keys the tool does not use/);
  });
  it('keys that do not belong to a tool are dropped, never rejected (run 1: start/end on repo_search failed 6 of smollm2\'s 15)', () => {
    const spec = patchSpec(sha);
    const search = spec.checkCall('repo_search', { query: 'greet', path: '', start: 1, end: 60, find: '', edits: null });
    assert.equal(search.ok, true, JSON.stringify(search)); if (search.ok) { assert.equal(search.args.query, 'greet'); assert.ok(!('start' in search.args) && !('end' in search.args) && !('find' in search.args) && !('edits' in search.args)); }
    const read = spec.checkCall('repo_read', { path: 'apps/web/src/greeter.js', query: 'x', find: 'y', replace: 'z' }); assert.equal(read.ok, true); if (read.ok) { assert.equal(read.args.path, 'apps/web/src/greeter.js'); assert.ok(!('query' in read.args) && !('find' in read.args) && !('replace' in read.args)); }
    assert.equal(spec.checkCall('repo_read', { path: 'a.js', start: 1, end: 5 }).ok, true);
    assert.equal(spec.checkCall('delete_everything', {}).ok, false);
  });
  it('propose_change takes FLAT arguments from the model (path, find, replace) and still hands the governed tool one edit; the nested form and a new file are accepted too', async () => {
    const spec = patchSpec(sha);
    assert.deepEqual(spec.checkCall('propose_change', { path: 'a.js', find: 'x', replace: 'y', summary: 's', start: 3, query: 'q' }), { ok: true, args: { edits: [{ path: 'a.js', find: 'x', replace: 'y' }], summary: 's' } });
    assert.deepEqual(spec.checkCall('propose_change', { path: 'n.js', create: 'text' }), { ok: true, args: { edits: [{ path: 'n.js', create: 'text' }] } });
    assert.deepEqual(spec.checkCall('propose_change', { edits: FIX, summary: 's' }), { ok: true, args: { edits: FIX, summary: 's' } });
    for (const bad of [{}, { path: 'a.js' }, { path: 'a.js', find: '' , replace: 'y' }, { find: 'x', replace: 'y' }]) assert.equal(spec.checkCall('propose_change', bad).ok, false, JSON.stringify(bad));
    const flat = (spec.nativeTools[2] as any).function; assert.equal(flat.name, 'propose_change'); assert.deepEqual(Object.keys(flat.parameters.properties).sort(), ['create', 'find', 'path', 'replace', 'summary']); assert.deepEqual(flat.parameters.required, ['path']);
    // end to end: a flat call produces the same patch as the nested one
    const a = await drive('qwen2.5:3b', scripted(['tools'], [nativeCall('repo_read', { path: 'apps/web/src/greeter.js' }), nativeCall('propose_change', { path: 'apps/web/src/greeter.js', find: "'helo '", replace: "'hello '", summary: 'flat' })]).chat);
    const b = await drive('qwen2.5:3b', scripted(['tools'], [nativeCall('repo_read', { path: 'apps/web/src/greeter.js' }), nativeCall('propose_change', { edits: FIX, summary: 'nested' })]).chat);
    assert.equal(a.result.success, true, JSON.stringify(a.result.failure)); assert.equal(b.result.success, true);
    assert.equal((a.result.evidence.at(-1) as any).patch_sha256, (b.result.evidence.at(-1) as any).patch_sha256); assert.equal(a.result.answer, 'flat');
  });
  for (const m of MODELS) {
    it(`${m.name}: an empty reply or plain text BEFORE any tool call gets ONE nudge to call a tool, and then the run goes on (run 1: qwen2.5:3b returned empty replies, qwen2.5:1.5b answered in text 15 times)`, async () => {
      for (const first of [m.name.startsWith('qwen') ? turn({ content: '' }) : m.answer(''), m.answer('The total function is not defined, you should define it.')]) {
        const s = scripted(m.caps, [first, m.call('repo_read', { path: 'apps/web/src/greeter.js' }), m.call('propose_change', { path: 'apps/web/src/greeter.js', find: "'helo '", replace: "'hello '", summary: 'Fixed.' })]);
        const { result } = await drive(m.name, s.chat);
        assert.equal(result.success, true, JSON.stringify(result.failure)); assert.equal(result.answer, 'Fixed.');
        assert.ok(result.steps.some((x) => x.outcome === 'recovery_retry'), 'the nudge is a step on the record'); assert.match(JSON.stringify(s.requests[1]!.messages), /Do not answer in text\. Call repo_search now/);
      }
    });
  }
  it('a patch worker may be handed back FOUR recoverable errors in a row (guessed paths), not two; the fifth ends the run (run 1: several models guessed three paths)', async () => {
    const bad = (p: string) => nativeCall('repo_read', { path: p });
    const ok = scripted(['tools'], [bad('src/a.js'), bad('lib/b.js'), bad('c.py'), bad('d/e.js'), nativeCall('repo_read', { path: 'apps/web/src/greeter.js' }), nativeCall('propose_change', { path: 'apps/web/src/greeter.js', find: "'helo '", replace: "'hello '" })]);
    const a = await drive('qwen2.5:3b', ok.chat); assert.equal(a.result.success, true, JSON.stringify(a.result.failure)); assert.equal(a.result.tool_retries, 4);
    const tooMany = scripted(['tools'], [bad('a1.js'), bad('a2.js'), bad('a3.js'), bad('a4.js'), bad('a5.js'), nativeCall('repo_read', { path: 'apps/web/src/greeter.js' })]);
    const b = await drive('qwen2.5:3b', tooMany.chat); assert.equal(b.result.success, false); assert.equal(b.result.failure?.kind, 'tool_failed'); assert.match(String(b.result.failure?.message), /file not found: a5\.js/);
  });
  it('a malformed propose_change request (no edits) is repaired once, never run', async () => {
    const s = scripted(['tools'], [nativeCall('propose_change', { summary: 'x' }), nativeCall('propose_change', { summary: 'x' })]);
    const { result } = await drive('qwen2.5:3b', s.chat); assert.equal(result.success, false); assert.match(String(result.failure?.message), /propose_change needs path, find and replace/);
  });
});

function harness(over: { approve?: boolean; patchModel?: string; agentModel?: string | null; rounds?: number } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'local-sim-run-'));
  const store = new ConvoyStore(path.join(dir, 'c.json')); const runStore = new RunStore(path.join(dir, 'r.json'));
  const patchModel = over.patchModel ?? 'qwen2.5:3b';
  const planned = planConvoy({ goal: 'Fix the typo in the greeting so the greeting test passes', mode: 'simulate', lookupModel: patchModel, routing: { source: 'operator', model: patchModel, reason: 'chosen by the operator' }, agentModel: over.agentModel === undefined ? 'mercury-2' : over.agentModel, isLocalModel: (m) => !m.startsWith('mercury'), availableTools: TOOLS, now: 1, costOf: () => ({ usd: 0, basis: 'test' }) });
  assert.ok(planned.ok, JSON.stringify(planned));
  const plan = (planned as any).plan; plan.simulation.checks = ['test']; plan.simulation.max_rounds = over.rounds ?? 1;
  const c = store.create(plan.goal, plan, evaluatePolicy(plan)); store.submit(c.id); store.decide(c.id, 'approve', 'human');
  const approvals: Array<{ tool: string; reason: string }> = []; const agentCalls: string[] = [];
  const deps = (chat: LocalChat): RunnerDeps => ({
    store, runStore, repo: null, isLocalModel: (m) => !m.startsWith('mercury'), chat,
    newChildRun: (g, runId, model, convoyId, workerId) => runStore.create({ id: runId, session_id: 's', goal: g, model, provider: model === 'sandbox' ? 'sandbox' : 'ollama', status: 'running', started_at: Date.now(), steps: [], current_step: 0, tool_calls: 0, prompt_tokens: 0, completion_tokens: 0, cost_usd: 0, approvals: { approved: 0, denied: 0 }, files: [], jobId: convoyId, specialistId: workerId } as RunRecord),
    hooksFor: (_r, signal, allowedTools) => ({ ...lookupHooks({ signal, requestApproval: async (tool, _a, reason) => { approvals.push({ tool, reason }); return over.approve ?? true; } }).hooks, allowedTools }),
    runAgent: async (g, m): Promise<AgentRunResult> => { agentCalls.push(m); throw new Error('Mercury must not be used for a local patch worker'); },
    runSpecialists: async () => ({}), broadcast: () => {}, signal: new AbortController().signal,
  });
  return { c, deps, approvals, agentCalls, store, runStore };
}

describe('a SIMULATE convoy with a local patch worker, end to end', () => {
  for (const m of MODELS) {
    it(`${m.name}: proposes, a human approves the run, the sandbox verifies; Mercury is never called and the cost is zero`, { skip }, async () => {
      const h = harness({ patchModel: m.name });
      assert.equal(h.c.plan.simulation?.patch_local, true); assert.equal(h.c.workers[0]!.model, m.name);
      const s = scripted(m.caps, [m.call('repo_read', { path: 'apps/web/src/greeter.js' }), m.call('propose_change', { edits: FIX, summary: 'Fixes the typo in the greeting.' })]);
      const c = await executeConvoy(h.deps(s.chat), h.c.id);
      assert.equal(c.state, 'COMPLETED', JSON.stringify(c.error)); assert.equal(c.outcome, 'success'); assert.equal(c.simulation!.verified, true); assert.equal(c.simulation!.proposed_by, m.name);
      assert.deepEqual(h.agentCalls, [], 'the Mercury agent loop was not used'); assert.equal(c.cost_usd, 0);
      assert.equal(h.approvals.length, 1); assert.equal(h.approvals[0]!.tool, 'run_checks');
      assert.match(c.final_answer!, new RegExp(`^Proposed change by ${m.name.replace('.', '\\.')} on commit`)); assert.match(c.final_answer!, /verified: yes/);
      const run = h.runStore.get(c.run_ids[0]!)!; assert.equal(run.model, m.name); assert.ok(run.steps.length >= 2, 'the local steps are on the run record');
      assert.ok(JSON.stringify(run.steps).includes('route: lane=patch'), 'the route line names the lane and the model');
      assert.ok(c.policy.rules.some((r) => r.id === 'source-stays-local'));
    });
  }
  it('a local model that never proposes ends the convoy FAILED with no_patch-style failure and the sandbox is never asked (no approval prompt)', { skip }, async () => {
    const h = harness();
    const s = scripted(['tools'], [turn({ content: 'I would change the greeting.' })]);
    const c = await executeConvoy(h.deps(s.chat), h.c.id);
    assert.equal(c.state, 'FAILED'); assert.equal(h.approvals.length, 0); assert.equal(c.workers.find((w) => w.id === 'checks-1')!.status, 'skipped'); assert.equal(c.simulation, undefined);
    assert.match(c.error ?? '', /patch worker failed: agent_failed|agent_failed:/); assert.deepEqual(h.agentCalls, []);
    assert.ok(s.requests.length >= 1 && s.requests.every((r) => r.timeoutMs === 300_000), `a local patch worker waits up to 300 s per call, got ${JSON.stringify(s.requests.map((r) => r.timeoutMs))}`);
  });
  it('a local proposal that does not fix the problem is PARTIAL (verified: NO), and the model\'s claim that tests pass changes nothing', { skip }, async () => {
    const h = harness();
    const s = scripted(['tools'], [nativeCall('repo_read', { path: 'apps/web/src/greeter.js' }), nativeCall('propose_change', { edits: [{ path: 'apps/web/src/greeter.js', find: "'helo '", replace: "'hullo '" }], summary: 'All tests pass now.' })]);
    const c = await executeConvoy(h.deps(s.chat), h.c.id);
    assert.equal(c.state, 'PARTIAL'); assert.equal(c.simulation!.verified, false); assert.match(c.final_answer!, /Its summary: All tests pass now\./); assert.match(c.final_answer!, /verified: NO/);
  });
  it('a denied sandbox run leaves the local proposal kept and marked not verified', { skip }, async () => {
    const h = harness({ approve: false });
    const s = scripted(['tools'], [nativeCall('repo_read', { path: 'apps/web/src/greeter.js' }), nativeCall('propose_change', { edits: FIX, summary: 'Fix.' })]);
    const c = await executeConvoy(h.deps(s.chat), h.c.id);
    assert.equal(c.state, 'PARTIAL'); assert.equal(c.simulation!.checks_ran, false); assert.equal(c.simulation!.verified, null); assert.match(c.final_answer!, /NOT VERIFIED/);
  });
});
