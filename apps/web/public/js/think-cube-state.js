// kudbEE Think Token Cube — deterministic state model.
//
// This module is the VISUALIZATION LAYER's state engine for one existing #288 Think Token. It
// introduces no new token model and no new persistence: it only maps events already available
// from the dashboard (WebSocket 'thought' messages, the existing token:created/token:used
// events) onto a 100-cell cube state. It has zero DOM APIs, so it is plain, framework-free,
// synchronous, and fully unit-testable under plain Node (see
// tests/think-cube-state.test.ts) without a browser or jsdom.
//
// LIVE vs NOT-LIVE boundary (read this before wiring anything to real data):
//   - 'intent'      <- real: the 'goal' thought server.ts emits at the start of runAgentGoal.
//   - 'execution'   <- real: 'tool_call' / 'tool_result' thoughts (agent.ts).
//   - 'evidence'    <- real: the same tool_result thoughts, counted.
//   - 'think_token' <- real: the 'think_token' thought server.ts emits after a run mints one
//                      (server-learning-integration.ts / think-token-propagation.ts).
//   - 'decompose', 'swarm', 'challenge', 'repair', 'jury', 'harvest', 'commons' are NOT produced
//     by any current backend signal: #288 has no multi-Think-Box swarm, no adversarial
//     challenge, no jury and no cross-session propagation today (the existing audit,
//     docs/enterprise/think-token-audit.md, confirms those concepts live only in an unrelated,
//     unwired experiment, experiments/kudbee_orchestrator.py). Driving this engine's 'swarm' /
//     'challenge' / 'repair' / 'jury' / 'harvest' / 'commons' stages therefore always means a
//     deterministic demo driver, never a live event — see think-cube-render.js's
//     `runDeterministicDemo` for the only place that does this, which labels itself as such.

export const STAGES = Object.freeze([
  'idle', 'intent', 'decompose', 'swarm', 'execution', 'evidence',
  'challenge', 'repair', 'jury', 'proof', 'think_token', 'harvest', 'commons',
]);

// The spec's ten semantic categories for what a cell can represent. 100 cells / 10 roles = 10
// cells per role, assigned deterministically by index (see createInitialCubeState).
export const ROLES = Object.freeze([
  'identity', 'jobState', 'thinkBox', 'propagation', 'evidence',
  'validation', 'memory', 'outcome', 'tokenState', 'relationship',
]);

export const CELL_COUNT = 100;
export const FACE_COUNT = 6;

/** Which face (0-5) a cell belongs to, purely from its index — deterministic, no randomness. */
function faceOf(index) {
  return index % FACE_COUNT;
}

function roleOf(index) {
  return ROLES[index % ROLES.length];
}

/** One cell's state. Plain data — never touches the DOM. */
function createCell(index) {
  return {
    index,
    face: faceOf(index),
    role: roleOf(index),
    active: false,
    locked: false,
    disrupted: false,
    shared: false,
    value: 0,
  };
}

/**
 * The cube's full state for one Think Token's lifecycle. `stage` is the current named stage
 * (one of STAGES); `history` records every stage the cube has passed through, oldest first,
 * for "how the token changed over time".
 */
export function createInitialCubeState() {
  return {
    stage: 'idle',
    tokenId: null,
    verdict: null, // 'pass' | 'fail' | null
    stable: false,
    cells: Array.from({ length: CELL_COUNT }, (_, i) => createCell(i)),
    history: [],
  };
}

function cellsWithRole(cells, role) {
  return cells.filter((c) => c.role === role);
}

/** Returns a new cells array with `patch` applied to every cell matching `predicate`. */
function patchCells(cells, predicate, patch) {
  return cells.map((c) => (predicate(c) ? { ...c, ...patch } : c));
}

/**
 * The reducer. Pure: same (state, event) always produces the same new state, no Date.now(),
 * no randomness, no DOM. `event` is `{ stage, payload }`; unknown stages throw rather than
 * silently no-op, since a state model that accepts anything cannot be deterministic in the
 * sense the cube task asked for.
 */
