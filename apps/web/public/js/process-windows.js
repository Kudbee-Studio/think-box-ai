// Process windows: every agent (a convoy worker) has its own popup, and each step deeper opens another popup layered over it.
//   Agent  ->  Run steps  ->  Tool call  ->  Evidence
// They are ordinary .modal-backdrop panels, so the window manager adopts them: they get a title bar, a taskbar entry, drag/resize and z-order, and a new
// one opens over the one that opened it. Opening a window that is already open brings it to the front. All data comes from the convoy API
// (GET /api/convoys/:id and /api/beads); open windows re-read it on every `convoy:update`. Built with createElement/textContent only.
(function (root) {
  'use strict';

  var SIZES = { agent: '540x600', run: '540x540', tool: '580x520', evidence: '580x540' };
  var LANE_LABEL = { ready: 'READY', open: 'OPEN', review: 'REVIEW', finished: 'FINISHED' };

  function short(id) { return String(id || '').slice(0, 8); }
  function usd(n) { return n === null || n === undefined ? 'unmeasured' : '$' + Number(n).toFixed(Number(n) < 0.01 ? 5 : 4); }
  function ms(n) { return n === null || n === undefined ? '—' : (Number(n) / 1000).toFixed(1) + 's'; }
  function pretty(v) { try { return JSON.stringify(v, null, 2); } catch (e) { return String(v); } }

  function ProcessWindows(options) {
    options = options || {};
    this.doc = options.document || root.document;
    this.win = options.window || root;
    this.fetch = options.fetch || (root.fetch ? root.fetch.bind(root) : null);
    this.open_ = {};
    this.mounted = false;
  }

  ProcessWindows.prototype.mount = function () {
    if (this.mounted) return true;
    var self = this;
    if (this.win.addEventListener) this.win.addEventListener('convoy:update', function () { self.refreshAll(); });
    this.mounted = true;
    return true;
  };

  ProcessWindows.prototype._json = function (path) {
    if (!this.fetch) return Promise.reject(new Error('fetch unavailable'));
    return this.fetch(path).then(function (res) { return res.json().then(function (b) { if (!res.ok) throw new Error(b && b.error ? b.error : 'HTTP ' + res.status); return b; }); });
  };

  ProcessWindows.prototype._el = function (tag, cls, text) {
    var e = this.doc.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = String(text);
    return e;
  };

  ProcessWindows.prototype._key = function (kind, ctx) {
    return ['pw', kind, short(ctx.convoyId), ctx.workerId || '', ctx.runId ? short(ctx.runId) : '', ctx.stepIndex === undefined ? '' : String(ctx.stepIndex)].filter(function (x, i) { return i < 3 || x !== ''; }).join('-').replace(/[^a-zA-Z0-9_-]/g, '_');
  };

  /** Open (or bring forward) the window of this kind. Returns its element. */
  ProcessWindows.prototype.open = function (kind, ctx) {
    if (!SIZES[kind] || !ctx || !ctx.convoyId) return null;
    var key = this._key(kind, ctx);
    var rec = this.open_[key];
    if (rec && rec.el && rec.el.parentNode) {
      rec.el.hidden = false;
      this._raise(rec.el);
      this._load(rec);
      return rec.el;
    }
    rec = { key: key, kind: kind, ctx: ctx, el: this._create(kind, key, ctx), data: null, error: '' };
    this.open_[key] = rec;
    this._load(rec);
    return rec.el;
  };

  ProcessWindows.prototype._raise = function (el) {
    var wm = this.win.windowManager || root.windowManager;
    if (wm && typeof wm.raise === 'function' && el.dataset && el.dataset.wmKey) wm.raise(el.dataset.wmKey);
  };

  ProcessWindows.prototype.close = function (key) {
    var rec = this.open_[key];
    if (!rec) return;
    if (rec.el && rec.el.remove) rec.el.remove();
    delete this.open_[key];
  };

  ProcessWindows.prototype.openKeys = function () { return Object.keys(this.open_); };

  ProcessWindows.prototype._create = function (kind, key, ctx) {
    var self = this;
    var el = this.doc.createElement('div');
    el.className = 'modal-backdrop process-window process-window-' + kind;
    el.id = key;
    if (el.dataset) { el.dataset.wmSize = SIZES[kind]; el.dataset.processKind = kind; el.dataset.convoyId = ctx.convoyId; }
    var section = this._el('section', 'modal modal-wide process-modal');
    section.setAttribute('role', 'dialog');
    section.setAttribute('aria-modal', 'true');
    var header = this._el('div', 'modal-header');
    var wrap = this._el('div');
    wrap.appendChild(this._el('span', 'modal-eyebrow', kind.toUpperCase()));
    var h2 = this._el('h2', 'pw-title', kind === 'agent' ? 'Agent' : kind === 'run' ? 'Run steps' : kind === 'tool' ? 'Tool call' : 'Evidence');
    wrap.appendChild(h2);
    var close = this._el('button', 'btn-icon pw-close', '×');
    close.type = 'button'; close.setAttribute('title', 'Close'); close.setAttribute('aria-label', 'Close ' + kind + ' window');
    close.addEventListener('click', function () { self.close(key); });
    header.appendChild(wrap); header.appendChild(close);
    var body = this._el('div', 'pw-body');
    section.appendChild(header); section.appendChild(body);
    el.appendChild(section);
    this.doc.body.appendChild(el);
    return el;
  };

  ProcessWindows.prototype._load = function (rec) {
    var self = this;
    var calls = [this._json('/api/convoys/' + encodeURIComponent(rec.ctx.convoyId))];
    if (rec.kind === 'agent') calls.push(this._json('/api/beads?type=task').catch(function () { return { beads: [] }; }));
    return Promise.all(calls).then(function (r) { rec.data = { convoy: r[0].convoy, beads: r[1] ? r[1].beads : [] }; rec.error = ''; self._render(rec); }, function (err) { rec.error = String(err && err.message || err); self._render(rec); });
  };

  ProcessWindows.prototype.refreshAll = function () {
    var self = this;
    Object.keys(this.open_).forEach(function (k) { var rec = self.open_[k]; if (rec.el && rec.el.parentNode) self._load(rec); else delete self.open_[k]; });
  };

  // ── rendering ──────────────────────────────────────────────────────────────
  ProcessWindows.prototype._row = function (label, value, cls) {
    var row = this._el('div', 'pw-row');
    row.appendChild(this._el('span', 'pw-label', label));
    row.appendChild(this._el('span', 'pw-value' + (cls ? ' ' + cls : ''), value));
    return row;
  };

  ProcessWindows.prototype._button = function (label, cls, handler) {
    var b = this._el('button', cls, label); b.type = 'button'; b.addEventListener('click', handler); return b;
  };

  ProcessWindows.prototype._render = function (rec) {
    var body = rec.el.querySelector('.pw-body');
    if (!body) return;
    while (body.firstChild) body.removeChild(body.firstChild);
    if (rec.error) { var err = this._el('div', 'pw-error', rec.error); err.setAttribute('role', 'alert'); body.appendChild(err); return; }
    if (!rec.data) { body.appendChild(this._el('div', 'pw-muted', 'Loading…')); return; }
    var c = rec.data.convoy;
    var title = rec.el.querySelector('.pw-title');
    if (rec.kind === 'agent') this._agent(rec, body, c, title);
    else if (rec.kind === 'run') this._run(rec, body, c, title);
    else if (rec.kind === 'tool') this._tool(rec, body, c, title);
    else this._evidence(rec, body, c, title);
  };

  ProcessWindows.prototype._agent = function (rec, body, c, title) {
    var self = this;
    var w = (c.workers || []).find(function (x) { return x.id === rec.ctx.workerId; });
    if (!w) { body.appendChild(this._el('div', 'pw-error', 'This agent is no longer part of the convoy.')); return; }
    if (title) title.textContent = w.name + ' · ' + (w.model || 'no model');
    var lane = c.lanes && c.lanes[w.id] ? c.lanes[w.id] : null;
    var bead = (rec.data.beads || []).find(function (b) { return b.convoy_id === c.id && b.worker_id === w.id; }) || null;
    var head = this._el('div', 'pw-head');
    head.appendChild(this._el('span', 'pw-lane pw-lane-' + (lane ? lane.lane : 'none'), lane ? LANE_LABEL[lane.lane] : 'NOT READY'));
    head.appendChild(this._el('span', 'pw-state', w.status.toUpperCase() + (lane ? ' · ' + lane.detail : '')));
    body.appendChild(head);
    body.appendChild(this._row('Goal', c.goal));
    body.appendChild(this._row('Bead', bead ? bead.id + ' · ' + bead.status + (bead.ready ? ' · ready' : '') : '—'));
    if (bead && bead.blocked_by && bead.blocked_by.length) body.appendChild(this._row('Blocked by', bead.blocked_by.join(', ')));
    if (bead && bead.waiting_for) body.appendChild(this._row('Waiting for', bead.waiting_for === 'approval' ? 'a human to approve the plan' : 'other beads to close'));
    body.appendChild(this._row('Convoy', short(c.id) + ' · ' + c.state + (c.outcome ? ' · ' + c.outcome : '') + ' · mode ' + String((c.plan && c.plan.think_mode) || 'observe').toUpperCase()));
    body.appendChild(this._row('Work', w.tool_calls + ' tool call(s) · ' + w.tokens + ' tokens · ' + usd(w.cost_usd) + ' · ' + ms(w.duration_ms)));
    if (w.grounding) {
      body.appendChild(this._row('Grounding', w.grounding.status + ' (' + w.grounding.classification + ')', w.grounding.status === 'GROUNDED' ? 'pw-ok' : 'pw-bad'));
      (w.grounding.unsupported || []).forEach(function (u) { body.appendChild(self._row('Unsupported', u.kind + ': ' + u.claim + ' (' + u.why + ')', 'pw-bad')); });
    }
    if (w.failure) body.appendChild(this._row('Failure', w.failure.kind + ': ' + w.failure.message, 'pw-bad'));
    if (w.answer) body.appendChild(this._row('Result', w.answer));
    if (c.review && c.review.state !== 'not_required') body.appendChild(this._row('Outcome review', c.review.state + (c.review.decided_by ? ' by ' + c.review.decided_by : '') + (c.review.note ? ': ' + c.review.note : '')));

    var actions = this._el('div', 'pw-actions');
    var run = w.run_id ? (c.runs || []).find(function (r) { return r.id === w.run_id; }) : null;
    if (run) actions.appendChild(this._button('Run steps ›', 'btn-primary pw-go-run', function () { self.open('run', { convoyId: c.id, workerId: w.id, runId: run.id }); }));
    if ((c.evidence && c.evidence.length) || (c.repo_evidence && c.repo_evidence.length) || c.finding) actions.appendChild(this._button('Evidence ›', 'btn-secondary pw-go-evidence', function () { self.open('evidence', { convoyId: c.id, workerId: w.id }); }));
    actions.appendChild(this._button('Convoy ›', 'btn-secondary pw-go-convoy', function () { var cw = self.win.convoyWindow; if (cw) { cw.selected = c.id; cw.detail = null; cw.open(); } }));
    if (lane && lane.lane === 'review') {
      actions.appendChild(this._button('Accept outcome', 'btn-primary pw-accept', function () { self._review(c.id, 'accept'); }));
      actions.appendChild(this._button('Reject outcome', 'btn-secondary pw-reject', function () { self._review(c.id, 'reject'); }));
    }
    if (c.state === 'RUNNING') actions.appendChild(this._button('Stop convoy', 'btn-danger pw-stop', function () { self._event('convoy:stop', { id: c.id }); }));
    body.appendChild(actions);
  };

  ProcessWindows.prototype._event = function (name, detail) {
    var EventCtor = this.win.CustomEvent || root.CustomEvent;
    if (EventCtor && this.win.dispatchEvent) this.win.dispatchEvent(new EventCtor(name, { detail: detail }));
  };
  ProcessWindows.prototype._review = function (id, decision) { this._event('convoy:review', { id: id, decision: decision }); };

  ProcessWindows.prototype._runOf = function (c, rec) { return (c.runs || []).find(function (r) { return r.id === rec.ctx.runId; }) || null; };

  ProcessWindows.prototype._run = function (rec, body, c, title) {
    var self = this;
    var run = this._runOf(c, rec);
    if (!run) { body.appendChild(this._el('div', 'pw-error', 'This run is no longer on the convoy.')); return; }
    if (title) title.textContent = 'Run · ' + (run.model || '') + ' · ' + short(run.id);
    body.appendChild(this._row('Status', String(run.status).toUpperCase() + (run.error ? ' · ' + run.error : '')));
    body.appendChild(this._row('Cost', usd(run.cost_usd) + ' · ' + ((run.prompt_tokens || 0) + (run.completion_tokens || 0)) + ' tokens · ' + (run.tool_calls || 0) + ' tool call(s)'));
    var list = this._el('div', 'pw-steps'); list.setAttribute('role', 'list');
    (run.steps || []).forEach(function (s, i) {
      if (s.kind === 'tool') {
        var b = self._el('button', 'pw-step pw-step-tool' + (s.ok ? '' : ' pw-step-bad'), 'tool ' + s.name + ' · ' + (s.ok ? 'ok' : 'FAILED') + ' · ' + ms(s.latency_ms) + (s.approval ? ' · ' + s.approval : '') + ' ›');
        b.type = 'button'; b.setAttribute('role', 'listitem');
        b.addEventListener('click', function () { self.open('tool', { convoyId: c.id, workerId: rec.ctx.workerId, runId: run.id, stepIndex: i }); });
        list.appendChild(b);
      } else {
        var m = self._el('div', 'pw-step pw-step-model'); m.setAttribute('role', 'listitem');
        m.appendChild(self._el('div', null, 'model step ' + s.step + ' · ' + (s.prompt_tokens || 0) + '+' + (s.completion_tokens || 0) + ' tok · ' + ms(s.latency_ms) + ((s.tool_calls || []).length ? ' → ' + s.tool_calls.join(', ') : ' → answer')));
        if (s.content) m.appendChild(self._el('div', 'pw-muted', String(s.content).slice(0, 260)));
        list.appendChild(m);
      }
    });
    if (!(run.steps || []).length) list.appendChild(this._el('div', 'pw-muted', 'No steps were recorded.'));
    body.appendChild(list);
  };

  ProcessWindows.prototype._tool = function (rec, body, c, title) {
    var self = this;
    var run = this._runOf(c, rec);
    var s = run && run.steps ? run.steps[rec.ctx.stepIndex] : null;
    if (!s || s.kind !== 'tool') { body.appendChild(this._el('div', 'pw-error', 'This tool call is no longer on the run.')); return; }
    if (title) title.textContent = 'Tool · ' + s.name;
    body.appendChild(this._row('Result', s.ok ? 'ok' : 'FAILED' + (s.error ? ': ' + s.error : ''), s.ok ? 'pw-ok' : 'pw-bad'));
    body.appendChild(this._row('Latency', ms(s.latency_ms)));
    if (s.approval) body.appendChild(this._row('Approval', s.approval + (s.approval_reason ? ' — ' + s.approval_reason : '')));
    body.appendChild(this._el('div', 'pw-label', 'Arguments'));
    body.appendChild(this._el('pre', 'pw-pre', pretty(s.args)));
    body.appendChild(this._el('div', 'pw-label', 'Output (stored output is cut at 1500 characters)'));
    body.appendChild(this._el('pre', 'pw-pre', String(s.output || s.error || '')));
    var actions = this._el('div', 'pw-actions');
    if (/live_lookup|repo_search|repo_read/.test(s.name)) actions.appendChild(this._button('Evidence ›', 'btn-primary pw-go-evidence', function () { self.open('evidence', { convoyId: c.id, workerId: rec.ctx.workerId }); }));
    if (actions.firstChild) body.appendChild(actions);
  };

  ProcessWindows.prototype._evidence = function (rec, body, c, title) {
    var self = this;
    if (title) title.textContent = 'Evidence · convoy ' + short(c.id);
    var any = false;
    if (c.grounding) { any = true; body.appendChild(this._row('Grounding', c.grounding.status + ' (' + c.grounding.classification + ')', c.grounding.status === 'GROUNDED' ? 'pw-ok' : 'pw-bad')); (c.grounding.unsupported || []).forEach(function (u) { body.appendChild(self._row('Unsupported', u.kind + ': ' + u.claim + ' (' + u.why + ')', 'pw-bad')); }); }
    if (c.finding) {
      any = true;
      body.appendChild(this._row('Finding', c.finding.found ? c.finding.file + ':' + c.finding.line + ' — ' + c.finding.claim : 'none: ' + c.finding.reason));
      if (c.finding.quote) body.appendChild(this._row('Quote', c.finding.quote));
      if (c.finding_check) body.appendChild(this._row('Disk re-check', c.finding_check.disk_verified ? 'the quote is on disk' : 'FAILED: ' + (c.finding_check.reason || ''), c.finding_check.disk_verified ? 'pw-ok' : 'pw-bad'));
    }
    (c.evidence || []).forEach(function (e) {
      any = true;
      var box = self._el('div', 'pw-evidence');
      box.appendChild(self._el('div', 'pw-label', e.recipe + ' · ' + e.repo + ' · ' + (e.items || []).length + ' item(s) · ' + e.latency_ms + ' ms' + (e.complete ? '' : ' · cut off')));
      box.appendChild(self._el('div', 'pw-muted', e.source_url + ' · fetched ' + e.fetched_at));
      (e.items || []).forEach(function (i) { box.appendChild(self._el('div', 'pw-item', i.kind === 'branch' ? i.name : i.kind === 'run' ? i.name + ' on ' + i.branch + ': ' + (i.conclusion || i.status) + ' (run ' + i.run_number + ')' : '#' + i.number + ' ' + i.title + ' (' + i.state + ') ' + i.url)); });
      body.appendChild(box);
    });
    (c.repo_evidence || []).forEach(function (e) {
      any = true;
      var box = self._el('div', 'pw-evidence');
      if (e.tool === 'repo_search') {
        box.appendChild(self._el('div', 'pw-label', 'search "' + e.query + '"' + (e.path ? ' in ' + e.path : '') + ' · ' + e.matches.length + ' match(es)' + (e.truncated ? ' (cut off)' : '') + ' · ' + e.files_scanned + ' file(s) scanned'));
        e.matches.slice(0, 12).forEach(function (m) { box.appendChild(self._el('div', 'pw-item', m.path + ':' + m.line + ': ' + m.text)); });
        if (!e.matches.length) box.appendChild(self._el('div', 'pw-item pw-ok', 'NO MATCHES (evidence of absence)'));
      } else {
        box.appendChild(self._el('div', 'pw-label', 'read ' + e.path + ' lines ' + e.start + '-' + e.end + ' of ' + e.total_lines));
        e.lines.slice(0, 40).forEach(function (l) { box.appendChild(self._el('div', 'pw-item', l.n + ': ' + l.text)); });
      }
      body.appendChild(box);
    });
    if (!any) body.appendChild(this._el('div', 'pw-muted', 'This convoy has no evidence yet.'));
  };

  root.ProcessWindows = ProcessWindows;
  if (root.document && root.document.addEventListener) {
    root.processWindows = new ProcessWindows({});
    var start = function () { root.processWindows.mount(); };
    if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', start); else start();
  }
})(typeof window !== 'undefined' ? window : globalThis);
