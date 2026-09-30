// Tests the Think Token Cube's deterministic state engine (public/js/think-cube-state.js) in
// isolation from the DOM: no jsdom, no browser — it's plain data in, plain data out, which is
// exactly what "deterministic and testable" requires. See that file's header comment for the
// LIVE vs NOT-LIVE boundary these stages sit on.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  STAGES as STAGES_UNTYPED,
  ROLES as ROLES_UNTYPED,
  CELL_COUNT as CELL_COUNT_UNTYPED,
  createInitialCubeState as createInitialCubeStateUntyped,
  applyEvent as applyEventUntyped,
  cellsToRenderProps as cellsToRenderPropsUntyped,
  summarize as summarizeUntyped,
  // @ts-expect-error — plain JS module under public/, which tsconfig excludes from the program
  // entirely, so it has no declaration file; the interfaces and casts right below stand in.
} from '../public/js/think-cube-state.js';

// think-cube-state.js is plain JS with no .d.ts, so TypeScript would otherwise infer `any` for
// everything imported from it, and noImplicitAny then flags every callback parameter derived
// from it below. These shapes mirror that module's actual (and tested-by-it) return values.
interface CubeCell {
  index: number;
  face: number;
  role: string;
  active: boolean;
  locked: boolean;
  disrupted: boolean;
  shared: boolean;
  value: number;
}
interface CubeState {
  stage: string;
  tokenId: string | null;
  verdict: 'pass' | 'fail' | null;
  stable: boolean;
  cells: CubeCell[];
  history: string[];
}
interface RenderProp {
  index: number;
  face: number;
  role: string;
  className: string;
  title: string;
  opacity: number;
}

const STAGES = STAGES_UNTYPED as readonly string[];
const ROLES = ROLES_UNTYPED as readonly string[];
const CELL_COUNT = CELL_COUNT_UNTYPED as number;
const createInitialCubeState = createInitialCubeStateUntyped as () => CubeState;
const applyEvent = applyEventUntyped as (state: CubeState, event: { stage: string; payload?: Record<string, unknown> }) => CubeState;
const cellsToRenderProps = cellsToRenderPropsUntyped as (state: CubeState) => RenderProp[];
const summarize = summarizeUntyped as (state: CubeState) => {
  stage: string; tokenId: string | null; verdict: string | null; stable: boolean;
  activeCount: number; lockedCount: number; disruptedCount: number; sharedCount: number; historyLength: number;
};

