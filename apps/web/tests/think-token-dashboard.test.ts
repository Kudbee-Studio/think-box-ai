// Behavior tests for the merged Think Tokens view (ADR 029 P1 + P2). The real browser script is loaded into a node:vm
// context with a small fake DOM, a fake window (events + sendThinkTokenMessage) and a fake cube, then driven through
// its public events and click handlers. These prove state and handler logic; real rendering is shown by the
// screenshots in the PR, not by this file.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const pub = join(here, '../public');
const scriptSource = readFileSync(join(pub, 'js/think-token-dashboard.js'), 'utf8');
const css = readFileSync(join(pub, 'css/think-token-dashboard.css'), 'utf8');
const indexHtml = readFileSync(join(pub, 'index.html'), 'utf8');

class FakeEl {
  tag: string;
  className = '';
  id = '';
  title = '';
  type = '';
  value = '';
  dataset: Record<string, string> = {};
  attrs: Record<string, string> = {};
  children: FakeEl[] = [];
  listeners: Record<string, Array<(e: any) => void>> = {};
  parts: Record<string, FakeEl> = {};
  style = { props: {} as Record<string, string>, setProperty(k: string, v: string) { this.props[k] = v; }, removeProperty(k: string) { delete this.props[k]; } };
  attached = false;
  scrollTop = 0;
  html = '';
  private text = '';
  constructor(tag = 'div') { this.tag = tag; }
  get textContent(): string { return this.text + this.children.map((c) => c.textContent).join(''); }
  set textContent(v: string) { this.text = String(v); this.children = []; }
  get innerHTML() { return this.html; }
  set innerHTML(v: string) { this.html = v; }
  classList = {
    add: (c: string) => { if (!this.className.split(' ').includes(c)) this.className = `${this.className} ${c}`.trim(); },
    remove: (c: string) => { this.className = this.className.split(' ').filter((x) => x !== c).join(' '); },
    contains: (c: string) => this.className.split(' ').includes(c),
    toggle: (c: string, on?: boolean) => { if (on ?? !this.classList.contains(c)) this.classList.add(c); else this.classList.remove(c); },
  };
  setAttribute(k: string, v: string) { this.attrs[k] = v; }
  addEventListener(type: string, fn: (e: any) => void) { (this.listeners[type] ||= []).push(fn); }
  append(...nodes: FakeEl[]) { for (const n of nodes) this.children.push(n); }
  appendChild(c: FakeEl) { this.children.push(c); c.attached = true; return c; }
  replaceChildren(...nodes: FakeEl[]) { this.children = [...nodes]; this.text = ''; }
  insertAdjacentElement() { return null; }
  querySelector(sel: string) { return (this.parts[sel] ||= new FakeEl('part')); }
  querySelectorAll() { return []; }
  contains(el: FakeEl) { return el.attached; }
  remove() { this.attached = false; }
  click() {}
}

const all = (root: FakeEl): FakeEl[] => [root, ...root.children.flatMap(all)];
const byClass = (root: FakeEl, cls: string) => all(root).filter((e) => e.className.split(' ').includes(cls));
const text = (root: FakeEl) => root.textContent;

class FakeCube {
  static instances: FakeCube[] = [];
  container: FakeEl;
  statusEl = new FakeEl();
  inspectEl = new FakeEl();
  calls: string[] = [];
  pulses: Array<[string, number]> = [];
  constructor(container: FakeEl) { this.container = container; FakeCube.instances.push(this); }
  handleThought(t: any) { this.calls.push(`thought:${t.type}`); }
  pulse(kind: string, intensity: number) { this.pulses.push([kind, intensity]); return true; }
  pause() { this.calls.push('pause'); }
  resume() { this.calls.push('resume'); }
  reset() { this.calls.push('reset'); }
  replay() { this.calls.push('replay'); }
  runDeterministicDemo() { this.calls.push('demo'); }
  render() { this.calls.push('render'); }
}

function setup(opts: { cube?: boolean; connected?: boolean; dock?: boolean } = {}) {
  FakeCube.instances = [];
  const clock = { t: 1_700_000_000_000 };
  const windowListeners: Record<string, Array<(e: any) => void>> = {};
  const sent: any[] = [];
  const timers = { intervals: [] as Array<() => void>, cleared: 0, timeouts: [] as Array<{ fn: () => void; ms: number }> };
  const body = new FakeEl('body');
  const dockEl = new FakeEl('div');
  const doc: any = {
    body,
    createElement: (tag: string) => new FakeEl(tag),
    createElementNS: (_ns: string, tag: string) => new FakeEl(tag),
    getElementById: (id: string) => (opts.dock && id === 'tt-cube-dock' ? dockEl : null),
    addEventListener: () => {},
  };
  const blobs: string[] = [];
  const win: any = {
    addEventListener: (type: string, fn: (e: any) => void) => { (windowListeners[type] ||= []).push(fn); },
    ThinkCubeRenderer: opts.cube === false ? undefined : FakeCube,
    sendThinkTokenMessage: (m: unknown) => { if (opts.connected === false) return false; sent.push(JSON.parse(JSON.stringify(m))); return true; },
  };
  class FakeDate extends Date { static override now() { return clock.t; } }
  const ctx: any = {
    window: win,
    document: doc,
    Date: FakeDate,
    setInterval: (fn: () => void) => { timers.intervals.push(fn); return timers.intervals.length; },
    clearInterval: () => { timers.cleared += 1; },
    setTimeout: (fn: () => void, ms: number) => { timers.timeouts.push({ fn, ms }); return timers.timeouts.length; },
    clearTimeout: () => {},
    Blob: class { constructor(parts: string[]) { blobs.push(parts.join('')); } },
    URL: { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} },
  };
  vm.createContext(ctx);
  const api = vm.runInContext(`${scriptSource}\n;({ ThinkTokenDashboard, validTokenEvent })`, ctx) as { ThinkTokenDashboard: any; validTokenEvent: (d: unknown) => boolean };
  const dash: any = new api.ThinkTokenDashboard();
  const fire = (type: string, detail: any) => (windowListeners[type] ?? []).forEach((fn) => fn({ detail }));
  const click = (modal: FakeEl, selectors: Record<string, any>) => {
    const target = { closest: (sel: string) => selectors[sel] ?? null };
    (modal.listeners.click ?? []).forEach((fn) => fn({ target }));
  };
  const modal = () => body.children.find((c) => c.id === 'think-token-modal') as FakeEl;
  const open = () => { dash.openDashboard(); return modal(); };
  const msg = (type: string, data: unknown) => fire('think-tokens:message', { type, data });
  return { dockEl, dash, doc, body, fire, click, modal, open, msg, windowListeners, timers, sent, blobs, clock, api };
}

