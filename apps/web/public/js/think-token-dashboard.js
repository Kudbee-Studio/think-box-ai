// kudbEE Think Token Dashboard — Real-time learning visualization

class ThinkTokenDashboard {
  constructor() {
    this.tokens = [];
    this.propagationStats = {
      totalTokens: 0,
      activeTokens: 0,
      avgConfidence: 0,
      totalInteractions: 0
    };
    this.setupEventListeners();
    this.startLiveUpdates();
  }

  setupEventListeners() {
    document.addEventListener('DOMContentLoaded', () => {
      const learnBtn = document.getElementById('think-token-button');
      if (learnBtn) {
        learnBtn.addEventListener('click', () => this.openDashboard());
      }
    });

    window.addEventListener('token:created', (e) => this.addToken(e.detail));
    window.addEventListener('token:used', (e) => this.recordTokenUsage(e.detail));
    window.addEventListener('propagation:active', (e) => this.updatePropagationStats(e.detail));
  }

  addToken(tokenData) {
    const token = {
      id: tokenData.id || `token-${Date.now()}`,
      type: tokenData.type || 'reasoning',
      content: tokenData.content || '',
      confidence: tokenData.confidence || 0.5,
      createdAt: Date.now(),
      usageCount: 0,
      successCount: 0,
      failureCount: 0
    };

    this.tokens.unshift(token);
    this.updateDashboard();
  }

  recordTokenUsage(usageData) {
    const token = this.tokens.find(t => t.id === usageData.tokenId);
    if (token) {
      token.usageCount++;
      if (usageData.success) {
        token.successCount++;
      } else {
        token.failureCount++;
      }
      token.confidence = this.calculateConfidence(token);
      this.updateDashboard();
    }
  }

  calculateConfidence(token) {
    if (token.usageCount === 0) return token.confidence || 0.5;
    const successRate = token.successCount / token.usageCount;
    return Math.min(1, Math.max(0, successRate * 0.9 + (token.confidence || 0.5) * 0.1));
  }

  updatePropagationStats(stats) {
    this.propagationStats = stats;
    this.updateDashboard();
  }

