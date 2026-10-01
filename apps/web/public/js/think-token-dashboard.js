// kudbEE Think Token Dashboard — session view of the Think Token lifecycle.
//
// Data sources (nothing else is displayed as fact):
//  - 'think-cube:thought': every real WebSocket thought, forwarded by app.js. Drives the live cube
//    and the "Current run" panel (job id, status, last capture error).
//  - 'token:created': dispatched by app.js when the server emits a think_token thought. These are
//    IN-MEMORY, THIS-SESSION UI entries, not rows read from the database. Persisted tokens live in
//    the separate Tokens panel (ADR 028, think-tokens.db).
//  - 'token:used': nothing dispatches this today, so usage numbers appear only if it ever fires.
// No timers, no generated events. The Demo drawer runs on its own throwaway cube, never the live one.

const THINK_TOKEN_TYPE_ICONS = {
  reasoning: '🤔',
  approach: '📋',
  error_recovery: '🔧',
  tool_sequence: '⚙️',
  optimization: '⚡',
};

class ThinkTokenDashboard {
  constructor() {
    this.tokens = [];
    this.currentJobId = null;
    this.currentRunStatus = null;
    this.lastError = null;
    // The cube is created once, detached from the document, so it keeps receiving real events
    // whether or not the modal is open; openDashboard() re-parents this same node into the modal.
    // Without window.ThinkCubeRenderer (module failed to load) there is no cube and no fake one.
    this.cube = window.ThinkCubeRenderer ? new window.ThinkCubeRenderer(document.createElement('div')) : null;
    this.demoCube = null;
    this.modalEl = null;
    this.setupEventListeners();
  }

  setupEventListeners() {
    const learnBtn = document.getElementById('think-token-button');
    if (learnBtn) learnBtn.addEventListener('click', () => this.openDashboard());

    window.addEventListener('token:created', (e) => this.addToken(e.detail));
    window.addEventListener('token:used', (e) => this.recordTokenUsage(e.detail));
    window.addEventListener('think-cube:thought', (e) => this.handleThought(e.detail));
  }

  handleThought(thought) {
    if (!thought) return;
    this.cube?.handleThought(thought);
    if (thought.type === 'goal') {
      const id = thought.run_id ?? thought.job_id;
      this.currentJobId = id == null ? null : String(id);
      this.currentRunStatus = 'running';
      this.lastError = null;
    } else if (thought.type === 'think_token') {
      if (thought.status === 'error') {
        this.currentRunStatus = 'token capture failed';
        this.lastError = String(thought.content || 'Think Token capture failed');
      } else {
        this.currentRunStatus = 'completed';
      }
    } else if (thought.type === 'memory' && String(thought.content || '').startsWith('Saved episode')) {
      this.currentRunStatus = 'completed';
    }
    this.refreshRunInfo();
  }

  addToken(tokenData) {
    const data = tokenData || {};
    this.tokens.unshift({
      id: String(data.id || `token-${Date.now()}`),
      type: data.type || 'reasoning',
      content: String(data.content || ''),
      confidence: data.confidence || 0.5,
      createdAt: Date.now(),
      usageCount: 0,
      successCount: 0,
      failureCount: 0,
    });
    this.refreshOpenViews();
  }

  recordTokenUsage(usageData) {
    const token = this.tokens.find((t) => t.id === usageData?.tokenId);
    if (!token) return;
    token.usageCount++;
    if (usageData.success) token.successCount++;
    else token.failureCount++;
    token.confidence = this.calculateConfidence(token);
    this.refreshOpenViews();
  }

  calculateConfidence(token) {
    if (token.usageCount === 0) return token.confidence || 0.5;
    const successRate = token.successCount / token.usageCount;
    return Math.min(1, Math.max(0, successRate * 0.9 + (token.confidence || 0.5) * 0.1));
  }

  // ── Pure view builders (strings only; no DOM access) ────────────────────────────────────────

  tokensTabLabel() {
    return `This session (${this.tokens.length})`;
  }

