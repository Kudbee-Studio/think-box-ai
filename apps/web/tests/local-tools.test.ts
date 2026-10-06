// Phase 2 proof: governed tool calling for local Ollama models. Qwen-style (native tools) and Gemma-style (constrained JSON) models drive the SAME
// live_lookup tool through runGovernedTool. A scripted model makes each case deterministic; a fake Ollama HTTP server proves the wire format.
import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { newRunContext } from '../agent.ts';
import { CONSTRAINED_SCHEMA, parseConstrainedTurn, parseNativeTurn, runLocalToolLoop, toolModeFor, type LocalChat } from '../local-tools.ts';
import { createModelClients, type OllamaChatTurn } from '../ollama-client.ts';
import { lookupHooks, startFakeGithub, type FakeGithub } from './helpers/lookup-hooks.ts';

const REPO = 'Acme/widgets';
const pr = (number: number, o: Record<string, unknown> = {}) => ({ number, title: `PR ${number}`, state: 'closed', merged_at: '2026-10-04T10:00:00Z', draft: false, user: { login: 'dev' }, head: { ref: `feat/pr${number}` }, updated_at: '2026-10-04T10:00:00Z', html_url: `https://github.com/Acme/widgets/pull/${number}`, ...o });
const run = (conclusion: string) => ({ workflow_runs: [{ name: 'CI', head_branch: 'feat/pr361', event: 'push', status: 'completed', conclusion, run_number: 812, html_url: 'https://github.com/Acme/widgets/actions/runs/1', updated_at: '2026-10-04T10:00:00Z' }] });

const turn = (o: Partial<OllamaChatTurn>): OllamaChatTurn => ({ content: '', tool_calls: [], prompt_tokens: 10, completion_tokens: 5, latency_ms: 7, ...o });
const nativeCall = (args: unknown, name = 'live_lookup') => turn({ tool_calls: [{ function: { name, arguments: args } }] });
const jsonTurn = (body: unknown) => turn({ content: JSON.stringify(body) });

/** A scripted model: replays `turns` in order and records every request it was sent. */
function scripted(capabilities: string[], turns: OllamaChatTurn[]) {
  const requests: Array<{ messages: any[]; tools?: unknown[]; format?: unknown }> = [];
  const chat: LocalChat = {
    modelCapabilities: async () => capabilities,
    chatOnce: async (_m, messages, opts = {}) => { requests.push({ messages: JSON.parse(JSON.stringify(messages)), tools: opts.tools, format: opts.format }); return turns.shift() ?? turn({ error: 'script exhausted' }); },
  };
  return { chat, requests };
}

const MODELS = [
  { name: 'qwen2.5:3b', caps: ['completion', 'tools'], mode: 'native' as const, call: (args: unknown) => nativeCall(args), answer: (text: string) => turn({ content: text }) },
  { name: 'gemma3:4b', caps: ['completion', 'vision'], mode: 'constrained' as const, call: (args: any) => jsonTurn({ action: 'call', ...args }), answer: (text: string) => jsonTurn({ action: 'answer', answer: text }) },
];

