// Convoy store: one parent record, a strict state machine, human-only approval, a hash-chained evidence log, aggregation from children.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { APPROVAL_TTL_MS, ConvoyError, ConvoyStore, TRANSITIONS, canApprove, verifyChain } from '../convoy.ts';
import { evaluatePolicy, planConvoy } from '../mayor.ts';

const TOOLS = ['read_file', 'write_file', 'fetch_url', 'live_lookup', 'read_rss', 'recall'];
const mkPlan = (goal = 'What is the last PR?', budget: unknown = undefined) => {
  const r = planConvoy({ goal, budget, lookupModel: 'qwen2.5:3b', agentModel: 'mercury-2', isLocalModel: (m) => !m.startsWith('mercury'), availableTools: TOOLS, now: 1, costOf: (m) => ({ usd: m === 'mercury-2' ? 0.004 : 0, basis: 'test' }) });
  assert.ok(r.ok); return (r as any).plan;
};
function fresh(now = { t: 1_000_000 }) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'convoy-'));
  const file = path.join(dir, 'convoys.json');
  const store = new ConvoyStore(file, undefined, () => now.t);
  const create = (goal?: string) => { const plan = mkPlan(goal); return store.create(plan.goal, plan, evaluatePolicy(plan)); };
  return { dir, file, store, create, now };
}
const throwsCode = (fn: () => unknown, code: string) => assert.throws(fn, (e: unknown) => e instanceof ConvoyError && e.code === code, code);

describe('ConvoyStore lifecycle', () => {
  it('a new convoy is PLAN ONLY: planned, not approved, nothing started, one event', () => {
    const { store, create } = fresh();
    const c = create();
    assert.equal(c.state, 'PLANNED');
    assert.equal(c.mode, 'plan_only');
    assert.equal(c.approval, null);
    assert.equal(c.started_at, undefined);
    assert.deepEqual(c.run_ids, []);
    assert.deepEqual(c.workers.map((w) => w.status), ['pending']);
    assert.equal(c.events.length, 1);
    assert.match(c.events[0]!.note, /PLAN ONLY: no worker started, nothing approved/);
    assert.equal(store.get(c.id)!.id, c.id);
  });

  it('PLANNED -> PENDING -> APPROVED -> RUNNING -> COMPLETED, each step in the evidence chain', () => {
    const { store, create } = fresh();
    const c = create();
    store.submit(c.id);
    assert.equal(c.state, 'PENDING');
    assert.equal(c.approval!.state, 'PENDING');
    assert.equal(c.approval!.snapshot.goal, 'What is the last PR?');
    assert.deepEqual(c.approval!.snapshot.tools, ['live_lookup']);
    assert.equal(c.approval!.snapshot.policy.decision, 'requires_approval');
    assert.equal(c.approval!.snapshot.worker_budget.max_workers, 4);
    assert.throws(() => store.start(c.id), /only runs after a human approved/);
    store.decide(c.id, 'approve', 'human', 'looks right');
    assert.equal(c.state, 'APPROVED');
    assert.equal(c.approval!.decided_by, 'human');
    store.start(c.id);
    assert.equal(c.state, 'RUNNING');
    assert.equal(c.mode, 'live');
    store.finish(c.id, 'success', 'worker finished');
    assert.equal(c.state, 'COMPLETED');
    assert.equal(c.outcome, 'success');
    assert.deepEqual(c.events.map((e) => e.state), ['PLANNED', 'PENDING', 'APPROVED', 'RUNNING', 'COMPLETED']);
    assert.deepEqual(verifyChain(c), { ok: true });
  });

  it('only a human can approve: a model, a worker, the system or an empty name is refused, and the convoy stays PENDING', () => {
    const { store, create } = fresh();
    const c = create(); store.submit(c.id);
    for (const by of ['model', 'model:mercury-2', 'worker:lookup-1', 'agent', 'system', '', 'Human', 'human ']) {
      throwsCode(() => store.decide(c.id, 'approve', by), 'forbidden');
      throwsCode(() => store.decide(c.id, 'reject', by), 'forbidden');
    }
    assert.equal(c.state, 'PENDING');
    assert.equal(canApprove('human'), true);
    assert.equal(canApprove('model:x'), false);
  });

  it('the state machine refuses every move it does not list, including running without approval', () => {
    const { store, create } = fresh();
    const c = create();
    throwsCode(() => store.decide(c.id, 'approve', 'human'), 'bad_transition'); // not submitted
    throwsCode(() => store.start(c.id), 'forbidden');
    throwsCode(() => store.finish(c.id, 'success', 'x'), 'bad_transition');
    store.submit(c.id);
    throwsCode(() => store.submit(c.id), 'bad_transition');
    store.decide(c.id, 'reject', 'human', 'no');
    assert.equal(c.state, 'REJECTED');
    throwsCode(() => store.decide(c.id, 'approve', 'human'), 'bad_transition');
    throwsCode(() => store.start(c.id), 'forbidden');
    for (const [from, to] of Object.entries(TRANSITIONS)) if (to.length === 0) assert.ok(['COMPLETED', 'PARTIAL', 'FAILED', 'REJECTED', 'EXPIRED', 'CANCELLED'].includes(from));
  });

  it('a pending approval expires on its own and can no longer be approved or run', () => {
    const { store, create, now } = fresh();
    const c = create(); store.submit(c.id);
    now.t += APPROVAL_TTL_MS - 1;
    assert.equal(store.get(c.id)!.state, 'PENDING');
    now.t += 2;
    assert.equal(store.get(c.id)!.state, 'EXPIRED');
    assert.equal(c.approval!.state, 'EXPIRED');
    assert.equal(c.approval!.decided_by, 'system');
    throwsCode(() => store.decide(c.id, 'approve', 'human'), 'bad_transition');
    throwsCode(() => store.start(c.id), 'forbidden');
    assert.match(c.events.at(-1)!.note, /nothing ran/);
  });

  it('cancel works before the run; a cancelled approval is recorded', () => {
    const { store, create } = fresh();
    const c = create(); store.submit(c.id);
    store.cancel(c.id, 'human');
    assert.equal(c.state, 'CANCELLED');
    assert.equal(c.approval!.state, 'CANCELLED');
    assert.equal(create().state, 'PLANNED');
  });

  it('a plan that is not executable, or that policy denies, cannot be submitted', () => {
    const { store } = fresh();
    const plan = mkPlan('Research the latest release notes and write a summary', { max_workers: 1 });
    const c = store.create(plan.goal, plan, evaluatePolicy(plan));
    assert.equal(plan.executable, false);
    throwsCode(() => store.submit(c.id), 'blocked');
    assert.equal(c.state, 'PLANNED');
  });
});

