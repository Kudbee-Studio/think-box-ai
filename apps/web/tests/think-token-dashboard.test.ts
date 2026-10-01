// Behavior tests for the Think Token Dashboard. The real browser script is loaded into a node:vm
// context with a minimal fake DOM and a fake cube, then driven through its public events and click
// handlers. Nothing here proves pixel layout; see the browser screenshots in the PR for that.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const scriptSource = readFileSync(join(here, '../public/js/think-token-dashboard.js'), 'utf8');
const css = readFileSync(join(here, '../public/css/think-token-dashboard.css'), 'utf8');

class FakeEl {
  tag: string;
  dataset: Record<string, string> = {};
  attrs: Record<string, string> = {};
  attached = false;
  children: FakeEl[] = [];
  listeners: Record<string, Array<(e: any) => void>> = {};
  parts: Record<string, FakeEl> = {};
  lists: Record<string, any[]> = {};
  classes = new Set<string>();
  scrollTop = 0;
  textContent = '';
  className = '';
  id = '';
  htmlWrites = 0;
  focused = false;
  onHtml?: () => void;
  private _html = '';
  constructor(tag = 'div') { this.tag = tag; }
  get innerHTML() { return this._html; }
  set innerHTML(v: string) { this._html = v; this.htmlWrites++; this.onHtml?.(); }
  classList = {
    toggle: (c: string, on: boolean) => { if (on) this.classes.add(c); else this.classes.delete(c); },
  };
  setAttribute(k: string, v: string) { this.attrs[k] = v; }
  addEventListener(type: string, fn: (e: any) => void) { (this.listeners[type] ||= []).push(fn); }
  appendChild(c: FakeEl) { this.children.push(c); c.attached = true; return c; }
  insertAdjacentElement() { return null; }
  querySelector(sel: string) { return (this.parts[sel] ||= new FakeEl('part')); }
  querySelectorAll(sel: string) { return this.lists[sel] ?? []; }
  contains(el: FakeEl) { return el.attached; }
  remove() { this.attached = false; }
  focus() { this.focused = true; }
  click() {}
}

class FakeCube {
  static instances: FakeCube[] = [];
  container: FakeEl;
  statusEl = new FakeEl();
  inspectEl = new FakeEl();
  calls: string[] = [];
  constructor(container: FakeEl) { this.container = container; FakeCube.instances.push(this); }
  handleThought(t: any) { this.calls.push(`thought:${t.type}`); }
  pause() { this.calls.push('pause'); }
  resume() { this.calls.push('resume'); }
  reset() { this.calls.push('reset'); }
  replay() { this.calls.push('replay'); }
  runDeterministicDemo() { this.calls.push('demo'); }
  render() { this.calls.push('render'); }
}

function setup(opts: { cube?: boolean } = {}) {
  FakeCube.instances = [];
  const windowListeners: Record<string, Array<(e: any) => void>> = {};
  const timers: string[] = [];
  const body = new FakeEl('body');
  const doc: any = {
    body,
    activeElement: null as any,
    createElement: (tag: string) => new FakeEl(tag),
    getElementById: () => null,
    addEventListener: () => {},
  };
  const blobs: string[] = [];
  const win: any = {
    addEventListener: (type: string, fn: (e: any) => void) => { (windowListeners[type] ||= []).push(fn); },
    ThinkCubeRenderer: opts.cube === false ? undefined : FakeCube,
  };
  const ctx: any = {
    window: win,
    document: doc,
    setInterval: () => { timers.push('setInterval'); return 0; },
    setTimeout: () => { timers.push('setTimeout'); return 0; },
    Blob: class { constructor(parts: string[]) { blobs.push(parts.join('')); } },
    URL: { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} },
  };
  vm.createContext(ctx);
  const Dashboard = vm.runInContext(`${scriptSource}\n;ThinkTokenDashboard`, ctx);
  const dash: any = new Dashboard();
  const fire = (type: string, detail: any) => (windowListeners[type] ?? []).forEach((fn) => fn({ detail }));
  const click = (modal: FakeEl, selectors: Record<string, any>) => {
    const target = { closest: (sel: string) => selectors[sel] ?? null };
    (modal.listeners.click ?? []).forEach((fn) => fn({ target }));
  };
  const modal = () => body.children.find((c) => c.id === 'think-token-modal') as FakeEl;
  return { dash, doc, body, fire, click, modal, windowListeners, timers, blobs };
}

