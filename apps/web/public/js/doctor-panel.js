// Tools > Health check: runs the same checks as `kudbee doctor` (GET /api/doctor) and lists them. Read-only; the network checks run only when you ask.
(function () {
  'use strict';
  var LABEL = { ok: 'OK', warn: 'Check', fail: 'Fix', skipped: 'Not run' };
  function render(report, doc) {
    var box = doc.createElement('div');
    report.checks.forEach(function (c) {
      var row = doc.createElement('div');
      row.className = 'doctor-row doctor-' + c.status;
      var tag = doc.createElement('span'); tag.className = 'doctor-tag'; tag.textContent = LABEL[c.status] || c.status;
      var name = doc.createElement('strong'); name.textContent = c.id.replace(/-/g, ' ');
      var detail = doc.createElement('span'); detail.className = 'doctor-detail'; detail.textContent = c.detail;
      row.appendChild(tag); row.appendChild(name); row.appendChild(detail);
      box.appendChild(row);
    });
    var sum = doc.createElement('p'); sum.className = 'doctor-summary';
    sum.textContent = report.ok ? 'No failures.' : 'Failures found. In a terminal: kudbee doctor --fix locks the data folder.';
    box.appendChild(sum);
    return box;
  }
  function init(doc, fetchFn) {
    var btn = doc.getElementById('doctor-button'); var panel = doc.getElementById('doctor-panel'); var out = doc.getElementById('doctor-container');
    if (!btn || !panel || !out) return;
    function load(online) {
      out.textContent = 'Checking…';
      return fetchFn('/api/doctor' + (online ? '?online=1' : '')).then(function (r) { return r.json(); }).then(function (report) {
        out.textContent = '';
        out.appendChild(render(report, doc));
        if (!online) {
          var more = doc.createElement('button'); more.className = 'btn-secondary'; more.textContent = 'Also check dependencies (uses the network)';
          more.addEventListener('click', function () { load(true); });
          out.appendChild(more);
        }
      }).catch(function () { out.textContent = 'Could not run the health check.'; });
    }
    btn.addEventListener('click', function () { panel.hidden = false; load(false); });
    var close = doc.getElementById('close-doctor');
    if (close) close.addEventListener('click', function () { panel.hidden = true; });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { init: init, render: render };
  if (typeof document !== 'undefined') init(document, function (u) { return fetch(u); });
})();
