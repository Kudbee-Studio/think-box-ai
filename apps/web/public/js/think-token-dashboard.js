// kudbEE Think Tokens — ONE view inside the Agent OS dashboard (ADR 029 P1 + P2): live cube, Energy Core, current run,
// and the saved tokens. It replaces the old "🎫 Learning" (in-memory) and "🧩 Tokens" (persisted) panels.
//
// Where every number comes from (nothing else is shown as fact):
//  - Saved tokens, counts, ledger status: the `think_tokens` WebSocket message, read from SQLite (think-tokens.db) by the
//    server's shared reader. The same reader feeds `kudbee tokens list|show`, so the CLI and this view agree.
//  - Live cube: every real WebSocket 'thought', forwarded by app.js as 'think-cube:thought'.
//  - Cube pulses: the server's `think_token_learned` / `think_token_used` events, which exist only for a stored token.
//  - Energy Core: events per minute (real thoughts in the last 60 s), runs currently running (real run_update status),
//    tokens learned/used during THIS browser session (real events), time since the last accepted proof (real thought).
//    It reads zero when nothing is happening. The 1 s timer that runs while the view is open only repaints; it never
//    creates or dispatches an event.
// Token text is rendered with textContent only; it never reaches innerHTML.

const TT_ENERGY_WINDOW_MS = 60_000;
const TT_IDLE_AFTER_MS = 30_000;
const TT_MAX_EVENTS = 2000;
const TT_ID_LIKE = /^(?:tt-?)?\d{1,9}$/i;
const TT_STATUS_ORDER = ['candidate', 'extracted', 'scored', 'challenged', 'accepted', 'rejected', 'retired'];
const TT_FINISHED_RUN_STATES = new Set(['completed', 'failed', 'stopped']);

