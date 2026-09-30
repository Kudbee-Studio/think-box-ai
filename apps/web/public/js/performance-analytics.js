// kudbEE Performance Analytics — Cost, tokens, and latency optimization

class PerformanceAnalytics {
  constructor() {
    this.metrics = this.loadMetrics();
    this.costs = this.loadCosts();
    this.setupChart();
    this.setupEventListeners();
  }

  loadMetrics() {
    const stored = localStorage.getItem('kudbee-perf-metrics');
    return stored ? JSON.parse(stored) : {
      runs: [],
      tokens: { saved: 0, spent: 0 },
      latencies: [],
      costs: { daily: {}, monthly: {} }
    };
  }

  loadCosts() {
    const stored = localStorage.getItem('kudbee-costs');
    return stored ? JSON.parse(stored) : {
      localModel: { costPer1k: 0.01 },
      mercury2: { costPer1k: 0.10 },
      opus: { costPer1k: 0.15 },
      current: {}
    };
  }

  setupEventListeners() {
    // Instances are created on DOMContentLoaded, so wire the header button now (a nested
    // DOMContentLoaded listener would never fire and the button would do nothing).
    const analyticsBtn = document.getElementById('performance-analytics-button');
    if (analyticsBtn) {
      analyticsBtn.addEventListener('click', () => this.openDashboard());
    }

    window.addEventListener('run:completed', (e) => {
      this.recordRunMetrics(e.detail);
    });
  }

  recordRunMetrics(run) {
    const metric = {
      id: run.id,
      model: run.model,
      inputTokens: run.inputTokens || 0,
      outputTokens: run.outputTokens || 0,
      latency: run.latency || 0,
      cost: run.cost || 0,
      timestamp: new Date().toISOString(),
      isLocal: run.model?.includes('local') || false
    };

    this.metrics.runs.push(metric);
    this.metrics.tokens.spent += metric.inputTokens + metric.outputTokens;
    this.metrics.latencies.push(metric.latency);

    // Update cost tracking
    const today = new Date().toISOString().split('T')[0];
    if (!this.metrics.costs.daily[today]) {
      this.metrics.costs.daily[today] = 0;
    }
    this.metrics.costs.daily[today] += metric.cost;

    localStorage.setItem('kudbee-perf-metrics', JSON.stringify(this.metrics));
    this.updateDashboard();
  }