describe('the evidence chain', () => {
  it('detects an altered note, a removed event, a reordered event and a forged approver', () => {
    const { store, create } = fresh();
    const c = create(); store.submit(c.id); store.decide(c.id, 'approve', 'human'); store.start(c.id);
    const copy = () => structuredClone({ id: c.id, events: c.events });
    assert.deepEqual(verifyChain(copy()), { ok: true });
    let x = copy(); x.events[2]!.by = 'someone-else'; assert.deepEqual(verifyChain(x), { ok: false, at: 3 });
    x = copy(); x.events[1]!.note = 'edited'; assert.deepEqual(verifyChain(x), { ok: false, at: 2 });
    x = copy(); x.events.splice(1, 1); assert.equal(verifyChain(x).ok, false);
    x = copy(); [x.events[1], x.events[2]] = [x.events[2]!, x.events[1]!]; assert.equal(verifyChain(x).ok, false);
    x = copy(); x.id = 'another-convoy'; assert.equal(verifyChain(x).ok, false);
  });
  it('records who approved what: the approval event names the actor, the workers, the budget and the risk', () => {
    const { store, create } = fresh();
    const c = create(); store.submit(c.id); store.decide(c.id, 'approve', 'human', 'ok');
    const e = c.events.find((x) => x.state === 'APPROVED')!;
    assert.equal(e.by, 'human');
    assert.match(e.note, /approved by human for exactly this snapshot \(1 worker\(s\), budget 4\/\$0\.1, risk low\): ok/);
  });
});