const TOKEN = (n: number, over: Record<string, unknown> = {}) => ({
  id: `TT-${String(n).padStart(6, '0')}`, legacy_id: null, kind: 'lesson', title: `Lesson ${n}`, content: `Use write_file after fetch_url (lesson ${n}).`, tags: ['research'],
  status: 'accepted', score: 0.525,
  score_breakdown: { formula: '0.45*usefulness + 0.20*recency + 0.15*reuse + 0.20*feedback', weights: { usefulness: 0.45, recency: 0.2, reuse: 0.15, feedback: 0.2 },
    inputs: { success_runs: 0, failed_runs: 0, uses: 0, thumbs_up: 0, thumbs_down: 0, age_days: 0, half_life_days: 30 },
    components: { usefulness: 0.5, recency: 1, reuse: 0, feedback: 0.5 }, weighted: { usefulness: 0.225, recency: 0.2, reuse: 0, feedback: 0.1 }, score: 0.525 },
  source_run_id: 'ab5e5299-854f-472d-80be-0d55ed2e5184', evidence_ref: 'run:ab5e5299', extractor: 'mercury', extract_model: 'mercury-2',
  challenge: { verdict: 'pass', reason: 'specific and supported', model: 'mercury-2', meta: {} },
  uses: 0, last_used_at: null, success_runs: 0, failed_runs: 0, thumbs_up: 0, thumbs_down: 0, seen_count: 1, created_at: 1, used_by: [],
  receipt: { receipt_id: 'ttr_0123456789abcdef', seq: 5, hash: 'h', prev_hash: 'p', action: 'transition', decision: 'admitted' }, ...over,
});
const EVENT = (over: Record<string, unknown> = {}) => ({ token_id: 'TT-000007', run_id: 'ab5e5299-854f-472d-80be-0d55ed2e5184', kind: 'lesson', status: 'accepted', score: 0.62, delta: 0, uses: 0, title: 'Lesson 7', ...over });

describe('Think Tokens view: data honesty', () => {
  it('listens only to the three real sources; no timer exists until the view is open, and none dispatches an event', () => {
    const { windowListeners, timers, open, dash } = setup();
    assert.deepEqual(Object.keys(windowListeners).sort(), ['think-cube:run', 'think-cube:thought', 'think-tokens:message']);
    assert.equal(timers.intervals.length, 0);
    const m = open();
    assert.equal(timers.intervals.length, 1, 'one repaint interval while open');
    timers.intervals[0]();
    timers.intervals[0]();
    assert.equal(dash.tokens.length, 0, 'repaint changes no data');
    dash.closeDashboard();
    assert.equal(timers.cleared, 1, 'the interval is cleared on close');
    assert.equal(m.attached, false);
  });

  it('has no in-memory token list: token:created is gone and the persisted list is the only source', () => {
    const { windowListeners } = setup();
    assert.equal(windowListeners['token:created'], undefined);
    assert.equal(windowListeners['token:used'], undefined);
    assert.doesNotMatch(scriptSource, /propagation:active/);
    assert.doesNotMatch(scriptSource, /dispatchEvent/);
  });

  it('feeds every real thought to the live cube exactly once', () => {
    const { fire } = setup();
    fire('think-cube:thought', { type: 'goal', run_id: 'r1' });
    fire('think-cube:thought', { type: 'tool_call' });
    assert.deepEqual(FakeCube.instances[0].calls, ['thought:goal', 'thought:tool_call']);
  });

  it('counts are labeled by source: saved tokens come from SQLite, Energy Core is session-only', () => {
    const { open, msg } = setup();
    const m = open();
    msg('think_tokens', { tokens: [TOKEN(1), TOKEN(2, { status: 'candidate' })], ledger: { ok: true, entries: 9 } });
    assert.match(text(m.querySelector('.tt-meta-line')), /2 shown from SQLite \(1 candidate, 1 accepted\)/);
    assert.match(text(m.querySelector('.tt-meta-line')), /write ledger verified \(9 entries\)/);
    assert.match(m.html, /Real signals from this browser session only/);
  });

  it('shows a health card from the server counts, and says it is not a measurement of benefit', () => {
    const { open, msg } = setup();
    const m = open();
    const health = { total: 4, by_status: { accepted: 3, rejected: 1 }, accepted: 3, used: 2, used_7d: 1, waiting: 1, stale: 1, runs_finished: 5, runs_failed: 1, thumbs_up: 0, thumbs_down: 0, challenge_pass: 3, challenge_fail: 1, top_used: [], stale_ids: [], note: 'Counts only. Whether tokens make runs better is measured by the A/B experiments, not by this card.' };
    msg('think_tokens', { tokens: [TOKEN(1)], ledger: { ok: true, entries: 1 }, health });
    const card = text(m.querySelector('.tt-health'));
    assert.match(card, /3accepted/); assert.match(card, /2\/3used by a run/); assert.match(card, /5\/6runs finished/); assert.match(card, /measured by the A\/B experiments/);
    msg('think_tokens', { tokens: [TOKEN(1)], ledger: { ok: true, entries: 1 } });
    assert.equal(text(m.querySelector('.tt-health')), '', 'no health in the message: the card is empty, never invented');
  });

  it('merged view: one header button, no separate Tokens modal or panel script, and the old panel file is gone', () => {
    assert.equal((indexHtml.match(/id="think-token-button"/g) ?? []).length, 1);
    assert.doesNotMatch(indexHtml, /think-tokens-open|think-tokens-modal|think-tokens-panel\.js|🎫 Learning/);
    assert.equal(existsSync(join(pub, 'js/think-tokens-panel.js')), false);
  });
});

