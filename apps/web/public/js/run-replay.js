// kudbEE Run Replay — Step-through execution timeline with reasoning inspection

class RunReplay {
  constructor() {
    this.currentRun = null;
    this.currentStepIndex = 0;
    this.isPlaying = false;
    this.playbackSpeed = 1;

    this.setupEventListeners();
  }

  setupEventListeners() {
    window.addEventListener('run:opened', (e) => {
      this.loadRun(e.detail);
    });

    document.addEventListener('click', (e) => {
      if (e.target.id === 'replay-play') this.play();
      if (e.target.id === 'replay-pause') this.pause();
      if (e.target.id === 'replay-prev') this.previousStep();
      if (e.target.id === 'replay-next') this.nextStep();
    });
  }

  loadRun(run) {
    this.currentRun = run;
    this.currentStepIndex = 0;
    this.renderTimeline();
  }

  renderTimeline() {
    if (!this.currentRun || !this.currentRun.timeline || !document) return;

    const timeline = document.getElementById('run-timeline');
    if (!timeline) return;

    timeline.innerHTML = '';

    const events = this.currentRun.timeline;
    if (!Array.isArray(events)) return;

    events.forEach((event, index) => {
      const item = document.createElement('div');
      item.className = `tl-item ${event.type || 'step'}`;
      if (event.status === 'failed') item.classList.add('fail');
      if (event.status === 'denied') item.classList.add('denied');

      item.innerHTML = `
        <div class="tl-head">
          <span>${event.type === 'tool' ? '🔧' : event.type === 'thought' ? '💭' : '→'} ${event.title || 'Step'}</span>
          <small>${this.formatTime(event.timestamp)}</small>
        </div>
        ${event.content ? `<div class="tl-body">${this.escapeHtml(event.content)}</div>` : ''}
        ${event.status ? `<span class="tl-tag ${event.status}">${event.status.toUpperCase()}</span>` : ''}
      `;

      item.addEventListener('click', () => this.selectStep(index));
      timeline.appendChild(item);
    });

    this.addReplayControls();
  }

  addReplayControls() {
    const modal = document.getElementById('run-modal');
    if (!modal) return;

    let controls = modal.querySelector('.replay-controls');
    if (!controls) {
      controls = document.createElement('div');
      controls.className = 'replay-controls';
      controls.innerHTML = `
        <button id="replay-prev" class="btn-secondary" title="Previous step">◀ Prev</button>
        <button id="replay-play" class="btn-primary" title="Play">▶ Play</button>
        <button id="replay-pause" class="btn-secondary" title="Pause">⏸ Pause</button>
        <button id="replay-next" class="btn-secondary" title="Next step">Next ▶</button>
        <span class="replay-info">Step <span id="step-counter">0</span> of <span id="step-total">0</span></span>
      `;
      const summary = modal.querySelector('#run-summary');
      if (summary) summary.parentNode.insertBefore(controls, summary.nextSibling);
    }

    document.getElementById('step-counter').textContent = this.currentStepIndex + 1;
    document.getElementById('step-total').textContent = this.currentRun.timeline.length;
  }

  selectStep(index) {
    this.currentStepIndex = index;
    this.highlightStep();
    this.renderStepDetails();
  }

  highlightStep() {
    document.querySelectorAll('#run-timeline .tl-item').forEach((el, idx) => {
      el.classList.toggle('active', idx === this.currentStepIndex);
    });
  }

  renderStepDetails() {
    if (!this.currentRun || !this.currentRun.timeline[this.currentStepIndex]) return;

    const step = this.currentRun.timeline[this.currentStepIndex];
    const details = document.querySelector('.tl-details');

    if (details) {
      details.innerHTML = `
        <h4>${step.title}</h4>
        <dl>
          <dt>Type</dt><dd>${step.type}</dd>
          <dt>Status</dt><dd><span class="status-badge ${step.status}">${step.status}</span></dd>
          <dt>Duration</dt><dd>${step.duration}ms</dd>
          ${step.toolName ? `<dt>Tool</dt><dd>${step.toolName}</dd>` : ''}
          ${step.input ? `<dt>Input</dt><dd><pre>${JSON.stringify(step.input, null, 2)}</pre></dd>` : ''}
          ${step.output ? `<dt>Output</dt><dd><pre>${JSON.stringify(step.output, null, 2)}</pre></dd>` : ''}
        </dl>
      `;
    }

    this.updateStepCounter();
  }

  updateStepCounter() {
    const counter = document.getElementById('step-counter');
    if (counter) counter.textContent = this.currentStepIndex + 1;
  }

  play() {
    this.isPlaying = true;
    this.autoAdvance();
  }

  pause() {
    this.isPlaying = false;
  }

  autoAdvance() {
    if (!this.isPlaying) return;

    if (this.currentStepIndex < this.currentRun.timeline.length - 1) {
      this.currentStepIndex++;
      this.highlightStep();
      this.renderStepDetails();

      const delay = 1000 / this.playbackSpeed;
      setTimeout(() => this.autoAdvance(), delay);
    } else {
      this.isPlaying = false;
    }
  }

  nextStep() {
    if (this.currentStepIndex < this.currentRun.timeline.length - 1) {
      this.currentStepIndex++;
      this.highlightStep();
      this.renderStepDetails();
    }
  }

  previousStep() {
    if (this.currentStepIndex > 0) {
      this.currentStepIndex--;
      this.highlightStep();
      this.renderStepDetails();
    }
  }

  formatTime(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.runReplay = new RunReplay();
});
