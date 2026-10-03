// Analytics Panel - Dashboard visualization component

import { getAnalyticsService, type KPICard } from '../services/analytics.js';
import { getUserPreferencesService } from '../services/user-preferences.js';

export class AnalyticsPanel {
  private container: HTMLElement | null = null;
  private analyticsService = getAnalyticsService();
  private preferencesService = getUserPreferencesService();

  async render(container: HTMLElement): Promise<void> {
    this.container = container;
    this.container.innerHTML = this.buildHTML();
    this.attachEventListeners();
    this.updateCharts();
  }

  async cleanup(): Promise<void> {
    if (this.container) {
      this.container.innerHTML = '';
    }
  }

  private buildHTML(): string {
    const kpis = this.analyticsService.getKPICards();

    return `
      <div class="analytics-dashboard">
        <!-- KPI Cards Row -->
        <div class="kpi-row">
          ${kpis.map((kpi) => this.buildKPICard(kpi)).join('')}
        </div>

        <!-- Charts Section -->
        <div class="charts-grid">
          <!-- Runs Per Hour -->
          <div class="chart-container">
            <div class="chart-header">
              <h4>Runs Per Hour</h4>
              <span class="chart-range">Last 24h</span>
            </div>
            <canvas id="chart-runs-per-hour" class="chart-canvas"></canvas>
          </div>

          <!-- Latency Trend -->
          <div class="chart-container">
            <div class="chart-header">
              <h4>Latency Trend</h4>
              <span class="chart-range">Last 20 runs</span>
            </div>
            <canvas id="chart-latency-trend" class="chart-canvas"></canvas>
          </div>

          <!-- Model Distribution -->
          <div class="chart-container">
            <div class="chart-header">
              <h4>Model Distribution</h4>
              <span class="chart-range">All time</span>
            </div>
            <div id="chart-model-dist" class="model-distribution"></div>
          </div>

          <!-- Failure Analysis -->
          <div class="chart-container">
            <div class="chart-header">
              <h4>Failure Analysis</h4>
              <span class="chart-range">All time</span>
            </div>
            <div id="chart-failures" class="failure-analysis"></div>
          </div>
        </div>

        <!-- Week Comparison -->
        <div class="comparison-card">
          <div class="comparison-header">
            <h4>This Week vs Last Week</h4>
          </div>
          <div id="comparison-stats" class="comparison-stats"></div>
        </div>

        <!-- Controls -->
        <div class="analytics-controls">
          <button id="refresh-analytics" class="btn-secondary">🔄 Refresh</button>
          <button id="export-analytics" class="btn-secondary">📥 Export Data</button>
          <button id="clear-analytics" class="btn-secondary">🗑 Clear All</button>
        </div>
      </div>
    `;
  }

  private buildKPICard(kpi: KPICard): string {
    const trendClass = kpi.trend
      ? kpi.trend > 0
        ? 'trend-up'
        : 'trend-down'
      : '';
    const trendText = kpi.trend ? (kpi.trend > 0 ? '↑' : '↓') : '';

    return `
      <div class="kpi-card kpi-${kpi.color}">
        <div class="kpi-icon">${kpi.icon}</div>
        <div class="kpi-content">
          <div class="kpi-title">${kpi.title}</div>
          <div class="kpi-value">${kpi.value}</div>
          ${
            kpi.trend !== undefined
              ? `<div class="kpi-trend ${trendClass}">${trendText} ${Math.abs(kpi.trend)}%</div>`
              : ''
          }
        </div>
      </div>
    `;
  }

  private updateCharts(): void {
    this.renderRunsPerHour();
    this.renderLatencyTrend();
    this.renderModelDistribution();
    this.renderFailureAnalysis();
    this.renderWeekComparison();
  }

