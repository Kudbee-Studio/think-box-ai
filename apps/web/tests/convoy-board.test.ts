// The agent board (READY / OPEN / REVIEW / FINISHED) and the human review of an outcome, as pure rules over convoy records.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { boardFor, laneOf, LANES } from '../convoy-board.ts';
import { ConvoyError, ConvoyStore, verifyChain } from '../convoy.ts';
import { evaluatePolicy, planConvoy } from '../mayor.ts';

const TOOLS = ['live_lookup', 'repo_search', 'repo_read', 'fetch_url', 'read_rss', 'recall', 'read_file', 'write_file', 'remember'];
function fresh(goal = 'What is the last PR?', budget?: unknown) {
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'board-')), 'c.json');
  const store = new ConvoyStore(file);
  const r = planConvoy({ goal, budget, lookupModel: 'qwen2.5:3b', agentModel: 'mercury-2', isLocalModel: (m) => !m.startsWith('mercury'), availableTools: TOOLS, now: 1, costOf: () => ({ usd: 0, basis: 't' }) });
  assert.ok(r.ok); const plan = (r as any).plan;
  const c = store.create(plan.goal, plan, evaluatePolicy(plan));
  return { store, file, c };
}
const approved = (t: ReturnType<typeof fresh>) => { t.store.submit(t.c.id); t.store.decide(t.c.id, 'approve', 'human'); };
const running = (t: ReturnType<typeof fresh>) => { approved(t); t.store.start(t.c.id); };
const lane = (t: ReturnType<typeof fresh>, id = t.c.workers[0]!.id) => laneOf(t.c, t.store.worker(t.c, id))?.lane ?? null;
const throwsCode = (fn: () => unknown, code: string) => assert.throws(fn, (e: unknown) => e instanceof ConvoyError && e.code === code, code);

describe('lanes follow the life of a worker', () => {
  it('a plan, or a plan waiting for approval, is not on the board', () => {
    const t = fresh();
    assert.equal(lane(t), null);
    t.store.submit(t.c.id);
    assert.equal(lane(t), null);
  });
  it('approved and not started: READY. running: OPEN', () => {
    const t = fresh();
    approved(t);
    assert.equal(lane(t), 'ready');
    t.store.start(t.c.id);
    assert.equal(lane(t), 'ready', 'still ready until an agent takes it');
    t.store.worker(t.c, 'lookup-1').status = 'running';
    assert.equal(lane(t), 'open');
  });
  it('a completed worker of a successful convoy waits in REVIEW, and moves to FINISHED when a human accepts', () => {
    const t = fresh(); running(t);
    t.store.worker(t.c, 'lookup-1').status = 'completed';
    t.store.finish(t.c.id, 'success', 'ok');
    assert.equal(t.c.review?.state, 'pending');
    assert.equal(lane(t), 'review');
    t.store.review(t.c.id, 'accept', 'human', 'looks right');
    assert.equal(lane(t), 'finished');
    assert.equal(laneOf(t.c, t.c.workers[0]!)!.detail, 'completed, outcome accepted');
  });
  it('a rejected outcome is FINISHED too, and says so', () => {
    const t = fresh(); running(t);
    t.store.worker(t.c, 'lookup-1').status = 'completed';
    t.store.finish(t.c.id, 'success', 'ok');
    t.store.review(t.c.id, 'reject', 'human', 'wrong file');
    assert.equal(laneOf(t.c, t.c.workers[0]!)!.detail, 'completed, outcome rejected');
  });
  it('a failed or ungrounded convoy has nothing to accept: its workers go straight to FINISHED', () => {
    for (const outcome of ['failed', 'grounding_failed'] as const) {
      const t = fresh(); running(t);
      t.store.worker(t.c, 'lookup-1').status = 'failed';
      t.store.worker(t.c, 'lookup-1').failure = { kind: 'tool_failed', message: 'x' };
      t.store.finish(t.c.id, outcome, 'x');
      assert.equal(t.c.review?.state, 'not_required');
      assert.equal(lane(t), 'finished');
      assert.match(laneOf(t.c, t.c.workers[0]!)!.detail, /failed: tool_failed/);
    }
  });
  it('rejected, expired and cancelled convoys put their workers in FINISHED', () => {
    const a = fresh(); a.store.submit(a.c.id); a.store.decide(a.c.id, 'reject', 'human');
    assert.equal(lane(a), 'finished');
    const b = fresh(); b.store.cancel(b.c.id, 'human');
    assert.equal(laneOf(b.c, b.c.workers[0]!)!.detail, 'cancelled');
  });
  it('a worker waiting on a worker that has not finished is NOT ready; once its blocker closes it is', () => {
    const t = fresh('Research the latest release notes and write a short summary report', { max_workers: 12, max_cost_usd: 1, max_tool_calls: 100 });
    approved(t); t.store.start(t.c.id);
    const dependent = t.c.plan.workers.find((w) => w.depends_on.length)!;
    const blocker = dependent.depends_on[0]!;
    assert.equal(lane(t, dependent.id), null, 'blocked: invisible to agents');
    assert.equal(lane(t, blocker), 'ready');
    // one blocker closed is not enough when there are several; all of them closed makes it ready
    t.store.worker(t.c, blocker).status = 'completed';
    if (dependent.depends_on.length > 1) assert.equal(lane(t, dependent.id), null, 'still blocked by the others');
    for (const d of dependent.depends_on) t.store.worker(t.c, d).status = 'completed';
    assert.equal(lane(t, dependent.id), 'ready');
    t.store.worker(t.c, dependent.depends_on[0]!).status = 'failed';
    assert.equal(lane(t, dependent.id), 'ready', 'a failed blocker is closed too: the worker is free to run (the job proof will say what that means)');
  });
});