  renderRunInfoHtml() {
    const rows = [
      ['Current job', this.currentJobId ? this.escapeHtml(this.currentJobId.substring(0, 12)) : 'none yet'],
      ['Status', this.escapeHtml(this.currentRunStatus || 'idle')],
      ['Think Tokens seen (this session, UI)', String(this.tokens.length)],
    ];
    let html = rows.map(([label, value]) => `
      <div class="job-info-item">
        <span class="job-info-label">${label}</span>
        <span class="job-info-value">${value}</span>
      </div>`).join('');
    if (this.lastError) {
      html += `<div class="job-info-error" role="alert">${this.escapeHtml(this.lastError)}</div>`;
    }
    return html;
  }

  renderTokenCard(token) {
    const type = this.escapeHtml(token.type);
    const used = token.usageCount > 0
      ? `<span class="token-usage">${token.usageCount} uses · ${token.successCount}✓ ${token.failureCount}✗</span>`
      : '';
    return `
      <div class="token-card" data-token-id="${this.escapeHtml(token.id)}">
        <div class="token-header">
          <span class="token-type">${this.getTypeIcon(token.type)} ${type}</span>
          <span class="token-confidence" title="Confidence reported with the token">${(token.confidence * 100).toFixed(0)}%</span>
        </div>
        <div class="token-content">${this.escapeHtml(token.content.substring(0, 100))}${token.content.length > 100 ? '…' : ''}</div>
        <div class="token-meta">
          <span class="token-age">${this.formatAge(token.createdAt)}</span>
          ${used}
        </div>
        <button type="button" class="token-expand btn-quiet" data-token-details="${this.escapeHtml(token.id)}">Details</button>
      </div>`;
  }

  renderTokensPaneHtml() {
    if (this.tokens.length === 0) {
      return `<p class="empty-state">No Think Token has been reported in this browser session yet.
        A token appears here when a run emits one. Saved, reviewable tokens are in the 🧩 Tokens panel.</p>`;
    }
    return `<p class="pane-note">In-memory entries for this session only (not read from the database). Showing the latest ${Math.min(10, this.tokens.length)}.</p>
      <div class="token-list">${this.tokens.slice(0, 10).map((t) => this.renderTokenCard(t)).join('')}</div>`;
  }

  renderAnalyticsPaneHtml() {
    if (this.tokens.length === 0) {
      return '<p class="empty-state">Nothing to summarise yet. These figures describe this session\'s tokens only.</p>';
    }
    const high = this.tokens.filter((t) => t.confidence > 0.7).length;
    const mid = this.tokens.filter((t) => t.confidence >= 0.4 && t.confidence <= 0.7).length;
    const low = this.tokens.filter((t) => t.confidence < 0.4).length;
    const dist = this.getTokenTypeDistribution();
    const max = Math.max(...dist.map((x) => x[1]));
    const used = this.tokens.some((t) => t.usageCount > 0);
    return `
      <p class="pane-note">Computed from this session's in-memory tokens, not from persisted statistics.</p>
      <div class="analytics-grid">
        <div class="analytics-card">
          <h4>Confidence</h4>
          <div class="confidence-tiers">
            <div class="tier high-confidence"><span class="tier-label">High (&gt;70%)</span><span class="tier-count">${high}</span></div>
            <div class="tier medium-confidence"><span class="tier-label">Medium (40–70%)</span><span class="tier-count">${mid}</span></div>
            <div class="tier low-confidence"><span class="tier-label">Low (&lt;40%)</span><span class="tier-count">${low}</span></div>
          </div>
        </div>
        <div class="analytics-card">
          <h4>Types</h4>
          <div class="type-bars">${dist.map(([type, count]) => `
            <div class="type-bar">
              <span class="type-name">${this.escapeHtml(type)}</span>
              <div class="bar-container"><div class="bar-fill" style="width: ${(count / max) * 100}%"></div></div>
              <span class="type-count">${count}</span>
            </div>`).join('')}</div>
        </div>
        <div class="analytics-card">
          <h4>Usage</h4>
          ${used
            ? `<div class="metric-display"><span class="metric-value">${this.calculateAverageSuccessRate()}%</span><span class="metric-label">average success where usage was reported</span></div>`
            : '<p class="empty-state">No usage events have been reported, so there is no success rate to show.</p>'}
        </div>
      </div>`;
  }

