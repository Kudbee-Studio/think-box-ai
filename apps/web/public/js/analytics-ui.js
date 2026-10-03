// Analytics Dashboard UI - Handle display and interaction

import { getAnalyticsService } from '../services/analytics.js';

export class AnalyticsDashboardUI {
  constructor() {
    this.analyticsService = getAnalyticsService();
    this.dashboardPanel = document.getElementById('analytics-dashboard-panel');
    this.container = document.getElementById('analytics-container');
    this.analyticsButton = document.getElementById('performance-analytics-button');
    this.closeButton = document.getElementById('close-analytics');

    this.init();
  }

  init() {
    if (!this.analyticsButton) return;

    // Wire up button clicks
    this.analyticsButton.addEventListener('click', () => this.toggleDashboard());

    if (this.closeButton) {
      this.closeButton.addEventListener('click', () => this.closeDashboard());
    }

    // Auto-refresh every 10 seconds
    setInterval(() => this.updateDashboard(), 10000);
  }

  toggleDashboard() {
    if (this.dashboardPanel.hidden) {
      this.openDashboard();
    } else {
      this.closeDashboard();
    }
  }

  openDashboard() {
    this.dashboardPanel.hidden = false;
    this.updateDashboard();
  }

  closeDashboard() {
    this.dashboardPanel.hidden = true;
  }

  updateDashboard() {
    if (this.dashboardPanel.hidden) return;

    const kpis = this.analyticsService.getKPICards();
    const modelDist = this.analyticsService.getModelDistribution();
    const failures = this.analyticsService.getFailureAnalysis();
    const weekComparison = this.analyticsService.getWeekComparison();

    this.container.innerHTML = `
      <div class="analytics-dashboard">
        <!-- KPI Cards -->
        <div class="analytics-kpis">
          ${kpis.map(kpi => this.buildKPICard(kpi)).join('')}
        </div>

        <!-- Model Distribution -->
        <div class="analytics-section">
          <h4>Model Distribution</h4>
          <div class="model-list">
            ${modelDist.map(m => `
              <div class="model-row">
                <span class="model-name">${m.model}</span>
                <div class="model-bar"><div class="model-fill" style="width: ${m.percentage}%"></div></div>
                <span class="model-percent">${m.percentage}%</span>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- Failure Analysis -->
        ${failures.length > 0 ? `
          <div class="analytics-section">
            <h4>Failures</h4>
            <div class="failure-list">
              ${failures.map(f => `
                <div class="failure-row">
                  <span class="failure-name">${f.category}</span>
                  <span class="failure-count">${f.count}</span>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}

        <!-- Week Comparison -->
        <div class="analytics-section">
          <h4>This Week vs Last Week</h4>
          <div class="comparison-row">
            <div class="comparison-item">
              <span>This Week</span>
              <strong>${weekComparison.thisWeek}</strong>
            </div>
            <div class="comparison-item">
              <span>Last Week</span>
              <strong>${weekComparison.lastWeek}</strong>
            </div>
            <div class="comparison-item">
              <span>Change</span>
              <strong class="change-${weekComparison.improvement > 0 ? 'positive' : 'negative'}">
                ${weekComparison.improvement > 0 ? '↑' : '↓'} ${Math.abs(weekComparison.improvement)}%
              </strong>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  buildKPICard(kpi) {
    const trendClass = kpi.trend
      ? kpi.trend > 0 ? 'trend-up' : 'trend-down'
      : '';

    return `
      <div class="analytics-kpi kpi-${kpi.color}">
        <div class="kpi-icon">${kpi.icon}</div>
        <div class="kpi-content">
          <div class="kpi-label">${kpi.title}</div>
          <div class="kpi-value">${kpi.value}</div>
          ${kpi.trend !== undefined ? `
            <div class="kpi-trend ${trendClass}">
              ${kpi.trend > 0 ? '↑' : '↓'} ${Math.abs(kpi.trend)}%
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    new AnalyticsDashboardUI();
  });
} else {
  new AnalyticsDashboardUI();
}
