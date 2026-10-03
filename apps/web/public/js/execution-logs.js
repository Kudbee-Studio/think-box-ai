// kudbEE Execution Logs — Complete audit trail with filtering and search

class ExecutionLogs {
  constructor() {
    this.logs = readStoredJson('kudbee-exec-logs', []);
    this.filters = { level: 'all', service: 'all', status: 'all', search: '' };
    this.setupEventListeners();
  }

  setupEventListeners() {
    // Instances are created on DOMContentLoaded, so wire the header button now (a nested
    // DOMContentLoaded listener would never fire and the button would do nothing).
    const logsBtn = document.getElementById('execution-logs-button');
    if (logsBtn) {
      logsBtn.addEventListener('click', () => this.openLogs());
    }

    window.addEventListener('agent:action', (e) => this.recordAction(e.detail));
    window.addEventListener('tool:executed', (e) => this.recordToolExecution(e.detail));
    window.addEventListener('error:occurred', (e) => this.recordError(e.detail));
  }

  recordAction(action) {
    const log = {
      id: `log-${Date.now()}`,
      timestamp: new Date().toISOString(),
      level: 'INFO',
      service: 'agent',
      status: 'success',
      action: action.name,
      message: action.description,
      metadata: action.metadata || {},
      duration: action.duration || 0
    };
    this.logs.unshift(log);
    this.trimLogs();
    this.saveLogs();
  }

  recordToolExecution(tool) {
    const log = {
      id: `log-${Date.now()}`,
      timestamp: new Date().toISOString(),
      level: 'DEBUG',
      service: 'tools',
      status: tool.success ? 'success' : 'failed',
      action: `${tool.name}`,
      message: tool.result || tool.error,
      metadata: { input: tool.input, output: tool.output },
      duration: tool.duration || 0
    };
    this.logs.unshift(log);
    this.trimLogs();
    this.saveLogs();
  }

  recordError(error) {
    const log = {
      id: `log-${Date.now()}`,
      timestamp: new Date().toISOString(),
      level: 'ERROR',
      service: error.service || 'unknown',
      status: 'error',
      action: error.action || 'unknown',
      message: error.message,
      metadata: { stack: error.stack, code: error.code },
      duration: 0
    };
    this.logs.unshift(log);
    this.trimLogs();
    this.saveLogs();
  }

  openLogs() {
    const filtered = this.getFilteredLogs();
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.id = 'logs-modal';
    modal.innerHTML = `
      <section class="modal modal-wide" role="dialog" aria-modal="true">
        <div class="modal-header">
          <div>
            <span class="modal-eyebrow">OPERATIONS</span>
            <h2>Execution Logs</h2>
          </div>
          <button class="btn-icon" data-action="close">×</button>
        </div>

        <div class="logs-controls">
          <div class="logs-search">
            <input id="logs-search-input" type="text" class="search-input" placeholder="Search logs..."
              data-search="1">
          </div>

          <div class="logs-filters">
            <select data-filter="level">
              <option value="all">All levels</option>
              <option value="DEBUG">Debug</option>
              <option value="INFO">Info</option>
              <option value="WARN">Warning</option>
              <option value="ERROR">Error</option>
            </select>

            <select data-filter="service">
              <option value="all">All services</option>
              <option value="agent">Agent</option>
              <option value="tools">Tools</option>
              <option value="memory">Memory</option>
              <option value="server">Server</option>
            </select>

            <select data-filter="status">
              <option value="all">All status</option>
              <option value="success">Success</option>
              <option value="failed">Failed</option>
              <option value="error">Error</option>
            </select>

            <button class="btn-secondary" data-action="clear">Clear Logs</button>
            <button class="btn-secondary" data-action="export">Export</button>
          </div>
        </div>

        <div class="logs-container">
          <div class="logs-list">
            <div class="logs-header">
              <span class="col-time">Time</span>
              <span class="col-level">Level</span>
              <span class="col-service">Service</span>
              <span class="col-message">Message</span>
              <span class="col-duration">Duration</span>
              <span class="col-actions">Actions</span>
            </div>

            ${filtered.map(log => `
              <div class="log-entry level-${escapeHtml(String(log.level).toLowerCase())} status-${escapeHtml(log.status)}">
                <span class="col-time">${new Date(log.timestamp).toLocaleTimeString()}</span>
                <span class="col-level">
                  <badge class="badge-${escapeHtml(String(log.level).toLowerCase())}">${escapeHtml(log.level)}</badge>
                </span>
                <span class="col-service">${escapeHtml(log.service)}</span>
                <span class="col-message">
                  <strong>${escapeHtml(log.action)}</strong>: ${escapeHtml(log.message)}
                </span>
                <span class="col-duration">${Number(log.duration) || 0}ms</span>
                <span class="col-actions">
                  <button class="btn-icon" data-action="details" data-log-id="${escapeHtml(log.id)}">📋</button>
                </span>
              </div>
            `).join('')}

            ${filtered.length === 0 ? '<div class="logs-empty">No logs match your filters</div>' : ''}
          </div>
        </div>

        <div class="logs-stats">
          <div class="stat">
            <span class="stat-label">Total Logs:</span>
            <span class="stat-value">${this.logs.length}</span>
          </div>
          <div class="stat">
            <span class="stat-label">Errors:</span>
            <span class="stat-value error">${this.logs.filter(l => l.level === 'ERROR').length}</span>
          </div>
          <div class="stat">
            <span class="stat-label">Success Rate:</span>
            <span class="stat-value">${this.getSuccessRate()}%</span>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" data-action="close">Close</button>
        </div>
      </section>
    `;

    modal.addEventListener('click', (e) => {
      if (e.target === modal) { modal.remove(); return; }
      this.handleModalAction(e, modal);
    });
    modal.addEventListener('change', (e) => {
      const filter = e.target && e.target.dataset ? e.target.dataset.filter : null;
      if (filter) this.updateFilter(filter, e.target.value);
    });
    modal.addEventListener('keyup', (e) => {
      if (e.target && e.target.dataset && e.target.dataset.search) this.updateSearch(e.target.value);
    });

    document.body.appendChild(modal);
  }

