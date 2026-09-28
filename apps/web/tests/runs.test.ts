import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { RunStore, classifyFailure, type RunRecord } from '../runs.ts';

const tmpFile = () => path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-runs-test-')), 'runs.json');
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function newRun(store: RunStore, id: string, startedAt = Date.now()): RunRecord {
  return store.create({
    id,
    session_id: 's',
    goal: `goal ${id}`,
    model: 'mercury-2',
    provider: 'inception',
    status: 'running',
    started_at: startedAt,
    steps: [],
    current_step: 0,
    tool_calls: 0,
    prompt_tokens: 0,
    completion_tokens: 0,
    cost_usd: 0,
    approvals: { approved: 0, denied: 0 },
    files: [],
  });
}

test('classifyFailure maps errors to failure kinds', () => {
  assert.equal(classifyFailure(undefined, false), undefined);
  assert.equal(classifyFailure('anything', true), 'stopped');
  assert.equal(classifyFailure('Daily budget of $1.00 reached', false), 'budget');
  assert.equal(classifyFailure('Reached the 20-step limit without finishing', false), 'step_limit');
  assert.equal(classifyFailure('Inception API HTTP 500: boom', false), 'api_error');
  assert.equal(classifyFailure('fetch failed', false), 'network');
  assert.equal(classifyFailure('something odd', false), 'error');
});

test('events accumulate tokens, cost, tool calls, approvals and written files', () => {
  const store = new RunStore(tmpFile());
  const run = newRun(store, 'r1');
  store.addEvent(run, { kind: 'model', step: 1, latency_ms: 100, prompt_tokens: 1000, completion_tokens: 100, cost_usd: 0.0003, tool_calls: ['write_file'], content: '' });
  store.addEvent(run, { kind: 'tool', step: 1, name: 'write_file', args: { path: 'a.md' }, ok: true, latency_ms: 5, output: '{}', approval: 'approved' });
  store.addEvent(run, { kind: 'tool', step: 1, name: 'write_file', args: { path: 'a.md' }, ok: true, latency_ms: 5, output: '{}' });
  store.addEvent(run, { kind: 'tool', step: 1, name: 'fetch_url', args: { url: 'x' }, ok: false, latency_ms: 5, output: '{}', approval: 'denied' });
  assert.equal(run.prompt_tokens, 1000);
  assert.equal(run.cost_usd, 0.0003);
  assert.equal(run.tool_calls, 3);
  assert.deepEqual(run.approvals, { approved: 1, denied: 1 });
  assert.deepEqual(run.files, ['a.md'], 'a file written twice is listed once');
  assert.equal(run.current_action, 'fetch_url');
});

test('stats: success rate, percentiles, failures, per-tool numbers and hourly buckets', () => {
  const store = new RunStore(tmpFile());
  const ok = newRun(store, 'ok');
  store.addEvent(ok, { kind: 'tool', step: 1, name: 'read_rss', args: {}, ok: true, latency_ms: 40, output: '' });
  store.finish(ok, { status: 'completed', result: 'fine' });
  const bad = newRun(store, 'bad');
  store.addEvent(bad, { kind: 'tool', step: 1, name: 'read_rss', args: {}, ok: false, latency_ms: 60, output: '' });
  store.finish(bad, { status: 'failed', error: 'Daily budget reached', failure_kind: 'budget' });
  newRun(store, 'live');
  newRun(store, 'old', Date.now() - 48 * 3600_000);

  const stats = store.stats() as any;
  assert.equal(stats.runs_total, 4);
  assert.equal(stats.runs_today >= 3, true);
  assert.equal(stats.running, 2);
  assert.equal(stats.success_rate, 50);
  assert.deepEqual(stats.failures, { budget: 1 });
  assert.deepEqual(stats.tools.read_rss, { calls: 2, success_rate: 50, avg_ms: 50, denied: 0 });
  assert.equal(stats.hourly.length, 24);
  assert.equal(stats.hourly[23].runs, 3, 'runs from the last hour land in the newest bucket; 48 h-old run is excluded');
});

test('history persists and interrupted runs are marked on reload', async () => {
  const file = tmpFile();
  const store = new RunStore(file);
  const done = newRun(store, 'done');
  store.finish(done, { status: 'completed' });
  newRun(store, 'interrupted');
  await sleep(400); // saves are debounced by 250 ms
  const reloaded = new RunStore(file);
  assert.equal(reloaded.get('done')?.status, 'completed');
  const interrupted = reloaded.get('interrupted');
  assert.equal(interrupted?.status, 'failed');
  assert.equal(interrupted?.failure_kind, 'interrupted');
  assert.deepEqual(reloaded.list(10).map((r) => r.id), ['interrupted', 'done'], 'newest first');
});

test('a corrupt history file starts empty instead of crashing', () => {
  const file = tmpFile();
  fs.writeFileSync(file, '{not json');
  assert.equal(new RunStore(file).list().length, 0);
});

test('costToday only counts runs started today', () => {
  const store = new RunStore(tmpFile());
  const today = newRun(store, 't');
  today.cost_usd = 0.5;
  const old = newRun(store, 'o', Date.now() - 3 * 86400_000);
  old.cost_usd = 9;
  assert.equal(store.costToday(), 0.5);
});
