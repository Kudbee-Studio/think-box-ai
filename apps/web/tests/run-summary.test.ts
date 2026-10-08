import assert from 'node:assert/strict';
import { test } from 'node:test';
import { summarizeRun } from '../run-summary.ts';

const base = { id: 'r1', goal: 'fix it', status: 'completed', started_at: 0, duration_ms: 12_300, steps: [], tool_calls: 4, cost_usd: 0.0123, approvals: { approved: 0, denied: 0 }, files: [] } as any;

test('a finished run with changed files says what changed, what it cost, and points at review and undo', () => {
  const s = summarizeRun({ ...base, files: ['a.ts', 'b.ts'], approvals: { approved: 2, denied: 1 }, steps: [1, 2, 3] });
  assert.equal(s.headline, 'Done in 12.3s');
  const text = s.lines.join('\n');
  for (const part of ['Changed 2 files: a.ts, b.ts', '$0.0123', '3 steps', '4 tool calls', '2 approved, 1 denied']) assert.ok(text.includes(part), part);
  assert.ok(s.next.some((n) => /Review the changes/.test(n) && /undo/i.test(n)));
});

test('a long file list is cut with a count, and one file reads in the singular', () => {
  const many = Array.from({ length: 9 }, (_, i) => `f${i}.ts`);
  assert.match(summarizeRun({ ...base, files: many }).lines.join('\n'), /Changed 9 files: f0\.ts, f1\.ts, f2\.ts, f3\.ts, f4\.ts and 4 more/);
  assert.match(summarizeRun({ ...base, files: ['x.ts'] }).lines.join('\n'), /Changed 1 file: x\.ts/);
});

test('a run that changed nothing says so and does not suggest reviewing', () => {
  const s = summarizeRun(base);
  assert.ok(s.lines.join('\n').includes('No files changed'));
  assert.deepEqual(s.next.filter((n) => /Review/.test(n)), []);
});

test('a failed run leads with the error and points at the timeline; a stopped run says stopped', () => {
  const f = summarizeRun({ ...base, status: 'failed', error: 'Budget reached' });
  assert.equal(f.headline, 'Failed: Budget reached');
  assert.ok(f.next.some((n) => /timeline/i.test(n)));
  assert.equal(summarizeRun({ ...base, status: 'stopped' }).headline, 'Stopped before it finished');
});

test('a contradiction between the answer and a tool result is called out', () => {
  const s = summarizeRun({ ...base, evidence_conflicts: ['answer says 3 files, list_files shows 2'] });
  assert.ok(s.lines.some((l) => /disagreed with what a tool returned/.test(l) && l.includes('list_files')));
});

test('a run with no cost data does not invent one', () => {
  assert.ok(!summarizeRun({ ...base, cost_usd: undefined, duration_ms: undefined }).lines.join('\n').includes('NaN'));
});
