// kudbEE Think Token Cube — DOM renderer and wiring.
//
// This file is deliberately thin: everything decidable without the DOM lives in
// think-cube-state.js (tested in tests/think-cube-state.test.ts). This file only (a) paints a
// CubeState into a grid of divs, and (b) listens for real events and turns them into calls to
// that module's `applyEvent`. It has no logic worth unit-testing on its own beyond what's
// already covered by the state module.
//
// LIVE MAPPING (from real WebSocket 'thought' messages — see app.js's dispatch of
// 'think-cube:thought'):
//   thought.type === 'goal'                          -> stage 'intent'   (a new run starts)
//   thought.type === 'tool_call'                      -> stage 'execution', step += 1
//   thought.type === 'tool_result', status 'success'  -> stage 'evidence', evidenceCount += 1
//   thought.type === 'tool_result', status 'error'     -> stage 'challenge' (a real tool failure,
//                                                         shown as a disruption — this is NOT the
//                                                         orchestrator's Jury/adversarial-review
//                                                         concept, which #288 does not have)
//   thought.type === 'memory' ("Saved episode...")     -> stage 'harvest'
//   thought.type === 'think_token'                     -> stage 'proof' then 'think_token'
//
// NOT LIVE: 'decompose', 'swarm', 'jury' (pass/fail) and 'commons' have no real #288 signal to
// drive them (confirmed in docs/enterprise/think-token-audit.md). `runDeterministicDemo` below
// is the only place that produces them, and it is opt-in and clearly labeled in the UI as a demo.

import { createInitialCubeState, applyEvent, cellsToRenderProps, summarize, CELL_COUNT } from './think-cube-state.js';

export class ThinkCubeRenderer {
  constructor(container) {
    this.container = container;
    this.state = createInitialCubeState();
    this.toolCallCount = 0;
    this.evidenceCount = 0;
    this.vulnerabilityCount = 0;
    this.paused = false;
    this.recordedEvents = [];
    this._buildGrid();
    this.render();
  }

