// Convoys window refresh coalescing (public/js/convoy-window.js): live updates arriving while a refresh is in flight collapse into ONE follow-up refresh, and
// responses never apply out of order.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { bootScripts } from './helpers/fake-dom.ts';

const jsDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../public/js');

function setup() {
  const { win, doc } = bootScripts(jsDir, ['convoy-window.js']) as { win: any; doc: any };
  // Every request is held until the test releases it, so "in flight" is under the test's control.
  const requests: Array<{ path: string; release: (body: unknown) => void }> = [];
  const fetchFn = (p: string): Promise<unknown> => new Promise((resolve) => {
    requests.push({ path: p, release: (body) => resolve({ ok: true, status: 200, json: () => Promise.resolve(body) }) });
  });
  const w = new win.ConvoyWindow({ document: doc, window: win, fetch: fetchFn });
  return { w, requests };
}
const tick = (): Promise<void> => new Promise((r) => setImmediate(r));
const board = (n: number) => ({ counts: { ready: 0, open: n, review: 0, finished: 0 }, lanes: { ready: [], open: [], review: [], finished: [] } });

test('two live updates during an in-flight refresh produce exactly one follow-up, started only after the first finishes', async () => {
  const { w, requests } = setup();
  w.open(); // refresh #1 starts: board request is in flight
  await tick();
  assert.deepEqual(requests.map((r) => r.path), ['/api/convoys/board']);
  w.onUpdate({ id: 'a' });
  w.onUpdate({ id: 'b' });
  await tick();
  assert.equal(requests.length, 1, 'no extra request is issued while a refresh is in flight');

  requests[0]!.release(board(1)); await tick();
  assert.deepEqual(requests.map((r) => r.path), ['/api/convoys/board', '/api/convoys'], 'the first refresh continues in order');
  requests[1]!.release({ convoys: [] }); await tick();
  // the first refresh is done; now (and only now) the single follow-up starts
  assert.deepEqual(requests.map((r) => r.path), ['/api/convoys/board', '/api/convoys', '/api/convoys/board']);
  requests[2]!.release(board(2)); await tick();
  requests[3]!.release({ convoys: [] }); await tick();
  assert.equal(requests.length, 4, 'exactly one follow-up refresh (2 requests), not two');
  assert.equal(requests.filter((r) => r.path === '/api/convoys/board').length, 2);
  assert.equal(w.board.counts.open, 2, 'the follow-up result is the one that is applied last');
});

test('an update with no refresh in flight starts one immediately, and none is queued afterwards', async () => {
  const { w, requests } = setup();
  w.open(); await tick();
  requests[0]!.release(board(0)); await tick(); requests[1]!.release({ convoys: [] }); await tick();
  assert.equal(requests.length, 2);
  w.onUpdate({ id: 'a' }); await tick();
  assert.equal(requests.length, 3);
  requests[2]!.release(board(0)); await tick(); requests[3]!.release({ convoys: [] }); await tick();
  assert.equal(requests.length, 4, 'nothing left queued');
});

// Slice 4: the draft-PR button is offered only when the server says so, sends one event naming the convoy, and a link is shown only if it is a github.com pull request.
const simConvoy = (extra: Record<string, unknown> = {}) => ({
  id: 'c1', goal: 'fix typo', state: 'COMPLETED', outcome: 'success', mode: 'live', chain: { ok: true }, plan: { workers: [] }, policy: { risk: 'low', rules: [] }, workers: [], runs: [],
  review: { state: 'accepted', decided_by: 'human' }, simulation: { sha: 'a'.repeat(40), patch_sha256: 'b'.repeat(64), files: ['x.js'], proposed_by: 'mercury-2', flags: [], verified: true, patch: 'diff' }, ...extra,
});
test('the draft PR button appears only when the server marks the proposal eligible, and clicking it sends one open_draft_pr event for that convoy', () => {
  const { w } = setup(); const sent: any[] = [];
  w.win.addEventListener('convoy:open_draft_pr', (e: any) => sent.push(e.detail));
  const none = w._detail(simConvoy({ draft_pr_available: false })); assert.equal(none.querySelectorAll('.convoy-open-draft-pr').length, 0);
  const yes = w._detail(simConvoy({ draft_pr_available: true })); const btn = yes.querySelectorAll('.convoy-open-draft-pr');
  assert.equal(btn.length, 1); assert.match(btn[0].textContent, /^Open a draft PR/);
  btn[0].click(); assert.equal(JSON.stringify(sent), JSON.stringify([{ id: 'c1' }]));
});
test('an opened draft shows its link only for a github.com pull request URL; a pushed branch without a PR offers to finish and says why it stopped', () => {
  const { w } = setup();
  const ok = w._detail(simConvoy({ draft_pr: { state: 'opened', url: 'https://github.com/Acme/widgets/pull/7' }, draft_pr_available: false })).querySelectorAll('.convoy-draft-link');
  assert.equal(ok.length, 1); assert.equal(ok[0].href, 'https://github.com/Acme/widgets/pull/7'); assert.equal(ok[0].rel, 'noopener noreferrer');
  for (const url of ['javascript:alert(1)', 'https://evil.example/Acme/widgets/pull/7', 'https://github.com/Acme/widgets/issues/7', 'https://github.com/a/b/pull/7/files']) {
    const bad = w._detail(simConvoy({ draft_pr: { state: 'opened', url }, draft_pr_available: false }));
    assert.equal(bad.querySelectorAll('.convoy-draft-link').length, 0, url); assert.equal(bad.querySelectorAll('.convoy-open-draft-pr').length, 0, url);
  }
  const resume = w._detail(simConvoy({ draft_pr: { state: 'branch_pushed', branch: 'kudbee/sim-1', repo: 'Acme/widgets', error: 'rate limited' }, draft_pr_available: true }));
  assert.equal(resume.querySelectorAll('.convoy-open-draft-pr')[0].textContent, 'Finish opening the draft PR…');
  assert.ok(resume.querySelectorAll('.convoy-blocked').some((e: any) => /kudbee\/sim-1 is pushed to Acme\/widgets.*rate limited/.test(e.textContent)));
});
