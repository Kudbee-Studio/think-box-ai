// Tools > Job templates: ready goals for common repository jobs (GET /api/job-templates). "Put in goal box" fills the goal box with the finished goal; the person reads it and presses run.
(function () {
  'use strict';
  function el(doc, tag, cls, text) { var e = doc.createElement(tag); e.className = cls; if (text !== undefined) e.textContent = text; return e; }

  function render(data, hasRepo, onUse, doc) {
    var box = el(doc, 'div', 'jobs-list');
    if (!hasRepo) box.appendChild(el(doc, 'div', 'jobs-warning', 'No repository is chosen. In Files, pick a cloned repository and press "Use for agent" first; these jobs work on that repository.'));
    (data.templates || []).forEach(function (t) {
      var card = el(doc, 'div', 'jobs-card');
      card.appendChild(el(doc, 'div', 'jobs-name', t.name));
      card.appendChild(el(doc, 'div', 'jobs-desc', t.description));
      var input = null;
      if (t.param) { input = el(doc, 'input', 'jobs-input'); input.placeholder = t.param.label + ': ' + t.param.placeholder; input.maxLength = 300; card.appendChild(input); }
      var btn = el(doc, 'button', 'btn-secondary jobs-use', 'Put in goal box');
      btn.addEventListener('click', function () { onUse(t, input ? input.value : ''); });
      card.appendChild(btn);
      box.appendChild(card);
    });
    return box;
  }

  function useTemplate(t, value, doc, fetchFn) {
    return fetchFn('/api/job-templates/' + encodeURIComponent(t.id), { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ input: value }) })
      .then(function (r) { return r.json(); })
      .then(function (r) {
        var goalBox = doc.getElementById('goal-input');
        if (!r.goal || !goalBox) return { ok: false, error: r.error || 'The goal box was not found.' };
        goalBox.value = r.goal;
        if (goalBox.dispatchEvent && typeof Event !== 'undefined') goalBox.dispatchEvent(new Event('input', { bubbles: true }));
        if (goalBox.focus) goalBox.focus();
        return { ok: true };
      });
  }

  function init(doc, fetchFn) {
    var btn = doc.getElementById('jobs-button'); var panel = doc.getElementById('jobs-panel'); var out = doc.getElementById('jobs-container');
    if (!btn || !panel || !out) return;
    btn.addEventListener('click', function () {
      panel.hidden = false; out.textContent = 'Loading…';
      Promise.all([fetchFn('/api/job-templates').then(function (r) { return r.json(); }), fetchFn('/api/repo/active').then(function (r) { return r.json(); }).catch(function () { return { active: null }; })]).then(function (r) {
        out.textContent = '';
        out.appendChild(render(r[0], !!r[1].active, function (t, v) {
          useTemplate(t, v, doc, fetchFn).then(function (res) { if (res.ok) panel.hidden = true; else { var msg = el(doc, 'div', 'jobs-warning', res.error); out.insertBefore(msg, out.firstChild); } });
        }, doc));
      }).catch(function () { out.textContent = 'Could not load the job templates.'; });
    });
    var close = doc.getElementById('close-jobs');
    if (close) close.addEventListener('click', function () { panel.hidden = true; });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { init: init, render: render, useTemplate: useTemplate };
  if (typeof document !== 'undefined') init(document, function (u, o) { return fetch(u, o); });
})();