  handleModalAction(e, modal) {
    const el = e.target.closest ? e.target.closest('[data-action]') : null;
    if (!el || !modal.contains(el)) return;
    const action = el.dataset.action;
    if (action === 'close') modal.remove();
    else if (action === 'clear') this.clearLogs();
    else if (action === 'export') this.exportLogs();
    else if (action === 'details') this.showDetails(el.dataset.logId);
    else if (action === 'copy-id') this.copyLogId(el.dataset.logId);
  }

  getFilteredLogs() {
    return this.logs.filter(log => {
      if (this.filters.level !== 'all' && log.level !== this.filters.level) return false;
      if (this.filters.service !== 'all' && log.service !== this.filters.service) return false;
      if (this.filters.status !== 'all' && log.status !== this.filters.status) return false;
      if (this.filters.search) {
        const msg = typeof log.message === 'string' ? log.message : String(log.message || '');
        if (!msg.toLowerCase().includes(this.filters.search.toLowerCase())) return false;
      }
      return true;
    });
  }

  updateFilter(filterName, value) {
    this.filters[filterName] = value;
    this.openLogs();
  }

  updateSearch(value) {
    this.filters.search = value;
    this.openLogs();
  }

  getSuccessRate() {
    if (this.logs.length === 0) return 100;
    const successful = this.logs.filter(l => l.status === 'success').length;
    return Math.round((successful / this.logs.length) * 100);
  }

  showDetails(logId) {
    const log = this.logs.find(l => l.id === logId);
    if (!log) return;

    const detailModal = document.createElement('div');
    detailModal.className = 'modal-backdrop';
    detailModal.innerHTML = `
      <section class="modal modal-log-details" role="dialog" aria-modal="true">
        <div class="modal-header">
          <h2>Log Details</h2>
          <button class="btn-icon" data-action="close">×</button>
        </div>

        <div class="log-details-content">
          <div class="detail-row">
            <span class="detail-label">ID:</span>
            <code>${escapeHtml(log.id)}</code>
          </div>
          <div class="detail-row">
            <span class="detail-label">Timestamp:</span>
            <span>${new Date(log.timestamp).toLocaleString()}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Level:</span>
            <badge class="badge-${escapeHtml(String(log.level).toLowerCase())}">${escapeHtml(log.level)}</badge>
          </div>
          <div class="detail-row">
            <span class="detail-label">Service:</span>
            <span>${escapeHtml(log.service)}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Action:</span>
            <code>${escapeHtml(log.action)}</code>
          </div>
          <div class="detail-row">
            <span class="detail-label">Status:</span>
            <badge class="badge-${escapeHtml(log.status)}">${escapeHtml(log.status)}</badge>
          </div>
          <div class="detail-row full">
            <span class="detail-label">Message:</span>
            <div class="detail-message">${escapeHtml(log.message)}</div>
          </div>
          ${Object.keys(log.metadata).length > 0 ? `
            <div class="detail-row full">
              <span class="detail-label">Metadata:</span>
              <pre><code>${escapeHtml(JSON.stringify(log.metadata, null, 2))}</code></pre>
            </div>
          ` : ''}
          <div class="detail-row">
            <span class="detail-label">Duration:</span>
            <span>${Number(log.duration) || 0}ms</span>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" data-action="copy-id" data-log-id="${escapeHtml(log.id)}">Copy ID</button>
          <button class="btn-secondary" data-action="close">Close</button>
        </div>
      </section>
    `;

    detailModal.addEventListener('click', (e) => {
      if (e.target === detailModal) { detailModal.remove(); return; }
      this.handleModalAction(e, detailModal);
    });

    document.body.appendChild(detailModal);
  }

  copyLogId(id) {
    navigator.clipboard.writeText(id);
    alert('Log ID copied to clipboard');
  }

  trimLogs() {
    if (this.logs.length > 1000) {
      this.logs = this.logs.slice(0, 1000);
    }
  }

  clearLogs() {
    if (confirm('Clear all logs? This cannot be undone.')) {
      this.logs = [];
      this.saveLogs();
      this.openLogs();
    }
  }

  exportLogs() {
    const csv = ['Timestamp,Level,Service,Action,Status,Message,Duration'].concat(
      this.logs.map(l =>
        `"${l.timestamp}","${l.level}","${l.service}","${l.action}","${l.status}","${l.message.replace(/"/g, '""')}",${l.duration}`
      )
    ).join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `kudbee-logs-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
  }

  saveLogs() {
    localStorage.setItem('kudbee-exec-logs', JSON.stringify(this.logs));
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.executionLogs = new ExecutionLogs();
});
