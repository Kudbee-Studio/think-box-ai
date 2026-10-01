// Display-only pulses for real token events (think-cube-render.js pulse()). The renderer is loaded under Node with a
// stub DOM and mock timers. Pulses must never change the cube's deterministic state, must queue instead of
// overlapping, must throttle bursts, and must not twist when the user prefers reduced motion.
import { describe, it, beforeEach, afterEach, mock } from 'node:test';
import assert from 'node:assert/strict';

class El {
  className = '';
  title = '';
  innerHTML = '';
  textContent = '';
  tabIndex = 0;
  dataset: Record<string, string> = {};
  style = { props: {} as Record<string, string>, opacity: '', setProperty(k: string, v: string) { this.props[k] = v; }, removeProperty(k: string) { delete this.props[k]; } };
  children: El[] = [];
  parentElement: El | null = null;
  listeners: Record<string, unknown[]> = {};
  attrs: Record<string, string> = {};
  classes = new Set<string>();
  classList = { add: (c: string) => this.classes.add(c), remove: (c: string) => this.classes.delete(c), contains: (c: string) => this.classes.has(c) };
  setAttribute(k: string, v: string) { this.attrs[k] = v; }
  addEventListener(t: string, fn: unknown) { (this.listeners[t] ||= []).push(fn); }
  appendChild(c: El) { this.children.push(c); return c; }
  insertAdjacentElement() { return null; }
}

(globalThis as any).document = { createElement: () => new El() };
const { ThinkCubeRenderer } = await import('../public/js/think-cube-render.js');
const { createInitialCubeState } = await import('../public/js/think-cube-state.js');

const lit = (cube: any, kind: string) => cube.cellEls.map((el: El, i: number) => (el.dataset.pulse === kind ? i : -1)).filter((i: number) => i >= 0);
const roleCells = (cube: any, role: string) => cube.state.cells.filter((c: any) => c.role === role).map((c: any) => c.index);

describe('cube pulses for real token events', () => {
  beforeEach(() => { mock.timers.enable({ apis: ['setTimeout'] }); delete (globalThis as any).window; });
  afterEach(() => { mock.timers.reset(); delete (globalThis as any).window; });

  it('learned lights exactly the tokenState cells with glow = score, twists, then clears', () => {
    const cube = new ThinkCubeRenderer(new El());
    assert.equal(cube.pulse('learned', 0.62), true);
    assert.deepEqual(lit(cube, 'learned'), roleCells(cube, 'tokenState'));
    assert.equal(roleCells(cube, 'tokenState').length, 10);
    assert.equal(cube.cellEls[roleCells(cube, 'tokenState')[0]].style.props['--tt-glow'], '0.62');
    assert.ok(cube.container.classes.has('tt-twist'));
    mock.timers.tick(700);
    assert.deepEqual(lit(cube, 'learned'), []);
    assert.ok(!cube.container.classes.has('tt-twist'));
    assert.equal(cube.cellEls[roleCells(cube, 'tokenState')[0]].style.props['--tt-glow'], undefined);
  });

  it('used lights the relationship cells and does not twist', () => {
    const cube = new ThinkCubeRenderer(new El());
    cube.pulse('used', 0.8);
    assert.deepEqual(lit(cube, 'used'), roleCells(cube, 'relationship'));
    assert.ok(!cube.container.classes.has('tt-twist'));
    mock.timers.tick(700);
    assert.deepEqual(lit(cube, 'used'), []);
  });

  it('rejects an unknown kind and clamps the glow into 0.1..1', () => {
    const cube = new ThinkCubeRenderer(new El());
    assert.equal(cube.pulse('exploded', 1), false);
    assert.equal(cube.pulse('toString', 1), false, 'prototype keys are not pulse kinds');
    assert.deepEqual(lit(cube, 'learned'), []);
    cube.pulse('learned', 5);
    assert.equal(cube.cellEls[roleCells(cube, 'tokenState')[0]].style.props['--tt-glow'], '1');
    mock.timers.tick(700);
    cube.pulse('learned', -3);
    assert.equal(cube.cellEls[roleCells(cube, 'tokenState')[0]].style.props['--tt-glow'], '0.1');
    mock.timers.tick(700);
    cube.pulse('learned', Number.NaN);
    assert.equal(cube.cellEls[roleCells(cube, 'tokenState')[0]].style.props['--tt-glow'], '0.5');
  });

  it('queues pulses one at a time: the second starts only after the first clears', () => {
    const cube = new ThinkCubeRenderer(new El());
    cube.pulse('learned', 0.5);
    cube.pulse('used', 0.5);
    assert.deepEqual(lit(cube, 'used'), [], 'the second pulse waits');
    mock.timers.tick(700);
    assert.deepEqual(lit(cube, 'learned'), []);
    assert.deepEqual(lit(cube, 'used'), roleCells(cube, 'relationship'));
    mock.timers.tick(700);
    assert.deepEqual(lit(cube, 'used'), []);
    assert.equal(cube.pulseCount, 2);
  });

  it('a burst keeps only the newest few instead of animating for minutes', () => {
    const cube = new ThinkCubeRenderer(new El());
    for (let i = 0; i < 50; i++) cube.pulse('learned', 0.5);
    for (let i = 0; i < 20; i++) mock.timers.tick(700);
    assert.ok(cube.pulseCount <= 6, `ran ${cube.pulseCount} pulses for a burst of 50`);
    assert.equal(cube._pulsing, false);
  });

  it('reduced motion: no twist, a longer plain highlight', () => {
    (globalThis as any).window = { matchMedia: (q: string) => ({ matches: q.includes('prefers-reduced-motion') }) };
    const cube = new ThinkCubeRenderer(new El());
    cube.pulse('learned', 0.9);
    assert.deepEqual(lit(cube, 'learned'), roleCells(cube, 'tokenState'), 'still highlighted');
    assert.ok(!cube.container.classes.has('tt-twist'));
    mock.timers.tick(700);
    assert.deepEqual(lit(cube, 'learned'), roleCells(cube, 'tokenState'), 'held longer than the animated pulse');
    mock.timers.tick(500);
    assert.deepEqual(lit(cube, 'learned'), []);
  });

  it('never changes the deterministic cube state or its recorded events, and survives a repaint mid-pulse', () => {
    const cube = new ThinkCubeRenderer(new El());
    cube.handleThought({ type: 'goal', run_id: 'r1' });
    cube.handleThought({ type: 'tool_call' });
    const stateBefore = JSON.stringify(cube.state);
    const recordedBefore = JSON.stringify(cube.recordedEvents);
    cube.pulse('learned', 0.7);
    cube.render();
    assert.deepEqual(lit(cube, 'learned'), roleCells(cube, 'tokenState'), 'a render does not erase the pulse');
    mock.timers.tick(700);
    assert.equal(JSON.stringify(cube.state), stateBefore);
    assert.equal(JSON.stringify(cube.recordedEvents), recordedBefore);
    assert.equal(JSON.stringify(createInitialCubeState()).length > 0, true);
  });
});