describe('aggregation and failure handling', () => {
  it('totals the children: cost, tool calls, tokens and worker time, from the workers only', () => {
    const { store, create } = fresh();
    const c = create(); store.submit(c.id); store.decide(c.id, 'approve', 'human'); store.start(c.id);
    const w = store.worker(c, 'lookup-1');
    Object.assign(w, { status: 'completed', cost_usd: 0.0031, tool_calls: 2, tokens: 1226, duration_ms: 4200 });
    c.workers.push({ ...w, id: 'escalation-1', cost_usd: 0.0042, tool_calls: 1, tokens: 800, duration_ms: 1800 });
    store.aggregate(c);
    assert.deepEqual({ cost: c.cost_usd, calls: c.tool_calls, tokens: c.tokens, ms: c.worker_duration_ms }, { cost: 0.0073, calls: 3, tokens: 2026, ms: 6000 });
  });
  it('a failed worker is never turned into success: PARTIAL / FAILED keep the evidence and the error', () => {
    const { store, create } = fresh();
    const c = create(); store.submit(c.id); store.decide(c.id, 'approve', 'human'); store.start(c.id);
    c.evidence.push({ recipe: 'latest_pr', repo: 'a/b', source_url: 'u', fetched_at: 't', http_status: 200, complete: true, items: [], tool_calls: 1, latency_ms: 1 });
    store.worker(c, 'lookup-1').status = 'failed';
    store.finish(c.id, 'failed', 'worker failed', 'tool_failed: HTTP 500');
    assert.equal(c.state, 'FAILED');
    assert.equal(c.outcome, 'failed');
    assert.equal(c.error, 'tool_failed: HTTP 500');
    assert.equal(c.evidence.length, 1, 'partial evidence kept');
    throwsCode(() => store.finish(c.id, 'success', 'again'), 'bad_transition');
  });
  it('grounding failure is its own outcome, not a success', () => {
    const { store, create } = fresh();
    const c = create(); store.submit(c.id); store.decide(c.id, 'approve', 'human'); store.start(c.id);
    store.finish(c.id, 'grounding_failed', 'answer not supported by evidence');
    assert.equal(c.state, 'FAILED');
    assert.equal(c.outcome, 'grounding_failed');
  });
});

describe('persistence', () => {
  it('survives a reload, and a convoy that was RUNNING or APPROVED at shutdown becomes FAILED (interrupted)', () => {
    const { store, file, create, now } = fresh();
    const a = create(); store.submit(a.id); store.decide(a.id, 'approve', 'human'); store.start(a.id);
    const b = create(); store.submit(b.id); store.decide(b.id, 'approve', 'human');
    const c = create(); store.submit(c.id);
    store.flush();
    const reloaded = new ConvoyStore(file, undefined, () => now.t);
    assert.equal(reloaded.get(a.id)!.state, 'FAILED');
    assert.equal(reloaded.get(b.id)!.state, 'FAILED');
    assert.equal(reloaded.get(a.id)!.error, 'Interrupted by server restart');
    assert.equal(reloaded.get(c.id)!.state, 'PENDING', 'a pending approval is still waiting');
    assert.deepEqual(verifyChain(reloaded.get(a.id)!), { ok: true });
  });
  it('keeps a corrupt file instead of overwriting it', () => {
    const { dir, file } = fresh();
    fs.writeFileSync(file, '{not json');
    const s = new ConvoyStore(file);
    assert.deepEqual(s.list(), []);
    assert.ok(fs.readdirSync(dir).some((f) => f.includes('.corrupt-')));
  });
  it('scopes convoys to the active profile and bounds the history', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'convoy-'));
    const file = path.join(dir, 'c.json');
    const store = new ConvoyStore(file, 'profile-a', Date.now, 3);
    const plan = mkPlan();
    const a = store.create('g', plan, evaluatePolicy(plan));
    store.setProfile('profile-b');
    assert.equal(store.get(a.id), undefined);
    assert.deepEqual(store.list(), []);
    for (let i = 0; i < 5; i += 1) store.create(`g${i}`, plan, evaluatePolicy(plan));
    assert.equal(store.list(10).length, 3);
  });
});
