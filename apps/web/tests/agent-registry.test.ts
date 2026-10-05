// Unit tests for the agent registry (public/js/agent-registry.js): message ingest -> agent records, approvals and change events.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const src = fs.readFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../public/js/agent-registry.js'), 'utf8');
const sandbox: Record<string, unknown> = {};
vm.createContext(sandbox);
vm.runInContext(src, sandbox, { filename: 'agent-registry.js' });
const AgentRegistry = sandbox.AgentRegistry as new (o: { emit: (d: unknown) => void }) => {
  ingest(m: unknown): boolean;
  get(id: string): any;
  list(): any[];
  runningCount(): number;
  resolveApproval(id: string, approved?: boolean): boolean;
  clear(): void;
};

function make(): { reg: any; changes: any[] } {
  const changes: any[] = [];
  return { reg: new AgentRegistry({ emit: (d) => changes.push(d) }), changes };
}

test('run_update creates a running agent and emits agents:changed once', () => {
  const { reg, changes } = make();
  assert.equal(reg.ingest({ type: 'run_update', data: { id: 'run-1', status: 'running', goal: 'Deploy', current_step: 2 } }), true);
  const a = reg.get('run-1');
  assert.equal(a.status, 'running');
  assert.equal(a.goal, 'Deploy');
  assert.equal(a.run_id, 'run-1');
  assert.equal(a.steps_completed, 2);
  assert.equal(reg.runningCount(), 1);
  assert.equal(changes.length, 1);
  assert.equal(changes[0].runningCount, 1);
});

test('re-ingesting unchanged data does not emit', () => {
  const { reg, changes } = make();
  reg.ingest({ type: 'run_update', data: { id: 'run-1', status: 'running', goal: 'Deploy' } });
  const before = changes.length;
  assert.equal(reg.ingest({ type: 'run_update', data: { id: 'run-1', status: 'running', goal: 'Deploy' } }), false);
  assert.equal(changes.length, before);
});

test('a completed run_update flips the agent to idle', () => {
  const { reg } = make();
  reg.ingest({ type: 'run_update', data: { id: 'run-1', status: 'running' } });
  reg.ingest({ type: 'run_update', data: { id: 'run-1', status: 'completed' } });
  assert.equal(reg.get('run-1').status, 'idle');
  assert.equal(reg.runningCount(), 0);
});

test('an approval_request attaches to the running agent and resolution clears it', () => {
  const { reg, changes } = make();
  reg.ingest({ type: 'run_update', data: { id: 'run-1', status: 'running', goal: 'Deploy' } });
  reg.ingest({ type: 'approval_request', data: { id: 'ap1', reason: 'overwrite file' } });
  const a = reg.get('run-1');
  assert.equal(a.approval_pending, true);
  assert.equal(a.approvals.length, 1);
  assert.equal(a.approvals[0].reason, 'overwrite file');
  assert.equal(reg.resolveApproval('ap1', true), true);
  assert.equal(reg.get('run-1').approval_pending, false);
  assert.equal(changes.length >= 2, true);
});

test('a duplicate approval id is not added twice', () => {
  const { reg } = make();
  reg.ingest({ type: 'run_update', data: { id: 'run-1', status: 'running' } });
  reg.ingest({ type: 'approval_request', data: { id: 'ap1', reason: 'x' } });
  reg.ingest({ type: 'approval_request', data: { id: 'ap1', reason: 'x' } });
  assert.equal(reg.get('run-1').approvals.length, 1);
});

test('an approval with no running agent creates a session agent', () => {
  const { reg } = make();
  reg.ingest({ type: 'approval_request', data: { id: 'ap1', reason: 'sensitive action' } });
  const session = reg.get('session');
  assert.ok(session);
  assert.equal(session.approval_pending, true);
});

test('specialist_result creates an agent per specialist', () => {
  const { reg } = make();
  reg.ingest({ type: 'specialist_result', data: { jobId: 'job-9', status: 'COMPLETED', intent: 'build', specialistsExecuted: [
    { specialistId: 'builder', status: 'COMPLETED', thinkBoxId: 'box-1' },
    { specialistId: 'tester', status: 'FAILED', failure: 'no exec' },
  ] } });
  assert.equal(reg.get('builder').status, 'idle');
  assert.equal(reg.get('builder').think_box_id, 'box-1');
  assert.equal(reg.get('builder').run_id, 'job-9');
  assert.equal(reg.get('tester').status, 'failed');
});

test('think_token_cube sets the Think Box and think_token_used increments tokens', () => {
  const { reg } = make();
  reg.ingest({ type: 'run_update', data: { id: 'run-1', status: 'running' } });
  reg.ingest({ type: 'think_token_cube', data: { thinkBoxId: 'box-7', tokens: [1, 2, 3] } });
  assert.equal(reg.get('run-1').think_box_id, 'box-7');
  assert.equal(reg.get('run-1').tokens_used, 3);
  reg.ingest({ type: 'think_token_used', data: {} });
  assert.equal(reg.get('run-1').tokens_used, 4);
});

