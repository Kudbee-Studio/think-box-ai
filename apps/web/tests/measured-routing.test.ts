// Routing from the measured table: the table decides, a model that fails the rule is never picked, investigation never lands on a JSON-prompted model.
import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { newRunContext } from '../agent.ts';
import { COLD_LOAD_MS, LOCAL_CALL_TIMEOUT_MS, lookupSpec, runLocalToolLoop, type LocalChat } from '../local-tools.ts';
import { routeLine } from '../convoy-runner.ts';
import { DEFAULT_EVAL_FILE, goalClassOf, loadMeasurements, pickMeasured, pickRepoStarter, rerouteLookup, type Measurements } from '../measured-routing.ts';
import { planConvoy } from '../mayor.ts';
import type { Trial } from '../local-eval.ts';
import type { OllamaChatTurn } from '../ollama-client.ts';
import { lookupHooks } from './helpers/lookup-hooks.ts';

const trial = (model: string, cls: 'lookup' | 'repo', outcome: Trial['outcome'], mode = 'native', latency = 10_000): Trial => ({ model, task: 't', class: cls, outcome, why: '', latency_ms: latency, tool_calls: 1, tokens: 500, mode });
const many = (model: string, cls: 'lookup' | 'repo', pass: number, total: number, mode: string, over: Partial<Record<Trial['outcome'], number>> = {}): Trial[] => {
  const out: Trial[] = []; let p = pass;
  for (let i = 0; i < total; i += 1) out.push(trial(model, cls, p-- > 0 ? 'pass' : 'wrong', mode));
  for (const [o, n] of Object.entries(over)) for (let i = 0; i < n!; i += 1) out[i] = trial(model, cls, o as Trial['outcome'], mode);
  return out;
};
const table = (trials: Trial[]): Measurements => ({ trials, generated_at: '2026-10-05T00:00:00Z', file: '/x/local-eval.json' });
const INSTALLED = ['gemma3:4b', 'qwen2.5:3b', 'qwen2.5:1.5b'];

describe('table -> route', () => {
  it('a lookup goes to the installed model the table qualifies, and the reason cites the evidence', () => {
    const m = table([...many('gemma3:4b', 'lookup', 15, 15, 'constrained'), ...many('qwen2.5:3b', 'lookup', 8, 10, 'native', { ungrounded: 1 })]);
    const pick = pickMeasured('lookup', INSTALLED, m);
    assert.equal(pick.model, 'gemma3:4b');
    assert.match(pick.reason, /gemma3:4b measured 15\/15 on lookup goals with 0 ungrounded/);
  });
  it('when several qualify, the better pass rate wins, then the faster median', () => {
    const m = table([...many('qwen2.5:3b', 'lookup', 9, 10, 'native'), ...many('gemma3:4b', 'lookup', 10, 10, 'constrained')]);
    assert.equal(pickMeasured('lookup', INSTALLED, m).model, 'gemma3:4b');
    const tie = table([...Array.from({ length: 6 }, () => trial('qwen2.5:3b', 'lookup', 'pass', 'native', 5000)), ...Array.from({ length: 6 }, () => trial('gemma3:4b', 'lookup', 'pass', 'constrained', 9000))]);
    assert.equal(pickMeasured('lookup', INSTALLED, tie).model, 'qwen2.5:3b');
  });
  it('gemma not installed: it is not picked, and the next qualified model (or nothing) is', () => {
    const m = table([...many('gemma3:4b', 'lookup', 15, 15, 'constrained'), ...many('qwen2.5:1.5b', 'lookup', 9, 10, 'native')]);
    assert.equal(pickMeasured('lookup', ['qwen2.5:1.5b'], m).model, 'qwen2.5:1.5b');
    const none = pickMeasured('lookup', ['smollm2:360m'], m);
    assert.equal(none.model, null); assert.match(none.reason, /no installed model has been measured/);
  });
  it('the real measured table, as committed: gemma3:4b for lookups, nothing for repository investigation', () => {
    const real = loadMeasurements(DEFAULT_EVAL_FILE);
    assert.ok(real, 'the measured table is on file');
    assert.equal(pickMeasured('lookup', INSTALLED, real).model, 'gemma3:4b');
    assert.equal(pickMeasured('repo', INSTALLED, real).model, null);
  });
});

