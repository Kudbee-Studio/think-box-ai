// P3.12 fixes from the live CLI run of "what PR are we working on?": known repository, no false conflict from an earlier failed call, no reading guessed
// files in an empty workspace. Unit tests plus agent-level replays of that trace with a scripted model.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { startMockInception, say, call, type MockInception } from './helpers/mock-inception.ts';
import type { AgentHooks } from '../agent.ts';
import { conflictCandidate, supersededFlags, type ToolEvidence } from '../evidence.ts';
import { detectRepo, parseRepo, repoContextLine } from '../repo-context.ts';

test('parseRepo understands https, ssh and bare owner/name; detectRepo prefers KUDBEE_REPO and reads this checkout\'s git remote otherwise', () => {
  for (const t of ['https://github.com/Kudbee-Studio/think-box-ai.git', 'https://github.com/Kudbee-Studio/think-box-ai', 'git@github.com:Kudbee-Studio/think-box-ai.git', 'ssh://git@github.com/Kudbee-Studio/think-box-ai.git', 'Kudbee-Studio/think-box-ai', 'https://user:tok@github.com/Kudbee-Studio/think-box-ai.git'.replace(':tok', '')]) {
    assert.equal(parseRepo(t), 'Kudbee-Studio/think-box-ai', t);
  }
  for (const bad of ['', 'not a repo', 'https://example.com/a/b', 'a/b/c', null, undefined]) assert.equal(parseRepo(bad as string), null, String(bad));
  assert.equal(detectRepo({ KUDBEE_REPO: 'Acme/widgets' }), 'Acme/widgets');
  assert.equal(detectRepo({ KUDBEE_REPO: 'garbage' }, os.tmpdir()), null, 'a bad override falls through to git, and a directory with no repo gives null');
  // Hermetic: a throwaway repo whose remote is the GitHub one (the real checkout's origin can be anything, e.g. a GitLab mirror).
  const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'detect-repo-'));
  try {
    execFileSync('git', ['init', '-q', scratch]);
    execFileSync('git', ['-C', scratch, 'remote', 'add', 'origin', 'git@github.com:Kudbee-Studio/think-box-ai.git']);
    assert.equal(detectRepo({}, scratch), 'Kudbee-Studio/think-box-ai');
  } finally { fs.rmSync(scratch, { recursive: true, force: true }); }
  assert.match(repoContextLine('Acme/widgets'), /KNOWN REPOSITORY: .*Acme\/widgets.*never guess/);
  assert.equal(repoContextLine(null), '');
});

const FAIL = (name: string, out: string): ToolEvidence => ({ name, ok: true, output: out });
// The tool results of the live run cfc21e14 (2026-10-02), in order, trimmed.
const TRACE: ToolEvidence[] = [
  FAIL('list_files', '{"ok":true,"files":[]}'),
  FAIL('fetch_url', '{"ok":true,"url":"https://api.github.com/repos/kudbEE/kudbEE/pulls?state=open","status":404,"content_type":"application/json; charset=utf-8","text":"{\\"message\\":\\"Not Found\\"}"}'),
  FAIL('fetch_url', '{"ok":true,"url":"https://api.github.com/search/issues?q=repo:kudbEE+type:pr+state:open","status":422,"content_type":"application/json","text":"{}"}'),
  FAIL('recall', '{"ok":true,"backend":"local-bm25","results":[{"id":"task/x","title":"PULL INFO FOR PR 278 AND THE LAST PR YOU CAN ACCESS?"}]}'),
  { name: 'read_file', ok: false, output: '{"ok":false,"error":"ENOENT: no such file or directory"}' },
  FAIL('list_files', '{"ok":true,"files":[]}'),
  FAIL('fetch_url', '{"ok":true,"url":"https://github.com/Kudbee-Studio/think-box-ai/pulls","status":200,"content_type":"text/html","text":"Pull requests Open 0 Closed 304 Kudbee-Studio/think-box-ai"}'),
];
const TRACE_ANSWER = 'The repository **Kudbee-Studio/think-box-ai** currently has **no open pull requests** (the GitHub "Pull requests" page shows "Open 0"). The most recent PR referenced earlier was #278, but it is now closed.';