describe('Think Tokens view: saved tokens (persisted list)', () => {
  it('requests the list when opened and renders each token with id, kind, status, score, lesson, breakdown, run, challenge, receipt', () => {
    const { open, msg, sent } = setup();
    const m = open();
    assert.deepEqual(sent[0], { type: 'think_tokens_list', limit: 50 });
    msg('think_tokens', { tokens: [TOKEN(7)], ledger: { ok: true, entries: 3 } });
    const card = byClass(m.querySelector('.tt-list'), 'tt-card')[0];
    const t = text(card);
    for (const needle of ['TT-000007', 'lesson', 'accepted', 'score 0.525', 'Lesson 7', 'Use write_file after fetch_url (lesson 7).', 'Score breakdown', 'usefulness: 0.5 × 0.45 = 0.225', 'run ab5e5299', 'extractor: mercury (mercury-2)', 'challenge: pass by mercury-2', 'receipt ttr_0123456789abcdef', 'Not used by any run yet']) {
      assert.ok(t.includes(needle), needle);
    }
    assert.equal(card.dataset.tokenId, 'TT-000007');
  });

  it('shows a token\'s links with kind, direction, weight and evidence, and says so when there are none', () => {
    const { open, msg } = setup();
    const m = open();
    const links = [
      { from_id: 'TT-000002', to_id: 'TT-000007', kind: 'same_tool', weight: 0.7, evidence: 'shared tools: write_file, recall', created_at: 1 },
      { from_id: 'TT-000007', to_id: 'TT-000009', kind: 'co_used', weight: 0.5, evidence: 'used together in 1 run', created_at: 2 },
    ];
    msg('think_tokens', { tokens: [TOKEN(7, { links }), TOKEN(8, { links: [] })], ledger: { ok: true, entries: 3 } });
    const [linked, bare] = byClass(m.querySelector('.tt-list'), 'tt-card');
    const t = text(linked);
    for (const needle of ['Links (2)', 'same_tool ← TT-000002  w=0.70  shared tools: write_file, recall', 'co_used → TT-000009  w=0.50  used together in 1 run']) assert.ok(t.includes(needle), needle);
    assert.match(text(bare), /No relationship links yet/);
  });

  it('openWithQuery (the terminal /tokens, /token and /lessons commands) opens the view with the search or TT-id already typed and asks for that list', () => {
    const { dash, sent, modal } = setup();
    dash.openWithQuery('TT-000007');
    assert.equal(dash.filters.query, 'TT-000007');
    assert.deepEqual(sent.at(-1), { type: 'think_tokens_list', limit: 50, query: 'TT-000007' });
    assert.ok(modal());
    dash.openWithQuery('stale memory');
    assert.equal(dash.filters.query, 'stale memory');
    assert.deepEqual(sent.at(-1), { type: 'think_tokens_list', limit: 50, query: 'stale memory' }, 'reopening with a new query re-requests the list');
  });

  it('marks template-extracted tokens as not model-written, and shows legacy ids and uses', () => {
    const { open, msg } = setup();
    const m = open();
    msg('think_tokens', { tokens: [TOKEN(1, { extractor: 'template', extract_model: null, status: 'candidate', legacy_id: 'tt_e52e627d85a9d763', challenge: { verdict: null, reason: null, model: null, meta: {} }, used_by: [{ run_id: 'run-abcdef123456', used_at: 1, success: 1 }] })], ledger: { ok: true, entries: 1 } });
    const t = text(m.querySelector('.tt-list'));
    assert.match(t, /extractor: template \(not model-written\)/);
    assert.match(t, /challenge: none yet/);
    assert.match(t, /was tt_e52e627d85a9d763/);
    assert.match(t, /Used by runs: run-abcd ✓/);
  });

  it('token text is only ever textContent: hostile content makes no element and never reaches innerHTML', () => {
    const { open, msg } = setup();
    const m = open();
    const hostile = '<img src=x onerror=alert(1)><script>alert(2)</script>';
    msg('think_tokens', { tokens: [TOKEN(1, { title: hostile, content: hostile, tags: [hostile] })], ledger: { ok: true, entries: 1 } });
    assert.ok(text(m.querySelector('.tt-list')).includes(hostile), 'shown literally as text');
    assert.ok(all(m.querySelector('.tt-list')).every((e) => e.tag !== 'img' && e.tag !== 'script'));
    assert.ok(!m.html.includes('onerror'), 'the skeleton never contains token data');
  });

  it('ignores malformed token lists instead of rendering them', () => {
    const { open, msg, dash } = setup();
    open();
    msg('think_tokens', { tokens: 'nope' });
    assert.equal(dash.loaded, false);
    msg('think_tokens', { tokens: [{ id: 5 }, null, TOKEN(2)], ledger: null });
    assert.equal(dash.tokens.length, 1);
  });

  it('shows distinct loading, empty, filtered-empty and error states', () => {
    const { open, msg, dash } = setup();
    const m = open();
    const list = () => text(m.querySelector('.tt-list'));
    assert.match(list(), /Loading saved tokens/);
    msg('think_tokens', { tokens: [], ledger: { ok: true, entries: 0 } });
    assert.match(list(), /No Think Tokens saved yet/);
    dash.filters.status = 'accepted';
    dash.renderList();
    assert.match(list(), /No saved token matches this search or filter/);
    const off = setup({ connected: false });
    const m2 = off.open();
    assert.match(text(m2.querySelector('.tt-list')), /Not connected to the Agent OS backend/);
    assert.equal(byClass(m2.querySelector('.tt-list'), 'tt-error')[0].attrs.role, 'alert');
  });

  it('search and filter send the right request; the id-like search highlights the matching card', () => {
    const { open, msg, sent, timers, dash } = setup();
    const m = open();
    sent.length = 0;
    const search = m.querySelector('#tt-search');
    search.value = 'TT-42';
    search.listeners.input.forEach((fn) => fn({}));
    assert.equal(sent.length, 0, 'debounced');
    timers.timeouts[timers.timeouts.length - 1].fn();
    assert.deepEqual(sent[0], { type: 'think_tokens_list', limit: 50, query: 'TT-42' });
    const status = m.querySelector('#tt-status');
    status.value = 'rejected';
    status.listeners.change.forEach((fn) => fn({}));
    assert.deepEqual(sent[1], { type: 'think_tokens_list', limit: 50, query: 'TT-42', status: 'rejected' });
    msg('think_tokens', { tokens: [TOKEN(41), TOKEN(42)], ledger: { ok: true, entries: 1 } });
    const cards = byClass(m.querySelector('.tt-list'), 'tt-card');
    assert.deepEqual(cards.map((c) => c.classList.contains('is-jump')), [false, true]);
    dash.filters.query = 'x'.repeat(500);
    sent.length = 0;
    dash.requestList();
    assert.equal(sent[0].query.length, 100, 'query is capped before sending');
  });

  it('accept / retire / thumbs send one validated action and show the approval and result messages', () => {
    const { open, msg, sent, click } = setup();
    const m = open();
    msg('think_tokens', { tokens: [TOKEN(3, { status: 'candidate' })], ledger: { ok: true, entries: 1 } });
    const card = byClass(m.querySelector('.tt-list'), 'tt-card')[0];
    const buttons = all(card).filter((e) => e.tag === 'button' && e.dataset.ttAction);
    assert.deepEqual(buttons.map((b) => b.dataset.ttAction), ['accept', 'retire', 'thumb_up', 'thumb_down']);
    sent.length = 0;
    click(m, { '[data-tt-action]': buttons[0] });
    assert.deepEqual(sent[0], { type: 'think_token_action', action: 'accept', id: 'TT-000003' });
    assert.match(text(m.querySelector('.tt-meta-line')), /Waiting for your approval/);
    sent.length = 0;
    msg('think_token_result', { ok: true, id: 'TT-000003', action: 'accept', receipt: { receipt_id: 'ttr_abc' } });
    assert.match(text(m.querySelector('.tt-meta-line')), /Applied accept to TT-000003 \(receipt ttr_abc\)/);
    assert.equal(sent[0].type, 'think_tokens_list', 'the list reloads after an action');
    msg('think_token_result', { ok: false, id: 'TT-000003', action: 'accept', error: 'Not approved' });
    assert.match(text(m.querySelector('.tt-meta-line')), /Not applied: Not approved/);
    msg('think_token_error', { error: 'invalid token id' });
    assert.match(text(m.querySelector('.tt-meta-line')), /Rejected: invalid token id/);
  });

  it('retired tokens offer no Accept or Retire; accepted tokens offer Retire only', () => {
    const { open, msg } = setup();
    const m = open();
    msg('think_tokens', { tokens: [TOKEN(1, { status: 'retired' }), TOKEN(2, { status: 'accepted' })], ledger: null });
    const labels = byClass(m.querySelector('.tt-list'), 'tt-card').map((c) => all(c).filter((e) => e.tag === 'button' && e.dataset.ttAction).map((b) => b.dataset.ttAction));
    assert.deepEqual(labels, [['thumb_up', 'thumb_down'], ['retire', 'thumb_up', 'thumb_down']]);
  });

  it('export labels its scope as persisted tokens and contains what is shown', () => {
    const { open, msg, click, blobs } = setup();
    const m = open();
    msg('think_tokens', { tokens: [TOKEN(1)], ledger: { ok: true, entries: 1 } });
    click(m, { '[data-dashboard-export]': {} });
    const data = JSON.parse(blobs[0]);
    assert.match(data.scope, /SQLite/);
    assert.equal(data.tokenCount, 1);
    assert.equal(data.tokens[0].id, 'TT-000001');
  });
});

