// Tools > Project: the repository the agent is working on, on one page (GET /api/project). Read-only; every value is shown as text.
(function () {
  'use strict';
  function el(doc, cls, text) { var e = doc.createElement('div'); e.className = cls; if (text !== undefined) e.textContent = text; return e; }
  function usd(n) { return '$' + (Number(n) || 0).toFixed(4); }
  function section(doc, title) { var s = el(doc, 'project-section'); s.appendChild(el(doc, 'project-title', title)); return s; }
  function render(p, doc) {
    var box = el(doc, 'project-home');
    if (!p.repo) { box.appendChild(el(doc, 'project-note', p.note)); return box; }
    var head = el(doc, 'project-head'); head.appendChild(el(doc, 'project-name', p.repo.name)); if (p.repo.repo) head.appendChild(el(doc, 'project-remote', p.repo.repo)); box.appendChild(head);
    (p.next || []).forEach(function (n) { box.appendChild(el(doc, 'project-next', '→ ' + n)); });
    var ch = section(doc, p.changes.count + ' uncommitted ' + (p.changes.count === 1 ? 'change' : 'changes'));
    (p.changes.files || []).forEach(function (f) { ch.appendChild(el(doc, 'project-row', f.path + '  (' + f.status + ')')); });
    box.appendChild(ch);
    var r = section(doc, p.runs.count + ' runs on this repository · ' + p.runs.failed + ' failed · ' + usd(p.runs.total_usd) + ' total · ' + usd(p.runs.today_usd) + ' today');
    r.appendChild(el(doc, 'project-subtitle', 'Recent runs'));
    (p.runs.recent || []).forEach(function (x) { r.appendChild(el(doc, 'project-row project-run-' + x.status, String(x.id).slice(0, 8) + '  ' + x.status + '  ' + usd(x.cost_usd) + '  ' + x.files + ' files  ' + x.goal)); });
    box.appendChild(r);
    var t = section(doc, p.tokens.repo_scoped + ' Think Tokens learned in this repository');
    (p.tokens.titles || []).forEach(function (title) { t.appendChild(el(doc, 'project-row', title)); });
    box.appendChild(t);
    var ev = section(doc, 'Recent repository decisions');
    (p.events || []).forEach(function (e) { ev.appendChild(el(doc, 'project-row', String(e.kind).replace(/_/g, ' ') + '  ·  ' + e.actor + '  ·  ' + e.summary)); });
    box.appendChild(ev);
    box.appendChild(el(doc, 'project-note', p.note));
    return box;
  }
  function init(doc, fetchFn) {
    var btn = doc.getElementById('project-button'); var panel = doc.getElementById('project-panel'); var out = doc.getElementById('project-container');
    if (!btn || !panel || !out) return;
    btn.addEventListener('click', function () {
      panel.hidden = false; out.textContent = 'Loading…';
      fetchFn('/api/project').then(function (r) { return r.json(); }).then(function (p) { out.textContent = ''; out.appendChild(render(p, doc)); }).catch(function () { out.textContent = 'Could not load the project.'; });
    });
    var close = doc.getElementById('close-project');
    if (close) close.addEventListener('click', function () { panel.hidden = true; });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { init: init, render: render };
  if (typeof document !== 'undefined') init(document, function (u) { return fetch(u); });
})();
