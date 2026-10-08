// Tools > Audit & spend: what was spent (GET /api/spend) and what was decided (GET /api/audit, with the chain check from /api/audit/verify). Read-only; every value is shown as text.
(function () {
  'use strict';
  function el(doc, cls, text) { var e = doc.createElement('div'); e.className = cls; if (text !== undefined) e.textContent = text; return e; }
  function usd(n) { return '$' + (Number(n) || 0).toFixed(2); }
  function usedPercent(spent, limit) { return limit > 0 ? Math.min(100, Math.round((spent / limit) * 100)) : 0; }

  function renderSpend(s, doc) {
    var box = el(doc, 'audit-spend');
    var row = el(doc, 'audit-figures');
    [['Today', s.today_usd], ['Last 7 days', s.last_7d_usd], ['All time', s.all_time_usd]].forEach(function (f) {
      var cell = el(doc, 'audit-figure'); cell.appendChild(el(doc, 'audit-figure-value', usd(f[1]))); cell.appendChild(el(doc, 'audit-figure-label', f[0])); row.appendChild(cell);
    });
    box.appendChild(row);
    var daily = (s.budget && s.budget.daily) || 0; var perRun = (s.budget && s.budget.run) || 0;
    if (!daily && !perRun) box.appendChild(el(doc, 'audit-note', 'No spend limit set. Set KUDBEE_DAILY_BUDGET_USD to stop runs at a daily amount.'));
    if (daily) {
      var pct = usedPercent(s.today_usd, daily);
      box.appendChild(el(doc, 'audit-note', 'Daily limit ' + usd(daily) + ': ' + pct + '% used'));
      var bar = el(doc, 'audit-bar' + (pct >= 80 ? ' audit-bar-warn' : '')); var fill = el(doc, 'audit-bar-fill'); fill.style.width = pct + '%'; bar.appendChild(fill); box.appendChild(bar);
      if (pct >= 80) box.appendChild(el(doc, 'audit-warning', 'Near the daily limit: runs stop when it is reached.'));
    }
    if (perRun) box.appendChild(el(doc, 'audit-note', 'Per-run limit ' + usd(perRun)));
    (s.by_model || []).forEach(function (m) { box.appendChild(el(doc, 'audit-model', m.model + ': ' + usd(m.cost_usd) + ' over ' + m.runs + ' runs')); });
    return box;
  }

  function renderAudit(a, chain, doc) {
    var box = el(doc, 'audit-log');
    box.appendChild(chain.ok ? el(doc, 'audit-chain audit-chain-ok', 'Chain intact (' + chain.entries + ' entries)') : el(doc, 'audit-chain audit-chain-bad', 'Chain BROKEN at entry ' + chain.broken_at + ': ' + chain.reason));
    var events = a.events || [];
    if (!events.length) box.appendChild(el(doc, 'audit-note', 'Nothing recorded yet. Approvals, finished runs and repository decisions appear here.'));
    events.forEach(function (e) {
      var row = el(doc, 'audit-event');
      row.appendChild(el(doc, 'audit-when', new Date(e.ts).toISOString().replace('T', ' ').slice(0, 19)));
      row.appendChild(el(doc, 'audit-kind', String(e.kind).replace(/_/g, ' ')));
      row.appendChild(el(doc, 'audit-actor', e.actor));
      row.appendChild(el(doc, 'audit-run', e.run_id ? String(e.run_id).slice(0, 8) : ''));
      row.appendChild(el(doc, 'audit-summary', e.summary));
      box.appendChild(row);
    });
    return box;
  }

  function init(doc, fetchFn) {
    var btn = doc.getElementById('audit-button'); var panel = doc.getElementById('audit-panel'); var out = doc.getElementById('audit-container');
    if (!btn || !panel || !out) return;
    function json(u) { return fetchFn(u).then(function (r) { return r.json(); }); }
    function load() {
      out.textContent = 'Loading…';
      return Promise.all([json('/api/spend'), json('/api/audit?limit=50'), json('/api/audit/verify')]).then(function (r) {
        out.textContent = '';
        out.appendChild(renderSpend(r[0], doc)); out.appendChild(renderAudit(r[1], r[2], doc));
      }).catch(function () { out.textContent = 'Could not load the audit log.'; });
    }
    btn.addEventListener('click', function () { panel.hidden = false; load(); });
    var close = doc.getElementById('close-audit');
    if (close) close.addEventListener('click', function () { panel.hidden = true; });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { init: init, renderSpend: renderSpend, renderAudit: renderAudit, usedPercent: usedPercent };
  if (typeof document !== 'undefined') init(document, function (u) { return fetch(u); });
})();