describe('review rules', () => {
  const finished = () => { const t = fresh(); running(t); t.store.worker(t.c, 'lookup-1').status = 'completed'; t.store.finish(t.c.id, 'success', 'ok'); return t; };
  it('only a human reviews, and only once', () => {
    const t = finished();
    for (const by of ['model', 'worker:lookup-1', 'system', '', 'agent']) throwsCode(() => t.store.review(t.c.id, 'accept', by), 'forbidden');
    assert.equal(t.c.review?.state, 'pending');
    t.store.review(t.c.id, 'accept', 'human');
    throwsCode(() => t.store.review(t.c.id, 'reject', 'human'), 'bad_transition');
    assert.equal(t.c.review?.state, 'accepted');
  });
  it('a convoy that has not finished, or has nothing to review, cannot be reviewed', () => {
    const t = fresh(); running(t);
    throwsCode(() => t.store.review(t.c.id, 'accept', 'human'), 'bad_transition');
    t.store.worker(t.c, 'lookup-1').status = 'failed';
    t.store.finish(t.c.id, 'failed', 'x');
    throwsCode(() => t.store.review(t.c.id, 'accept', 'human'), 'bad_transition');
  });
  it('the decision is in the evidence chain, names who and why, and a tampered note is detected', () => {
    const t = finished();
    t.store.review(t.c.id, 'reject', 'human', 'the finding is off-topic');
    const e = t.c.events.at(-1)!;
    assert.equal(e.by, 'human');
    assert.match(e.note, /outcome rejected by human: the finding is off-topic/);
    assert.deepEqual(verifyChain(t.c), { ok: true });
    const copy = structuredClone({ id: t.c.id, events: t.c.events });
    copy.events.at(-1)!.note = 'outcome accepted by human';
    assert.equal(verifyChain(copy).ok, false);
  });
  it('a pending review survives a restart; a convoy interrupted mid-run does not invent one', () => {
    const t = finished();
    t.store.flush();
    const again = new ConvoyStore(t.file);
    assert.equal(again.get(t.c.id)!.review?.state, 'pending');
    const u = fresh(); running(u); u.store.flush();
    const reloaded = new ConvoyStore(u.file).get(u.c.id)!;
    assert.equal(reloaded.state, 'FAILED');
    assert.equal(reloaded.review, undefined);
    assert.equal(laneOf(reloaded, reloaded.workers[0]!)?.lane, 'finished');
  });
});

describe('boardFor', () => {
  it('groups every worker of every convoy into the four lanes, newest first, and counts what is not ready yet', () => {
    const a = fresh(); running(a); a.store.worker(a.c, 'lookup-1').status = 'running';
    const b = fresh(); running(b); b.store.worker(b.c, 'lookup-1').status = 'completed'; b.store.finish(b.c.id, 'success', 'ok');
    const c = fresh(); approved(c);
    const d = fresh();
    const board = boardFor([a.c, b.c, c.c, d.c]);
    assert.deepEqual(board.counts, { ready: 1, open: 1, review: 1, finished: 0 });
    assert.equal(board.not_ready, 1, 'the plan that was never submitted');
    assert.deepEqual(LANES, ['ready', 'open', 'review', 'finished']);
    const card = board.lanes.review[0]!;
    assert.equal(card.convoy_id, b.c.id);
    assert.equal(card.worker_id, 'lookup-1');
    assert.equal(card.model, 'qwen2.5:3b');
    assert.equal(card.detail, 'awaiting human review');
  });
});