describe('Think Tokens view: real token events (P2)', () => {
  it('a valid think_token_learned pulses the cube by score, records the token, counts it and reloads the list', () => {
    const { open, msg, sent, dash } = setup();
    const m = open();
    sent.length = 0;
    msg('think_token_learned', EVENT({ score: 0.62 }));
    assert.deepEqual(FakeCube.instances[0].pulses, [['learned', 0.62]]);
    assert.equal(dash.energy.learned, 1);
    assert.match(text(m.querySelector('.last-token')), /TT-000007.*Lesson 7.*score 0\.620.*run ab5e5299.*used 0×/);
    assert.equal(sent[0].type, 'think_tokens_list');
  });

  it('a think_token_used pulses the relationship cells and updates the last token\'s use count', () => {
    const { open, msg, dash } = setup();
    const m = open();
    msg('think_token_learned', EVENT());
    msg('think_token_used', EVENT({ uses: 1, score: 0.64, delta: 0.02 }));
    assert.deepEqual(FakeCube.instances[0].pulses[1], ['used', 0.64]);
    assert.equal(dash.energy.used, 1);
    assert.match(text(m.querySelector('.last-token')), /used 1×/);
  });

  it('malformed, oversized or forged events are ignored: no pulse, no counter, no list reload', () => {
    const { open, msg, sent, dash, api } = setup();
    open();
    sent.length = 0;
    const bad = [
      null, 'x', [], {},
      EVENT({ token_id: "TT-1'; DROP" }), EVENT({ token_id: 'nope' }), EVENT({ score: 2 }), EVENT({ score: -0.1 }), EVENT({ score: '0.5' }), EVENT({ delta: 5 }),
      EVENT({ status: 'admin' }), EVENT({ title: 'x'.repeat(121) }), EVENT({ run_id: 'r'.repeat(81) }), EVENT({ uses: -1 }), EVENT({ uses: 1.5 }), EVENT({ kind: 'k'.repeat(21) }),
    ];
    for (const b of bad) {
      assert.equal(api.validTokenEvent(b), false, JSON.stringify(b)?.slice(0, 60));
      msg('think_token_learned', b);
      msg('think_token_used', b);
    }
    assert.equal(FakeCube.instances[0].pulses.length, 0);
    assert.equal(dash.energy.learned + dash.energy.used, 0);
    assert.equal(sent.length, 0);
    assert.equal(dash.ignoredEvents, bad.length * 2);
    assert.equal(api.validTokenEvent(EVENT()), true);
    assert.equal(api.validTokenEvent(EVENT({ token_id: 'tt_0123456789abcdef' })), true, 'a pre-migration id is still valid');
  });

  it('events work with no cube loaded, without throwing', () => {
    const { open, msg } = setup({ cube: false });
    open();
    assert.doesNotThrow(() => { msg('think_token_learned', EVENT()); msg('think_token_used', EVENT()); });
  });
});