function ttEl(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function ttIsToken(t) {
  return Boolean(t) && typeof t === 'object' && typeof t.id === 'string' && typeof t.title === 'string' && typeof t.content === 'string'
    && typeof t.status === 'string' && typeof t.score === 'number' && Array.isArray(t.tags) && typeof t.source_run_id === 'string';
}

/** A think_token_learned / think_token_used payload is trusted only if it is well formed and within the server's limits. */
function validTokenEvent(d) {
  return Boolean(d) && typeof d === 'object'
    && typeof d.token_id === 'string' && /^(?:TT-\d{1,9}|tt_[a-f0-9]{16})$/.test(d.token_id)
    && typeof d.run_id === 'string' && d.run_id.length <= 80
    && typeof d.score === 'number' && d.score >= 0 && d.score <= 1
    && typeof d.delta === 'number' && Math.abs(d.delta) <= 1
    && typeof d.status === 'string' && TT_STATUS_ORDER.includes(d.status)
    && typeof d.title === 'string' && d.title.length <= 120
    && typeof d.kind === 'string' && d.kind.length <= 20
    && Number.isInteger(d.uses) && d.uses >= 0;
}

class ThinkTokenDashboard {
  constructor() {
    this.tokens = [];
    this.ledger = null;
    this.loaded = false;
    this.listError = null;
    this.filters = { query: '', status: '' };
    this.actionMessage = null;
    this.currentJobId = null;
    this.currentRunStatus = null;
    this.lastError = null;
    this.lastLearned = null;
    this.ignoredEvents = 0;
    this.energy = { events: [], runs: new Map(), learned: 0, used: 0, lastProofAt: null, lastEventAt: null };
    // The cube is created once, detached from the document, so it keeps receiving real events whether or not the view is
    // open; opening re-parents this same node. Without window.ThinkCubeRenderer there is no cube and no fake one.
    this.cube = window.ThinkCubeRenderer ? new window.ThinkCubeRenderer(document.createElement('div')) : null;
    this.demoCube = null;
    this.modalEl = null;
    this.repaintTimer = null;
    this.searchTimer = null;
    this.setupEventListeners();
  }

  setupEventListeners() {
    const button = document.getElementById('think-token-button');
    if (button) button.addEventListener('click', () => this.openDashboard());
    window.addEventListener('think-cube:thought', (e) => this.handleThought(e.detail));
    window.addEventListener('think-cube:run', (e) => this.handleRun(e.detail));
    window.addEventListener('think-tokens:message', (e) => this.handleTokenMessage(e.detail));
  }

  // ── Real events in ───────────────────────────────────────────────────────────────────────────

  handleThought(thought) {
    if (!thought) return;
    this.cube?.handleThought(thought);
    const now = Date.now();
    this.energy.events.push(now);
    if (this.energy.events.length > TT_MAX_EVENTS) this.energy.events.splice(0, this.energy.events.length - TT_MAX_EVENTS);
    this.energy.lastEventAt = now;
    if (thought.type === 'proof_accepted') this.energy.lastProofAt = now;
    if (thought.type === 'goal') {
      const id = thought.run_id ?? thought.job_id;
      this.currentJobId = id == null ? null : String(id);
      this.currentRunStatus = 'running';
      this.lastError = null;
    } else if (thought.type === 'think_token') {
      if (thought.status === 'error') {
        this.currentRunStatus = 'token capture failed';
        this.lastError = String(thought.content || 'Think Token capture failed');
      } else if (this.currentRunStatus === 'running') {
        this.currentRunStatus = 'completed';
      }
    } else if (thought.type === 'memory' && String(thought.content || '').startsWith('Saved episode')) {
      this.currentRunStatus = 'completed';
    }
    this.refreshRunInfo();
    this.renderEnergy();
  }

  handleRun(run) {
    if (!run || typeof run.id !== 'string' || typeof run.status !== 'string') return;
    if (TT_FINISHED_RUN_STATES.has(run.status)) this.energy.runs.delete(run.id);
    else this.energy.runs.set(run.id, run.status);
    this.energy.lastEventAt = Date.now();
    this.renderEnergy();
  }

  handleTokenMessage(msg) {
    if (!msg || typeof msg.type !== 'string') return;
    switch (msg.type) {
      case 'think_tokens': {
        const data = msg.data || {};
        if (!Array.isArray(data.tokens)) return;
        this.tokens = data.tokens.filter(ttIsToken);
        this.ledger = data.ledger || null;
        this.loaded = true;
        this.listError = null;
        this.renderList();
        this.refreshRunInfo();
        return;
      }
      case 'think_tokens_changed':
        this.requestList();
        return;
      case 'think_token_learned': {
        if (!validTokenEvent(msg.data)) { this.ignoredEvents += 1; return; }
        this.energy.learned += 1;
        this.energy.lastEventAt = Date.now();
        this.lastLearned = { ...msg.data };
        this.cube?.pulse?.('learned', msg.data.score);
        this.renderLastToken();
        this.renderEnergy();
        this.requestList();
        return;
      }
      case 'think_token_used': {
        if (!validTokenEvent(msg.data)) { this.ignoredEvents += 1; return; }
        this.energy.used += 1;
        this.energy.lastEventAt = Date.now();
        if (this.lastLearned && this.lastLearned.token_id === msg.data.token_id) this.lastLearned = { ...this.lastLearned, uses: msg.data.uses, score: msg.data.score };
        this.cube?.pulse?.('used', msg.data.score);
        this.renderLastToken();
        this.renderEnergy();
        this.requestList();
        return;
      }
      case 'think_token_result': {
        const d = msg.data || {};
        this.actionMessage = d.ok ? `Applied ${d.action} to ${d.id}${d.receipt ? ` (receipt ${d.receipt.receipt_id})` : ''}` : `Not applied: ${d.error || 'unknown error'}`;
        this.renderMeta();
        this.requestList();
        return;
      }
      case 'think_token_error':
        this.actionMessage = `Rejected: ${(msg.data && msg.data.error) || 'invalid request'}`;
        this.renderMeta();
        return;
      default:
    }
  }

  requestList() {
    if (!this.isOpen()) return false;
    const message = { type: 'think_tokens_list', limit: 50 };
    const query = this.filters.query.trim().slice(0, 100);
    if (query) message.query = query;
    if (this.filters.status) message.status = this.filters.status;
    const sent = typeof window.sendThinkTokenMessage === 'function' ? window.sendThinkTokenMessage(message) : false;
    if (!sent) {
      this.listError = 'Not connected to the Agent OS backend, so saved tokens cannot be loaded.';
      this.renderList();
    }
    return sent;
  }

  sendAction(action, id) {
    const sent = typeof window.sendThinkTokenMessage === 'function' ? window.sendThinkTokenMessage({ type: 'think_token_action', action, id }) : false;
    this.actionMessage = sent ? 'Waiting for your approval…' : 'Not connected to the Agent OS backend.';
    this.renderMeta();
    return sent;
  }

  // ── Derived numbers (pure) ───────────────────────────────────────────────────────────────────

  energySnapshot(now = Date.now()) {
    const recent = this.energy.events.filter((t) => now - t <= TT_ENERGY_WINDOW_MS);
    const activeRuns = this.energy.runs.size;
    const active = activeRuns > 0 || (this.energy.lastEventAt !== null && now - this.energy.lastEventAt <= TT_IDLE_AFTER_MS);
    return {
      eventsPerMinute: recent.length,
      activeRuns,
      learned: this.energy.learned,
      used: this.energy.used,
      lastProofAgoMs: this.energy.lastProofAt === null ? null : now - this.energy.lastProofAt,
      state: active ? 'active' : 'idle',
      intensity: Math.min(1, recent.length / 60),
    };
  }

  formatAge(ms) {
    const s = Math.floor(ms / 1000);
    if (s < 60) return `${s}s ago`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    return h < 24 ? `${h}h ago` : `${Math.floor(h / 24)}d ago`;
  }

  statusCounts() {
    const counts = {};
    for (const t of this.tokens) counts[t.status] = (counts[t.status] || 0) + 1;
    return counts;
  }

  // ── Modal lifecycle ──────────────────────────────────────────────────────────────────────────

  isOpen() {
    return Boolean(this.modalEl) && document.body.contains(this.modalEl);
  }

  closeDashboard() {
    if (this.repaintTimer !== null) { clearInterval(this.repaintTimer); this.repaintTimer = null; }
    clearTimeout(this.searchTimer);
    this.modalEl?.remove();
    this.modalEl = null;
  }

  openDashboard() {
    if (this.isOpen()) { this.requestList(); return; }
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.id = 'think-token-modal';
    this.modalEl = modal;

    // Static markup only: no token or run data is ever interpolated here.
    modal.innerHTML = `
      <section class="modal modal-dashboard" role="dialog" aria-modal="true" aria-labelledby="think-token-title">
        <div class="modal-header">
          <div>
            <span class="modal-eyebrow">🧩 LEARNING UNITS · ADR 029</span>
            <h2 id="think-token-title">Think Tokens</h2>
          </div>
          <button type="button" class="btn-icon" aria-label="Close" data-dashboard-close>×</button>
        </div>

        <div class="dashboard-layout">
          <div class="dashboard-primary">
            <div class="cube-section">
              <h3>🧊 Live cube</h3>
              ${this.cube ? `
                <div class="think-cube-wrap"><div class="think-cube-slot"></div></div>
                <div class="cube-controls">
                  <button type="button" class="btn-quiet" data-cube-action="pause" title="Stop repainting; events are still recorded">⏸ Pause</button>
                  <button type="button" class="btn-quiet" data-cube-action="resume" title="Catch up on events recorded while paused">▶ Resume</button>
                  <button type="button" class="btn-quiet" data-cube-action="reset" title="Clear the cube and its recorded events">↻ Reset</button>
                  <button type="button" class="btn-quiet" data-cube-action="replay" title="Replay the real events recorded so far">↺ Replay</button>
                </div>
                <div class="last-token" aria-live="polite"></div>
                <details class="cube-legend-detail">
                  <summary>What is live?</summary>
                  <div class="cube-legend-content">
                    <strong>Driven by real backend events:</strong> intent (goal), execution (tool call), evidence (tool success), challenge (tool error), harvest (episode saved), think token.
                    Specialist jobs also drive swarm, jury and proof from their own events.
                    A learned token pulses the token-state cells (glow = its score); a token used by a run pulses the relationship cells.
                    <br><strong>Never driven by the backend yet:</strong> decompose, repair, commons. They appear only in the simulated demo below.
                  </div>
                </details>
                <details class="demo-drawer">
                  <summary>Demo (simulated, not live)</summary>
                  <p class="demo-note">Runs a scripted lifecycle on a separate cube. It does not touch the live cube or its recorded events.</p>
                  <button type="button" class="btn-quiet" data-cube-action="demo">Run simulated lifecycle</button>
                  <div class="demo-cube-wrap"><div class="demo-cube-slot"></div></div>
                </details>
              ` : '<p class="cube-legend">Cube unavailable: its module script did not load.</p>'}
            </div>

            <div class="energy-core" data-state="idle">
              <h3>⚡ Energy Core</h3>
              <div class="energy-body">
                <div class="energy-ring" aria-hidden="true"></div>
                <dl class="energy-stats"></dl>
              </div>
              <p class="pane-note">Real signals from this browser session only: nothing here is simulated or persisted.</p>
            </div>

            <div class="current-job-section">
              <h3>📍 Current run</h3>
              <div class="current-job-info" aria-live="polite"></div>
            </div>
          </div>

          <div class="dashboard-secondary">
            <div class="tt-toolbar">
              <input id="tt-search" type="search" maxlength="100" placeholder="Search, or jump to TT-42" aria-label="Search Think Tokens or jump to an id">
              <select id="tt-status" aria-label="Filter by status">
                <option value="">All statuses</option>
                <option value="candidate">Candidate</option>
                <option value="extracted">Extracted</option>
                <option value="scored">Scored</option>
                <option value="challenged">Challenged</option>
                <option value="accepted">Accepted</option>
                <option value="rejected">Rejected</option>
                <option value="retired">Retired</option>
              </select>
              <button type="button" class="btn-secondary tt-btn" data-tt-refresh title="Reload from the database">↻</button>
            </div>
            <div class="tt-meta-line memory-meta" aria-live="polite"></div>
            <div class="tt-list" aria-live="polite"></div>
          </div>
        </div>

        <div class="modal-actions">
          <button type="button" class="btn-secondary" data-dashboard-export title="Exports the saved tokens currently shown">Export shown tokens</button>
          <button type="button" class="btn-secondary" data-dashboard-close>Close</button>
        </div>
      </section>
    `;

    modal.addEventListener('click', (e) => {
      if (e.target === modal) return this.closeDashboard();
      const target = e.target;
      if (target.closest?.('[data-dashboard-close]')) return this.closeDashboard();
      if (target.closest?.('[data-dashboard-export]')) return this.exportTokens();
      if (target.closest?.('[data-tt-refresh]')) return void this.requestList();
      const action = target.closest?.('[data-tt-action]');
      if (action) return void this.sendAction(action.dataset.ttAction, action.dataset.tokenId);
      const cube = target.closest?.('[data-cube-action]');
      if (cube) this.runCubeAction(cube.dataset.cubeAction, modal);
    });
    const search = modal.querySelector('#tt-search');
    search?.addEventListener('input', () => {
      this.filters.query = search.value || '';
      clearTimeout(this.searchTimer);
      this.searchTimer = setTimeout(() => this.requestList(), 250);
    });
    const status = modal.querySelector('#tt-status');
    status?.addEventListener('change', () => {
      this.filters.status = status.value || '';
      this.requestList();
    });

    document.body.appendChild(modal);

    if (this.cube) {
      const slot = modal.querySelector('.think-cube-slot');
      slot.appendChild(this.cube.container);
      modal.querySelector('.think-cube-wrap').insertAdjacentElement('afterend', this.cube.statusEl);
      this.cube.statusEl.insertAdjacentElement('afterend', this.cube.inspectEl);
      this.cube.render();
    }

    this.renderAll();
    this.requestList();
    // Repaint only (relative times and the sliding events/minute window). Never dispatches or invents an event.
    this.repaintTimer = setInterval(() => { this.renderEnergy(); this.refreshRunInfo(); }, 1000);
  }

  runCubeAction(name, modal) {
    if (!this.cube) return;
    if (name === 'pause') this.cube.pause();
    else if (name === 'resume') this.cube.resume();
    else if (name === 'reset') this.cube.reset();
    else if (name === 'replay') this.cube.replay();
    else if (name === 'demo') this.runDemo(modal);
  }

  runDemo(modal) {
    const slot = modal.querySelector('.demo-cube-slot');
    if (!slot || !window.ThinkCubeRenderer) return;
    if (!this.demoCube) this.demoCube = new window.ThinkCubeRenderer(slot);
    else this.demoCube.reset();
    this.demoCube.runDeterministicDemo();
  }

  // ── Rendering (DOM nodes + textContent; the only innerHTML above is the static skeleton) ──────

  renderAll() {
    this.renderList();
    this.renderEnergy();
    this.renderLastToken();
    this.refreshRunInfo();
  }

  renderMeta() {
    if (!this.isOpen()) return;
    const line = this.modalEl.querySelector('.tt-meta-line');
    if (!line) return;
    const parts = [];
    if (this.loaded) {
      const counts = this.statusCounts();
      const tally = TT_STATUS_ORDER.filter((s) => counts[s]).map((s) => `${counts[s]} ${s}`).join(', ');
      parts.push(`${this.tokens.length} shown from SQLite${tally ? ` (${tally})` : ''}`);
      if (this.ledger) parts.push(`write ledger ${this.ledger.ok ? 'verified' : 'BROKEN'} (${this.ledger.entries ?? 0} entries)`);
    }
    if (this.actionMessage) parts.push(this.actionMessage);
    line.textContent = parts.join(' · ');
  }

  renderList() {
    if (!this.isOpen()) return;
    const list = this.modalEl.querySelector('.tt-list');
    if (!list) return;
    const scroll = list.scrollTop;
    list.replaceChildren();
    if (this.listError) {
      const err = ttEl('div', 'empty-state tt-error', this.listError);
      err.setAttribute('role', 'alert');
      list.append(err);
    } else if (!this.loaded) {
      list.append(ttEl('div', 'empty-state', 'Loading saved tokens…'));
    } else if (!this.tokens.length) {
      const filtered = this.filters.query.trim() || this.filters.status;
      list.append(ttEl('div', 'empty-state', filtered
        ? 'No saved token matches this search or filter.'
        : 'No Think Tokens saved yet. A successful run saves its lessons here; Mercury 2 (or the local model) writes them from the run record.'));
    } else {
      const jumpTo = TT_ID_LIKE.test(this.filters.query.trim()) ? this.filters.query.trim().replace(/\D/g, '').replace(/^0+/, '') : null;
      for (const token of this.tokens) {
        const card = this.renderTokenCard(token);
        if (jumpTo !== null && String(token.id).replace(/\D/g, '').replace(/^0+/, '') === jumpTo) card.classList.add('is-jump');
        list.append(card);
      }
    }
    list.scrollTop = scroll;
    this.renderMeta();
  }

  renderTokenCard(token) {
    const card = ttEl('article', `tt-card tt-${token.status}`);
    card.dataset.tokenId = token.id;
    const head = ttEl('div', 'tt-head');
    head.append(ttEl('code', 'tt-id', token.id), ttEl('span', 'tt-kind', String(token.kind).replace('_', ' ')), ttEl('strong', 'tt-title', token.title), ttEl('span', `tt-status ${token.status}`, token.status));
    const score = ttEl('span', 'tt-score', `score ${token.score.toFixed(3)}`);
    if (token.score_breakdown) score.title = token.score_breakdown.formula;
    head.append(score);
    card.append(head, ttEl('p', 'tt-content', token.content));

    const b = token.score_breakdown;
    if (b && b.components && b.weights && b.weighted && b.inputs) {
      const details = ttEl('details', 'tt-breakdown');
      details.append(ttEl('summary', '', 'Score breakdown'));
      const rows = [
        ['usefulness', `success ${b.inputs.success_runs}, failed ${b.inputs.failed_runs}`],
        ['recency', `age ${b.inputs.age_days} days, half-life ${b.inputs.half_life_days}`],
        ['reuse', `uses ${b.inputs.uses}`],
        ['feedback', `up ${b.inputs.thumbs_up}, down ${b.inputs.thumbs_down}`],
      ];
      for (const [name, why] of rows) details.append(ttEl('div', 'tt-breakdown-row', `${name}: ${b.components[name]} × ${b.weights[name]} = ${b.weighted[name]}  (${why})`));
      details.append(ttEl('div', 'tt-breakdown-row', `total ${b.score} = ${b.formula}`));
      card.append(details);
    }

    const meta = ttEl('div', 'tt-meta');
    const run = ttEl('code', '', `run ${String(token.source_run_id).slice(0, 8)}`);
    run.title = token.source_run_id;
    meta.append(run, ttEl('span', '', token.extractor === 'template' ? 'extractor: template (not model-written)' : `extractor: ${token.extractor}${token.extract_model ? ` (${token.extract_model})` : ''}`));
    const ch = token.challenge;
    meta.append(ttEl('span', '', ch && ch.verdict ? `challenge: ${ch.verdict} by ${ch.model || 'unknown'}${ch.reason ? ` — ${ch.reason}` : ''}` : 'challenge: none yet'));
    meta.append(ttEl('span', '', `uses ${token.uses}`), ttEl('span', '', `👍 ${token.thumbs_up} 👎 ${token.thumbs_down}`));
    if (token.receipt) meta.append(ttEl('code', '', `receipt ${token.receipt.receipt_id}`));
    if (token.legacy_id) meta.append(ttEl('span', '', `was ${token.legacy_id}`));
    if (token.tags.length) meta.append(ttEl('span', 'tt-tags', token.tags.join(' · ')));
    card.append(meta);

    const used = ttEl('div', 'tt-used');
    if (token.used_by && token.used_by.length) {
      used.append(ttEl('span', '', 'Used by runs: '));
      for (const use of token.used_by) used.append(ttEl('code', '', `${String(use.run_id).slice(0, 8)}${use.success === 1 ? ' ✓' : use.success === 0 ? ' ✗' : ''}`));
    } else {
      used.textContent = 'Not used by any run yet';
    }
    card.append(used);

    const actions = ttEl('div', 'tt-actions');
    const add = (label, action, title) => {
      const button = ttEl('button', 'btn-secondary tt-btn', label);
      button.type = 'button';
      button.title = title;
      button.dataset.ttAction = action;
      button.dataset.tokenId = token.id;
      actions.append(button);
    };
    if (token.status !== 'accepted' && token.status !== 'retired') add('Accept', 'accept', 'Make this token eligible for planner context (asks for approval)');
    if (token.status !== 'retired') add('Retire', 'retire', 'Stop using this token (asks for approval)');
    add('👍', 'thumb_up', 'Helpful');
    add('👎', 'thumb_down', 'Not helpful');
    card.append(actions);
    return card;
  }

  renderLastToken() {
    if (!this.isOpen()) return;
    const box = this.modalEl.querySelector('.last-token');
    if (!box) return;
    box.replaceChildren();
    const t = this.lastLearned;
    if (!t) {
      box.append(ttEl('span', 'pane-note', 'No token learned in this session yet. The cube pulses when the server saves one.'));
      return;
    }
    box.append(ttEl('code', 'tt-id', t.token_id), ttEl('strong', '', t.title), ttEl('span', 'tt-score', `score ${t.score.toFixed(3)}`), ttEl('code', '', `run ${t.run_id.slice(0, 8)}`), ttEl('span', '', `used ${t.uses}×`));
  }

  renderEnergy() {
    if (!this.isOpen()) return;
    const core = this.modalEl.querySelector('.energy-core');
    const stats = this.modalEl.querySelector('.energy-stats');
    if (!core || !stats) return;
    const s = this.energySnapshot();
    core.dataset.state = s.state;
    core.style.setProperty('--energy', String(s.intensity));
    stats.replaceChildren();
    const row = (label, value) => { stats.append(ttEl('dt', '', label), ttEl('dd', '', value)); };
    row('state', s.state);
    row('events / min', String(s.eventsPerMinute));
    row('runs running', String(s.activeRuns));
    row('learned (session)', String(s.learned));
    row('used (session)', String(s.used));
    row('last proof', s.lastProofAgoMs === null ? 'none yet' : this.formatAge(s.lastProofAgoMs));
  }

  renderRunInfoNodes() {
    const info = ttEl('div', '');
    const rows = [
      ['Current job', this.currentJobId ? this.currentJobId.slice(0, 12) : 'none yet'],
      ['Status', this.currentRunStatus || 'idle'],
      ['Tokens saved (persisted, shown)', this.loaded ? String(this.tokens.length) : 'loading…'],
    ];
    for (const [label, value] of rows) {
      const item = ttEl('div', 'job-info-item');
      item.append(ttEl('span', 'job-info-label', label), ttEl('span', 'job-info-value', value));
      info.append(item);
    }
    if (this.lastError) {
      const err = ttEl('div', 'job-info-error', this.lastError);
      err.setAttribute('role', 'alert');
      info.append(err);
    }
    return info;
  }

  refreshRunInfo() {
    if (!this.isOpen()) return;
    const box = this.modalEl.querySelector('.current-job-info');
    if (box) box.replaceChildren(...this.renderRunInfoNodes().children);
  }

  exportTokens() {
    const data = {
      exportedAt: new Date().toISOString(),
      scope: 'saved Think Tokens currently shown, read from SQLite (think-tokens.db) via the server; not session-only data',
      filters: { ...this.filters },
      tokenCount: this.tokens.length,
      tokens: this.tokens,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `think-tokens-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    window.thinkTokenDashboard = new ThinkTokenDashboard();
  });
}