export function applyEvent(state, event) {
  const { stage, payload = {} } = event;
  if (!STAGES.includes(stage) && stage !== 'reset') {
    throw new Error(`Unknown cube stage: ${stage}`);
  }

  if (stage === 'reset') {
    return createInitialCubeState();
  }

  const history = [...state.history, stage];
  let cells = state.cells;

  switch (stage) {
    case 'intent': {
      // A fresh token: identity cells light up, everything else about the previous token clears.
      cells = createInitialCubeState().cells;
      cells = patchCells(cells, (c) => c.role === 'identity', { active: true, value: 1 });
      return { stage, tokenId: payload.tokenId ?? state.tokenId, verdict: null, stable: false, cells, history: [stage] };
    }

    case 'decompose': {
      // "different regions represent opportunities/capabilities" — activate jobState cells up
      // to the number of opportunities found, capped at that role's 10 cells.
      const count = Math.max(0, Math.min(10, Number(payload.opportunities ?? 0)));
      const jobCells = cellsWithRole(cells, 'jobState');
      const toActivate = new Set(jobCells.slice(0, count).map((c) => c.index));
      cells = patchCells(cells, (c) => toActivate.has(c.index), { active: true, value: 1 });
      break;
    }

    case 'swarm': {
      // One participating Think Box per thinkBox cell, up to 10; NOT driven by any real signal
      // today (#288 has no multi-box swarm) — see the module header.
      const boxes = Array.isArray(payload.boxIds) ? payload.boxIds.slice(0, 10) : [];
      const thinkBoxCells = cellsWithRole(cells, 'thinkBox');
      const toActivate = new Set(thinkBoxCells.slice(0, boxes.length).map((c) => c.index));
      cells = patchCells(cells, (c) => toActivate.has(c.index), { active: true, value: 1 });
      break;
    }

    case 'execution': {
      // "information visibly propagates across the cube" — activate propagation cells
      // progressively as `step` increases. This is the one stage with a direct real mapping:
      // each real tool_call/tool_result thought can drive one step.
      const step = Math.max(0, Math.min(10, Number(payload.step ?? 0)));
      const propCells = cellsWithRole(cells, 'propagation');
      const toActivate = new Set(propCells.slice(0, step).map((c) => c.index));
      cells = patchCells(cells, (c) => c.role === 'propagation', { active: false, value: 0 });
      cells = patchCells(cells, (c) => toActivate.has(c.index), { active: true, value: 1 });
      break;
    }

    case 'evidence': {
      // "verified cells become marked/locked" — lock evidence cells for each piece of evidence
      // gathered (real: agent.ts tool_result successes).
      const count = Math.max(0, Math.min(10, Number(payload.evidenceCount ?? 0)));
      const evidenceCells = cellsWithRole(cells, 'evidence');
      const toLock = new Set(evidenceCells.slice(0, count).map((c) => c.index));
      cells = patchCells(cells, (c) => toLock.has(c.index), { active: true, locked: true, value: 1 });
      break;
    }

    case 'challenge': {
      // "disrupted cells visibly react" — mark validation cells as disrupted for each named
      // vulnerability. Not driven by any real #288 signal (no adversarial review exists there).
      const vulns = Math.max(0, Math.min(10, Number(payload.vulnerabilities ?? 0)));
      const validationCells = cellsWithRole(cells, 'validation');
      const toDisrupt = new Set(validationCells.slice(0, vulns).map((c) => c.index));
      cells = patchCells(cells, (c) => toDisrupt.has(c.index), { disrupted: true, active: true });
      break;
    }

    case 'repair': {
      // "affected regions reconfigure" — clear disrupted flags, keep the cells active.
      cells = patchCells(cells, (c) => c.disrupted, { disrupted: false, active: true });
      break;
    }

    case 'jury': {
      // "cube resolves toward PASS or FAIL" — a pass clears every remaining disruption; a fail
      // leaves disrupted cells as visible, unresolved state.
      const verdict = payload.passed ? 'pass' : 'fail';
      if (verdict === 'pass') {
        cells = patchCells(cells, (c) => c.disrupted, { disrupted: false });
      }
      return { ...state, stage, verdict, cells, history };
    }

    case 'proof': {
      // "verified structure stabilizes" — lock memory + outcome cells; the cube is now stable.
      cells = patchCells(cells, (c) => c.role === 'memory' || c.role === 'outcome', { active: true, locked: true, value: 1 });
      return { ...state, stage, stable: true, cells, history };
    }

    case 'think_token': {
      // "completed token state becomes visually coherent" — the tokenState cells light up and
      // lock together; this is the real, already-wired signal (server.ts's 'think_token'
      // thought, emitted only after ThinkTokenFactory + persistence actually succeeded).
      cells = patchCells(cells, (c) => c.role === 'tokenState', { active: true, locked: true, value: 1 });
      return { ...state, stage, tokenId: payload.tokenId ?? state.tokenId, cells, history };
    }

    case 'harvest': {
      // "information propagates outward" — relationship cells activate.
      cells = patchCells(cells, (c) => c.role === 'relationship', { active: true, value: 1 });
      break;
    }

    case 'commons': {
      // "reusable knowledge visibly transfers beyond the original token" — relationship cells
      // are marked shared, distinct from merely active.
      cells = patchCells(cells, (c) => c.role === 'relationship', { shared: true });
      break;
    }

    default:
      throw new Error(`Unhandled cube stage: ${stage}`);
  }

  return { ...state, stage, cells, history };
}

/**
 * Pure state -> render-props mapping. Returns 100 plain objects describing exactly what a DOM
 * renderer should show for each cell, with nothing browser-specific — this is the part the
 * cube task called "deterministic rendering/state mapping", and it's what
 * tests/think-cube-state.test.ts checks directly, with no DOM involved.
 */
export function cellsToRenderProps(state) {
  return state.cells.map((c) => ({
    index: c.index,
    face: c.face,
    role: c.role,
    className: [
      'cube-cell',
      `role-${c.role}`,
      `face-${c.face}`,
      c.active ? 'is-active' : '',
      c.locked ? 'is-locked' : '',
      c.disrupted ? 'is-disrupted' : '',
      c.shared ? 'is-shared' : '',
    ].filter(Boolean).join(' '),
    title: `${c.role} · face ${c.face}${c.locked ? ' · verified' : ''}${c.disrupted ? ' · disrupted' : ''}`,
    opacity: c.active ? Math.max(0.35, c.value) : 0.12,
  }));
}

/** Small summary for a status line: what's happening, where, what's verified, what isn't. */
export function summarize(state) {
  const activeCount = state.cells.filter((c) => c.active).length;
  const lockedCount = state.cells.filter((c) => c.locked).length;
  const disruptedCount = state.cells.filter((c) => c.disrupted).length;
  const sharedCount = state.cells.filter((c) => c.shared).length;
  return {
    stage: state.stage,
    tokenId: state.tokenId,
    verdict: state.verdict,
    stable: state.stable,
    activeCount,
    lockedCount,
    disruptedCount,
    sharedCount,
    historyLength: state.history.length,
  };
}