describe('Think Tokens view: Energy Core is built only from real signals', () => {
  it('reads zero and idle when nothing has happened', () => {
    const { dash } = setup();
    assert.deepEqual(JSON.parse(JSON.stringify(dash.energySnapshot())), { eventsPerMinute: 0, activeRuns: 0, learned: 0, used: 0, lastProofAgoMs: null, state: 'idle', intensity: 0 });
  });

  it('events per minute counts only real thoughts in the last 60 seconds, and decays to idle', () => {
    const { dash, fire, clock } = setup();
    for (let i = 0; i < 5; i++) { fire('think-cube:thought', { type: 'tool_call' }); clock.t += 1000; }
    assert.equal(dash.energySnapshot().eventsPerMinute, 5);
    assert.equal(dash.energySnapshot().state, 'active');
    clock.t += 31_000;
    assert.equal(dash.energySnapshot().state, 'idle', 'no event for 30 s and no running run');
    assert.equal(dash.energySnapshot().eventsPerMinute, 5);
    clock.t += 40_000;
    assert.equal(dash.energySnapshot().eventsPerMinute, 0, 'the window slid past every event');
  });

  it('intensity is capped at 1; the event buffer is bounded', () => {
    const { dash, fire } = setup();
    for (let i = 0; i < 2500; i++) fire('think-cube:thought', { type: 'tool_call' });
    assert.equal(dash.energySnapshot().intensity, 1);
    assert.ok(dash.energy.events.length <= 2000);
  });

  it('runs running come from real run_update statuses and drop out when the run finishes', () => {
    const { dash, fire } = setup();
    fire('think-cube:run', { id: 'r1', status: 'running' });
    fire('think-cube:run', { id: 'r2', status: 'running' });
    assert.equal(dash.energySnapshot().activeRuns, 2);
    assert.equal(dash.energySnapshot().state, 'active');
    fire('think-cube:run', { id: 'r1', status: 'completed' });
    fire('think-cube:run', { id: 'r2', status: 'failed' });
    assert.equal(dash.energySnapshot().activeRuns, 0);
    fire('think-cube:run', { id: 5, status: 'running' });
    fire('think-cube:run', null);
    assert.equal(dash.energySnapshot().activeRuns, 0, 'malformed run updates are ignored');
  });

  it('last proof is the time of the last real proof_accepted thought; nothing else sets it', () => {
    const { dash, fire, clock } = setup();
    fire('think-cube:thought', { type: 'tool_call' });
    assert.equal(dash.energySnapshot().lastProofAgoMs, null);
    fire('think-cube:thought', { type: 'proof_accepted' });
    clock.t += 5000;
    assert.equal(dash.energySnapshot().lastProofAgoMs, 5000);
    assert.equal(dash.formatAge(5000), '5s ago');
    assert.equal(dash.formatAge(125_000), '2m ago');
  });

  it('renders its stats into the view', () => {
    const { open, fire, msg } = setup();
    const m = open();
    fire('think-cube:thought', { type: 'tool_call' });
    fire('think-cube:run', { id: 'r1', status: 'running' });
    msg('think_token_learned', EVENT());
    const t = text(m.querySelector('.energy-stats'));
    for (const needle of ['state', 'active', 'events / min', 'runs running', 'learned (session)', 'last proof']) assert.ok(t.includes(needle), needle);
    assert.equal(m.querySelector('.energy-core').dataset.state, 'active');
  });
});

