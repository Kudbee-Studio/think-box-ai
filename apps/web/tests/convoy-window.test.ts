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