  _buildGrid() {
    this.container.classList.add('think-cube');
    this.container.innerHTML = '';
    this.container.setAttribute('role', 'img');
    this.container.setAttribute('aria-label', 'Think Token cube: 100 cells representing the current token\'s lifecycle state');
    this.paused = false;
    this.cellEls = [];
    for (let i = 0; i < CELL_COUNT; i++) {
      const el = document.createElement('div');
      el.dataset.index = String(i);
      el.tabIndex = 0;
      // Inspect: click or focus+Enter shows exactly what this cell currently represents.
      el.addEventListener('click', () => this._inspect(i));
      el.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this._inspect(i); } });
      this.container.appendChild(el);
      this.cellEls.push(el);
    }
    this.statusEl = document.createElement('div');
    this.statusEl.className = 'cube-status';
    this.container.parentElement?.insertBefore(this.statusEl, this.container.nextSibling);
    this.inspectEl = document.createElement('div');
    this.inspectEl.className = 'cube-inspect';
    this.inspectEl.textContent = 'Click or focus+Enter any cell to inspect it.';
    this.statusEl.insertAdjacentElement('afterend', this.inspectEl);
  }

  _inspect(index) {
    const cell = this.state.cells[index];
    const parts = [`cell #${index}`, `role: ${cell.role}`, `face: ${cell.face}`];
    parts.push(cell.active ? 'active' : 'inactive');
    if (cell.locked) parts.push('verified/locked');
    if (cell.disrupted) parts.push('disrupted');
    if (cell.shared) parts.push('shared to commons');
    if (this.inspectEl) this.inspectEl.textContent = parts.join(' · ');
  }

  /** Repaint every cell from the current state. Pure mapping (cellsToRenderProps) -> DOM. */
  render() {
    const props = cellsToRenderProps(this.state);
    for (let i = 0; i < CELL_COUNT; i++) {
      const el = this.cellEls[i];
      const p = props[i];
      el.className = p.className;
      el.title = p.title;
      el.style.opacity = String(p.opacity);
    }
    const s = summarize(this.state);
    const bits = [`stage: ${s.stage}`];
    if (s.tokenId) bits.push(`token: ${s.tokenId}`);
    if (s.thinkBoxIds.length) bits.push(`boxes: ${s.thinkBoxIds.length} (${s.specialistIds.join(', ')})`);
    bits.push(`active ${s.activeCount}`, `verified ${s.lockedCount}`);
    if (s.disruptedCount) bits.push(`disrupted ${s.disruptedCount}`);
    if (s.sharedCount) bits.push(`shared ${s.sharedCount}`);
    if (s.verdict) bits.push(`jury: ${s.verdict}`);
    if (this.statusEl) this.statusEl.textContent = bits.join(' · ');
  }

  dispatch(stage, payload) {
    // Paused means the cube stops visibly reacting to new events, but nothing is lost: every
    // dispatch (paused or not) is still recorded, so resuming or replaying later is accurate.
    this.recordedEvents.push({ stage, payload });
    if (this.paused && stage !== 'reset') return;
    this.state = applyEvent(this.state, { stage, payload });
    this.render();
  }

  pause() { this.paused = true; }

  /** Resume: catch up on everything dispatched while paused, in the same order, deterministically. */
  resume() {
    if (!this.paused) return;
    this.paused = false;
    const pending = [...this.recordedEvents];
    this.state = createInitialCubeState();
    for (const { stage, payload } of pending) this.state = applyEvent(this.state, { stage, payload });
    this.render();
  }

  reset() {
    this.state = createInitialCubeState();
    this.toolCallCount = 0;
    this.evidenceCount = 0;
    this.vulnerabilityCount = 0;
    this.recordedEvents = [];
    this.render();
  }

  /** Deterministic replay of everything recorded so far, from a clean idle state, paced for viewing. */
  async replay(delayMs = 400) {
    const events = [...this.recordedEvents];
    this.state = createInitialCubeState();
    this.render();
    for (const { stage, payload } of events) {
      this.state = applyEvent(this.state, { stage, payload });
      this.render();
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }

  /**
   * Feed one real WebSocket thought in. See the LIVE MAPPING comment above for exactly which
   * thought types move the cube and which don't — anything not listed here is a no-op, never a
   * fabricated stage.
   */
  handleThought(thought) {
    switch (thought?.type) {
      case 'goal':
        this.toolCallCount = 0;
        this.evidenceCount = 0;
        this.vulnerabilityCount = 0;
        this.dispatch('intent', { tokenId: thought.run_id ?? null });
        break;
      case 'tool_call':
        this.toolCallCount = Math.min(10, this.toolCallCount + 1);
        this.dispatch('execution', { step: this.toolCallCount });
        break;
      case 'tool_result':
        if (thought.status === 'error') {
          this.vulnerabilityCount = Math.min(10, this.vulnerabilityCount + 1);
          this.dispatch('challenge', { vulnerabilities: this.vulnerabilityCount });
        } else {
          this.evidenceCount = Math.min(10, this.evidenceCount + 1);
          this.dispatch('evidence', { evidenceCount: this.evidenceCount });
        }
        break;
      case 'specialist_wave_started':
        this.dispatch('swarm', {
          boxIds: thought.thinkBoxIds ?? [],
          specialistIds: thought.specialistIds ?? [],
        });
        break;
      case 'specialist_validation':
        this.dispatch('jury', { passed: thought.status === 'success' });
        break;
      case 'proof_accepted':
        this.dispatch('jury', { passed: true });
        this.dispatch('proof', {});
        break;
      case 'proof_refused':
        this.dispatch('jury', { passed: false });
        break;
      case 'memory':
        if (typeof thought.content === 'string' && thought.content.startsWith('Saved episode')) {
          this.dispatch('harvest', {});
        }
        break;
      case 'think_token':
        if (!this.state.stable) this.dispatch('proof', {});
        this.dispatch('think_token', { tokenId: thought.tokenId ?? this.state.tokenId });
        break;
      default:
        break;
    }
  }

  /**
   * Demo driver for the stages #288 has no real signal for (decompose, swarm, jury, commons).
   * Explicitly opt-in and labeled — never called from real thought handling. Exists so the
   * cube's full visual range can be seen before those backend signals exist, per the "build
   * against a deterministic state model and clearly label the integration boundary" instruction.
   */
  async runDeterministicDemo() {
    const steps = [
      ['intent', { tokenId: 'demo-token' }],
      ['decompose', { opportunities: 4 }],
      ['swarm', { boxIds: ['box-a', 'box-b', 'box-c'] }],
      ['execution', { step: 6 }],
      ['evidence', { evidenceCount: 4 }],
      ['challenge', { vulnerabilities: 1 }],
      ['repair', {}],
      ['jury', { passed: true }],
      ['proof', {}],
      ['think_token', { tokenId: 'demo-token' }],
      ['harvest', {}],
      ['commons', {}],
    ];
    for (const [stage, payload] of steps) {
      this.dispatch(stage, payload);
      await new Promise((resolve) => setTimeout(resolve, 450));
    }
  }
}

// Classic scripts (think-token-dashboard.js) can't `import` an ES module; expose the class on
// `window` so they can still use it. No-op under Node (there is no `window`), so this file stays
// importable from tests/think-cube-state.test.ts-style node:test files without side effects.
if (typeof window !== 'undefined') {
  window.ThinkCubeRenderer = ThinkCubeRenderer;
}