describe('Think Tokens view: current run', () => {
  it('goal sets running and the job id; completion signals set completed; a new goal resets the error', () => {
    const { dash, fire } = setup();
    fire('think-cube:thought', { type: 'goal', run_id: 'run-abcdefghijklmnop' });
    assert.equal(dash.currentRunStatus, 'running');
    assert.equal(dash.currentJobId, 'run-abcdefghijklmnop');
    fire('think-cube:thought', { type: 'think_token', status: 'error', content: 'Could not save Think Tokens: boom' });
    assert.equal(dash.currentRunStatus, 'token capture failed');
    assert.equal(dash.lastError, 'Could not save Think Tokens: boom');
    fire('think-cube:thought', { type: 'goal', run_id: 'r2' });
    assert.equal(dash.currentRunStatus, 'running');
    assert.equal(dash.lastError, null);
    fire('think-cube:thought', { type: 'think_token', status: 'success', content: 'x' });
    assert.equal(dash.currentRunStatus, 'completed');
  });

  it('shows the real run id (plain runs now carry one) and the error as an alert', () => {
    const { open, fire } = setup();
    const m = open();
    fire('think-cube:thought', { type: 'goal', run_id: 'ab5e5299-854f-472d-80be-0d55ed2e5184' });
    fire('think-cube:thought', { type: 'think_token', status: 'error', content: 'Could not save Think Tokens: boom' });
    const info = m.querySelector('.current-job-info');
    assert.match(text(info), /Current job.*ab5e5299-854/);
    assert.equal(byClass(info, 'job-info-error')[0].attrs.role, 'alert');
  });

  it('survives a goal with a non-string or missing run id', () => {
    const { dash, fire } = setup();
    fire('think-cube:thought', { type: 'goal', run_id: 12345 });
    assert.equal(dash.currentJobId, '12345');
    fire('think-cube:thought', { type: 'goal' });
    assert.equal(dash.currentJobId, null);
  });
});

describe('Think Tokens view: controls, demo isolation, unavailable cube', () => {
  it('main controls drive the live cube; demo is not among them and runs on a separate cube', () => {
    const { open, click } = setup();
    const m = open();
    for (const name of ['pause', 'resume', 'reset', 'replay']) click(m, { '[data-cube-action]': { dataset: { cubeAction: name } } });
    const live = FakeCube.instances[0];
    for (const name of ['pause', 'resume', 'reset', 'replay']) assert.ok(live.calls.includes(name), name);
    const controls = m.html.slice(m.html.indexOf('class="cube-controls"'), m.html.indexOf('</div>', m.html.indexOf('class="cube-controls"')));
    assert.doesNotMatch(controls, /demo/);
    assert.match(m.html, /<details class="demo-drawer">\s*<summary>Demo \(simulated, not live\)<\/summary>/);
    const before = [...live.calls];
    click(m, { '[data-cube-action]': { dataset: { cubeAction: 'demo' } } });
    assert.equal(FakeCube.instances.length, 2);
    assert.ok(FakeCube.instances[1].calls.includes('demo'));
    assert.deepEqual(live.calls, before, 'the live cube is untouched by the demo');
  });

  it('the legend names only decompose, repair and commons as never backend-driven', () => {
    const { open } = setup();
    assert.match(open().html, /Never driven by the backend yet:<\/strong> decompose, repair, commons\./);
  });

  it('says so when the cube module did not load, and still handles every event', () => {
    const { open, fire, msg } = setup({ cube: false });
    const m = open();
    assert.match(m.html, /Cube unavailable/);
    assert.doesNotMatch(m.html, /data-cube-action/);
    assert.doesNotThrow(() => { fire('think-cube:thought', { type: 'goal', run_id: 'r1' }); msg('think_tokens', { tokens: [TOKEN(1)], ledger: null }); });
  });

  it('opening twice reuses the same modal and cube; closing stops the repaint timer', () => {
    const { dash, body, timers } = setup();
    dash.openDashboard();
    dash.openDashboard();
    assert.equal(body.children.length, 1);
    assert.equal(FakeCube.instances.length, 1);
    assert.equal(timers.intervals.length, 1);
    dash.closeDashboard();
    assert.equal(dash.modalEl, null);
  });

  it('clicking a close button closes it', () => {
    const { dash, click, open } = setup();
    const m = open();
    click(m, { '[data-dashboard-close]': {} });
    assert.equal(dash.modalEl, null);
    assert.equal(m.attached, false);
  });
});

describe('Think Tokens view: no inline handlers and responsive CSS (static checks, not a browser run)', () => {
  it('the modal skeleton has no inline event handlers', () => {
    const { open } = setup();
    assert.doesNotMatch(open().html, /\son[a-z]+=/i);
  });

  it('declares breakpoints at 1024px, 768px and 480px and collapses to one column at 1024px', () => {
    for (const bp of ['1024px', '768px', '480px']) assert.ok(css.includes(`max-width: ${bp}`), bp);
    const block = css.slice(css.indexOf('max-width: 1024px'));
    assert.ok(/\.dashboard-layout\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\);/.test(block));
  });

  it('reduced motion disables the Energy Core animation and the cube twist', () => {
    assert.match(css, /prefers-reduced-motion: reduce\)\s*\{\s*\.energy-core\[data-state="active"\] \.energy-ring \{ animation: none; \}/);
    const cubeCss = readFileSync(join(pub, 'css/think-cube.css'), 'utf8');
    assert.match(cubeCss, /prefers-reduced-motion: reduce[\s\S]*\.think-cube\.tt-twist \{ animation: none; \}/);
  });
});


