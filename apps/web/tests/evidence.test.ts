// ADR 029 P3.9: fresh evidence beats memory. Unit tests for the helpers, the dated/STALE labels in the planner context, and agent-level regression
// replays of the 2026-10-02 incident (a stale "#304 draft" memory repeated although the API returned []) plus two more conflict cases.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { startMockInception, say, call, type MockInception } from './helpers/mock-inception.ts';
import type { AgentEvent, AgentHooks } from '../agent.ts';
import { EVIDENCE_RULE, conflictCandidate, unsupportedClaims, freshnessLabel, isLiveStateText, isNegativeEvidence, parseJudge } from '../evidence.ts';
import { MemoryStore, type MemoryItem } from '../memory.ts';
import { SqliteTokenStore, formatTokensForPrompt } from '../think-token-store.ts';

const DAY = 86_400_000;
const NOW = Date.parse('2026-10-02T12:00:00Z');

test('freshnessLabel: dated always; live-state text older than 24 h is STALE; other old text is just dated; undated live-state is STALE', () => {
  assert.equal(freshnessLabel('2026-10-02T06:00:00Z', 'Open PR state: #304 draft', NOW), '2026-10-02');
  assert.equal(freshnessLabel('2026-09-30T10:00:00Z', 'Open PR state: #304 draft', NOW), '2026-09-30, STALE, verify with a tool');
  assert.equal(freshnessLabel('2026-09-30T10:00:00Z', 'Think token meanings: five unrelated things', NOW), '2026-09-30');
  assert.equal(freshnessLabel(NOW - 2 * DAY, 'CI is green on main', NOW).includes('STALE'), true);
  assert.equal(freshnessLabel(undefined, 'the server is running on port 3000', NOW), 'undated, STALE, verify with a tool');
  for (const live of ['open PRs', 'CI status', 'the server is running', 'wallet balance', 'deployed to prod', 'port 3001']) assert.equal(isLiveStateText(live), true, live);
  assert.equal(isLiveStateText('how write_file reports bytes'), false);
});

test('the planner context labels a recalled live-state memory STALE and a fresh one not; tokens carry their save date', () => {
  const item = (updated: string, title: string): MemoryItem => ({ id: 'org/x', layer: 'org', title, tags: [], source: 'agent', created: updated, updated, content: 'main is the merged baseline; #304 is a draft', path: 'org/x.md' });
  const stale = MemoryStore.formatForPrompt([{ item: item('2026-09-30T10:00:00Z', 'Open PR state 2026-09-30'), score: 1 }], NOW);
  assert.match(stale, /updated 2026-09-30, STALE, verify with a tool/);
  const fresh = MemoryStore.formatForPrompt([{ item: item('2026-10-02T09:00:00Z', 'Open PR state'), score: 1 }], NOW);
  assert.doesNotMatch(fresh, /STALE/);
  const store = new SqliteTokenStore();
  const id = store.write({ source_run_id: 'r', kind: 'lesson', title: 'How to list open pull requests', content: 'Fetch the pulls endpoint.', tags: [], evidence_ref: 'x' }, 't');
  assert.ok(id.ok);
  const row = store.get((id as { id: string }).id)!;
  assert.match(formatTokensForPrompt([row], row.created_at + 5 * DAY), /\(lesson, saved \d{4}-\d{2}-\d{2}, STALE, verify with a tool\)/);
  assert.match(formatTokensForPrompt([row], row.created_at + 1000), /\(lesson, saved \d{4}-\d{2}-\d{2}\)/);
  store.close();
});

test('the system rule says tool results from this run outrank memory', () => {
  assert.match(EVIDENCE_RULE, /Tool results from THIS run outrank recalled memories and lessons/);
  assert.match(EVIDENCE_RULE, /never answer from memory alone when a tool already answered/);
});