  // ── Modal lifecycle ─────────────────────────────────────────────────────────────────────────

  isOpen() {
    return Boolean(this.modalEl) && document.body.contains(this.modalEl);
  }

  closeDashboard() {
    this.modalEl?.remove();
    this.modalEl = null;
  }

  openDashboard() {
    if (this.isOpen()) {
      this.refreshOpenViews();
      return;
    }

    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.id = 'think-token-modal';
    this.modalEl = modal;

    modal.innerHTML = `
      <section class="modal modal-dashboard" role="dialog" aria-modal="true" aria-labelledby="think-token-title">
        <div class="modal-header">
          <div>
            <span class="modal-eyebrow">🎫 LEARNING SYSTEM</span>
            <h2 id="think-token-title">Think Token Dashboard</h2>
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
                <details class="cube-legend-detail">
                  <summary>What is live?</summary>
                  <div class="cube-legend-content">
                    <strong>Driven by real backend events:</strong> intent (goal), execution (tool call), evidence (tool success), challenge (tool error), harvest (episode saved), think token.
                    Specialist jobs also drive swarm, jury and proof from their own events.
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

            <div class="current-job-section">
              <h3>📍 Current run</h3>
              <div class="current-job-info" aria-live="polite"></div>
            </div>
          </div>

          <div class="dashboard-secondary">
            <div class="tabs" role="tablist">
              <button type="button" class="tab-button active" role="tab" data-tab="tokens" aria-selected="true"></button>
              <button type="button" class="tab-button" role="tab" data-tab="analytics" aria-selected="false">Analytics</button>
            </div>
            <div class="tab-content">
              <div class="tab-pane active" id="tab-tokens" role="tabpanel"></div>
              <div class="tab-pane" id="tab-analytics" role="tabpanel"></div>
            </div>
          </div>
        </div>

        <div class="modal-actions">
          <button type="button" class="btn-secondary" data-dashboard-export title="Exports this session's in-memory tokens">Export session tokens</button>
          <button type="button" class="btn-secondary" data-dashboard-close>Close</button>
        </div>
      </section>
    `;

    modal.addEventListener('click', (e) => {
      if (e.target === modal) return this.closeDashboard();
      const target = e.target;
      if (target.closest?.('[data-dashboard-close]')) return this.closeDashboard();
      if (target.closest?.('[data-dashboard-export]')) return this.exportLearnings();
      const details = target.closest?.('[data-token-details]');
      if (details) return this.showTokenDetails(details.dataset.tokenDetails);
      const tab = target.closest?.('[data-tab]');
      if (tab) return this.switchTab(tab.dataset.tab, modal);
      const action = target.closest?.('[data-cube-action]');
      if (action) this.runCubeAction(action.dataset.cubeAction, modal);
    });

    document.body.appendChild(modal);

    if (this.cube) {
      const slot = modal.querySelector('.think-cube-slot');
      slot.appendChild(this.cube.container);
      modal.querySelector('.think-cube-wrap').insertAdjacentElement('afterend', this.cube.statusEl);
      this.cube.statusEl.insertAdjacentElement('afterend', this.cube.inspectEl);
      this.cube.render();
    }

    this.refreshOpenViews();
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
    if (!this.demoCube) {
      this.demoCube = new window.ThinkCubeRenderer(slot);
    } else {
      this.demoCube.reset();
    }
    this.demoCube.runDeterministicDemo();
  }

  switchTab(tabName, modal) {
    modal.querySelectorAll('.tab-button').forEach((btn) => {
      const active = btn.dataset.tab === tabName;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-selected', String(active));
    });
    modal.querySelectorAll('.tab-pane').forEach((pane) => {
      pane.classList.toggle('active', pane.id === `tab-${tabName}`);
    });
  }

  // ── In-place updates (never rebuild the modal, so tab, scroll, focus and the cube survive) ──

  refreshRunInfo() {
    if (!this.isOpen()) return;
    const el = this.modalEl.querySelector('.current-job-info');
    if (el) el.innerHTML = this.renderRunInfoHtml();
  }