// ─── P3.13: the 100-cell cube in the Think Tokens view ──────────

import { CELL_DEFS, projectTo54 } from '../think-token-cube.ts';

const CUBE = (id: string, changed: string[] = [], over: Record<string, { value: number | null; display: string }> = {}) => {
  const cells = CELL_DEFS.map((d) => ({ ...d, value: over[d.key] ? over[d.key]!.value : 0.5, display: over[d.key] ? over[d.key]!.display : '1' })).map((c) => ({ ...c, empty: c.value === null }));
  return { id, cells, stickers: projectTo54(cells as any), events: [], last_change: changed.length ? { cause: 'used', ts: 1, keys: changed } : null, filled: cells.filter((c) => !c.empty).length };
};

describe('Think Tokens view: the 100-cell cube', () => {
  it('opens on demand: asks the server for the cube, shows a loading line, then 100 cells and a 54-sticker view with changed cells marked and empty cells dim', () => {
    const { open, msg, click, sent } = setup();
    const m = open();
    msg('think_tokens', { tokens: [TOKEN(7)], ledger: { ok: true, entries: 3 } });
    click(m, { '[data-tt-cube]': { dataset: { ttCube: 'TT-000007' } } });
    assert.deepEqual(sent.at(-1), { type: 'think_token_cube', id: 'TT-000007' });
    assert.match(text(m.querySelector('.tt-list')), /Loading the 100 cells/);
    msg('think_token_cube', CUBE('TT-000007', ['uses', 'score'], { win_rate: { value: null, display: 'empty' } }));
    const list = m.querySelector('.tt-list');
    const cells = byClass(list, 'tt-cell');
    assert.equal(cells.length, 100);
    assert.equal(byClass(list, 'tt-sticker').length, 54);
    assert.equal(byClass(list, 'tt-face').length, 6);
    assert.deepEqual(cells.filter((c) => c.className.includes('is-changed')).map((c) => c.dataset.key).sort(), ['score', 'uses']);
    assert.deepEqual(cells.filter((c) => c.className.includes('is-empty')).map((c) => c.dataset.key), ['win_rate']);
    assert.equal(byClass(list, 'tt-gridrow').length, 10);
    assert.match(text(list), /99 of 100 cells have data/);
    assert.match(text(list), /changed by "used"/);
    assert.ok(cells.every((c) => c.attrs['aria-label'] && c.title), 'every cell is labeled for assistive tech and hover');
  });

  it('hovering, focusing or tapping a cell shows its field, value, source and meaning; a sticker shows the cells it folds together', () => {
    const { open, msg, click } = setup();
    const m = open();
    msg('think_tokens', { tokens: [TOKEN(7)], ledger: { ok: true, entries: 3 } });
    click(m, { '[data-tt-cube]': { dataset: { ttCube: 'TT-000007' } } });
    msg('think_token_cube', CUBE('TT-000007', [], { uses: { value: 0.2, display: '4' } }));
    const list = m.querySelector('.tt-list');
    const uses = byClass(list, 'tt-cell').find((c) => c.dataset.key === 'uses')!;
    for (const ev of ['mouseenter', 'focus', 'click']) assert.ok((uses.listeners[ev] ?? []).length, ev);
    uses.listeners.mouseenter![0]({});
    const insp = text(byClass(list, 'tt-cell-inspector')[0]);
    assert.match(insp, /Uses: 4/);
    assert.match(insp, /source: think_tokens\.uses/);
    assert.match(insp, /row usage, column 1, cell 51 of 100/);
    const sticker = byClass(list, 'tt-sticker')[0];
    sticker.listeners.focus![0]({});
    assert.match(text(byClass(list, 'tt-cell-inspector')[0]), /Sticker U1 \(view only\)/);
  });

  it('is text-only (a hostile cell value is shown literally), ignores malformed cubes, and hides again on a second click', () => {
    const { open, msg, click, sent } = setup();
    const m = open();
    msg('think_tokens', { tokens: [TOKEN(7)], ledger: { ok: true, entries: 3 } });
    click(m, { '[data-tt-cube]': { dataset: { ttCube: 'TT-000007' } } });
    msg('think_token_cube', { ...CUBE('TT-000007'), cells: CUBE('TT-000007').cells.slice(0, 99) });
    assert.match(text(m.querySelector('.tt-list')), /Loading the 100 cells/, 'a 99-cell payload is refused');
    const hostile = '<img src=x onerror=alert(1)>';
    msg('think_token_cube', CUBE('TT-000007', [], { title_len: { value: 1, display: hostile } }));
    const list = m.querySelector('.tt-list');
    const cell = byClass(list, 'tt-cell').find((c) => c.dataset.key === 'title_len')!;
    cell.listeners.mouseenter![0]({});
    assert.ok(text(byClass(list, 'tt-cell-inspector')[0]).includes(hostile));
    assert.ok(all(list).every((e) => e.tag !== 'img' && e.tag !== 'script'));
    const before = sent.length;
    click(m, { '[data-tt-cube]': { dataset: { ttCube: 'TT-000007' } } });
    assert.equal(byClass(m.querySelector('.tt-list'), 'tt-cell').length, 0, 'second click hides the panel');
    assert.equal(sent.length, before, 'hiding asks the server for nothing');
  });

  it('an open cube refreshes when its token is used (so changed cells pulse as it happens); a closed one does not', () => {
    const { open, msg, click, sent } = setup();
    const m = open();
    msg('think_tokens', { tokens: [TOKEN(7), TOKEN(8)], ledger: { ok: true, entries: 3 } });
    click(m, { '[data-tt-cube]': { dataset: { ttCube: 'TT-000007' } } });
    const asked = () => sent.filter((s) => s.type === 'think_token_cube').length;
    assert.equal(asked(), 1);
    msg('think_token_used', EVENT({ token_id: 'TT-000007' }));
    assert.equal(asked(), 2, 'refreshed');
    msg('think_token_used', EVENT({ token_id: 'TT-000008' }));
    assert.equal(asked(), 2, 'a token whose cube is closed is not re-requested');
  });

  it('draws the token\'s links as lines (width = weight) next to the cube', () => {
    const { open, msg, click } = setup();
    const m = open();
    const links = [{ from_id: 'TT-000002', to_id: 'TT-000007', kind: 'same_tool', weight: 0.7, evidence: 'x', created_at: 1 }, { from_id: 'TT-000007', to_id: 'TT-000009', kind: 'co_used', weight: 0.3, evidence: 'y', created_at: 1 }];
    msg('think_tokens', { tokens: [TOKEN(7, { links })], ledger: { ok: true, entries: 3 } });
    click(m, { '[data-tt-cube]': { dataset: { ttCube: 'TT-000007' } } });
    msg('think_token_cube', CUBE('TT-000007'));
    const lines = all(m.querySelector('.tt-list')).filter((e) => e.tag === 'line');
    assert.equal(lines.length, 2);
    assert.deepEqual(lines.map((l) => l.attrs['stroke-width']).sort(), ['1.56', '2.84']);
    assert.ok(lines.every((l) => /kind-/.test(l.attrs.class ?? '')));
  });

  it('the styles keep it reduced-motion safe and usable on a phone: no pulse or spin under prefers-reduced-motion (the cube lays out flat), cells shrink to ten columns at 520 px', () => {
    const css = readFileSync(join(pub, 'css/think-token-dashboard.css'), 'utf8');
    const rm = css.slice(css.lastIndexOf('@media (prefers-reduced-motion: reduce)'));
    assert.match(rm, /\.tt-cell\.is-changed[\s\S]*animation: none/);
    assert.match(rm, /\.tt-cube3d \{[^}]*animation: none[^}]*transform: none/);
    assert.match(rm, /\.tt-face \{[^}]*position: static/);
    assert.match(css, /@media \(max-width: 520px\)[\s\S]*grid-template-columns: repeat\(10, minmax\(0, 1fr\)\)/);
  });
});

