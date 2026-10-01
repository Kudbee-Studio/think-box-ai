// kudbEE Metrics Dashboard — Real-time agent performance visualization

class MetricsDashboard {
  constructor() {
    this.runsToday = 0;
    this.successRate = 0;
    this.avgLatency = 0;
    this.p95Latency = 0;
    this.costToday = 0;
    this.tokensSaved = 0;
    this.sparklineData = [];
    this.tokenSavingsData = [];

    this.updateInterval = null;
    this.initialize();
  }

  initialize() {
    // Passive only. app.js's refreshStats() is the authoritative renderer for #metric-runs,
    // #metric-suc, #metric-lat and #metric-cost, from the real /api/stats endpoint. This class
    // used to also run a 5-second setInterval of simulateMetricsUpdate(), which generated
    // Math.random() "runs", latency, cost and tokens and wrote them over those same elements,
    // so the panel showed fabricated numbers that drifted away from the real ones. That
    // generator is removed; nothing here writes to the DOM unless a real 'metrics:updated'
    // event is dispatched (none is today — app.js renders directly).
    this.setupMetricsListener();
  }

  setupMetricsListener() {
    window.addEventListener('metrics:updated', (e) => {
      const metrics = e.detail;
      this.updateMetrics(metrics);
    });
  }

  updateMetrics(metrics) {
    this.runsToday = metrics.runsToday || 0;
    this.successRate = metrics.successRate || 0;
    this.avgLatency = metrics.avgLatency || 0;
    this.p95Latency = metrics.p95Latency || 0;
    this.costToday = metrics.costToday || 0;
    this.tokensSaved = metrics.tokensSaved || 0;

    this.renderMetrics();
  }

  renderMetrics() {
    if (!document) return;

    // Update KPI values
    const metricsEl = {
      runs: document.getElementById('metric-runs'),
      success: document.getElementById('metric-suc'),
      latency: document.getElementById('metric-lat'),
      cost: document.getElementById('metric-cost'),
      tokensSaved: document.getElementById('metric-tokens-saved')
    };

    if (metricsEl.runs) metricsEl.runs.textContent = this.runsToday;
    if (metricsEl.success) {
      const rate = (this.successRate * 100).toFixed(0);
      metricsEl.success.textContent = `${rate}%`;
      metricsEl.success.className = this.getSuccessClass(this.successRate);
    }
    if (metricsEl.latency) {
      metricsEl.latency.textContent = `${this.avgLatency}ms / ${this.p95Latency}ms`;
    }
    if (metricsEl.cost) {
      metricsEl.cost.textContent = `$${this.costToday.toFixed(4)}`;
    }
    if (metricsEl.tokensSaved) {
      metricsEl.tokensSaved.textContent = this.formatTokens(this.tokensSaved);
      metricsEl.tokensSaved.className = 'kpi-success';
    }
  }

  getSuccessClass(rate) {
    if (rate >= 0.95) return 'kpi-success';
    if (rate >= 0.80) return '';
    if (rate >= 0.60) return 'kpi-warning';
    return 'kpi-error';
  }

  formatTokens(tokens) {
    if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`;
    if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(1)}K`;
    return tokens.toString();
  }

}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.metricsDashboard = new MetricsDashboard();
});