describe('local tool calling', () => {
  let gh: FakeGithub;
  let prev: string | undefined;
  before(async () => {
    gh = await startFakeGithub({ 'pulls?': { body: [pr(361), pr(360)] }, 'actions/runs': { body: run('failure') }, issues: { status: 500, body: 'boom' }, branches: { body: [{ name: 'main', protected: true }, { name: 'feat/pr361' }] } });
    prev = process.env.KUDBEE_GITHUB_API; process.env.KUDBEE_GITHUB_API = gh.url; process.env.KUDBEE_REPO = REPO;
  });
  after(async () => { if (prev === undefined) delete process.env.KUDBEE_GITHUB_API; else process.env.KUDBEE_GITHUB_API = prev; delete process.env.KUDBEE_REPO; await gh.close(); });
  const drive = (model: string, chat: LocalChat, goal: string, approve: boolean | ((t: string) => boolean) = true, maxSteps?: number) => {
    const h = lookupHooks({}, approve);
    return runLocalToolLoop({ model, goal, hooks: h.hooks, context: newRunContext(), chat, repo: REPO, maxSteps }).then((result) => ({ result, ...h }));
  };

  it('picks native tool calling for a model Ollama says supports tools, constrained JSON otherwise', async () => {
    assert.equal(await toolModeFor('qwen2.5:3b', scripted(['completion', 'tools'], []).chat), 'native');
    assert.equal(await toolModeFor('gemma3:4b', scripted(['completion', 'vision'], []).chat), 'constrained');
    assert.equal(await toolModeFor('unreachable', scripted([], []).chat), 'constrained');
  });

  for (const m of MODELS) {
    describe(`${m.name} (${m.mode})`, () => {
      it('successful live-data lookup: the tool runs through the governed path, evidence is kept, the answer is grounded', async () => {
        gh.hits.length = 0;
        const { chat, requests } = scripted(m.caps, [m.call({ recipe: 'latest_pr' }), m.answer('The last PR is #361, PR 361, and it is merged.')]);
        const { result, approvals, events } = await drive(m.name, chat, 'What is the last PR?');
        assert.equal(result.success, true, JSON.stringify(result.failure));
        assert.equal(result.mode, m.mode);
        assert.equal(result.tool_calls, 1);
        assert.equal(result.evidence[0]!.items[0]!.kind, 'pr');
        assert.equal(result.grounding?.status, 'GROUNDED');
        assert.deepEqual(gh.hits, ['/repos/Acme/widgets/pulls?state=all&sort=created&direction=desc&per_page=5']);
        assert.equal(approvals.length, 1, 'first network access asked for approval, like Mercury');
        assert.equal(events.filter((e) => e.kind === 'tool').length, 1, 'one governed tool event');
        assert.deepEqual(result.steps.map((s) => s.outcome), ['tool_ok', 'answer']);
        assert.equal(result.prompt_tokens, 20);
        assert.equal(result.completion_tokens, 10);
        // wire shape: native sends the one governed tool schema, constrained sends the JSON schema
        if (m.mode === 'native') { assert.equal((requests[0]!.tools as any[])[0].function.name, 'live_lookup'); assert.equal(requests[0]!.format, undefined); }
        else { assert.deepEqual(requests[0]!.format, CONSTRAINED_SCHEMA); assert.equal(requests[0]!.tools, undefined); }
        // the second turn was handed the tool result as plain facts
        assert.match(JSON.stringify(requests[1]!.messages), /Most recent pull requests in Acme\/widgets/);
      });

      it('an ungrounded answer is reported as GROUNDING FAILED in the result, not hidden', async () => {
        const { chat } = scripted(m.caps, [m.call({ recipe: 'latest_pr' }), m.answer('The last PR is #999 and it was merged.')]);
        const { result } = await drive(m.name, chat, 'What is the last PR?');
        assert.equal(result.success, true);
        assert.equal(result.grounding?.status, 'GROUNDING FAILED');
        assert.ok(result.grounding!.unsupported.some((u) => u.claim.includes('999')));
      });

      it('a malformed request is never executed: one repair turn, then success', async () => {
        gh.hits.length = 0;
        const { chat, requests } = scripted(m.caps, [m.call({ recipe: 'merge_everything' }), m.call({ recipe: 'open_prs' }), m.answer('There is 1 open item: #361 (PR 361).')]);
        const { result } = await drive(m.name, chat, 'Which PRs are open?');
        assert.deepEqual(result.steps.map((s) => s.outcome), ['malformed', 'tool_ok', 'answer']);
        assert.equal(gh.hits.filter((h) => !h.includes('/search/issues')).length, 1, 'only the repaired request reached GitHub (plus its one read-only count request)');
        assert.equal(gh.hits.filter((h) => h.includes('/search/issues')).length, 1);
        assert.match(JSON.stringify(requests[1]!.messages), /That request was invalid: recipe must be one of/);
      });

      it('two malformed requests in a row fail explicitly and nothing runs', async () => {
        gh.hits.length = 0;
        const { chat } = scripted(m.caps, [m.call({ recipe: 'x' }), m.call({ recipe: 'repo_wipe', url: 'http://evil' })]);
        const { result, approvals } = await drive(m.name, chat, 'What is the last PR?');
        assert.equal(result.success, false);
        assert.equal(result.failure?.kind, 'malformed_tool_request');
        assert.equal(result.tool_calls, 0);
        assert.equal(gh.hits.length, 0);
        assert.equal(approvals.length, 0);
        assert.equal(result.answer, undefined);
      });

      it('another repository, and unknown arguments, are refused before any network access', async () => {
        gh.hits.length = 0;
        const { chat } = scripted(m.caps, [m.call({ recipe: 'latest_pr', repo: 'evil/other' }), m.call({ recipe: 'latest_pr', repo: 'evil/other' })]);
        const { result } = await drive(m.name, chat, 'What is the last PR of evil/other?');
        assert.equal(result.failure?.kind, 'malformed_tool_request');
        assert.match(result.failure!.message, /only the configured repository/);
        assert.equal(gh.hits.length, 0);
      });

      it('a denied approval stops the goal: no GitHub call, no answer, classified as denied', async () => {
        gh.hits.length = 0;
        const { chat, requests } = scripted(m.caps, [m.call({ recipe: 'latest_pr' }), m.answer('should never be asked')]);
        const { result } = await drive(m.name, chat, 'What is the last PR?', false);
        assert.equal(result.success, false);
        assert.equal(result.failure?.kind, 'tool_denied');
        assert.match(result.failure!.message, /Denied by human reviewer/);
        assert.equal(gh.hits.length, 0);
        assert.equal(requests.length, 1, 'the model was not asked again');
        assert.equal(result.steps.at(-1)!.outcome, 'tool_denied');
      });

      it('a tool failure is a failure with the reason, never a made-up answer', async () => {
        const { chat, requests } = scripted(m.caps, [m.call({ recipe: 'open_issues' }), m.answer('There are no issues.')]);
        const { result } = await drive(m.name, chat, 'Which issues are open?');
        assert.equal(result.success, false);
        assert.equal(result.failure?.kind, 'tool_failed');
        assert.match(result.failure!.message, /HTTP 500/);
        assert.equal(result.answer, undefined);
        assert.equal(requests.length, 1);
      });

      it('answering without ever looking anything up is a failure (it cannot be verified)', async () => {
        const { chat } = scripted(m.caps, [m.answer('The last PR is #12.')]);
        const { result } = await drive(m.name, chat, 'What is the last PR?');
        assert.equal(result.success, false);
        assert.equal(result.failure?.kind, 'no_tool_call');
      });

      it('a genuinely multi-step lookup: the second request uses a value only the first result contains', async () => {
        gh.hits.length = 0;
        // Step 1 returns head branch feat/pr361; the CI question for "the last PR's branch" needs it.
        const { chat, requests } = scripted(m.caps, [m.call({ recipe: 'latest_pr' }), m.call({ recipe: 'ci_status', branch: 'feat/pr361' }), m.answer('The last PR is #361 on branch feat/pr361, and its newest CI run failed (run 812).')]);
        const { result } = await drive(m.name, chat, "Did CI pass on the last PR's branch?");
        assert.equal(result.success, true, JSON.stringify(result.failure));
        assert.equal(result.tool_calls, 2);
        assert.deepEqual(result.steps.map((s) => s.outcome), ['tool_ok', 'tool_ok', 'answer']);
        assert.deepEqual(result.evidence.map((e) => e.recipe), ['latest_pr', 'ci_status']);
        assert.equal(result.evidence[1]!.branch, 'feat/pr361');
        assert.match(gh.hits[1]!, /actions\/runs\?per_page=5&exclude_pull_requests=true&branch=feat%2Fpr361/);
        assert.equal(result.grounding?.status, 'GROUNDED', JSON.stringify(result.grounding?.unsupported));
        assert.match(JSON.stringify(requests[2]!.messages), /The newest run: failure/);
      });

      it('stops at the step limit instead of looping forever', async () => {
        const { chat } = scripted(m.caps, Array.from({ length: 8 }, () => m.call({ recipe: 'branches' })));
        const { result } = await drive(m.name, chat, 'List branches forever', true, 2);
        assert.equal(result.success, false);
        assert.equal(result.failure?.kind, 'step_limit');
        assert.equal(result.tool_calls, 2);
      });

      it('a model failure is reported as such', async () => {
        const { chat } = scripted(m.caps, [turn({ error: 'model not found' })]);
        const { result } = await drive(m.name, chat, 'What is the last PR?');
        assert.deepEqual({ ok: result.success, kind: result.failure?.kind, msg: result.failure?.message }, { ok: false, kind: 'model_error', msg: 'model not found' });
      });
    });
  }

  it('native: a call to a tool that does not exist, or arguments that are not JSON, is malformed', async () => {
    const { chat } = scripted(['tools'], [nativeCall({ recipe: 'latest_pr' }, 'rm_rf'), nativeCall('{not json')]);
    const { result } = await drive('qwen2.5:3b', chat, 'What is the last PR?');
    assert.equal(result.failure?.kind, 'malformed_tool_request');
    assert.equal(result.tool_calls, 0);
    assert.match(result.steps[0]!.error!, /unknown tool "rm_rf"/);
    assert.match(result.steps[1]!.error!, /not valid JSON/);
  });
  it('native: arguments sent as a JSON string are accepted', async () => {
    const { chat } = scripted(['tools'], [nativeCall('{"recipe":"branches"}'), turn({ content: 'There are two branches.' })]);
    const { result } = await drive('qwen2.5:3b', chat, 'List the branches');
    assert.equal(result.tool_calls, 1);
  });
  it('constrained: non-JSON, a non-object and a bad action are malformed', () => {
    for (const content of ['I will look it up', '[1]', '{"action":"explode"}']) assert.equal(parseConstrainedTurn(turn({ content })).kind, 'malformed', content);
    assert.equal(parseConstrainedTurn(turn({ content: '' })).kind, 'empty', 'an empty reply is recoverable, not malformed');
    assert.equal(parseConstrainedTurn(turn({ content: '   ' })).kind, 'empty');
    assert.equal(parseConstrainedTurn(turn({ content: '{"action":"answer","answer":"  "}' })).kind, 'empty');
    assert.equal(parseNativeTurn(turn({})).kind, 'empty');
  });
});

