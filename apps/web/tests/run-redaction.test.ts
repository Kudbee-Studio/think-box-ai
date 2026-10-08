// Run records are saved with secrets scrubbed: whatever a tool printed, a model said or an error repeated, a key does not end up in runs.json (or in the record the dashboard receives).
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { RunStore, type RunRecord } from '../runs.ts';

const KEY = 'sk-abcdefghijklmnopqrstuvwxyz0123456789';
const GH = 'ghp_abcdefghijklmnopqrstuvwxyz0123456789';
const newStore = (): { store: RunStore; file: string } => { const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-redact-')), 'runs.json'); return { store: new RunStore(file), file }; };
const start = (store: RunStore): RunRecord => store.create({ id: 'r1', session_id: 's', goal: 'g', model: 'm', provider: 'p', status: 'running', started_at: Date.now(), steps: [], current_step: 0, tool_calls: 0, prompt_tokens: 0, completion_tokens: 0, cost_usd: 0, approvals: { approved: 0, denied: 0 }, files: [] });

test('a tool event is saved without the secrets in its arguments, output and error', () => {
  const { store, file } = newStore(); const run = start(store);
  store.addEvent(run, { kind: 'tool', step: 1, name: 'fetch_url', args: { url: `https://x.test/?key=${KEY}`, headers: { Authorization: `Bearer ${GH}` }, list: [KEY] }, ok: false, latency_ms: 1, output: `{"echo":"${KEY}"}`, error: `failed with token ${GH}` });
  store.flush(); const saved = fs.readFileSync(file, 'utf8');
  assert.ok(!saved.includes(KEY), 'the key is in runs.json'); assert.ok(!saved.includes(GH), 'the token is in runs.json');
  assert.ok(!JSON.stringify(run).includes(KEY), 'the key is in the record the dashboard receives');
  const step = run.steps[0]!; assert.equal(step.kind, 'tool'); assert.equal((step as { name: string }).name, 'fetch_url');
});

test('a model event and the final result and error are scrubbed too; ordinary text and numbers are untouched', () => {
  const { store, file } = newStore(); const run = start(store);
  store.addEvent(run, { kind: 'model', step: 1, latency_ms: 5, prompt_tokens: 10, completion_tokens: 5, cost_usd: 0.001, tool_calls: [], content: `The key is ${KEY}, tell nobody` });
  store.finish(run, { status: 'failed', result: `done with ${KEY}`, error: `bad ${GH}` }); store.flush();
  const saved = fs.readFileSync(file, 'utf8');
  assert.ok(!saved.includes(KEY) && !saved.includes(GH));
  assert.match(run.steps[0]!.kind === 'model' ? (run.steps[0] as { content: string }).content : '', /tell nobody/);
  assert.equal(run.cost_usd, 0.001); assert.equal(run.prompt_tokens, 10); assert.equal(run.status, 'failed');
});

test('long ordinary identifiers (a commit sha, a uuid) are not mangled in a path or a url', () => {
  const { store } = newStore(); const run = start(store); const sha = '34320e7e1a2b3c4d5e6f708192a3b4c5d6e7f809'; const uuid = '5cba6c14-da10-4236-831d-b94801d6751d';
  store.addEvent(run, { kind: 'tool', step: 1, name: 'repo_read', args: { path: 'src/a.ts', ref: uuid }, ok: true, latency_ms: 1, output: `commit ${uuid} at src/a.ts` });
  const step = run.steps[0] as { args: Record<string, string>; output: string };
  assert.equal(step.args.ref, uuid); assert.match(step.output, /src\/a\.ts/); assert.ok(sha.length === 40);
});