describe('the rule still gates', () => {
  it('one ungrounded answer, a pass rate under 80%, or fewer than 6 trials each disqualify a model', () => {
    assert.equal(pickMeasured('lookup', INSTALLED, table(many('gemma3:4b', 'lookup', 14, 15, 'constrained', { ungrounded: 1 }))).model, null);
    assert.equal(pickMeasured('lookup', INSTALLED, table(many('gemma3:4b', 'lookup', 7, 10, 'constrained'))).model, null);
    assert.equal(pickMeasured('lookup', INSTALLED, table(many('gemma3:4b', 'lookup', 5, 5, 'constrained'))).model, null);
    const r = pickMeasured('lookup', INSTALLED, table(many('qwen2.5:3b', 'lookup', 8, 10, 'native', { ungrounded: 1 })));
    assert.match(r.reason, /no installed model is measured sufficient for lookup goals \(best: qwen2\.5:3b 7\/10, 1 ungrounded\)/);
  });
  it('repository investigation never picks a JSON-prompted model, however well it scored, but does pick a native-tool one', () => {
    const m = table([...many('gemma3:4b', 'repo', 10, 10, 'constrained'), ...many('qwen2.5:3b', 'repo', 9, 10, 'native')]);
    assert.equal(pickMeasured('repo', INSTALLED, m).model, 'qwen2.5:3b');
    assert.equal(pickMeasured('repo', ['gemma3:4b'], table(many('gemma3:4b', 'repo', 10, 10, 'constrained'))).model, null);
  });
  it('lookup measurements do not qualify a model for investigation (classes are separate)', () => {
    assert.equal(pickMeasured('repo', INSTALLED, table(many('qwen2.5:3b', 'lookup', 10, 10, 'native'))).model, null);
  });
});

describe('missing or broken inputs say so and decide nothing', () => {
  let dir = '';
  before(() => { dir = fs.mkdtempSync(path.join(os.tmpdir(), 'routing-')); });
  after(() => fs.rmSync(dir, { recursive: true, force: true }));
  it('no file, a non-table file, garbage, an empty table: null; unknown installed list: null with a reason', () => {
    assert.equal(loadMeasurements(path.join(dir, 'nope.json')), null);
    for (const [name, body] of [['a.json', '{"x":1}'], ['b.json', 'not json'], ['c.json', '{"trials":[]}'], ['d.json', '{"trials":[{"model":3}]}']] as const) { fs.writeFileSync(path.join(dir, name), body); assert.equal(loadMeasurements(path.join(dir, name)), null, name); }
    assert.match(pickMeasured('lookup', INSTALLED, null).reason, /no measurements on file/);
    assert.match(pickMeasured('lookup', null, table(many('gemma3:4b', 'lookup', 15, 15, 'constrained'))).reason, /not known yet/);
  });
  it('a table written to disk is read back (and KUDBEE_LOCAL_EVAL points at it)', () => {
    const f = path.join(dir, 'ok.json');
    fs.writeFileSync(f, JSON.stringify({ generated_at: '2026-10-05T00:00:00Z', trials: many('gemma3:4b', 'lookup', 6, 6, 'constrained') }));
    assert.equal(loadMeasurements(f)!.trials.length, 6);
    process.env.KUDBEE_LOCAL_EVAL = f;
    try { assert.equal(loadMeasurements()!.file, f); } finally { delete process.env.KUDBEE_LOCAL_EVAL; }
  });
  it('goalClassOf maps the repo-goal flag to a class', () => { assert.equal(goalClassOf(true), 'repo'); assert.equal(goalClassOf(false), 'lookup'); });
});

