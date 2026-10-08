// Tools > Get started: the first-run checklist (GET /api/setup) and the one-line run summary text. The panel opens by itself once on a fresh install (no model connected), until dismissed.
(function () {
  'use strict';
  var DISMISS = 'kudbee-setup-dismissed';
  function summaryText(s) {
    if (!s || !s.headline) return '';
    return ['— ' + s.headline].concat((s.lines || []).map(function (l) { return '  ' + l; }), (s.next || []).map(function (n) { return '  → ' + n; })).join('\n');
  }
  function renderSteps(setup, doc) {
    var box = doc.createElement('div');
    var lead = doc.createElement('p'); lead.className = 'setup-lead';
    lead.textContent = setup.ready ? 'A model is connected. You are ready to run goals.' : 'One thing to do before the first run: connect a model.';
    box.appendChild(lead);
    (setup.steps || []).forEach(function (s) {
      var row = doc.createElement('div'); row.className = 'setup-step ' + (s.done ? 'setup-done' : 'setup-todo');
      var mark = doc.createElement('span'); mark.className = 'setup-mark'; mark.textContent = s.done ? 'Done' : (s.required ? 'To do' : 'Optional');
      var t = doc.createElement('strong'); t.textContent = s.title;
      var h = doc.createElement('span'); h.className = 'setup-hint'; h.textContent = s.hint;
      row.appendChild(mark); row.appendChild(t); row.appendChild(h); box.appendChild(row);
    });
    return box;
  }
  function store(win) { try { return win.localStorage; } catch (e) { return null; } }
  function init(doc, fetchFn, win) {
    var btn = doc.getElementById('setup-button'); var panel = doc.getElementById('setup-panel'); var out = doc.getElementById('setup-container');
    if (!btn || !panel || !out) return;
    function load(auto) {
      out.textContent = 'Checking…';
      return fetchFn('/api/setup').then(function (r) { return r.json(); }).then(function (setup) {
        if (auto && setup.ready) return;
        out.textContent = ''; out.appendChild(renderSteps(setup, doc)); panel.hidden = false;
      }).catch(function () { out.textContent = 'Could not read the setup status.'; });
    }
    btn.addEventListener('click', function () { load(false); });
    var close = doc.getElementById('close-setup');
    if (close) close.addEventListener('click', function () { panel.hidden = true; var st = store(win); if (st) { try { st.setItem(DISMISS, '1'); } catch (e) { /* private window */ } } });
    var st = store(win); var dismissed = false;
    try { dismissed = !!(st && st.getItem(DISMISS)); } catch (e) { dismissed = false; }
    if (!dismissed) load(true);
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { init: init, renderSteps: renderSteps, summaryText: summaryText };
  if (typeof document !== 'undefined') { window.runSummaryText = summaryText; init(document, function (u) { return fetch(u); }, window); }
})();