test('conflictCandidate: only when a tool said nothing/failed AND the answer asserts a concrete state without saying so', () => {
  const empty = [{ name: 'fetch_url', ok: true, output: '{"ok":true,"status":200,"text":"[]"}' }];
  assert.equal(isNegativeEvidence(empty[0]!), true);
  assert.equal(conflictCandidate('We are working on PR #304, a draft.', empty), true);
  assert.equal(conflictCandidate('There are no open pull requests right now.', empty), false);
  assert.equal(conflictCandidate('We are working on PR #304, a draft.', [{ name: 'fetch_url', ok: true, output: '{"ok":true,"status":200,"text":"[{\\"number\\":304,\\"draft\\":true}]"}' }]), false, 'the tool agreed');
  assert.equal(conflictCandidate('CI is passing.', [{ name: 'fetch_url', ok: true, output: '{"ok":true,"status":200,"text":"{\\"total_count\\":0,\\"workflow_runs\\":[]}"}' }]), true);
  assert.equal(conflictCandidate('The server is running.', [{ name: 'fetch_url', ok: true, output: '{"ok":true,"status":503,"text":"service unavailable"}' }]), true);
  assert.equal(conflictCandidate('Done.', empty), false);
  assert.equal(parseJudge('```json\n{"conflict":true,"detail":"The API returned []."}\n```')?.conflict, true);
  assert.equal(parseJudge('nonsense'), null);
});

test('non-empty conflicts: a PR number, status or count that is nowhere in this run\'s tool output makes the answer a candidate; supported claims do not', () => {
  const list = [{ name: 'fetch_url', ok: true, output: '{"ok":true,"status":200,"text":"[{\\"number\\":322,\\"title\\":\\"Real PR\\",\\"state\\":\\"open\\",\\"draft\\":false}]"}' }];
  assert.deepEqual(unsupportedClaims('The open PR is #304.', list), ['#304']);
  assert.equal(conflictCandidate('The open PR is #304.', list), true);
  assert.equal(conflictCandidate('The open PR is #322, Real PR.', list), false, 'the number is in the tool output');
  assert.deepEqual(unsupportedClaims('There are 3 open PRs.', list), ['3 prs']);
  assert.equal(conflictCandidate('There is 1 open PR.', list), false, 'the count appears in the output');
  const ci = [{ name: 'fetch_url', ok: true, output: '{"ok":true,"status":200,"text":"{\\"workflow_runs\\":[{\\"conclusion\\":\\"failure\\",\\"name\\":\\"test\\"}]}"}' }];
  assert.equal(conflictCandidate('CI is green and passing on main.', ci), true, 'the tool says failure');
  assert.equal(conflictCandidate('CI is failing: the latest run concluded with failure.', ci), false);
  assert.equal(conflictCandidate('CI is not green; the run failed.', ci), false, 'a negated status word is not a claim');
  assert.equal(conflictCandidate('Done.', []), false, 'no tool output, nothing to contradict');
  assert.equal(conflictCandidate('Wrote the file, 42 bytes.', [{ name: 'write_file', ok: true, output: '{"ok":true,"bytes":42}' }]), false, 'ordinary answers do not trigger');
});

// ─── agent-level replays ────────────────────────────────────────

let mock: MockInception;
let agent: typeof import('../agent.ts');
let workspace: string;
before(async () => {
  mock = await startMockInception();
  process.env.INCEPTION_BASE_URL = mock.baseUrl;
  process.env.INCEPTION_API_KEY = 'test-key';
  agent = await import('../agent.ts');
});
after(async () => { await mock.close(); });