describe('the plan shows how the model was chosen', () => {
  const base = { goal: 'What is the last PR?', lookupModel: 'gemma3:4b', agentModel: null, isLocalModel: () => true, availableTools: ['live_lookup'], costOf: () => ({ usd: 0, basis: 'local' }), now: 1 };
  it('routing is carried onto the plan, or null when the caller gave none', () => {
    const routing = { source: 'measured' as const, model: 'gemma3:4b', reason: 'gemma3:4b measured 15/15' };
    const a = planConvoy({ ...base, routing }); assert.ok(a.ok); assert.deepEqual(JSON.parse(JSON.stringify(a.plan.routing)), routing);
    const b = planConvoy(base); assert.ok(b.ok); assert.equal(b.plan.routing, null);
  });
});

describe('the lookup lane: generous timeout, cold vs warm on the record', () => {
  const turn = (o: Partial<OllamaChatTurn>): OllamaChatTurn => ({ content: '', tool_calls: [], prompt_tokens: 10, completion_tokens: 5, latency_ms: 3, ...o });
  const run = async (callTimeoutMs?: number) => {
    const seen: Array<number | undefined> = [];
    const turns = [turn({ content: JSON.stringify({ action: 'call', tool: 'live_lookup', recipe: 'latest_pr' }), load_ms: 50_500, latency_ms: 52_000 }), turn({ content: JSON.stringify({ action: 'answer', answer: 'ok' }), load_ms: 0 })];
    const chat: LocalChat = { modelCapabilities: async () => [], chatOnce: async (_m, _msgs, o = {}) => { seen.push(o.timeoutMs); return turns.shift() ?? turn({ error: 'exhausted' }); } };
    const h = lookupHooks({});
    const result = await runLocalToolLoop({ model: 'gemma3:4b', goal: 'What is the last PR?', hooks: h.hooks, context: newRunContext(), chat, repo: 'Acme/widgets', spec: lookupSpec('Acme/widgets'), ...(callTimeoutMs ? { callTimeoutMs } : {}) });
    return { seen, result };
  };
  it('every model call gets at least 60 s (cold load), never a short cap; the default is explicit', async () => {
    assert.ok(LOCAL_CALL_TIMEOUT_MS >= 60_000);
    const { seen } = await run();
    assert.ok(seen.length >= 1 && seen.every((t) => t === LOCAL_CALL_TIMEOUT_MS), JSON.stringify(seen));
    assert.deepEqual((await run(90_000)).seen.every((t) => t === 90_000), true);
  });
  it('the loop sums the model-load time, keeps it on the step, and the route line says cold or warm', async () => {
    const { result } = await run();
    assert.equal(result.cold_load_ms, 50_500);
    assert.equal(result.steps[0]!.load_ms, 50_500);
    assert.match(routeLine('lookup', 'gemma3:4b', 'constrained', 52_000, result.cold_load_ms), /^route: lane=lookup model=gemma3:4b mode=constrained latency=52\.0s cold \(model load 50\.5s\)$/);
    assert.match(routeLine('lookup', 'gemma3:4b', 'constrained', 8_300, 0), /latency=8\.3s warm$/);
    assert.equal(COLD_LOAD_MS, 1500);
  });
});