test('the live trace: every earlier failed or empty result is superseded by the later successful page, so it cannot make the correct answer a conflict candidate', () => {
  assert.deepEqual(supersededFlags(TRACE), [true, true, true, false, true, true, false], 'the recall result and the final page are not failures');
  assert.equal(conflictCandidate('There is one open pull request, #304, a draft.', TRACE.slice(0, 2)), true, 'with no later success the failure still counts');
  const failedThenOk = [TRACE[1]!, TRACE[6]!];
  assert.equal(conflictCandidate('The open pull request is the one shown on the page.', failedThenOk), false, 'a later success wins over an earlier 404');
  const only = [TRACE[1]!, FAIL('fetch_url', '{"ok":true,"status":200,"text":"Open pull requests: #278 Fix the thing"}')];
  assert.equal(conflictCandidate('The open pull request is #278.', only), false, 'everything the answer says is in the later result; the earlier 404 alone must not make it a candidate');
  assert.equal(conflictCandidate('The open pull request is #278.', [only[0]!]), true, 'with only the 404 it would');
  assert.equal(conflictCandidate(TRACE_ANSWER, TRACE), false, 'the exact answer from the live run is not flagged any more');
});

let mock: MockInception;
let agent: typeof import('../agent.ts');
before(async () => {
  mock = await startMockInception();
  process.env.INCEPTION_BASE_URL = mock.baseUrl;
  process.env.INCEPTION_API_KEY = 'test-key';
  agent = await import('../agent.ts');
});
after(async () => { await mock.close(); });

function hooks(): AgentHooks {
  const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-livefix-'));
  return { workspace, resolvePath: (r) => path.resolve(workspace, r), onThought: () => {}, onEvent: () => {}, onFilesChanged: () => {}, signal: new AbortController().signal, checkBudget: () => null,
    approvedDomains: new Set(), requestApproval: async () => true, remember: async (t) => ({ id: t }), recall: async () => ({ backend: 'x', results: [] }), rssFeed: async () => ({ items: [] }) };
}
const run = (goal: string) => agent.runToolAgent(goal, 'mercury-2', 8, 0.2, [], hooks(), '');

test('replay: an earlier 404 then a later 200 page; the answer holds an unverifiable status word, so a model is asked, it is shown the earlier failure as superseded, says no conflict, and the answer is kept (no retry)', async () => {
  mock.script([
    call('fetch_url', { url: `${mock.origin}/api/missing` }),
    call('fetch_url', { url: `${mock.origin}/api/pulls-page` }),
    say('There are no open pull requests (the page shows "Open 0"); the last one, #278, was merged earlier.'),
    say(JSON.stringify({ conflict: false, detail: '' })),
  ]);
  const r = await run('What PR are we working on?');
  assert.match(r.result!, /no open pull requests/);
  assert.equal(r.evidence_conflicts, undefined, 'no false conflict');
  assert.equal(mock.requests.length, 4, 'worker, tool, tool, answer, judge: and no retry call');
  const judge = mock.requests[3]!;
  assert.match(judge.messages[0]!.content!, /later successful result outranks an earlier failed or empty one/);
  const payload = JSON.parse(judge.messages[1]!.content!) as { tool_results: Array<{ order: number; superseded_by_later_success: boolean }> };
  assert.deepEqual(payload.tool_results.map((t) => [t.order, t.superseded_by_later_success]), [[1, true], [2, false]]);
});

test('empty workspace: after list_files returns nothing, read_file on a guessed name is refused without touching the file system; writing the file first makes reading it fine', async () => {
  mock.script([call('list_files', {}), call('read_file', { path: 'pr_status.md' }), call('write_file', { path: 'pr_status.md', content: 'hi' }), call('read_file', { path: 'pr_status.md' }), say('done')]);
  const r = await run('check the notes');
  assert.equal(r.success, true);
  const last = mock.requests.at(-1)!.messages.filter((m) => m.role === 'tool').map((m) => JSON.parse(m.content ?? '{}') as { ok: boolean; error?: string; content?: string });
  assert.equal(last[0]!.ok, true, 'list_files');
  assert.equal(last[1]!.ok, false);
  assert.match(last[1]!.error!, /workspace is empty .* Do not guess file names/);
  assert.equal(last[3]!.ok, true, 'after writing the file it can be read');
  assert.equal(last[3]!.content, 'hi');
  assert.match(mock.requests[0]!.messages[0]!.content!, /If list_files returns an empty list the workspace is empty/);
});

test('a non-empty workspace is unaffected: reading a missing file still gives the ordinary error', async () => {
  mock.script([call('write_file', { path: 'a.md', content: 'x' }), call('list_files', {}), call('read_file', { path: 'nope.md' }), say('ok')]);
  await run('x');
  const tools = mock.requests.at(-1)!.messages.filter((m) => m.role === 'tool').map((m) => JSON.parse(m.content ?? '{}') as { ok: boolean; error?: string });
  assert.equal(tools[2]!.ok, false);
  assert.match(tools[2]!.error!, /ENOENT/);
});
