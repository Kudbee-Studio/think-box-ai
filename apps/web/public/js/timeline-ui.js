// Timeline UI - Step-level execution visualization

import { getTimelineService } from '../services/timeline.js';
import { escapeHtml } from './escape-html.js';

export class TimelineUI {
  constructor() {
    this.timelineService = getTimelineService();
    this.timelinePanel = document.getElementById('timeline-panel');
    this.container = document.getElementById('timeline-container');
    this.timelineButton = document.getElementById('timeline-button');
    this.closeButton = document.getElementById('close-timeline');

    this.init();
  }

  init() {
    if (!this.timelineButton) return;

    this.timelineButton.addEventListener('click', () => this.toggleTimeline());
    if (this.closeButton) {
      this.closeButton.addEventListener('click', () => this.closeTimeline());
    }

    // Listen for run updates to refresh timeline
    window.addEventListener('run-update', () => this.updateTimeline());
  }

  toggleTimeline() {
    if (this.timelinePanel.hidden) {
      this.openTimeline();
    } else {
      this.closeTimeline();
    }
  }

  openTimeline() {
    this.timelinePanel.hidden = false;
    this.updateTimeline();
  }

  closeTimeline() {
    this.timelinePanel.hidden = true;
  }

  updateTimeline() {
    if (this.timelinePanel.hidden) return;

    const runId = this.getCurrentRunId();
    if (!runId) {
      this.container.innerHTML = '<div class="empty-state">No active run</div>';
      return;
    }

    const steps = this.timelineService.getSteps(runId);
    const criticalPath = this.timelineService.getCriticalPath(runId);

    this.container.innerHTML = `
      <div class="timeline">
        <div class="timeline-header">
          <h4>Execution Timeline</h4>
          <span class="run-id">${escapeHtml(runId.slice(0, 8))}</span>
        </div>

        <div class="timeline-stats">
          <div class="stat-item">
            <span class="stat-label">Total Steps</span>
            <strong>${steps.length}</strong>
          </div>
          <div class="stat-item">
            <span class="stat-label">Critical Path</span>
            <strong>${criticalPath}ms</strong>
          </div>
          <div class="stat-item">
            <span class="stat-label">Success Rate</span>
            <strong>${this.calculateSuccessRate(steps)}%</strong>
          </div>
        </div>

        <div class="timeline-items">
          ${steps.map((step, idx) => this.buildTimelineItem(step, idx, steps.length)).join('')}
        </div>
      </div>
    `;
  }

  buildTimelineItem(step, index, total) {
    const statusColor = {
      'pending': '#64748b',
      'running': '#3b82f6',
      'success': '#10b981',
      'failed': '#ef4444',
      'waiting': '#f59e0b'
    }[step.status] || '#64748b';

    const duration = step.endTime && step.startTime
      ? step.endTime - step.startTime
      : 0;

    return `
      <div class="timeline-item" data-status="${escapeHtml(step.status)}">
        <div class="timeline-dot" style="background-color: ${statusColor}"></div>
        <div class="timeline-content">
          <div class="step-header">
            <span class="step-num">Step ${index + 1}</span>
            <span class="step-name">${escapeHtml(step.name)}</span>
            <span class="step-status">${escapeHtml(step.status)}</span>
          </div>

          ${step.tool ? `
            <div class="step-tool">
              <span class="tool-icon">⚙️</span>
              <span class="tool-name">${escapeHtml(step.tool)}</span>
            </div>
          ` : ''}

          <div class="step-timing">
            <span class="timing-label">Duration:</span>
            <span class="timing-value">${duration}ms</span>
          </div>

          ${step.approvalWaitTime ? `
            <div class="step-approval">
              <span class="approval-label">⏳ Approval wait:</span>
              <span class="approval-time">${Number(step.approvalWaitTime) || 0}ms</span>
            </div>
          ` : ''}

          ${step.result ? `
            <div class="step-result">
              <details>
                <summary>Result</summary>
                <pre>${escapeHtml(JSON.stringify(step.result, null, 2))}</pre>
              </details>
            </div>
          ` : ''}

          ${step.error ? `
            <div class="step-error">
              <details>
                <summary>Error</summary>
                <pre>${escapeHtml(step.error)}</pre>
              </details>
            </div>
          ` : ''}
        </div>

        ${index < total - 1 ? '<div class="timeline-connector"></div>' : ''}
      </div>
    `;
  }

  calculateSuccessRate(steps) {
    if (steps.length === 0) return 0;
    const successful = steps.filter(s => s.status === 'success').length;
    return Math.round((successful / steps.length) * 100);
  }

  getCurrentRunId() {
    // Try to get run ID from localStorage or document state
    const openRunId = localStorage.getItem('openRunId');
    if (openRunId) return openRunId;

    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('runId') || null;
  }
}