describe('Think Token Dashboard: data honesty', () => {
  it('registers only the three real event sources and never listens for propagation:active', () => {
    const { windowListeners } = setup();
    assert.deepEqual(Object.keys(windowListeners).sort(), ['think-cube:thought', 'token:created', 'token:used']);
  });

  it('starts no timers and fabricates no events, even after live traffic and opening the modal', () => {
    const { dash, fire, timers } = setup();
    fire('think-cube:thought', { type: 'goal', run_id: 'r1' });
    fire('token:created', { id: 't1', type: 'tool_sequence', content: 'x', confidence: 0.6 });
    dash.openDashboard();
    assert.deepEqual(timers, []);
  });

  it('feeds every real thought to the live cube exactly once', () => {
    const { fire } = setup();
    fire('think-cube:thought', { type: 'goal', run_id: 'r1' });
    fire('think-cube:thought', { type: 'tool_call' });
    assert.deepEqual(FakeCube.instances[0].calls, ['thought:goal', 'thought:tool_call']);
  });

  it('labels in-memory counts as this session (UI) and does not call them persisted', () => {
    const { dash } = setup();
    dash.addToken({ id: 't1', content: 'x' });
    assert.match(dash.tokensTabLabel(), /^This session \(1\)$/);
    assert.match(dash.renderRunInfoHtml(), /this session, UI/);
    assert.match(dash.renderTokensPaneHtml(), /not read from the database/);
    assert.match(dash.renderAnalyticsPaneHtml(), /not from persisted statistics/);
  });

  it('exports session tokens with an explicit scope and no fabricated propagation stats', () => {
    const { dash, blobs } = setup();
    dash.addToken({ id: 't1', content: 'x' });
    dash.exportLearnings();
    const data = JSON.parse(blobs[0]);
    assert.match(data.scope, /in-memory/);
    assert.equal(data.tokenCount, 1);
    assert.equal('propagationStats' in data, false);
  });

  it('does not show a success rate or usage when no usage event was ever reported', () => {
    const { dash } = setup();
    dash.addToken({ id: 't1', content: 'x' });
    assert.match(dash.renderAnalyticsPaneHtml(), /No usage events have been reported/);
    assert.doesNotMatch(dash.renderTokenCard(dash.tokens[0]), /0 uses/);
    dash.recordTokenUsage({ tokenId: 't1', success: true });
    assert.match(dash.renderAnalyticsPaneHtml(), /average success where usage was reported/);
  });
});

describe('Think Token Dashboard: current run state', () => {
  it('goal sets running and the job id; completion signals set completed', () => {
    const { dash, fire } = setup();
    fire('think-cube:thought', { type: 'goal', run_id: 'run-abcdefghijklmnop' });
    assert.equal(dash.currentRunStatus, 'running');
    assert.equal(dash.currentJobId, 'run-abcdefghijklmnop');
    fire('think-cube:thought', { type: 'memory', content: 'Saved episode to task memory: task/x.md' });
    assert.equal(dash.currentRunStatus, 'completed');
  });

  it('a new goal resets status to running and clears the previous error', () => {
    const { dash, fire } = setup();
    fire('think-cube:thought', { type: 'goal', run_id: 'r1' });
    fire('think-cube:thought', { type: 'think_token', status: 'error', content: 'Could not capture Think Tokens: boom' });
    assert.equal(dash.currentRunStatus, 'token capture failed');
    assert.equal(dash.lastError, 'Could not capture Think Tokens: boom');
    assert.match(dash.renderRunInfoHtml(), /role="alert"/);
    fire('think-cube:thought', { type: 'goal', run_id: 'r2' });
    assert.equal(dash.currentRunStatus, 'running');
    assert.equal(dash.lastError, null);
    assert.doesNotMatch(dash.renderRunInfoHtml(), /role="alert"/);
  });

  it('unrelated memory thoughts do not mark the run completed', () => {
    const { dash, fire } = setup();
    fire('think-cube:thought', { type: 'goal', run_id: 'r1' });
    fire('think-cube:thought', { type: 'memory', content: 'Recalled 2 memories' });
    assert.equal(dash.currentRunStatus, 'running');
  });

  it('survives a goal with a non-string or missing run id', () => {
    const { dash, fire } = setup();
    fire('think-cube:thought', { type: 'goal', run_id: 12345 });
    assert.equal(dash.currentJobId, '12345');
    fire('think-cube:thought', { type: 'goal' });
    assert.equal(dash.currentJobId, null);
    assert.match(dash.renderRunInfoHtml(), /none yet/);
  });
});