  openDashboard() {
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.id = 'think-token-modal';
    modal.innerHTML = `
      <section class="modal modal-wide" role="dialog" aria-modal="true">
        <div class="modal-header">
          <div>
            <span class="modal-eyebrow">🎫 LEARNING SYSTEM</span>
            <h2>Think Token Dashboard</h2>
          </div>
          <button class="btn-icon" onclick="this.closest('.modal-backdrop').remove()">×</button>
        </div>

        <div class="think-token-dashboard">
          <!-- Stats Overview -->
          <div class="token-stats-grid">
            <div class="stat-card">
              <span class="stat-label">Tokens Created</span>
              <span class="stat-value">${this.tokens.length}</span>
              <span class="stat-trend">Persistent learning units</span>
            </div>
            <div class="stat-card">
              <span class="stat-label">Active Tokens</span>
              <span class="stat-value">${this.propagationStats.activeTokens}</span>
              <span class="stat-trend">Ready for propagation</span>
            </div>
            <div class="stat-card">
              <span class="stat-label">Avg Confidence</span>
              <span class="stat-value">${(this.propagationStats.avgConfidence * 100).toFixed(0)}%</span>
              <span class="stat-trend">Success rate</span>
            </div>
            <div class="stat-card">
              <span class="stat-label">Total Usage</span>
              <span class="stat-value">${this.propagationStats.totalInteractions}</span>
              <span class="stat-trend">Worker interactions</span>
            </div>
          </div>

          <!-- Think Token Timeline -->
          <div class="token-timeline-section">
            <h3>📜 Think Token Timeline (Recent)</h3>
            <div class="token-timeline">
              ${this.tokens.slice(0, 10).map(token => `
                <div class="token-card" data-token-id="${token.id}">
                  <div class="token-header">
                    <span class="token-type ${token.type}">${this.getTypeIcon(token.type)} ${token.type}</span>
                    <span class="token-confidence">${(token.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div class="token-content">
                    ${this.escapeHtml(token.content.substring(0, 100))}...
                  </div>
                  <div class="token-meta">
                    <span class="token-age">${this.formatAge(token.createdAt)}</span>
                    <span class="token-usage">${token.usageCount} uses</span>
                    <span class="token-success">${token.successCount}✓ ${token.failureCount}✗</span>
                  </div>
                  <button class="token-expand btn-quiet" onclick="thinkTokenDashboard.showTokenDetails('${token.id}')">Details</button>
                </div>
              `).join('')}
            </div>
          </div>

          <!-- Learning Loop Visualization -->
          <div class="learning-loop-section">
            <h3>🔄 Learning Loop Pipeline</h3>
            <div class="learning-pipeline">
              <div class="pipeline-stage">
                <span class="stage-icon">1️⃣</span>
                <span class="stage-title">Disruption</span>
                <span class="stage-desc">Agent encounters unexpected condition</span>
              </div>
              <div class="pipeline-arrow">→</div>
              <div class="pipeline-stage">
                <span class="stage-icon">2️⃣</span>
                <span class="stage-title">Capture</span>
                <span class="stage-desc">${this.tokens.length} observations captured</span>
              </div>
              <div class="pipeline-arrow">→</div>
              <div class="pipeline-stage">
                <span class="stage-icon">3️⃣</span>
                <span class="stage-title">Think Token</span>
                <span class="stage-desc">${this.propagationStats.activeTokens} high-value tokens</span>
              </div>
              <div class="pipeline-arrow">→</div>
              <div class="pipeline-stage">
                <span class="stage-icon">4️⃣</span>
                <span class="stage-title">Propagation</span>
                <span class="stage-desc">${this.propagationStats.totalInteractions} workers benefit</span>
              </div>
            </div>
          </div>

          <!-- Token Type Distribution -->
          <div class="token-distribution">
            <h3>📊 Token Types</h3>
            <div class="type-bars">
              ${this.getTokenTypeDistribution().map(([type, count]) => `
                <div class="type-bar">
                  <span class="type-name">${type}</span>
                  <div class="bar-container">
                    <div class="bar-fill" style="width: ${(count / Math.max(...this.getTokenTypeDistribution().map(x => x[1]))) * 100}%"></div>
                  </div>
                  <span class="type-count">${count}</span>
                </div>
              `).join('')}
            </div>
          </div>

          <!-- Confidence Distribution -->
          <div class="confidence-distribution">
            <h3>📈 Confidence Levels</h3>
            <div class="confidence-tiers">
              <div class="tier high-confidence">
                <span class="tier-label">High (>70%)</span>
                <span class="tier-count">${this.tokens.filter(t => t.confidence > 0.7).length}</span>
              </div>
              <div class="tier medium-confidence">
                <span class="tier-label">Medium (40-70%)</span>
                <span class="tier-count">${this.tokens.filter(t => t.confidence >= 0.4 && t.confidence <= 0.7).length}</span>
              </div>
              <div class="tier low-confidence">
                <span class="tier-label">Low (<40%)</span>
                <span class="tier-count">${this.tokens.filter(t => t.confidence < 0.4).length}</span>
              </div>
            </div>
          </div>

          <!-- Behavioral Impact -->
          <div class="behavioral-impact">
            <h3>🎯 Behavioral Impact</h3>
            <div class="impact-metrics">
              <div class="impact-item">
                <span class="impact-label">Workers Using Tokens</span>
                <span class="impact-value">${this.propagationStats.totalInteractions}</span>
              </div>
              <div class="impact-item">
                <span class="impact-label">Avg Success Rate</span>
                <span class="impact-value">${this.calculateAverageSuccessRate()}%</span>
              </div>
              <div class="impact-item">
                <span class="impact-label">Knowledge Reuse</span>
                <span class="impact-value">${this.calculateKnowledgeReuse()}%</span>
              </div>
            </div>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" onclick="thinkTokenDashboard.exportLearnings()">Export Learning</button>
          <button class="btn-secondary" onclick="this.closest('.modal-backdrop').remove()">Close</button>
        </div>
      </section>
    `;

    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });

    document.body.appendChild(modal);
  }