  refreshOpenViews() {
    if (!this.isOpen()) return;
    const modal = this.modalEl;
    const scroller = modal.querySelector('.tab-content');
    const scrollTop = scroller ? scroller.scrollTop : 0;
    const focusedId = document.activeElement?.dataset?.tokenDetails;

    const tabBtn = modal.querySelector('[data-tab="tokens"]');
    if (tabBtn) tabBtn.textContent = this.tokensTabLabel();
    const tokensPane = modal.querySelector('#tab-tokens');
    if (tokensPane) tokensPane.innerHTML = this.renderTokensPaneHtml();
    const analyticsPane = modal.querySelector('#tab-analytics');
    if (analyticsPane) analyticsPane.innerHTML = this.renderAnalyticsPaneHtml();
    this.refreshRunInfo();

    if (scroller) scroller.scrollTop = scrollTop;
    if (focusedId !== undefined) {
      const again = [...modal.querySelectorAll('[data-token-details]')].find((b) => b.dataset.tokenDetails === focusedId);
      again?.focus();
    }
  }

  showTokenDetails(tokenId) {
    const token = this.tokens.find((t) => t.id === tokenId);
    if (!token) return;

    const detailModal = document.createElement('div');
    detailModal.className = 'modal-backdrop';
    detailModal.innerHTML = `
      <section class="modal modal-token-details" role="dialog" aria-modal="true">
        <div class="modal-header">
          <h2>${this.getTypeIcon(token.type)} ${this.escapeHtml(token.type.toUpperCase())}</h2>
          <button type="button" class="btn-icon" aria-label="Close" data-detail-close>×</button>
        </div>
        <div class="token-details-content">
          <div class="detail-section">
            <h4>Content</h4>
            <pre><code>${this.escapeHtml(token.content)}</code></pre>
          </div>
          <div class="detail-section">
            <h4>This session (UI)</h4>
            <ul>
              <li>Id: ${this.escapeHtml(token.id)}</li>
              <li>Seen: ${new Date(token.createdAt).toLocaleString()}</li>
              <li>Confidence: ${(token.confidence * 100).toFixed(1)}%</li>
              <li>Usage events: ${token.usageCount > 0 ? `${token.usageCount} (${token.successCount} ok, ${token.failureCount} failed)` : 'none reported'}</li>
            </ul>
          </div>
        </div>
        <div class="modal-actions">
          <button type="button" class="btn-secondary" data-detail-close>Close</button>
        </div>
      </section>
    `;
    detailModal.addEventListener('click', (e) => {
      if (e.target === detailModal || e.target.closest?.('[data-detail-close]')) detailModal.remove();
    });
    document.body.appendChild(detailModal);
  }

  getTokenTypeDistribution() {
    const dist = {};
    this.tokens.forEach((t) => { dist[t.type] = (dist[t.type] || 0) + 1; });
    return Object.entries(dist).sort((a, b) => b[1] - a[1]);
  }

  getTypeIcon(type) {
    return THINK_TOKEN_TYPE_ICONS[type] || '🎫';
  }

  calculateAverageSuccessRate() {
    const rates = this.tokens.filter((t) => t.usageCount > 0).map((t) => (t.successCount / t.usageCount) * 100);
    return rates.length > 0 ? Math.round(rates.reduce((a, b) => a + b) / rates.length) : 0;
  }

  calculateKnowledgeReuse() {
    const totalPotential = this.tokens.length * 100;
    const actualReuse = this.tokens.reduce((sum, t) => sum + t.usageCount, 0);
    return totalPotential > 0 ? Math.round((actualReuse / totalPotential) * 100) : 0;
  }

  formatAge(timestamp) {
    const minutes = Math.floor((Date.now() - timestamp) / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'just now';
  }

  // String-based so it is safe in text and quoted attributes and needs no DOM.
  escapeHtml(text) {
    return String(text ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  exportLearnings() {
    const data = {
      exportedAt: new Date().toISOString(),
      scope: 'in-memory tokens seen in this browser session; not read from the database',
      tokenCount: this.tokens.length,
      tokens: this.tokens,
      analysis: {
        avgSuccessRate: this.calculateAverageSuccessRate(),
        knowledgeReuse: this.calculateKnowledgeReuse(),
      },
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `think-tokens-session-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    window.thinkTokenDashboard = new ThinkTokenDashboard();
  });
}