describe('Think Token Dashboard: update behavior (no modal rebuild)', () => {
  it('updates tab label, panes and run info in place; the modal markup is written once', () => {
    const { dash, fire, modal } = setup();
    dash.openDashboard();
    const m = modal();
    assert.equal(m.htmlWrites, 1);
    fire('token:created', { id: 't1', type: 'tool_sequence', content: 'first' });
    fire('think-cube:thought', { type: 'goal', run_id: 'r1' });
    assert.equal(m.htmlWrites, 1, 'modal root markup must not be rewritten by live events');
    assert.equal(m.querySelector('[data-tab="tokens"]').textContent, 'This session (1)');
    assert.match(m.querySelector('#tab-tokens').innerHTML, /first/);
    assert.match(m.querySelector('#tab-analytics').innerHTML, /Confidence/);
    assert.match(m.querySelector('.current-job-info').innerHTML, /running/);
  });

  it('opening an already-open dashboard reuses it and keeps the same live cube', () => {
    const { dash, body } = setup();
    dash.openDashboard();
    dash.openDashboard();
    assert.equal(body.children.length, 1);
    assert.equal(FakeCube.instances.length, 1);
  });

  it('preserves scroll position and the focused Details button across a live refresh', () => {
    const { dash, doc, fire, modal } = setup();
    dash.openDashboard();
    const m = modal();
    const scroller = m.querySelector('.tab-content');
    scroller.scrollTop = 120;
    m.querySelector('#tab-tokens').onHtml = () => { scroller.scrollTop = 0; };
    const btn = new FakeEl('button');
    btn.dataset.tokenDetails = 't1';
    m.lists['[data-token-details]'] = [btn];
    doc.activeElement = btn;
    fire('token:created', { id: 't2', content: 'second' });
    assert.equal(scroller.scrollTop, 120);
    assert.equal(btn.focused, true);
  });

  it('does no DOM work while the dashboard is closed, and stops after it is closed', () => {
    const { dash, fire, modal, click } = setup();
    fire('token:created', { id: 't0', content: 'before open' });
    assert.equal(dash.modalEl, null);
    dash.openDashboard();
    const m = modal();
    click(m, { '[data-dashboard-close]': {} });
    assert.equal(dash.modalEl, null);
    const writes = m.querySelector('#tab-tokens').htmlWrites;
    fire('token:created', { id: 't1', content: 'after close' });
    assert.equal(m.querySelector('#tab-tokens').htmlWrites, writes);
    assert.equal(dash.tokens.length, 2, 'tokens are still recorded while closed');
  });
});

describe('Think Token Dashboard: empty, unavailable and error states', () => {
  it('shows distinct empty states for tokens and analytics', () => {
    const { dash } = setup();
    assert.match(dash.renderTokensPaneHtml(), /No Think Token has been reported in this browser session yet/);
    assert.match(dash.renderAnalyticsPaneHtml(), /Nothing to summarise yet/);
  });

  it('says so when the cube module did not load, and still handles events without throwing', () => {
    const { dash, fire, modal } = setup({ cube: false });
    dash.openDashboard();
    assert.match(modal().innerHTML, /Cube unavailable/);
    assert.doesNotMatch(modal().innerHTML, /data-cube-action/);
    assert.doesNotThrow(() => fire('think-cube:thought', { type: 'goal', run_id: 'r1' }));
  });
});