  openDashboard() {
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.id = 'analytics-modal';
    modal.innerHTML = `
      <section class="modal modal-wide" role="dialog" aria-modal="true">
        <div class="modal-header">
          <div>
            <span class="modal-eyebrow">ANALYTICS</span>
            <h2>Performance & Cost Analysis</h2>
          </div>
          <button class="btn-icon" onclick="this.closest('.modal-backdrop').remove()">×</button>
        </div>

        <div class="analytics-dashboard">
          <div class="metrics-grid">
            <div class="metric-card">
              <div class="metric-label">Total Cost (30d)</div>
              <div class="metric-value">$${this.calculateTotalCost()}</div>
              <div class="metric-trend" id="cost-trend">↔ Stable</div>
            </div>

            <div class="metric-card">
              <div class="metric-label">Tokens Used</div>
              <div class="metric-value">${(this.metrics.tokens.spent / 1000).toFixed(1)}K</div>
              <div class="metric-trend" id="token-trend">↑ +${this.getTokenTrend()}</div>
            </div>

            <div class="metric-card">
              <div class="metric-label">Avg Latency</div>
              <div class="metric-value">${this.getAverageLatency()}ms</div>
              <div class="metric-trend" id="latency-trend">↓ -${this.getLatencyTrend()}ms</div>
            </div>

            <div class="metric-card">
              <div class="metric-label">Local Model %</div>
              <div class="metric-value">${this.getLocalModelPercentage()}%</div>
              <div class="metric-trend" id="local-trend">💡 Savings: $${this.calculateSavings()}</div>
            </div>
          </div>

          <div class="analytics-charts">
            <div class="chart-container">
              <h3>Daily Cost Trend (30 days)</h3>
              <canvas id="cost-chart"></canvas>
            </div>

            <div class="chart-container">
              <h3>Token Efficiency by Model</h3>
              <div class="efficiency-table">
                <div class="efficiency-row header">
                  <span>Model</span>
                  <span>Runs</span>
                  <span>Tokens/Run</span>
                  <span>Avg Latency</span>
                  <span>Cost/Run</span>
                </div>
                ${this.getModelEfficiency().map(m => `
                  <div class="efficiency-row">
                    <span>${m.model}</span>
                    <span>${m.runs}</span>
                    <span>${m.tokensPerRun}</span>
                    <span>${m.avgLatency}ms</span>
                    <span>$${m.costPerRun}</span>
                  </div>
                `).join('')}
              </div>
            </div>
          </div>

          <div class="optimization-suggestions">
            <h3>💡 Optimization Suggestions</h3>
            <ul class="suggestions-list">
              ${this.getOptimizationSuggestions().map(s => `
                <li class="suggestion">
                  <span class="suggestion-impact">${s.impact}</span>
                  <span class="suggestion-text">${s.text}</span>
                  <span class="suggestion-savings">Save: $${s.savings}</span>
                </li>
              `).join('')}
            </ul>
          </div>

          <div class="cost-breakdown">
            <h3>Cost Breakdown</h3>
            <div class="breakdown-bars">
              ${this.getCostBreakdown().map(item => `
                <div class="breakdown-item">
                  <span class="breakdown-label">${item.label}</span>
                  <div class="breakdown-bar">
                    <div class="breakdown-fill" style="width: ${item.percentage}%"></div>
                  </div>
                  <span class="breakdown-value">$${item.cost} (${item.percentage}%)</span>
                </div>
              `).join('')}
            </div>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" onclick="performanceAnalytics.exportMetrics()">Export Report</button>
          <button class="btn-secondary" onclick="this.closest('.modal-backdrop').remove()">Close</button>
        </div>
      </section>
    `;

    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });

    document.body.appendChild(modal);
    this.renderChart();
  }

  calculateTotalCost() {
    return Object.values(this.metrics.costs.daily || {})
      .reduce((sum, cost) => sum + cost, 0)
      .toFixed(2);
  }

  getAverageLatency() {
    if (this.metrics.latencies.length === 0) return 0;
    const sum = this.metrics.latencies.reduce((a, b) => a + b, 0);
    return Math.round(sum / this.metrics.latencies.length);
  }

  getTokenTrend() {
    return Math.max(0, this.metrics.runs.length > 0 ? Math.round(this.metrics.tokens.spent / this.metrics.runs.length / 100) : 0);
  }

  getLatencyTrend() {
    if (this.metrics.latencies.length < 2) return 0;
    const recent = this.metrics.latencies.slice(-10);
    const older = this.metrics.latencies.slice(-20, -10);
    const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length;
    const olderAvg = older.reduce((a, b) => a + b, 0) / older.length;
    return Math.round(Math.max(0, olderAvg - recentAvg));
  }

  getLocalModelPercentage() {
    if (this.metrics.runs.length === 0) return 0;
    const local = this.metrics.runs.filter(r => r.isLocal).length;
    return Math.round((local / this.metrics.runs.length) * 100);
  }

  calculateSavings() {
    return (this.metrics.tokens.saved * 0.0001).toFixed(2);
  }

  getModelEfficiency() {
    const models = {};
    this.metrics.runs.forEach(run => {
      if (!models[run.model]) {
        models[run.model] = { runs: 0, totalTokens: 0, totalLatency: 0, totalCost: 0 };
      }
      models[run.model].runs++;
      models[run.model].totalTokens += run.inputTokens + run.outputTokens;
      models[run.model].totalLatency += run.latency;
      models[run.model].totalCost += run.cost;
    });

    return Object.entries(models).map(([model, data]) => ({
      model,
      runs: data.runs,
      tokensPerRun: Math.round(data.totalTokens / data.runs),
      avgLatency: Math.round(data.totalLatency / data.runs),
      costPerRun: (data.totalCost / data.runs).toFixed(4)
    }));
  }

  getOptimizationSuggestions() {
    const suggestions = [];
    const localPct = this.getLocalModelPercentage();

    if (localPct < 30) {
      suggestions.push({
        impact: 'HIGH',
        text: 'Route more simple tasks to local models',
        savings: (this.calculateTotalCost() * 0.2).toFixed(2)
      });
    }

    if (this.getAverageLatency() > 500) {
      suggestions.push({
        impact: 'MEDIUM',
        text: 'Consider caching frequent queries',
        savings: (this.calculateTotalCost() * 0.1).toFixed(2)
      });
    }

    suggestions.push({
      impact: 'LOW',
      text: 'Batch similar requests together',
      savings: (this.calculateTotalCost() * 0.05).toFixed(2)
    });

    return suggestions;
  }

  getCostBreakdown() {
    const breakdown = {};
    this.metrics.runs.forEach(run => {
      if (!breakdown[run.model]) {
        breakdown[run.model] = 0;
      }
      breakdown[run.model] += run.cost;
    });

    const total = Object.values(breakdown).reduce((a, b) => a + b, 0);
    if (total === 0) return [];
    return Object.entries(breakdown).map(([model, cost]) => ({
      label: model,
      cost: cost.toFixed(2),
      percentage: ((cost / total) * 100).toFixed(1)
    }));
  }

  renderChart() {
    const canvas = document.getElementById('cost-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const days = Object.keys(this.metrics.costs.daily).sort().slice(-30);
    const costs = days.map(day => this.metrics.costs.daily[day] || 0);

    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    canvas.width = width;
    canvas.height = height;

    const maxCost = Math.max(...costs, 1);
    const padding = 40;
    const graphWidth = width - 2 * padding;
    const graphHeight = height - 2 * padding;

    ctx.fillStyle = '#1a1f2e';
    ctx.fillRect(0, 0, width, height);

    ctx.strokeStyle = '#304050';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const y = padding + (graphHeight * i) / 5;
      ctx.beginPath();
      ctx.moveTo(padding, y);
      ctx.lineTo(width - padding, y);
      ctx.stroke();
    }

    ctx.strokeStyle = '#4a9eff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    costs.forEach((cost, i) => {
      const x = padding + (graphWidth * i) / (costs.length - 1 || 1);
      const y = height - padding - (graphHeight * cost) / maxCost;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    ctx.fillStyle = '#4a9eff';
    costs.forEach((cost, i) => {
      const x = padding + (graphWidth * i) / (costs.length - 1 || 1);
      const y = height - padding - (graphHeight * cost) / maxCost;
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  setupChart() {
    // Chart setup will be done on modal open
  }

  updateDashboard() {
    if (document.getElementById('analytics-modal')) {
      this.openDashboard();
    }
  }

  exportMetrics() {
    const report = {
      generatedAt: new Date().toISOString(),
      summary: {
        totalCost: this.calculateTotalCost(),
        totalTokens: this.metrics.tokens.spent,
        averageLatency: this.getAverageLatency(),
        localModelUsage: this.getLocalModelPercentage() + '%'
      },
      modelEfficiency: this.getModelEfficiency(),
      costBreakdown: this.getCostBreakdown(),
      suggestions: this.getOptimizationSuggestions()
    };

    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `kudbee-analytics-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.performanceAnalytics = new PerformanceAnalytics();
});