  showTokenDetails(tokenId) {
    const token = this.tokens.find(t => t.id === tokenId);
    if (!token) return;

    const detailModal = document.createElement('div');
    detailModal.className = 'modal-backdrop';
    detailModal.innerHTML = `
      <section class="modal modal-token-details" role="dialog" aria-modal="true">
        <div class="modal-header">
          <h2>${this.getTypeIcon(token.type)} ${token.type.toUpperCase()}</h2>
          <button class="btn-icon" onclick="this.closest('.modal-backdrop').remove()">×</button>
        </div>

        <div class="token-details-content">
          <div class="detail-section">
            <h4>Content</h4>
            <pre><code>${this.escapeHtml(token.content)}</code></pre>
          </div>

          <div class="detail-section">
            <h4>Metrics</h4>
            <ul>
              <li>Created: ${new Date(token.createdAt).toLocaleString()}</li>
              <li>Confidence: ${(token.confidence * 100).toFixed(1)}%</li>
              <li>Total Uses: ${token.usageCount}</li>
              <li>Successes: ${token.successCount}</li>
              <li>Failures: ${token.failureCount}</li>
              <li>Success Rate: ${token.usageCount > 0 ? ((token.successCount / token.usageCount) * 100).toFixed(1) : 'N/A'}%</li>
            </ul>
          </div>

          <div class="detail-section">
            <h4>Status</h4>
            <span class="status-badge ${token.confidence > 0.7 ? 'active' : 'learning'}">
              ${token.confidence > 0.7 ? '✓ Ready for Propagation' : '🔄 Still Learning'}
            </span>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" onclick="this.closest('.modal-backdrop').remove()">Close</button>
        </div>
      </section>
    `;

    detailModal.addEventListener('click', (e) => {
      if (e.target === detailModal) detailModal.remove();
    });

    document.body.appendChild(detailModal);
  }

  getTokenTypeDistribution() {
    const dist = {};
    this.tokens.forEach(t => {
      dist[t.type] = (dist[t.type] || 0) + 1;
    });
    return Object.entries(dist).sort((a, b) => b[1] - a[1]);
  }

  getTypeIcon(type) {
    const icons = {
      reasoning: '🤔',
      approach: '📋',
      error_recovery: '🔧',
      tool_sequence: '⚙️',
      optimization: '⚡'
    };
    return icons[type] || '🎫';
  }

  calculateAverageSuccessRate() {
    if (this.tokens.length === 0) return 0;
    const rates = this.tokens
      .filter(t => t.usageCount > 0)
      .map(t => (t.successCount / t.usageCount) * 100);
    return rates.length > 0 ? Math.round(rates.reduce((a, b) => a + b) / rates.length) : 0;
  }

  calculateKnowledgeReuse() {
    const totalPotential = this.tokens.length * 100;
    const actualReuse = this.tokens.reduce((sum, t) => sum + t.usageCount, 0);
    return totalPotential > 0 ? Math.round((actualReuse / totalPotential) * 100) : 0;
  }

  formatAge(timestamp) {
    const age = Date.now() - timestamp;
    const minutes = Math.floor(age / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'just now';
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
  }

  updateDashboard() {
    // Update any open dashboard if needed
    const modal = document.getElementById('think-token-modal');
    if (modal) {
      this.openDashboard();
    }
  }

  exportLearnings() {
    const data = {
      exportedAt: new Date().toISOString(),
      tokenCount: this.tokens.length,
      propagationStats: this.propagationStats,
      tokens: this.tokens,
      analysis: {
        avgConfidence: this.propagationStats.avgConfidence,
        avgSuccessRate: this.calculateAverageSuccessRate(),
        knowledgeReuse: this.calculateKnowledgeReuse()
      }
    };

    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `think-tokens-${Date.now()}.json`;
    a.click();
  }

  startLiveUpdates() {
    // Simulate live updates (in production, subscribe to WebSocket or event stream)
    setInterval(() => {
      // Emit mock events for demo
      window.dispatchEvent(new CustomEvent('propagation:active', {
        detail: {
          totalTokens: this.tokens.length,
          activeTokens: this.tokens.filter(t => t.confidence > 0.5).length,
          avgConfidence: this.tokens.length > 0
            ? this.tokens.reduce((sum, t) => sum + t.confidence, 0) / this.tokens.length
            : 0,
          totalInteractions: this.tokens.reduce((sum, t) => sum + t.usageCount, 0)
        }
      }));
    }, 5000);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.thinkTokenDashboard = new ThinkTokenDashboard();
});