describe('the Ollama client sends the governed request on the wire', () => {
  let server: http.Server; const bodies: Record<string, any>[] = []; let base = '';
  before(async () => {
    server = http.createServer((req, res) => {
      let b = ''; req.on('data', (d) => { b += d; });
      req.on('end', () => {
        const body = b ? JSON.parse(b) : {}; bodies.push({ url: req.url, ...body });
        res.setHeader('content-type', 'application/json');
        if (req.url === '/api/show') return void res.end(JSON.stringify({ capabilities: body.model === 'qwen2.5:3b' ? ['completion', 'tools'] : ['completion', 'vision'] }));
        if (body.model === 'missing') { res.statusCode = 404; return void res.end(JSON.stringify({ error: 'model "missing" not found' })); }
        res.end(JSON.stringify({ message: body.tools ? { role: 'assistant', content: '', tool_calls: [{ function: { name: 'live_lookup', arguments: { recipe: 'latest_pr' } } }] } : { role: 'assistant', content: '{"action":"call","recipe":"latest_pr"}' }, done: true, prompt_eval_count: 161, eval_count: 23 }));
      });
    });
    await new Promise<void>((r) => server.listen(0, '127.0.0.1', r));
    base = `http://127.0.0.1:${(server.address() as { port: number }).port}`;
  });
  after(() => new Promise<void>((r) => server.close(() => r())));
  const clients = () => createModelClients({ ollamaBaseUrl: base, janusBaseUrl: 'http://127.0.0.1:9', janusEnabled: () => false });

  it('probes capabilities once per model and sends tools (native) or format (constrained) with temperature 0', async () => {
    bodies.length = 0;
    const c = clients();
    assert.deepEqual(await c.modelCapabilities('qwen2.5:3b'), ['completion', 'tools']);
    await c.modelCapabilities('qwen2.5:3b');
    assert.equal(bodies.filter((b) => b.url === '/api/show').length, 1, 'cached');
    const native = await c.chatOnce('qwen2.5:3b', [{ role: 'user', content: 'hi' }], { tools: [{ type: 'function' }] });
    assert.equal(native.tool_calls[0]!.function!.name, 'live_lookup');
    assert.equal(native.prompt_tokens, 161);
    assert.equal(native.completion_tokens, 23);
    const chat = bodies.find((b) => b.url === '/api/chat')!;
    assert.equal(chat.stream, false);
    assert.equal(chat.options.temperature, 0);
    assert.ok(Array.isArray(chat.tools));
    const constrained = await c.chatOnce('gemma3:4b', [{ role: 'user', content: 'hi' }], { format: CONSTRAINED_SCHEMA });
    assert.match(constrained.content, /latest_pr/);
    assert.deepEqual(bodies.at(-1)!.format, CONSTRAINED_SCHEMA);
  });
  it('reports a missing model or an unreachable Ollama as an error, never an empty success', async () => {
    const c = clients();
    assert.match((await c.chatOnce('missing', [])).error!, /not found/);
    const dead = createModelClients({ ollamaBaseUrl: 'http://127.0.0.1:9', janusBaseUrl: 'http://127.0.0.1:9', janusEnabled: () => false });
    assert.ok((await dead.chatOnce('x', [], { timeoutMs: 2000 })).error);
    assert.deepEqual(await dead.modelCapabilities('x'), []);
  });
});