describe('Think Cube state engine', () => {
  it('initial state: 100 cells, idle stage, nothing active/locked/disrupted', () => {
    const state = createInitialCubeState();
    assert.equal(state.stage, 'idle');
    assert.equal(state.cells.length, CELL_COUNT);
    assert.equal(state.tokenId, null);
    assert.equal(state.verdict, null);
    assert.equal(state.stable, false);
    assert.deepEqual(state.history, []);
    for (const cell of state.cells) {
      assert.equal(cell.active, false);
      assert.equal(cell.locked, false);
      assert.equal(cell.disrupted, false);
      assert.equal(cell.shared, false);
    }
  });

  it('every one of the 10 roles owns exactly 10 of the 100 cells', () => {
    const state = createInitialCubeState();
    for (const role of ROLES) {
      assert.equal(state.cells.filter((c) => c.role === role).length, 10, `role ${role}`);
    }
    assert.equal(ROLES.length, 10);
  });

  it('cells are deterministically distributed across 6 faces with no cell left out', () => {
    const state = createInitialCubeState();
    const faces = new Set(state.cells.map((c) => c.face));
    assert.equal(faces.size, 6);
    // Same input -> same face assignment, every time (no Math.random anywhere).
    const again = createInitialCubeState();
    assert.deepEqual(state.cells.map((c) => c.face), again.cells.map((c) => c.face));
  });

  it('intent: activates all 10 identity cells and resets everything else for a fresh token', () => {
    const state = applyEvent(createInitialCubeState(), { stage: 'intent', payload: { tokenId: 'tok-1' } });
    assert.equal(state.stage, 'intent');
    assert.equal(state.tokenId, 'tok-1');
    const identityCells = state.cells.filter((c) => c.role === 'identity');
    assert.equal(identityCells.length, 10);
    assert.ok(identityCells.every((c) => c.active));
    assert.ok(state.cells.filter((c) => c.role !== 'identity').every((c) => !c.active));
  });

  it('cell activation: decompose activates exactly N jobState cells for N opportunities', () => {
    let state = applyEvent(createInitialCubeState(), { stage: 'intent', payload: { tokenId: 'tok-2' } });
    state = applyEvent(state, { stage: 'decompose', payload: { opportunities: 3 } });
    const jobCells = state.cells.filter((c) => c.role === 'jobState');
    assert.equal(jobCells.filter((c) => c.active).length, 3);
  });

  it('decompose clamps to the 10 available jobState cells even if asked for more', () => {
    let state = applyEvent(createInitialCubeState(), { stage: 'intent' });
    state = applyEvent(state, { stage: 'decompose', payload: { opportunities: 999 } });
    assert.equal(state.cells.filter((c) => c.role === 'jobState' && c.active).length, 10);
  });

  it('information propagation: execution activates propagation cells progressively by step, replacing the prior step', () => {
    let state = applyEvent(createInitialCubeState(), { stage: 'intent' });
    state = applyEvent(state, { stage: 'execution', payload: { step: 2 } });
    assert.equal(state.cells.filter((c) => c.role === 'propagation' && c.active).length, 2);

    state = applyEvent(state, { stage: 'execution', payload: { step: 5 } });
    assert.equal(state.cells.filter((c) => c.role === 'propagation' && c.active).length, 5);
  });

  it('evidence: locks evidence cells and marks them active, one per piece of evidence', () => {
    let state = applyEvent(createInitialCubeState(), { stage: 'intent' });
    state = applyEvent(state, { stage: 'evidence', payload: { evidenceCount: 4 } });
    const evidenceCells = state.cells.filter((c) => c.role === 'evidence');
    assert.equal(evidenceCells.filter((c) => c.locked).length, 4);
    assert.ok(evidenceCells.filter((c) => c.locked).every((c) => c.active));
  });

  it('challenge state: marks validation cells disrupted for each vulnerability', () => {
    let state = applyEvent(createInitialCubeState(), { stage: 'intent' });
    state = applyEvent(state, { stage: 'challenge', payload: { vulnerabilities: 2 } });
    assert.equal(state.cells.filter((c) => c.role === 'validation' && c.disrupted).length, 2);
  });

  it('repair state: clears disruption from every disrupted cell without deactivating it', () => {
    let state = applyEvent(createInitialCubeState(), { stage: 'intent' });
    state = applyEvent(state, { stage: 'challenge', payload: { vulnerabilities: 3 } });
    assert.equal(state.cells.filter((c) => c.disrupted).length, 3);

    state = applyEvent(state, { stage: 'repair' });
    assert.equal(state.cells.filter((c) => c.disrupted).length, 0);
    assert.equal(state.cells.filter((c) => c.role === 'validation' && c.active).length, 3);
  });

  it('jury: a failing verdict leaves disruption visible; a passing verdict clears it', () => {
    let failing = applyEvent(createInitialCubeState(), { stage: 'intent' });
    failing = applyEvent(failing, { stage: 'challenge', payload: { vulnerabilities: 2 } });
    failing = applyEvent(failing, { stage: 'jury', payload: { passed: false } });
    assert.equal(failing.verdict, 'fail');
    assert.equal(failing.cells.filter((c) => c.disrupted).length, 2);

    let passing = applyEvent(createInitialCubeState(), { stage: 'intent' });
    passing = applyEvent(passing, { stage: 'challenge', payload: { vulnerabilities: 2 } });
    passing = applyEvent(passing, { stage: 'jury', payload: { passed: true } });
    assert.equal(passing.verdict, 'pass');
    assert.equal(passing.cells.filter((c) => c.disrupted).length, 0);
  });

  it('verified/proof state: locks memory and outcome cells and marks the cube stable', () => {
    let state = applyEvent(createInitialCubeState(), { stage: 'intent' });
    assert.equal(state.stable, false);
    state = applyEvent(state, { stage: 'proof' });
    assert.equal(state.stable, true);
    assert.equal(state.cells.filter((c) => c.role === 'memory' && c.locked).length, 10);
    assert.equal(state.cells.filter((c) => c.role === 'outcome' && c.locked).length, 10);
  });

  it('think_token: locks tokenState cells into a coherent final state and keeps the token id', () => {
    let state = applyEvent(createInitialCubeState(), { stage: 'intent', payload: { tokenId: 'tok-3' } });
    state = applyEvent(state, { stage: 'think_token', payload: { tokenId: 'tok-3' } });
    assert.equal(state.tokenId, 'tok-3');
    assert.equal(state.cells.filter((c) => c.role === 'tokenState' && c.locked && c.active).length, 10);
  });

  it('harvest then commons: relationship cells activate, then become marked shared', () => {
    let state = applyEvent(createInitialCubeState(), { stage: 'intent' });
    state = applyEvent(state, { stage: 'harvest' });
    assert.equal(state.cells.filter((c) => c.role === 'relationship' && c.active).length, 10);
    assert.equal(state.cells.filter((c) => c.shared).length, 0);

    state = applyEvent(state, { stage: 'commons' });
    assert.equal(state.cells.filter((c) => c.shared).length, 10);
  });

  it('the full named lifecycle runs end to end without throwing and ends stable with a coherent token', () => {
    let state = createInitialCubeState();
    const script: Array<{ stage: string; payload?: Record<string, unknown> }> = [
      { stage: 'intent', payload: { tokenId: 'tok-full' } },
      { stage: 'decompose', payload: { opportunities: 4 } },
      { stage: 'swarm', payload: { boxIds: ['box-a', 'box-b'] } },
      { stage: 'execution', payload: { step: 6 } },
      { stage: 'evidence', payload: { evidenceCount: 3 } },
      { stage: 'challenge', payload: { vulnerabilities: 1 } },
      { stage: 'repair' },
      { stage: 'jury', payload: { passed: true } },
      { stage: 'proof' },
      { stage: 'think_token', payload: { tokenId: 'tok-full' } },
      { stage: 'harvest' },
      { stage: 'commons' },
    ];
    for (const event of script) state = applyEvent(state, event);

    assert.equal(state.stage, 'commons');
    assert.equal(state.verdict, 'pass');
    assert.equal(state.stable, true);
    assert.equal(state.tokenId, 'tok-full');
    assert.equal(state.cells.filter((c) => c.disrupted).length, 0);
    assert.deepEqual(state.history, script.map((e) => e.stage));
  });

  it('reset/replay: returns to a fresh idle state, indistinguishable from createInitialCubeState()', () => {
    let state = applyEvent(createInitialCubeState(), { stage: 'intent', payload: { tokenId: 'tok-4' } });
    state = applyEvent(state, { stage: 'proof' });
    state = applyEvent(state, { stage: 'reset' });
    assert.deepEqual(state, createInitialCubeState());
  });

  it('an unknown stage throws rather than silently doing nothing', () => {
    assert.throws(() => applyEvent(createInitialCubeState(), { stage: 'not_a_real_stage' }));
  });

  it('applyEvent never mutates the state object it was given (pure reducer)', () => {
    const before = createInitialCubeState();
    const beforeSnapshot = JSON.parse(JSON.stringify(before));
    applyEvent(before, { stage: 'intent', payload: { tokenId: 'tok-5' } });
    assert.deepEqual(before, beforeSnapshot);
  });

  it('deterministic rendering/state mapping: cellsToRenderProps is pure and total over all 100 cells', () => {
    const state = applyEvent(createInitialCubeState(), { stage: 'intent' });
    const props = cellsToRenderProps(state);
    assert.equal(props.length, CELL_COUNT);
    for (const p of props) {
      assert.equal(typeof p.className, 'string');
      assert.ok(p.className.includes('cube-cell'));
      assert.ok(p.opacity >= 0 && p.opacity <= 1);
    }
    // Same state in -> byte-identical render props out, every time.
    assert.deepEqual(props, cellsToRenderProps(state));
    const identityProp = props.find((p) => p.role === 'identity');
    assert.ok(identityProp!.className.includes('is-active'));
  });

  it('summarize reports what is active, verified, disrupted and shared for a status line', () => {
    let state = applyEvent(createInitialCubeState(), { stage: 'intent', payload: { tokenId: 'tok-6' } });
    state = applyEvent(state, { stage: 'evidence', payload: { evidenceCount: 2 } });
    state = applyEvent(state, { stage: 'challenge', payload: { vulnerabilities: 1 } });
    const summary = summarize(state);
    assert.equal(summary.tokenId, 'tok-6');
    assert.equal(summary.lockedCount, 2);
    assert.equal(summary.disruptedCount, 1);
    assert.equal(summary.stable, false);
  });
});
