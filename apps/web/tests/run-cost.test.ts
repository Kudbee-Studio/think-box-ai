// Run cost accounting: Mercury 2 runs are priced per step and the run record sums the steps (it is not left at 0).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { costUsd } from '../agent.ts';
import { RunStore, type RunRecord } from '../runs.ts';

test('costUsd prices mercury-2 at $0.25 / $0.75 per million tokens; unknown (local) models are free', () => {
  assert.equal(costUsd('mercury-2', 1_000_000, 0), 0.25);
  assert.equal(costUsd('mercury-2', 0, 1_000_000), 0.75);
  assert.ok(Math.abs(costUsd('mercury-2', 3823, 408) - 0.00126) < 0.0001);
  assert.equal(costUsd('qwen2.5:1.5b', 5000, 500), 0);
});

test('the run record sums per-step costs and tokens, and the run totals feed the cost report', () => {
  const store = new RunStore(path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-cost-')), 'runs.json'));
  const run = store.create({ id: 'r1', session_id: 's', goal: 'g', model: 'mercury-2', provider: 'inception', status: 'running', started_at: Date.now(), steps: [], current_step: 0, tool_calls: 0, prompt_tokens: 0, completion_tokens: 0, cost_usd: 0, approvals: { approved: 0, denied: 0 }, files: [] } as RunRecord);
  for (const [step, p, c] of [[1, 2000, 100], [2, 2400, 60]] as const) {
    store.addEvent(run, { kind: 'model', step, latency_ms: 5, prompt_tokens: p, completion_tokens: c, cost_usd: costUsd('mercury-2', p, c), tool_calls: [], content: '' } as never);
  }
  assert.equal(run.prompt_tokens, 4400);
  assert.ok(run.cost_usd > 0);
  assert.ok(Math.abs(run.cost_usd - (costUsd('mercury-2', 2000, 100) + costUsd('mercury-2', 2400, 60))) < 1e-12);
  assert.equal(store.stats().cost_total_usd, run.cost_usd);
});
