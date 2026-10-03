// Sharing UI - Run sharing and export functionality

import { getRunSharingService } from '../services/run-sharing.js';

export class SharingUI {
  constructor() {
    this.sharingService = getRunSharingService();
    this.sharingPanel = document.getElementById('sharing-panel');
    this.container = document.getElementById('sharing-container');
    this.sharingButton = document.getElementById('share-button');
    this.closeButton = document.getElementById('close-sharing');

    this.init();
  }

  init() {
    if (!this.sharingButton) return;

    this.sharingButton.addEventListener('click', () => this.toggleSharing());
    if (this.closeButton) {
      this.closeButton.addEventListener('click', () => this.closeSharing());
    }
  }

  toggleSharing() {
    if (this.sharingPanel.hidden) {
      this.openSharing();
    } else {
      this.closeSharing();
    }
  }

  openSharing() {
    this.sharingPanel.hidden = false;
    this.updateSharing();
  }

  closeSharing() {
    this.sharingPanel.hidden = true;
  }

  updateSharing() {
    if (this.sharingPanel.hidden) return;

    const runId = this.getCurrentRunId();
    if (!runId) {
      this.container.innerHTML = '<div class="empty-state">No active run</div>';
      return;
    }

    const shares = this.sharingService.getSharesForRun(runId);

    this.container.innerHTML = `
      <div class="sharing-dashboard">
        <div class="sharing-header">
          <h4>Share & Export</h4>
          <span class="run-id">${runId.slice(0, 8)}</span>
        </div>

        <!-- Quick Share Section -->
        <div class="sharing-section">
          <h5>Create Share Link</h5>
          <div class="share-options">
            <div class="option-group">
              <label>Expiration</label>
              <select id="share-expiration" class="select-small">
                <option value="1h">1 hour</option>
                <option value="24h">24 hours</option>
                <option value="7d" selected>7 days</option>
                <option value="30d">30 days</option>
                <option value="never">Never</option>
              </select>
            </div>
            <div class="option-group">
              <label>Access</label>
              <select id="share-access" class="select-small">
                <option value="public">Public</option>
                <option value="password">Password protected</option>
                <option value="token">Token</option>
              </select>
            </div>
          </div>
          <div class="option-group" id="password-group" hidden>
            <label>Password</label>
            <input type="password" id="share-password" placeholder="Set a password" class="input-small">
          </div>
          <button id="create-share" class="btn-secondary" style="width: 100%; margin-top: 12px;">🔗 Create Share Link</button>
        </div>

        <!-- Active Shares -->
        ${shares.length > 0 ? `
          <div class="sharing-section">
            <h5>Active Shares (${shares.length})</h5>
            <div class="shares-list">
              ${shares.map(share => this.buildShareItem(share, runId)).join('')}
            </div>
          </div>
        ` : ''}

        <!-- Export Section -->
        <div class="sharing-section">
          <h5>Export Data</h5>
          <div class="export-options">
            <button class="export-btn" data-format="json">
              <span>📄</span> JSON
            </button>
            <button class="export-btn" data-format="markdown">
              <span>📝</span> Markdown
            </button>
            <button class="export-btn" data-format="html">
              <span>🌐</span> HTML
            </button>
            <button class="export-btn" data-format="csv">
              <span>📊</span> CSV
            </button>
          </div>
        </div>

        <!-- Snapshot Info -->
        <div class="sharing-section">
          <h5>Current Snapshot</h5>
          <div class="snapshot-info">
            <div class="info-row">
              <span class="label">Run ID:</span>
              <span class="value">${runId}</span>
            </div>
            <div class="info-row">
              <span class="label">Created:</span>
              <span class="value">${this.formatDate(new Date())}</span>
            </div>
            <div class="info-row">
              <span class="label">Status:</span>
              <span class="value">Active</span>
            </div>
          </div>
        </div>
      </div>
    `;

    // Attach event listeners
    this.attachEventListeners(runId, shares);
  }

  buildShareItem(share, runId) {
    const expiresIn = share.expiresAt
      ? Math.ceil((new Date(share.expiresAt) - Date.now()) / 1000 / 60)
      : null;

    const expiryText = expiresIn
      ? expiresIn > 0
        ? `Expires in ${expiresIn}m`
        : 'Expired'
      : 'Never expires';

    return `
      <div class="share-item">
        <div class="share-info">
          <div class="share-url">
            <code>${share.shareLink}</code>
            <button class="copy-btn" data-url="${share.shareLink}" title="Copy">📋</button>
          </div>
          <div class="share-meta">
            <span class="badge badge-${share.accessLevel}">${share.accessLevel}</span>
            <span class="expiry">${expiryText}</span>
            <span class="views">${share.viewCount || 0} views</span>
          </div>
        </div>
        <button class="delete-share-btn" data-share-id="${share.id}" title="Delete">✕</button>
      </div>
    `;
  }

  attachEventListeners(runId, shares) {
    const accessSelect = document.getElementById('share-access');
    const passwordGroup = document.getElementById('password-group');

    if (accessSelect && passwordGroup) {
      accessSelect.addEventListener('change', () => {
        passwordGroup.hidden = accessSelect.value !== 'password';
      });
    }

    const createBtn = document.getElementById('create-share');
    if (createBtn) {
      createBtn.addEventListener('click', () => this.createShare(runId));
    }

    document.querySelectorAll('.export-btn').forEach(btn => {
      btn.addEventListener('click', () => this.exportRun(runId, btn.dataset.format));
    });

    document.querySelectorAll('.copy-btn').forEach(btn => {
      btn.addEventListener('click', () => this.copyToClipboard(btn.dataset.url));
    });

    document.querySelectorAll('.delete-share-btn').forEach(btn => {
      btn.addEventListener('click', () => this.deleteShare(btn.dataset.shareId, runId));
    });
  }

  async createShare(runId) {
    const expiration = document.getElementById('share-expiration')?.value || '7d';
    const accessLevel = document.getElementById('share-access')?.value || 'public';
    const password = document.getElementById('share-password')?.value || '';

    try {
      const share = await this.sharingService.createShare(runId, {
        expiration,
        accessLevel,
        password: accessLevel === 'password' ? password : undefined,
      });

      this.updateSharing();
      this.copyToClipboard(share.shareLink);
    } catch (err) {
      alert(`Failed to create share: ${err.message}`);
    }
  }

  async exportRun(runId, format) {
    try {
      const data = await this.sharingService.exportRun(runId, format);
      this.downloadFile(data, `run-${runId.slice(0, 8)}.${format}`);
    } catch (err) {
      alert(`Failed to export: ${err.message}`);
    }
  }

  copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
      const btn = event.target;
      btn.textContent = '✓ Copied!';
      setTimeout(() => { btn.textContent = '📋'; }, 2000);
    });
  }

  async deleteShare(shareId, runId) {
    if (!confirm('Delete this share link?')) return;

    try {
      await this.sharingService.deleteShare(shareId);
      this.updateSharing();
    } catch (err) {
      alert(`Failed to delete share: ${err.message}`);
    }
  }

  downloadFile(content, filename) {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  formatDate(date) {
    return date.toLocaleString();
  }

  getCurrentRunId() {
    const openRunId = localStorage.getItem('openRunId');
    if (openRunId) return openRunId;

    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('runId') || null;
  }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    new SharingUI();
  });
} else {
  new SharingUI();
}