function hooksFor() {
  workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-evidence-'));
  const thoughts: Array<Record<string, unknown>> = [];
  const events: AgentEvent[] = [];
  const hooks: AgentHooks = {
    workspace, resolvePath: (rel) => path.resolve(workspace, rel), onThought: (t) => thoughts.push(t), onEvent: (e) => events.push(e), onFilesChanged: () => {},
    signal: new AbortController().signal, checkBudget: () => null, approvedDomains: new Set(), requestApproval: async () => true,
    remember: async (title) => ({ id: `org/${title}` }), recall: async () => ({ backend: 'test', results: [] }), rssFeed: async () => ({ items: [] }),
  };
  return { hooks, thoughts };
}
const STALE_MEMORY = MemoryStore.formatForPrompt([{ item: { id: 'org/open-pr-state-2026-09-30', layer: 'org', title: 'Open PR state 2026-09-30 (main is the merged baseline)', tags: [], source: 'agent', created: '2026-09-30T10:00:00Z', updated: '2026-09-30T10:00:00Z', content: 'Open PR: #304 Markdown organized into folders (draft).', path: 'org/open-pr-state.md' }, score: 1 }]);
const run = (goal: string, hooks: AgentHooks) => agent.runToolAgent(goal, 'mercury-2', 8, 0.2, [], hooks, STALE_MEMORY);
const verdict = (conflict: boolean, detail: string) => say(JSON.stringify({ conflict, detail }));