describe('rerouteLookup: a chosen model the table does not qualify is replaced, visibly', () => {
  const m = table([...many('gemma3:4b', 'lookup', 15, 15, 'constrained'), ...many('qwen2.5:3b', 'lookup', 8, 10, 'native', { ungrounded: 1 })]);
  it('qwen2.5:3b (measured insufficient) -> gemma3:4b, and the reason names both measurements', () => {
    const r = rerouteLookup('qwen2.5:3b', INSTALLED, m, {});
    assert.equal(r?.model, 'gemma3:4b');
    assert.match(r!.why, /gemma3:4b measured 15\/15 on lookup goals/);
    assert.match(r!.why, /qwen2\.5:3b measured 7\/10 on lookups with 1 ungrounded, which does not meet the rule/);
  });
  it('a never-measured model is replaced too, and says it has no measurements', () => {
    assert.match(rerouteLookup('smollm2:360m', [...INSTALLED, 'smollm2:360m'], m, {})!.why, /smollm2:360m has no lookup measurements/);
  });
  it('a model that already meets the rule is never replaced; nothing qualified or nothing known means leave it alone', () => {
    assert.equal(rerouteLookup('gemma3:4b', INSTALLED, m, {}), null);
    assert.equal(rerouteLookup('qwen2.5:3b', ['qwen2.5:3b', 'qwen2.5:1.5b'], m, {}), null, 'gemma is not installed');
    assert.equal(rerouteLookup('qwen2.5:3b', null, m, {}), null);
    assert.equal(rerouteLookup('qwen2.5:3b', INSTALLED, null, {}), null);
  });
  it('KUDBEE_MEASURED_ROUTING=off turns it off', () => {
    assert.equal(rerouteLookup('qwen2.5:3b', INSTALLED, m, { KUDBEE_MEASURED_ROUTING: 'off' }), null);
  });
});

describe('pickRepoStarter: a repository goal always starts on a local model (P3.36)', () => {
  const why = 'no installed model is measured sufficient for repo goals (best: qwen2.5:3b 4/6, 2 ungrounded)';
  it('takes the best-measured installed model that ran in native tool mode, and says the escalation is the backstop', () => {
    const m = table([...many('qwen2.5:3b', 'repo', 4, 6, 'native', { ungrounded: 2 }), ...many('qwen2.5:1.5b', 'repo', 1, 6, 'native'), ...many('gemma3:4b', 'repo', 6, 6, 'constrained')]);
    const r = pickRepoStarter(INSTALLED, m, 'smollm2:360m', why);
    assert.equal(r.model, 'qwen2.5:3b');
    assert.match(r.reason, /no installed model is measured sufficient.*starting on qwen2\.5:3b \(best measured, \d+\/6\) and escalating to the agent model/);
  });
  it('ignores JSON-prompted models and models that are not installed, then falls back to the configured local model without inventing a measurement', () => {
    const m = table([...many('gemma3:4b', 'repo', 6, 6, 'constrained'), ...many('llama3:8b', 'repo', 6, 6, 'native')]);
    const r = pickRepoStarter(INSTALLED, m, 'qwen2.5:1.5b', why);
    assert.equal(r.model, 'qwen2.5:1.5b');
    assert.match(r.reason, /configured local model qwen2\.5:1\.5b \(no native-tool repo measurements for an installed model\)/);
    assert.equal(pickRepoStarter(null, table(many('qwen2.5:3b', 'repo', 6, 6, 'native')), 'qwen2.5:1.5b', why).model, 'qwen2.5:1.5b', 'unknown installed list');
    assert.equal(pickRepoStarter(INSTALLED, null, 'qwen2.5:1.5b', why).model, 'qwen2.5:1.5b', 'no table');
  });
  it('matches an untagged installed name and ranks by pass rate, then latency', () => {
    const m = table([...many('qwen2.5:3b', 'repo', 3, 6, 'native'), ...many('qwen2.5:1.5b', 'repo', 3, 6, 'native')].map((t) => (t.model === 'qwen2.5:1.5b' ? { ...t, latency_ms: 2000 } : t)));
    assert.equal(pickRepoStarter(INSTALLED, m, 'x', why).model, 'qwen2.5:1.5b', 'equal pass rate: the faster one');
    assert.equal(pickRepoStarter(['qwen2.5:3b:latest'.replace(':latest', '')], table(many('qwen2.5:3b', 'repo', 3, 6, 'native')), 'x', why).model, 'qwen2.5:3b');
  });
});