describe('app.js routing', () => {
  it('forwards every message type the Think Tokens view handles (the live run found think_token_cube was not routed)', () => {
    const dash = readFileSync(join(pub, 'js/think-token-dashboard.js'), 'utf8');
    const app = readFileSync(join(pub, 'js/app.js'), 'utf8');
    const handled = [...dash.matchAll(/case '(think_token[a-z_]*)':/g)].map((m) => m[1]);
    assert.ok(handled.includes('think_token_cube'));
    for (const type of new Set(handled)) assert.ok(app.includes(`case '${type}':`), `app.js does not route ${type}`);
  });
});

describe('main dashboard dock (below the Memory Graph)', () => {
  it('loads the tokens itself, shows the best accepted token\'s cube without opening the modal, and follows the token that was just used', () => {
    const { dockEl, dash, msg, sent, timers } = setup({ dock: true });
    assert.equal(timers.intervals.length, 1, 'a start-up timer loads the list');
    timers.intervals[0]!();
    assert.deepEqual(sent.at(-1), { type: 'think_tokens_list', limit: 50 });
    msg('think_tokens', { tokens: [TOKEN(3, { status: 'accepted', score: 0.5 }), TOKEN(7, { status: 'accepted', score: 0.9 })], ledger: { ok: true, entries: 3 } });
    assert.deepEqual(sent.at(-1), { type: 'think_token_cube', id: 'TT-000007' });
    msg('think_token_cube', CUBE('TT-000007', ['score']));
    assert.equal(byClass(dockEl, 'tt-cell').length, 100);
    assert.equal(byClass(dockEl, 'tt-sticker').length, 54);
    msg('think_token_used', EVENT({ token_id: 'TT-000003' }));
    assert.deepEqual(sent.at(-1), { type: 'think_token_cube', id: 'TT-000003' });
    assert.equal(dash.dockId, 'TT-000003');
  });

  it('a viewer\'s pick sticks: later uses of other tokens do not move the dock', () => {
    const { dockEl, dash, msg, sent } = setup({ dock: true });
    msg('think_tokens', { tokens: [TOKEN(3), TOKEN(7)], ledger: { ok: true, entries: 3 } });
    const select = all(dockEl).find((e) => e.tag === 'select')!;
    select.value = 'TT-000007';
    select.listeners.change![0]({});
    assert.equal(dash.dockId, 'TT-000007');
    msg('think_token_used', EVENT({ token_id: 'TT-000003' }));
    assert.equal(dash.dockId, 'TT-000007');
    assert.notDeepEqual(sent.at(-1), { type: 'think_token_cube', id: 'TT-000003' });
  });

  it('the page has the dock under the Memory Graph and app.js is wired to it', () => {
    const html = readFileSync(join(pub, 'index.html'), 'utf8');
    assert.ok(html.indexOf('Memory Graph') < html.indexOf('id="tt-cube-dock"'));
    assert.ok(html.indexOf('id="tt-cube-dock"') < html.indexOf('Plugins'));
  });
});