test('INCIDENT REPLAY: stale "#304 draft" memory + API returns [] -> the wrong answer is caught, retried, and the final answer says no open PRs', async () => {
  mock.script([
    call('fetch_url', { url: `${mock.origin}/api/pulls` }),
    say('We are working on PR #304, Markdown organized into folders (draft).'),
    verdict(true, 'The pulls API returned an empty list, so no pull request is open.'),
    say('There are no open pull requests: the GitHub API returned an empty list. The memory about #304 is stale.'),
    verdict(false, ''),
  ]);
  const { hooks, thoughts } = hooksFor();
  const result = await run('WHAT PR ARE WE WORKING ON?', hooks);
  assert.equal(result.success, true);
  assert.match(result.result!, /no open pull requests/i);
  assert.doesNotMatch(result.result!, /#304, Markdown/);
  assert.deepEqual(result.evidence_conflicts, ['The pulls API returned an empty list, so no pull request is open.']);
  assert.ok(thoughts.some((t) => String(t.content).startsWith('Evidence check:')));
  assert.ok(mock.requests[0]!.messages[0]!.content!.includes('Tool results from THIS run outrank recalled memories'), 'the rule is in the system prompt');
  assert.ok(mock.requests[0]!.messages[0]!.content!.includes('2026-09-30, STALE, verify with a tool'), 'the stale memory is labeled in the planner context');
  const retryRequest = mock.requests[3]!;
  assert.ok(retryRequest.messages.at(-1)!.content!.includes('conflicts with this run'), 'the retry spells out the conflict');
  assert.ok(!retryRequest.tools?.length, 'the retry has no tools');
});

test('CI status: memory says green, the API returns no runs -> corrected', async () => {
  mock.script([
    call('fetch_url', { url: `${mock.origin}/api/ci` }),
    say('CI is passing on main.'),
    verdict(true, 'The API reports zero workflow runs, so there is no CI result to call passing.'),
    say('There is no CI run to report: the API returned zero workflow runs. The "CI is passing" memory is stale.'),
    verdict(false, ''),
  ]);
  const result = await run('Is CI green?', hooksFor().hooks);
  assert.match(result.result!, /no CI run/i);
  assert.equal(result.evidence_conflicts?.length, 1);
});

test('server status: memory says running, the health check returns 503 -> corrected', async () => {
  mock.script([
    call('fetch_url', { url: `${mock.origin}/api/health` }),
    say('The server is running on port 3000.'),
    verdict(true, 'The health check returned HTTP 503, so the server is not healthy.'),
    say('The health check returned HTTP 503, so the server is down or unhealthy. The remembered "running" status is stale.'),
    verdict(false, ''),
  ]);
  const result = await run('Is the server running?', hooksFor().hooks);
  assert.match(result.result!, /503/);
  assert.doesNotMatch(result.result!, /^The server is running/);
});

test('if the retry still conflicts, the answer is replaced by what the tools said and flagged', async () => {
  mock.script([
    call('fetch_url', { url: `${mock.origin}/api/pulls` }),
    say('We are working on PR #304 (draft).'),
    verdict(true, 'The pulls API returned an empty list.'),
    say('Still PR #304, a draft.'),
    verdict(true, 'The retry still names #304 although the API returned an empty list.'),
  ]);
  const result = await run('WHAT PR ARE WE WORKING ON?', hooksFor().hooks);
  assert.match(result.result!, /^FLAGGED: .*The pulls API returned an empty list\./);
  assert.equal(result.evidence_conflicts?.length, 2);
});

test('no extra model call when the answer agrees with the tools or says nothing was found', async () => {
  mock.script([call('fetch_url', { url: `${mock.origin}/api/pulls` }), say('There are no open pull requests; the API returned an empty list.')]);
  const result = await run('WHAT PR ARE WE WORKING ON?', hooksFor().hooks);
  assert.match(result.result!, /no open pull requests/);
  assert.equal(mock.requests.length, 2, 'worker call, tool, answer: no judge call');
  assert.equal(result.evidence_conflicts, undefined);
});

test('an unusable judge reply leaves the answer alone (no silent rewrite)', async () => {
  mock.script([call('fetch_url', { url: `${mock.origin}/api/pulls` }), say('We are working on PR #304 (draft).'), say('not json')]);
  const result = await run('WHAT PR ARE WE WORKING ON?', hooksFor().hooks);
  assert.equal(result.result, 'We are working on PR #304 (draft).');
  assert.equal(result.evidence_conflicts, undefined);
});

// ─── live-state classifier, superseded and duplicate memories (P3.10) ───

import { createLiveStateClassifier } from '../evidence.ts';
import { dedupeHits, isSuperseded, type MemoryHit } from '../memory.ts';

test('freshnessLabel honors an explicit live flag over the keyword list', () => {
  assert.equal(freshnessLabel('2026-09-30T10:00:00Z', 'Prod database failover is in progress', NOW, true), '2026-09-30, STALE, verify with a tool');
  assert.equal(freshnessLabel('2026-09-30T10:00:00Z', 'The project has a pull request template', NOW, false), '2026-09-30');
});

test('the live-state classifier says "live" when a text is closer to a live example than to any static one', async () => {
  // fake embedder: axis 0 = live-ish words, axis 1 = static-ish words
  const embed = async (texts: string[]) => texts.map((t) => { const v = new Float32Array(2); v[0] = (t.match(/currently|right now|today|down|running|failover/gi) ?? []).length; v[1] = (t.match(/stores|must|uses|decisions|lessons|supports|have/gi) ?? []).length; const n = Math.hypot(...v) || 1; return v.map((x) => x / n); });
  const classify = await createLiveStateClassifier({ embed });
  assert.deepEqual(await classify(['The service is down right now.', 'The tool must validate input.']), [true, false]);
});

test('superseded memories are never recalled and identical recalls collapse to the newest', () => {
  const item = (id: string, title: string, updated: string, tags: string[] = []): MemoryHit => ({ item: { id, layer: 'task', title, tags, source: 'run', created: updated, updated, content: 'Goal: WHAT PR ARE WE WORKING ON? Outcome: done', path: `${id}.md` }, score: 1 });
  assert.equal(isSuperseded({ title: '[SUPERSEDED 2026-10-02] Open PR state', tags: [] }), true);
  assert.equal(isSuperseded({ title: 'Open PR state', tags: ['status', 'Superseded'] }), true);
  assert.equal(isSuperseded({ title: 'Open PR state', tags: ['status'] }), false);
  const deduped = dedupeHits([item('task/a', 'WHAT PR ARE WE WORKING ON?', '2026-10-01T10:00:00Z'), item('task/b', 'what pr are we working on?', '2026-10-02T10:00:00Z'), item('task/c', 'Something else', '2026-10-02T11:00:00Z')]);
  assert.deepEqual(deduped.map((h) => h.item.id), ['task/b', 'task/c'], 'the two identical goals collapse; the newest is kept, order preserved');
});
