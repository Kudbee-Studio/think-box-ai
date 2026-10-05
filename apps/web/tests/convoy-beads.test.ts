// Beads: Gas City's work items as a view over convoys. open -> in_progress -> closed, blockers, ready, and a REVIEW result stays in_progress.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { beadId } from '../convoy-board.ts';
import { beadsFor } from '../convoy-beads.ts';
import { ConvoyStore } from '../convoy.ts';
import { evaluatePolicy, planConvoy } from '../mayor.ts';

const TOOLS = ['live_lookup', 'repo_search', 'repo_read', 'fetch_url', 'read_rss', 'recall', 'read_file', 'write_file', 'remember'];
function fresh(goal = 'What is the last PR?', budget?: unknown) {
  const store = new ConvoyStore(path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'beads-')), 'c.json'));
  const r = planConvoy({ goal, budget, lookupModel: 'qwen2.5:3b', agentModel: 'mercury-2', isLocalModel: (m) => !m.startsWith('mercury'), availableTools: TOOLS, now: 1, costOf: () => ({ usd: 0, basis: 't' }) });
  assert.ok(r.ok); const plan = (r as any).plan;
  return { store, c: store.create(plan.goal, plan, evaluatePolicy(plan)) };
}
const by = (beads: ReturnType<typeof beadsFor>, id: string) => beads.find((b) => b.id === id)!;

describe('beadsFor', () => {
  it('a convoy is a convoy bead and each worker a task bead under it, with stable readable ids', () => {
    const { c } = fresh();
    const beads = beadsFor([c]);
    const convoy = by(beads, beadId(c.id));
    const task = by(beads, beadId(c.id, 'lookup-1'));
    assert.match(convoy.id, /^tb-[0-9a-f]{8}$/);
    assert.equal(task.id, `${convoy.id}.lookup-1`);
    assert.deepEqual({ type: convoy.type, children: convoy.children }, { type: 'convoy', children: [task.id] });
    assert.deepEqual({ type: task.type, parent: task.parent, assignee: task.assignee }, { type: 'task', parent: convoy.id, assignee: 'qwen2.5:3b' });
  });
  it('a plan is open and waiting for approval, not ready; approval makes the task ready', () => {
    const { store, c } = fresh();
    let b = beadsFor([c]);
    assert.deepEqual([by(b, beadId(c.id)).status, by(b, beadId(c.id)).waiting_for], ['open', 'approval']);
    assert.deepEqual([by(b, beadId(c.id, 'lookup-1')).status, by(b, beadId(c.id, 'lookup-1')).ready, by(b, beadId(c.id, 'lookup-1')).waiting_for], ['open', false, 'approval']);
    store.submit(c.id); store.decide(c.id, 'approve', 'human');
    b = beadsFor([c]);
    assert.equal(by(b, beadId(c.id, 'lookup-1')).ready, true);
    assert.equal(by(b, beadId(c.id, 'lookup-1')).waiting_for, null);
  });
  it('running is in_progress; a result awaiting a human stays in_progress; accepting closes it (a rejected outcome closes it too)', () => {
    for (const decision of ['accept', 'reject'] as const) {
      const { store, c } = fresh();
      store.submit(c.id); store.decide(c.id, 'approve', 'human'); store.start(c.id);
      store.worker(c, 'lookup-1').status = 'running';
      assert.equal(by(beadsFor([c]), beadId(c.id, 'lookup-1')).status, 'in_progress');
      store.worker(c, 'lookup-1').status = 'completed';
      store.finish(c.id, 'success', 'ok');
      let b = beadsFor([c]);
      assert.equal(by(b, beadId(c.id, 'lookup-1')).status, 'in_progress');
      assert.equal(by(b, beadId(c.id, 'lookup-1')).lane, 'review');
      assert.equal(by(b, beadId(c.id)).status, 'in_progress', 'the convoy bead is not closed while a result awaits review');
      assert.equal(by(b, beadId(c.id)).detail, 'awaiting human review');
      store.review(c.id, decision, 'human');
      b = beadsFor([c]);
      assert.equal(by(b, beadId(c.id, 'lookup-1')).status, 'closed');
      assert.equal(by(b, beadId(c.id)).status, 'closed');
    }
  });
  it('a failed convoy closes straight away: there is nothing to review', () => {
    const { store, c } = fresh();
    store.submit(c.id); store.decide(c.id, 'approve', 'human'); store.start(c.id);
    store.worker(c, 'lookup-1').status = 'failed';
    store.finish(c.id, 'failed', 'x');
    const b = beadsFor([c]);
    assert.deepEqual([by(b, beadId(c.id)).status, by(b, beadId(c.id, 'lookup-1')).status], ['closed', 'closed']);
  });
  it('a bead with an open blocker is not ready and says what it waits for; closing the blockers frees it', () => {
    const { store, c } = fresh('Research the latest release notes and write a short summary report', { max_workers: 12, max_cost_usd: 1, max_tool_calls: 100 });
    store.submit(c.id); store.decide(c.id, 'approve', 'human'); store.start(c.id);
    const dependent = c.plan.workers.find((w) => w.depends_on.length)!;
    let b = beadsFor([c]);
    const bead = by(b, beadId(c.id, dependent.id));
    assert.equal(bead.ready, false);
    assert.equal(bead.waiting_for, 'dependencies');
    assert.deepEqual(bead.blocked_by.sort(), dependent.depends_on.map((d) => beadId(c.id, d)).sort());
    assert.ok(by(b, beadId(c.id, dependent.depends_on[0]!)).ready, 'its blocker is ready');
    for (const d of dependent.depends_on) store.worker(c, d).status = 'completed';
    b = beadsFor([c]);
    assert.equal(by(b, beadId(c.id, dependent.id)).ready, true);
    assert.deepEqual(by(b, beadId(c.id, dependent.id)).blocked_by, []);
  });
  it('is a pure view: same input, same beads, and the convoys are untouched', () => {
    const { c } = fresh();
    const before = JSON.stringify(c);
    assert.deepEqual(beadsFor([c]), beadsFor([c]));
    assert.equal(JSON.stringify(c), before);
  });
});