test('task, status and result messages update state without inventing runs', () => {
  const { reg } = make();
  reg.ingest({ type: 'task', data: { id: 'task-1', title: 'Write report', status: 'running', activity: [{}, {}] } });
  assert.equal(reg.get('task-1').status, 'running');
  assert.equal(reg.get('task-1').goal, 'Write report');
  assert.equal(reg.get('task-1').steps_completed, 2);
  reg.ingest({ type: 'status', data: 'running' });
  assert.equal(reg.get('task-1').status, 'running');
  reg.ingest({ type: 'result', data: { success: false } });
  assert.equal(reg.get('task-1').status, 'failed');
});

test('an unknown message type changes nothing', () => {
  const { reg, changes } = make();
  assert.equal(reg.ingest({ type: 'thought', data: { content: 'hi' } }), false);
  assert.equal(reg.ingest({ type: 'nope' }), false);
  assert.equal(reg.ingest(null), false);
  assert.equal(changes.length, 0);
  assert.equal(reg.list().length, 0);
});

test('a status:running that arrives before the next run exists does not revive the finished agent (no ghost "2 running")', () => {
  const { reg } = make();
  reg.ingest({ type: 'run_update', data: { id: 'run-1', status: 'running', goal: 'first' } });
  reg.ingest({ type: 'result', data: { success: true } });
  assert.equal(reg.runningCount(), 0);
  reg.ingest({ type: 'status', data: 'running' });
  assert.equal(reg.runningCount(), 0, 'nothing is running yet: the finished agent stays finished');
  reg.ingest({ type: 'run_update', data: { id: 'run-2', status: 'running', goal: 'second' } });
  assert.equal(reg.runningCount(), 1, 'exactly one agent runs');
  reg.ingest({ type: 'result', data: { success: true } });
  assert.equal(reg.runningCount(), 0, 'and it finishes cleanly');
  assert.equal(reg.get('run-1').status, 'idle');
});

const convoyUpdate = (lanes: Array<[string, string, string | null]>, o: Record<string, unknown> = {}) => ({
  type: 'convoy_update',
  data: { id: 'f0e1d2c3-aaaa-bbbb-cccc-ddddeeeeffff', goal: 'What is the last PR?', think_mode: 'learn', workers: lanes.map(([id, status, lane]) => ({ id, name: `Worker ${id}`, model: 'qwen2.5:3b', status, lane, run_id: `run-${id}`, bead: `tb-f0e1d2c3.${id}` })), ...o },
});

test('convoy workers are agents: each carries its lane, bead and convoy, and the lane decides the status', () => {
  const { reg, changes } = make();
  assert.equal(reg.ingest(convoyUpdate([['a', 'running', 'open'], ['b', 'pending', 'ready'], ['c', 'completed', 'review'], ['d', 'completed', 'finished'], ['e', 'failed', 'finished'], ['f', 'pending', null]])), true);
  const by = (w: string) => reg.get(`convoy:f0e1d2c3:${w}`);
  assert.deepEqual(['a', 'b', 'c', 'd', 'e', 'f'].map((w) => by(w).status), ['running', 'idle', 'paused', 'idle', 'failed', 'paused']);
  assert.deepEqual(['a', 'b', 'c', 'd', 'e', 'f'].map((w) => by(w).lane), ['open', 'ready', 'review', 'finished', 'finished', 'none']);
  assert.equal(by('a').bead, 'tb-f0e1d2c3.a');
  assert.equal(by('a').convoy_id, 'f0e1d2c3-aaaa-bbbb-cccc-ddddeeeeffff');
  assert.equal(by('a').worker_id, 'a');
  assert.equal(by('a').goal, 'What is the last PR?');
  assert.equal(reg.runningCount(), 1, 'only OPEN workers are running');
  assert.equal(changes.length, 1);
});

test('a worker moving between lanes updates the same agent (no duplicate), and a repeated update is not a change', () => {
  const { reg, changes } = make();
  reg.ingest(convoyUpdate([['a', 'running', 'open']]));
  assert.equal(reg.ingest(convoyUpdate([['a', 'running', 'open']])), false, 'same facts, no change event');
  reg.ingest(convoyUpdate([['a', 'completed', 'review']]));
  assert.equal(reg.list().length, 1);
  assert.equal(reg.get('convoy:f0e1d2c3:a').lane, 'review');
  assert.equal(reg.runningCount(), 0);
  reg.ingest(convoyUpdate([['a', 'completed', 'finished']]));
  assert.equal(reg.get('convoy:f0e1d2c3:a').status, 'idle');
  assert.equal(changes.length, 3);
});

test('a malformed convoy update is ignored, not fatal', () => {
  const { reg } = make();
  for (const bad of [{ type: 'convoy_update', data: null }, { type: 'convoy_update', data: { id: 'x' } }, { type: 'convoy_update', data: { workers: [] } }, { type: 'convoy_update' }]) assert.doesNotThrow(() => reg.ingest(bad));
  assert.equal(reg.list().length, 0);
});
