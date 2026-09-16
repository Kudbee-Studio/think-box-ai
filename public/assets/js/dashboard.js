/**
 * KUDBEE Control Dashboard — demo data loader and panel renderers.
 * All metrics are explicitly labeled demo unless a live API is wired later.
 */

document.addEventListener('DOMContentLoaded', () => {
  loadDashboardDemo();
  initCopyButtons();
});

async function loadDashboardDemo() {
  const banner = document.getElementById('demo-banner-text');
  try {
    const response = await fetch('../assets/data/dashboard-demo.json');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (banner && data._label) banner.textContent = data._label;
    renderGovernanceStrip(data.governance);
    renderDemoMetrics(data.burst);
    renderBurstSummary(data.burst);
    renderContrastPairs(data.contrast_pairs);
    renderOpsChips(data.ops);
  } catch (err) {
    if (banner) {
      banner.textContent = 'Demo JSON unavailable — showing inline placeholders.';
    }
    console.warn('Dashboard demo load failed:', err);
  }
}

function renderGovernanceStrip(gov) {
  if (!gov) return;
  setText('gov-admitted', gov.admitted);
  setText('gov-denied', gov.denied);
  setText('gov-last-decision', gov.last_decision || '—');
  setText('gov-last-reason', gov.last_reason || '—');
  const verified = document.getElementById('gov-ledger-verified');
  if (verified) {
    verified.textContent = gov.ledger_verified ? 'Ledger chain verified' : 'Ledger unverified';
    verified.className = `gov-chip ${gov.ledger_verified ? 'gov-chip-ok' : 'gov-chip-warn'}`;
  }
}

function renderDemoMetrics(burst) {
  if (!burst) return;
  setText('metric-groundedness', `${burst.groundedness_pct}%`);
  setText('metric-bind-failure', `${burst.bind_failure_pct}%`);
  setText('metric-reasoning', `${burst.reasoning_coverage_pct}%`);
}

function renderBurstSummary(burst) {
  if (!burst) return;
  setText('burst-id', burst.burst_id);
  setText('burst-pairs', burst.pairs_completed);
  setText('burst-traces', burst.traces_captured);
  setText('burst-model', burst.model);
  setText('burst-output', burst.output_path);
}

function renderContrastPairs(pairs) {
  const container = document.getElementById('contrast-pairs');
  if (!container || !pairs?.length) return;

  container.innerHTML = pairs.map((pair) => `
    <article class="contrast-card card">
      <header class="contrast-card-header">
        <span class="contrast-pair-id">${escapeHtml(pair.pair_id)}</span>
        <span class="demo-tag">demo</span>
      </header>
      <p class="contrast-question">${escapeHtml(pair.question)}</p>
      <div class="contrast-columns">
        <div class="contrast-col contrast-grounded">
          <div class="contrast-col-label">Grounded</div>
          <div class="contrast-answer">${escapeHtml(pair.grounded?.answer ?? '—')}</div>
          <div class="contrast-evidence">${escapeHtml(pair.grounded?.evidence_text || 'No evidence bound')}</div>
          <div class="contrast-meta">confidence ${pair.grounded?.confidence ?? 0}</div>
        </div>
        <div class="contrast-col contrast-ungrounded">
          <div class="contrast-col-label">Ungrounded</div>
          <div class="contrast-answer">${escapeHtml(pair.ungrounded?.answer ?? '—')}</div>
          <div class="contrast-evidence muted">No evidence refs — same surface answer, zero bind</div>
          <div class="contrast-meta">confidence ${pair.ungrounded?.confidence ?? 0}</div>
        </div>
      </div>
    </article>
  `).join('');
}

function renderOpsChips(ops) {
  if (!ops) return;
  setText('ops-gpu', ops.gpu_policy);
  setText('ops-cpu', ops.cpu_worker);
  setText('ops-inference', ops.inference);
}

function initCopyButtons() {
  document.querySelectorAll('[data-copy]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const text = btn.getAttribute('data-copy');
      if (!text) return;
      navigator.clipboard.writeText(text).then(() => {
        if (typeof showToast === 'function') showToast('Copied to clipboard', 'success');
      }).catch(() => {
        if (typeof showToast === 'function') showToast('Copy failed', 'error');
      });
    });
  });
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value ?? '—';
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