  private renderRunsPerHour(): void {
    const data = this.analyticsService.getRunsPerHour();
    const canvas = document.getElementById('chart-runs-per-hour') as HTMLCanvasElement;

    if (!canvas || data.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    this.drawLineChart(
      ctx,
      data.map((d: any) => d.value),
      data.map((d: any) => d.label),
      '#06b6d4'
    );
  }

  private renderLatencyTrend(): void {
    const data = this.analyticsService.getLatencyTrend();
    const canvas = document.getElementById('chart-latency-trend') as HTMLCanvasElement;

    if (!canvas || data.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    this.drawLineChart(
      ctx,
      data.map((d) => d.value),
      data.map((d) => d.label),
      '#0ea5e9'
    );
  }

  private renderModelDistribution(): void {
    const data = this.analyticsService.getModelDistribution();
    const container = document.getElementById('chart-model-dist');

    if (!container) return;

    const colors = [
      '#06b6d4',
      '#0ea5e9',
      '#38bdf8',
      '#22d3ee',
      '#67e8f9',
    ];

    container.innerHTML = data
      .map(
        (model, idx) => `
      <div class="model-item">
        <div class="model-bar">
          <div class="model-fill" style="width: ${model.percentage}%; background-color: ${colors[idx % colors.length]}"></div>
        </div>
        <div class="model-info">
          <span class="model-name">${model.model}</span>
          <span class="model-stats">${model.count} runs • ${model.avgDuration}ms avg</span>
        </div>
        <span class="model-percentage">${model.percentage}%</span>
      </div>
    `
      )
      .join('');
  }

  private renderFailureAnalysis(): void {
    const data = this.analyticsService.getFailureAnalysis();
    const container = document.getElementById('chart-failures');

    if (!container) return;

    if (data.length === 0) {
      container.innerHTML = '<div class="empty-state">No failures recorded</div>';
      return;
    }

    container.innerHTML = data
      .map(
        (failure) => `
      <div class="failure-item">
        <div class="failure-category">
          <strong>${failure.category}</strong>
          <span class="failure-count">${failure.count} ${failure.count === 1 ? 'failure' : 'failures'}</span>
        </div>
        <div class="failure-bar">
          <div class="failure-fill" style="width: ${failure.percentage}%"></div>
        </div>
        <span class="failure-percentage">${failure.percentage}%</span>
      </div>
    `
      )
      .join('');
  }

  private renderWeekComparison(): void {
    const comparison = this.analyticsService.getWeekComparison();
    const container = document.getElementById('comparison-stats');

    if (!container) return;

    const improvementClass =
      comparison.improvement > 0 ? 'improvement-positive' : 'improvement-negative';
    const improvementText =
      comparison.improvement > 0 ? '📈 Up' : comparison.improvement < 0 ? '📉 Down' : '→ Flat';

    container.innerHTML = `
      <div class="comparison-item">
        <div class="comparison-label">This Week</div>
        <div class="comparison-value">${comparison.thisWeek}</div>
      </div>
      <div class="comparison-item">
        <div class="comparison-label">Last Week</div>
        <div class="comparison-value">${comparison.lastWeek}</div>
      </div>
      <div class="comparison-item ${improvementClass}">
        <div class="comparison-label">Change</div>
        <div class="comparison-value">${improvementText} ${Math.abs(comparison.improvement)}%</div>
      </div>
    `;
  }

  private drawLineChart(
    ctx: CanvasRenderingContext2D,
    data: number[],
    labels: string[],
    color: string
  ): void {
    if (data.length === 0) return;

    const width = ctx.canvas.width;
    const height = ctx.canvas.height;
    const padding = 20;
    const graphWidth = width - 2 * padding;
    const graphHeight = height - 2 * padding;

    ctx.clearRect(0, 0, width, height);

    // Draw background
    ctx.fillStyle = 'rgba(6, 182, 212, 0.05)';
    ctx.fillRect(padding, padding, graphWidth, graphHeight);

    // Draw grid lines
    ctx.strokeStyle = 'rgba(6, 182, 212, 0.1)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = padding + (graphHeight / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padding, y);
      ctx.lineTo(width - padding, y);
      ctx.stroke();
    }

    // Draw line
    const maxValue = Math.max(...data);
    const minValue = Math.min(...data);
    const range = maxValue - minValue || 1;

    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();

    data.forEach((value, idx) => {
      const x = padding + (graphWidth / (data.length - 1 || 1)) * idx;
      const y = height - padding - ((value - minValue) / range) * graphHeight;

      if (idx === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });

    ctx.stroke();

    // Draw points
    ctx.fillStyle = color;
    data.forEach((value, idx) => {
      const x = padding + (graphWidth / (data.length - 1 || 1)) * idx;
      const y = height - padding - ((value - minValue) / range) * graphHeight;

      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  private attachEventListeners(): void {
    const refreshBtn = document.getElementById('refresh-analytics');
    const exportBtn = document.getElementById('export-analytics');
    const clearBtn = document.getElementById('clear-analytics');

    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => {
        this.updateCharts();
      });
    }

    if (exportBtn) {
      exportBtn.addEventListener('click', () => {
        this.exportData();
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        if (confirm('Clear all analytics data? This cannot be undone.')) {
          this.analyticsService.clear();
          this.render(this.container!);
        }
      });
    }
  }

  private exportData(): void {
    const runs = this.analyticsService.getAllRuns();
    const format = this.preferencesService.get('exportFormat');

    let content: string;
    let filename: string;

    if (format === 'csv') {
      content = this.convertToCSV(runs);
      filename = 'analytics.csv';
    } else if (format === 'markdown') {
      content = this.convertToMarkdown(runs);
      filename = 'analytics.md';
    } else {
      content = JSON.stringify(runs, null, 2);
      filename = 'analytics.json';
    }

    this.downloadFile(content, filename);
  }

  private convertToCSV(runs: any[]): string {
    const headers = [
      'ID',
      'Timestamp',
      'Duration',
      'Success',
      'Model',
      'Tokens Saved',
      'Tool Count',
    ];
    const rows = runs.map((r) => [
      r.id,
      new Date(r.timestamp).toISOString(),
      r.duration,
      r.success,
      r.model,
      r.tokensSaved || 0,
      r.toolCount,
    ]);

    return [headers, ...rows].map((row) => row.map((v) => `"${v}"`).join(',')).join('\n');
  }

  private convertToMarkdown(runs: any[]): string {
    let md = '# Analytics Report\n\n';
    md += `Generated: ${new Date().toISOString()}\n\n`;
    md += `## Summary\n- Total Runs: ${runs.length}\n`;
    md += `- Success Rate: ${Math.round((runs.filter((r) => r.success).length / runs.length) * 100)}%\n\n`;
    md += '## Run Details\n\n';
    md += '| ID | Timestamp | Duration | Success | Model |\n';
    md += '|----|-----------|----------|---------|-------|\n';

    runs.forEach((r) => {
      md += `| ${r.id} | ${new Date(r.timestamp).toISOString()} | ${r.duration}ms | ${r.success ? '✓' : '✗'} | ${r.model} |\n`;
    });

    return md;
  }

  private downloadFile(content: string, filename: string): void {
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
}