describe('Think Token Dashboard: controls', () => {
  it('main controls drive the live cube; demo is not among them', () => {
    const { dash, modal, click } = setup();
    dash.openDashboard();
    const m = modal();
    for (const name of ['pause', 'resume', 'reset', 'replay']) click(m, { '[data-cube-action]': { dataset: { cubeAction: name } } });
    const live = FakeCube.instances[0];
    for (const name of ['pause', 'resume', 'reset', 'replay']) assert.ok(live.calls.includes(name), name);
    const controls = m.innerHTML.slice(m.innerHTML.indexOf('class="cube-controls"'), m.innerHTML.indexOf('</div>', m.innerHTML.indexOf('class="cube-controls"')));
    assert.doesNotMatch(controls, /demo/);
  });

  it('demo lives in a collapsed, labeled drawer and runs on a separate cube, never the live one', () => {
    const { dash, modal, click } = setup();
    dash.openDashboard();
    const m = modal();
    assert.match(m.innerHTML, /<details class="demo-drawer">\s*<summary>Demo \(simulated, not live\)<\/summary>/);
    assert.doesNotMatch(m.innerHTML, /<details class="demo-drawer" open/);
    const liveBefore = [...FakeCube.instances[0].calls];
    click(m, { '[data-cube-action]': { dataset: { cubeAction: 'demo' } } });
    assert.equal(FakeCube.instances.length, 2);
    assert.deepEqual(FakeCube.instances[1].calls.includes('demo'), true);
    assert.deepEqual(FakeCube.instances[0].calls, liveBefore, 'live cube untouched by the demo');
    assert.equal(FakeCube.instances[1].container, m.querySelector('.demo-cube-slot'));
    click(m, { '[data-cube-action]': { dataset: { cubeAction: 'demo' } } });
    assert.equal(FakeCube.instances.length, 2, 'rerun reuses the demo cube');
    assert.ok(FakeCube.instances[1].calls.includes('reset'));
  });

  it('the legend names only decompose, repair and commons as never backend-driven', () => {
    const { dash, modal } = setup();
    dash.openDashboard();
    assert.match(modal().innerHTML, /Never driven by the backend yet:<\/strong> decompose, repair, commons\./);
    assert.match(modal().innerHTML, /Specialist jobs also drive swarm, jury and proof/);
  });

  it('tabs switch by toggling classes and aria-selected, without touching content', () => {
    const { dash, modal, click } = setup();
    dash.openDashboard();
    const m = modal();
    const b1 = new FakeEl('button'); b1.dataset.tab = 'tokens'; b1.classes.add('active');
    const b2 = new FakeEl('button'); b2.dataset.tab = 'analytics';
    const p1 = new FakeEl(); p1.id = 'tab-tokens'; p1.classes.add('active');
    const p2 = new FakeEl(); p2.id = 'tab-analytics';
    m.lists['.tab-button'] = [b1, b2];
    m.lists['.tab-pane'] = [p1, p2];
    const writes = m.htmlWrites;
    click(m, { '[data-tab]': b2 });
    assert.equal(b2.classes.has('active'), true);
    assert.equal(b1.classes.has('active'), false);
    assert.equal(b2.attrs['aria-selected'], 'true');
    assert.equal(p2.classes.has('active'), true);
    assert.equal(p1.classes.has('active'), false);
    assert.equal(m.htmlWrites, writes);
  });
});

describe('Think Token Dashboard: escaping and no inline handlers', () => {
  it('hostile ids and content render inert and never break out of an attribute', () => {
    const { dash } = setup();
    dash.addToken({ id: 'x" onclick="alert(1)', type: '<b>t</b>', content: '<img src=x onerror=alert(1)>' });
    const html = dash.renderTokenCard(dash.tokens[0]);
    assert.doesNotMatch(html, /<img/);
    assert.doesNotMatch(html, /<b>/);
    assert.doesNotMatch(html, /"\s*onclick=/);
    assert.match(html, /data-token-details="x&quot; onclick=&quot;alert\(1\)"/);
  });

  it('the modal contains no inline event handlers; Details opens through delegation', () => {
    const { dash, modal, click } = setup();
    dash.openDashboard();
    dash.addToken({ id: "t'1", content: 'x' });
    const m = modal();
    assert.doesNotMatch(m.innerHTML, /\sonclick=/);
    assert.doesNotMatch(m.querySelector('#tab-tokens').innerHTML, /\sonclick=/);
    let opened: string | null = null;
    dash.showTokenDetails = (id: string) => { opened = id; };
    click(m, { '[data-token-details]': { dataset: { tokenDetails: "t'1" } } });
    assert.equal(opened, "t'1");
  });
});

describe('Think Token Dashboard: responsive CSS (static check, not a browser run)', () => {
  it('declares breakpoints at 1024px, 768px and 480px', () => {
    for (const bp of ['1024px', '768px', '480px']) assert.ok(css.includes(`max-width: ${bp}`), bp);
  });

  it('collapses the two-column layout to one column at 1024px', () => {
    const block = css.slice(css.indexOf('max-width: 1024px'));
    assert.ok(/\.dashboard-layout\s*\{[^}]*grid-template-columns:\s*1fr;/.test(block));
  });
});
