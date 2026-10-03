// Terminal-style charts - Apple Terminal aesthetic for dashboard

export class TerminalChart {
  constructor(container) {
    this.container = container;
    this.theme = this.detectTheme();
  }

  detectTheme() {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  drawBarChart(data, options = {}) {
    const { title = '', maxValue = Math.max(...data.map(d => d.value)), width = 60 } = options;
    
    let output = '';
    if (title) output += `\n┌─ ${title} ${'─'.repeat(Math.max(0, width - title.length - 3))}┐\n`;
    
    data.forEach(({ label, value }) => {
      const barWidth = Math.round((value / maxValue) * (width - label.length - 5));
      const bar = '█'.repeat(Math.max(1, barWidth));
      const percentage = ((value / maxValue) * 100).toFixed(0);
      output += `│ ${label.padEnd(label.length)} │ ${bar} ${percentage}%\n`;
    });

    if (title) output += `└${'─'.repeat(width - 1)}┘\n`;
    return output;
  }

  drawLineChart(data, options = {}) {
    const { title = '', height = 10, width = 50 } = options;
    const minValue = Math.min(...data);
    const maxValue = Math.max(...data);
    const range = maxValue - minValue || 1;

    let output = '';
    if (title) output += `\n┌─ ${title} ${'─'.repeat(Math.max(0, width - title.length - 3))}┐\n`;

    const chart = Array(height).fill(null).map(() => Array(data.length).fill(' '));

    data.forEach((value, x) => {
      const normalized = (value - minValue) / range;
      const y = Math.round((1 - normalized) * (height - 1));
      chart[Math.min(y, height - 1)][x] = '●';
    });

    chart.forEach((row, idx) => {
      const yLabel = (maxValue - (idx / (height - 1)) * range).toFixed(0);
      output += `│ ${yLabel.padStart(5)} │ ${row.join('')}\n`;
    });

    if (title) output += `└${'─'.repeat(width - 1)}┘\n`;
    return output;
  }

  drawPieChart(data, options = {}) {
    const { title = '' } = options;
    const total = data.reduce((sum, d) => sum + d.value, 0);
    
    let output = '';
    if (title) output += `\n${title}\n${'='.repeat(title.length)}\n`;

    data.forEach(({ label, value }) => {
      const percentage = ((value / total) * 100).toFixed(1);
      const barLength = Math.round((value / total) * 20);
      const bar = '█'.repeat(barLength) + '░'.repeat(20 - barLength);
      output += `${label.padEnd(12)} │ ${bar} │ ${percentage}%\n`;
    });

    return output;
  }

  render(content) {
    const pre = document.createElement('pre');
    pre.className = `terminal-chart ${this.theme}-theme`;
    pre.textContent = content;
    pre.style.fontFamily = "'Monaco', 'Menlo', 'Ubuntu Mono', monospace";
    pre.style.fontSize = '11px';
    pre.style.lineHeight = '1.4';
    pre.style.padding = '12px';
    pre.style.borderRadius = '6px';
    pre.style.overflow = 'auto';
    pre.style.maxHeight = '300px';
    
    if (this.theme === 'dark') {
      pre.style.background = '#1a1a1a';
      pre.style.color = '#00d600';
      pre.style.border = '1px solid #00d600';
    } else {
      pre.style.background = '#f5f5f5';
      pre.style.color = '#333333';
      pre.style.border = '1px solid #cccccc';
    }

    this.container.innerHTML = '';
    this.container.appendChild(pre);
  }
}

export class TerminalDashboard {
  constructor(container) {
    this.chart = new TerminalChart(container);
  }

  displayAnalytics(kpis, modelDist, failures) {
    let output = this.header('kudbEE Analytics Dashboard');

    output += this.section('Key Performance Indicators');
    kpis.forEach(kpi => {
      const trend = kpi.trend ? (kpi.trend > 0 ? '↑' : '↓') : '→';
      output += `  ${kpi.title.padEnd(20)} ${kpi.value.toString().padStart(10)}  ${trend} ${Math.abs(kpi.trend || 0)}%\n`;
    });

    output += this.section('Model Distribution');
    output += this.chart.drawBarChart(modelDist, { maxValue: 100, width: 50 });

    if (failures.length > 0) {
      output += this.section('Failure Analysis');
      output += this.chart.drawPieChart(failures);
    }

    this.chart.render(output);
  }

  displayTimeline(steps, criticalPath) {
    let output = this.header('Execution Timeline');

    output += this.section('Steps');
    output += `  Total Steps:      ${steps.length}\n`;
    output += `  Critical Path:    ${criticalPath}ms\n`;
    output += `  Success Rate:     ${this.calcSuccessRate(steps)}%\n\n`;

    steps.forEach((step, idx) => {
      const status = step.status === 'success' ? '✓' : step.status === 'failed' ? '✗' : '◇';
      const duration = step.endTime && step.startTime ? step.endTime - step.startTime : 0;
      output += `  ${status} [${idx + 1}] ${step.name.padEnd(20)} ${duration}ms\n`;
    });

    this.chart.render(output);
  }

  displayStats(runs) {
    let output = this.header('Run Statistics');

    const successful = runs.filter(r => r.success).length;
    const failed = runs.filter(r => !r.success).length;
    const avgDuration = runs.length > 0 ? runs.reduce((sum, r) => sum + (r.duration || 0), 0) / runs.length : 0;

    output += this.section('Summary');
    output += `  Total Runs:       ${runs.length}\n`;
    output += `  Successful:       ${successful}\n`;
    output += `  Failed:           ${failed}\n`;
    output += `  Success Rate:     ${runs.length > 0 ? ((successful / runs.length) * 100).toFixed(1) : 0}%\n`;
    output += `  Avg Duration:     ${avgDuration.toFixed(0)}ms\n`;

    this.chart.render(output);
  }

  header(title) {
    const width = 60;
    const padding = Math.floor((width - title.length) / 2);
    return `\n${'═'.repeat(width)}\n  ${' '.repeat(padding)}${title}\n${'═'.repeat(width)}\n`;
  }

  section(title) {
    return `\n┌─ ${title}\n│\n`;
  }

  calcSuccessRate(steps) {
    if (steps.length === 0) return 0;
    return Math.round((steps.filter(s => s.status === 'success').length / steps.length) * 100);
  }
}
