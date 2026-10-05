// The job state: a convoy replayed into the existing 100-cell cube. Only real convoy facts drive stages; the rest stay off and say so.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { ConvoyStore } from '../convoy.ts';
import { projectJobState } from '../convoy-job-state.ts';
import { evaluatePolicy, planConvoy } from '../mayor.ts';

const TOOLS = ['live_lookup', 'repo_search', 'repo_read', 'fetch_url', 'read_rss', 'recall', 'read_file', 'write_file', 'remember'];
function convoy(goal = 'What is the last PR?', mode: any = 'observe') {
  const store = new ConvoyStore(path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'js-')), 'c.json'));
  const r = planConvoy({ goal, mode, lookupModel: 'qwen2.5:3b', agentModel: 'mercury-2', isLocalModel: (m) => !m.startsWith('mercury'), availableTools: TOOLS, now: 1, costOf: () => ({ usd: 0, basis: 't' }) });
  assert.ok(r.ok); const plan = (r as any).plan;
  return { store, c: store.create(plan.goal, plan, evaluatePolicy(plan)) };
}
const roleCount = (s: ReturnType<typeof projectJobState>, role: string, flag: 'active' | 'locked' | 'disrupted') => s.cells.filter((x) => x.role === role && x[flag]).length;
const run = (store: ConvoyStore, c: any) => { store.submit(c.id); store.decide(c.id, 'approve', 'human'); store.start(c.id); };

describe('projectJobState', () => {
  it('a plan has an identity and the planned jobs, and nothing else: no workers, no evidence, no verdict', () => {
    const { c } = convoy();
    const s = projectJobState(c);
    assert.equal(s.cells.length, 100);
    assert.equal(s.stage, 'decompose');
    assert.equal(roleCount(s, 'identity', 'active'), 10);
    assert.equal(roleCount(s, 'jobState', 'active'), 1, 'one planned worker');
    assert.equal(roleCount(s, 'thinkBox', 'active'), 0);
    assert.equal(roleCount(s, 'evidence', 'locked'), 0);
    assert.equal(s.verdict, null);
    assert.equal(s.stable, false);
    assert.deepEqual(s.signals.driven, ['intent', 'decompose']);
    assert.deepEqual(s.signals.no_signal, ['repair', 'harvest', 'commons']);
  });
  it('a successful run lights workers, propagation, locked evidence, a pass verdict and a stable proof', () => {
    const { store, c } = convoy();
    run(store, c);
    Object.assign(store.worker(c, 'lookup-1'), { status: 'completed', run_id: 'run-1', tool_calls: 2 });
    c.tool_calls = 2; c.evidence.push({ recipe: 'latest_pr', repo: 'a/b', source_url: 'u', fetched_at: 't', http_status: 200, complete: true, items: [], tool_calls: 1, latency_ms: 1 });
    c.grounding = { status: 'GROUNDED', classification: 'ok', unsupported: [], checked: { numbers: 0, urls: 0, ids: 1, branches: 0, states: 1 } };
    store.finish(c.id, 'success', 'ok');
    const s = projectJobState(c);
    assert.equal(roleCount(s, 'thinkBox', 'active'), 1);
    assert.equal(roleCount(s, 'propagation', 'active'), 2);
    assert.equal(roleCount(s, 'evidence', 'locked'), 1);
    assert.equal(s.verdict, 'pass');
    assert.equal(s.stable, true);
    assert.equal(roleCount(s, 'memory', 'locked'), 10);
    assert.equal(roleCount(s, 'outcome', 'locked'), 10);
    assert.equal(roleCount(s, 'tokenState', 'locked'), 0, 'no token was learned');
    assert.ok(s.signals.driven.includes('proof'));
  });
  it('a failed or ungrounded run shows disrupted validation cells, a fail verdict and no proof', () => {
    const { store, c } = convoy();
    run(store, c);
    store.worker(c, 'lookup-1').status = 'failed';
    c.grounding = { status: 'GROUNDING FAILED', classification: 'unsupported_claim', unsupported: [{ kind: 'id', claim: '#9', why: 'x' }, { kind: 'state', claim: 'merged', why: 'y' }], checked: { numbers: 0, urls: 0, ids: 1, branches: 0, states: 1 } };
    store.finish(c.id, 'grounding_failed', 'x');
    const s = projectJobState(c);
    assert.equal(s.verdict, 'fail');
    assert.equal(s.stable, false);
    assert.equal(roleCount(s, 'validation', 'disrupted'), 3, '2 unsupported claims + 1 failed worker');
    assert.equal(roleCount(s, 'memory', 'locked'), 0);
    assert.ok(!s.signals.driven.includes('proof'));
  });
  it('learned Think Token candidates light the token-state cells', () => {
    const { store, c } = convoy('What is the last PR?', 'learn');
    run(store, c);
    store.finish(c.id, 'success', 'ok');
    c.learned_tokens = [{ id: 'TT-000099', kind: 'tool_pattern', status: 'candidate', title: 't' }];
    const s = projectJobState(c);
    assert.equal(roleCount(s, 'tokenState', 'locked'), 10);
    assert.equal(s.facts.learned_tokens, 1);
  });
  it('is a pure function of the convoy: the same record gives the same cells, and it never mutates it', () => {
    const { store, c } = convoy();
    run(store, c);
    const before = JSON.stringify(c);
    assert.deepEqual(projectJobState(c), projectJobState(c));
    assert.equal(JSON.stringify(c), before);
  });
});
