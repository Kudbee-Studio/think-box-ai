// Convoys window: the Mayor's plans and the convoys they become, inside the one dashboard.
// ONE row per convoy (child runs never appear as separate rows); click a row to drill down: convoy -> workers/runs -> tools -> evidence.
// A convoy is either PLAN ONLY (nothing has run) or LIVE EXECUTION (a human approved it and real workers ran); the badge says which, always.
// Approving goes through the dashboard WebSocket (event `convoy:approve`, handled by app.js), never through a plain HTTP call.
// Built with createElement/textContent only (no innerHTML).
(function (root) {
  'use strict';

  /** The one-line mode a convoy is in. Pure, so the PLAN ONLY / LIVE EXECUTION distinction is testable. */
  function modeBadge(convoy) {
    if (!convoy) return { text: '', cls: '' };
    switch (convoy.state) {
      case 'PLANNED': return { text: 'PLAN ONLY \u2014 NOTHING HAS RUN', cls: 'convoy-badge-plan' };
      case 'PENDING': return { text: 'PENDING APPROVAL \u2014 NOTHING RUNS YET', cls: 'convoy-badge-pending' };
      case 'REJECTED': case 'EXPIRED': case 'CANCELLED': return { text: convoy.state + ' \u2014 NEVER RAN', cls: 'convoy-badge-stopped' };
      case 'APPROVED': return { text: 'APPROVED \u2014 STARTING LIVE', cls: 'convoy-badge-live' };
      default: return { text: 'LIVE EXECUTION', cls: 'convoy-badge-live' };
    }
  }

  function usd(n) { return n === null || n === undefined ? 'unmeasured' : '$' + Number(n).toFixed(Number(n) < 0.01 ? 5 : 4); }
  function ms(n) { return n === null || n === undefined ? '—' : (Number(n) / 1000).toFixed(1) + 's'; }

  function ConvoyWindow(options) {
    options = options || {};
    this.doc = options.document || root.document;
    this.win = options.window || root;
    this.fetch = options.fetch || (root.fetch ? root.fetch.bind(root) : null);
    this.el = null;
    this.selected = null;
    this.convoys = [];
    this.board = null;
    this.detail = null;
    this.error = '';
    // The form keeps what was typed across re-renders (a plan or a live update rebuilds the window).
    this.form = { goal: '', model: null, workers: '4', cost: '0.10', mode: 'observe' };
    this.mounted = false;
  }

  ConvoyWindow.prototype.mount = function () {
    if (this.mounted) return true;
    var self = this;
    var button = this.doc.getElementById && this.doc.getElementById('convoys-button');
    if (button) button.addEventListener('click', function () { self.toggle(); });
    // The goal bar: take the goal and model already typed there and plan them as a convoy (nothing runs until a human approves the plan).
    var planBtn = this.doc.getElementById && this.doc.getElementById('plan-convoy');
    if (planBtn) planBtn.addEventListener('click', function () {
      var g = self.doc.getElementById('goal-input'); var m = self.doc.getElementById('model-select');
      self.openWith({ goal: g && g.value ? g.value.trim() : '', model: m && m.value ? m.value : '' });
    });
    this._mountChip();
    if (this.win.addEventListener) {
      this.win.addEventListener('convoy:update', function (e) { self.onUpdate(e && e.detail); self.refreshChip(); });
      this.win.addEventListener('convoy:error', function (e) { self.error = e && e.detail && e.detail.error ? String(e.detail.error) : 'convoy error'; self.render(); });
    }
    this.mounted = true;
    return true;
  };

  /** Open the window with a goal and model already filled in (from the goal bar). */
  ConvoyWindow.prototype.openWith = function (preset) {
    if (preset && typeof preset.goal === 'string' && preset.goal) this.form.goal = preset.goal;
    if (preset && typeof preset.model === 'string' && preset.model) this.form.model = preset.model;
    this.open();
    var self = this;
    var focus = function () { var input = self.doc.getElementById && self.doc.getElementById('convoy-goal'); if (input && input.focus) input.focus(); };
    if (this.win.setTimeout) this.win.setTimeout(focus, 60); else focus();
  };

  /** The header chip: the board at a glance (READY / OPEN / REVIEW), and it asks for attention when a result is waiting for a human. */
  ConvoyWindow.prototype._mountChip = function () {
    var self = this;
    if (!this.doc.getElementById || this.doc.getElementById('convoy-chip')) return;
    var anchor = this.doc.getElementById('header-connection');
    if (!anchor || !anchor.parentNode) return;
    var chip = this._el('button', 'convoy-chip', 'Board');
    chip.id = 'convoy-chip'; chip.type = 'button'; chip.title = 'Agent board: READY / OPEN / REVIEW. Click to open the Convoys window.';
    chip.addEventListener('click', function () { self.open(); });
    anchor.parentNode.insertBefore(chip, anchor);
    this.refreshChip();
  };

  ConvoyWindow.prototype._chip = function (b) {
    var chip = this.doc.getElementById && this.doc.getElementById('convoy-chip');
    if (!chip || !b) return;
    var c = b.counts || {};
    chip.textContent = 'READY ' + (c.ready || 0) + ' \u00B7 OPEN ' + (c.open || 0) + ' \u00B7 REVIEW ' + (c.review || 0);
    chip.className = 'convoy-chip' + (c.review ? ' has-review' : '') + (c.open ? ' has-open' : '');
    chip.setAttribute('aria-label', (c.ready || 0) + ' ready, ' + (c.open || 0) + ' open, ' + (c.review || 0) + ' waiting for review');
  };

  // The board is optional chrome: no chip text rather than an error. While the window is open, refresh() already refreshes the chip from the same board read.
  ConvoyWindow.prototype.refreshChip = function () {
    var self = this;
    if (this.el) return Promise.resolve();
    return this._json('/api/convoys/board').then(function (b) { self._chip(b); }, function () {});
  };

  ConvoyWindow.prototype.toggle = function () {
    if (this.el && !this.el.hidden && this.el.parentNode) { this.close(); return; }
    this.open();
  };

  ConvoyWindow.prototype.open = function () {
    if (!this.el || !this.el.parentNode) this.el = this._create();
    this.el.hidden = false;
    this.error = '';
    this.refresh();
  };

  ConvoyWindow.prototype.close = function () {
    if (this.el && this.el.remove) this.el.remove();
    else if (this.el) this.el.hidden = true;
    this.el = null;
  };

  ConvoyWindow.prototype._create = function () {
    var doc = this.doc; var self = this;
    var el = doc.createElement('div');
    el.className = 'modal-backdrop convoy-window';
    el.id = 'convoy-window';
    if (el.dataset) el.dataset.wmSize = '760x620';
    var section = doc.createElement('section');
    section.className = 'modal modal-wide convoy-modal';
    section.setAttribute('role', 'dialog');
    section.setAttribute('aria-modal', 'true');
    var header = doc.createElement('div');
    header.className = 'modal-header';
    var titleWrap = doc.createElement('div');
    var eyebrow = doc.createElement('span'); eyebrow.className = 'modal-eyebrow'; eyebrow.textContent = 'MAYOR';
    var h2 = doc.createElement('h2'); h2.textContent = 'Convoys';
    titleWrap.appendChild(eyebrow); titleWrap.appendChild(h2);
    var close = doc.createElement('button');
    close.className = 'btn-icon convoy-close'; close.setAttribute('title', 'Close'); close.setAttribute('aria-label', 'Close convoys window'); close.textContent = '×';
    close.addEventListener('click', function () { self.close(); });
    header.appendChild(titleWrap); header.appendChild(close);
    var body = doc.createElement('div'); body.className = 'convoy-body';
    section.appendChild(header); section.appendChild(body);
    el.appendChild(section);
    doc.body.appendChild(el);
    return el;
  };

  ConvoyWindow.prototype._json = function (path, init) {
    if (!this.fetch) return Promise.reject(new Error('fetch unavailable'));
    return this.fetch(path, init).then(function (res) {
      return res.json().then(function (body) { if (!res.ok) throw new Error(body && body.error ? body.error : 'HTTP ' + res.status); return body; });
    });
  };

  // One refresh in flight at a time: updates that arrive meanwhile collapse into a single follow-up, so responses never apply out of order.
  ConvoyWindow.prototype.refresh = function () {
    var self = this;
    if (this._refreshing) { this._again = true; return this._refreshing; }
    var p = this._json('/api/convoys/board').then(function (bd) { self.board = bd; self._chip(bd); }, function () { self.board = null; }).then(function () { return self._json('/api/convoys'); }).then(function (b) {
      self.convoys = b.convoys || [];
      if (self.selected) return self._json('/api/convoys/' + encodeURIComponent(self.selected)).then(function (d) { self.detail = d.convoy; });
      return null;
    }).then(function () { self.render(); }, function (err) { self.error = String(err && err.message || err); self.render(); }).then(function () {
      self._refreshing = null;
      if (self._again) { self._again = false; return self.refresh(); }
      return null;
    });
    this._refreshing = p;
    return p;
  };

  // Any live update can move a worker between lanes, so the board, the list and the open detail are all re-read.
  ConvoyWindow.prototype.onUpdate = function (summary) {
    if (!summary || !this.el) return;
    this.refresh();
  };

  ConvoyWindow.prototype.plan = function (goal, model, budget, mode) {
    var self = this;
    this.error = '';
    return this._json('/api/convoys/plan', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ goal: goal, model: model || undefined, worker_budget: budget, mode: mode || undefined }) })
      .then(function (b) { self.selected = b.convoy.id; self.detail = b.convoy; return self.refresh(); })
      .catch(function (err) { self.error = String(err && err.message || err); self.render(); });
  };

  ConvoyWindow.prototype.act = function (id, action) {
    var self = this;
    this.error = '';
    return this._json('/api/convoys/' + encodeURIComponent(id) + '/' + action, { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}' })
      .then(function (b) { self.detail = b.convoy; return self.refresh(); })
      .catch(function (err) { self.error = String(err && err.message || err); self.render(); });
  };

  ConvoyWindow.prototype.review = function (id, decision) {
    var EventCtor = this.win.CustomEvent || root.CustomEvent;
    if (EventCtor && this.win.dispatchEvent) this.win.dispatchEvent(new EventCtor('convoy:review', { detail: { id: id, decision: decision } }));
  };

  /** READY / OPEN / REVIEW / FINISHED for every worker. REVIEW means a result is waiting for a human to accept or reject it. */
  ConvoyWindow.prototype._board = function () {
    var self = this; var b = this.board;
    var wrap = this._el('div', 'convoy-board'); wrap.id = 'convoy-board'; wrap.setAttribute('aria-label', 'Agent board');
    [['ready', 'READY', 'unblocked work waiting for an agent'], ['open', 'OPEN', 'an agent is working on it'], ['review', 'REVIEW', 'a result is waiting for a human to accept or reject it'], ['finished', 'FINISHED', 'accepted, rejected, failed or stopped']].forEach(function (lane) {
      var col = self._el('div', 'convoy-lane convoy-lane-' + lane[0]); col.dataset.lane = lane[0]; col.title = lane[2];
      col.appendChild(self._el('div', 'convoy-lane-head', lane[1] + ' \u00B7 ' + ((b.counts && b.counts[lane[0]]) || 0)));
      ((b.lanes && b.lanes[lane[0]]) || []).slice(0, 6).forEach(function (card) {
        var el = self._el('div', 'convoy-card'); el.dataset.convoyId = card.convoy_id;
        var open = self._el('button', 'convoy-card-open', card.name + ' \u00B7 ' + (card.model || 'no model')); open.type = 'button';
        // A card is an agent: its own window opens over this one, and goes deeper from there (Run steps, Tool call, Evidence).
        open.addEventListener('click', function () {
          self.selected = card.convoy_id; self.detail = null; self.refresh();
          var pw = self.win.processWindows || root.processWindows;
          if (pw) pw.open('agent', { convoyId: card.convoy_id, workerId: card.worker_id });
        });
        el.appendChild(open);
        el.appendChild(self._el('div', 'convoy-card-goal', card.goal));
        el.appendChild(self._el('div', 'convoy-card-detail', card.detail));
        if (lane[0] === 'review') {
          var row = self._el('div', 'convoy-card-actions');
          row.appendChild(self._button('Accept', 'btn-primary convoy-card-accept', function () { self.review(card.convoy_id, 'accept'); }));
          row.appendChild(self._button('Reject', 'btn-secondary convoy-card-reject', function () { self.review(card.convoy_id, 'reject'); }));
          el.appendChild(row);
        }
        col.appendChild(el);
      });
      wrap.appendChild(col);
    });
    if (b.not_ready) wrap.appendChild(self._el('div', 'convoy-line convoy-board-note', b.not_ready + ' worker(s) not on the board yet: their plan is waiting for approval or for a worker they depend on.'));
    return wrap;
  };

  ConvoyWindow.prototype.stop = function (id) {
    var EventCtor = this.win.CustomEvent || root.CustomEvent;
    if (EventCtor && this.win.dispatchEvent) this.win.dispatchEvent(new EventCtor('convoy:stop', { detail: { id: id } }));
  };

  ConvoyWindow.prototype._jobState = function (c) {
    var self = this; var js = c.job_state;
    var sec = this._section('Think Token \u00B7 job state \u00B7 mode ' + String((c.plan && c.plan.think_mode) || 'observe').toUpperCase());
    sec.id = 'convoy-jobstate';
    var line = this._el('div', 'convoy-line', 'Stage ' + js.stage + ' \u00B7 verdict ' + (js.verdict || 'none yet') + (js.stable ? ' \u00B7 STABLE' : '') + ' \u00B7 ' + js.summary.activeCount + ' active, ' + js.summary.lockedCount + ' verified, ' + js.summary.disruptedCount + ' disrupted');
    sec.appendChild(line);
    var grid = this._el('div', 'convoy-cube'); grid.setAttribute('role', 'img'); grid.setAttribute('aria-label', 'Job state: 100 cells, ' + js.summary.activeCount + ' active, ' + js.summary.lockedCount + ' verified');
    js.cells.forEach(function (cell) {
      var el = self._el('span', 'convoy-cell role-' + cell.role + (cell.active ? ' is-active' : '') + (cell.locked ? ' is-locked' : '') + (cell.disrupted ? ' is-disrupted' : ''));
      el.title = cell.role + (cell.locked ? ' \u00B7 verified' : cell.disrupted ? ' \u00B7 disrupted' : cell.active ? ' \u00B7 active' : ' \u00B7 off');
      grid.appendChild(el);
    });
    sec.appendChild(grid);
    var f = js.facts;
    sec.appendChild(this._el('div', 'convoy-line', 'Driven by: ' + f.workers + ' planned worker(s), ' + f.tool_calls + ' tool call(s), ' + f.evidence_records + ' evidence record(s), ' + f.unsupported_claims + ' unsupported claim(s), ' + f.failed_workers + ' failed worker(s), ' + f.learned_tokens + ' learned token(s). Stages with no signal for a convoy stay off: ' + js.signals.no_signal.join(', ') + '.'));
    var learned = c.learned_tokens || [];
    if (learned.length) {
      var list = this._el('div', 'convoy-learned');
      learned.forEach(function (t) { list.appendChild(self._el('div', 'convoy-item', t.id + ' \u00B7 ' + t.kind + ' \u00B7 ' + t.status.toUpperCase() + (t.duplicate ? ' \u00B7 already known' : '') + ' \u00B7 ' + t.title)); });
      sec.appendChild(list);
    } else if (c.plan && c.plan.think_mode === 'learn' && c.state === 'COMPLETED') sec.appendChild(this._el('div', 'convoy-line', 'LEARN produced no candidate for this run (the deterministic extractor found nothing reusable).'));
    if (c.learn_error) sec.appendChild(this._el('div', 'convoy-blocked', 'Learning failed: ' + c.learn_error));
    return sec;
  };

  ConvoyWindow.prototype.approve = function (id) {
    var EventCtor = this.win.CustomEvent || root.CustomEvent;
    if (EventCtor && this.win.dispatchEvent) this.win.dispatchEvent(new EventCtor('convoy:approve', { detail: { id: id } }));
  };

  // ── rendering ──────────────────────────────────────────────────────────────
  ConvoyWindow.prototype._el = function (tag, cls, text) {
    var e = this.doc.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = String(text);
    return e;
  };

  ConvoyWindow.prototype._button = function (label, cls, handler, id) {
    var b = this._el('button', cls, label);
    b.type = 'button';
    if (id) b.id = id;
    b.addEventListener('click', handler);
    return b;
  };

  ConvoyWindow.prototype.render = function () {
    if (!this.el) return;
    var body = this.el.querySelector('.convoy-body');
    if (!body) return;
    while (body.firstChild) body.removeChild(body.firstChild);
    if (this.error) body.appendChild(this._el('div', 'convoy-error', this.error)).setAttribute('role', 'alert');
    if (this.board) body.appendChild(this._board());
    body.appendChild(this._form());
    body.appendChild(this._list());
    if (this.selected && this.detail && this.detail.id === this.selected) body.appendChild(this._detail(this.detail));
  };

  ConvoyWindow.prototype._form = function () {
    var self = this;
    var form = this._el('div', 'convoy-form');
    var goal = this._el('input', 'convoy-goal'); goal.type = 'text'; goal.id = 'convoy-goal'; goal.placeholder = 'Goal for the Mayor to plan, e.g. What is the last PR?';
    goal.setAttribute('aria-label', 'Goal');
    var model = this._el('input', 'convoy-model'); model.type = 'text'; model.id = 'convoy-model'; model.placeholder = 'model (blank = default)'; model.setAttribute('aria-label', 'Model');
    var select = this.doc.getElementById && this.doc.getElementById('model-select');
    var f = this.form;
    goal.value = f.goal;
    model.value = f.model !== null ? f.model : (select && select.value ? select.value : '');
    var workers = this._el('input', 'convoy-budget'); workers.type = 'number'; workers.id = 'convoy-max-workers'; workers.min = '1'; workers.max = '12'; workers.value = '4'; workers.setAttribute('aria-label', 'Max workers');
    var cost = this._el('input', 'convoy-budget'); cost.type = 'number'; cost.id = 'convoy-max-cost'; cost.step = '0.01'; cost.min = '0'; cost.value = '0.10'; cost.setAttribute('aria-label', 'Max cost in dollars');
    workers.value = f.workers; cost.value = f.cost;
    goal.addEventListener('input', function () { f.goal = goal.value; });
    model.addEventListener('input', function () { f.model = model.value; });
    workers.addEventListener('input', function () { f.workers = workers.value; });
    cost.addEventListener('input', function () { f.cost = cost.value; });
    var go = this._button('Plan (dry run)', 'btn-primary convoy-plan', function () {
      var g = goal.value.trim();
      if (!g) { self.error = 'Enter a goal to plan.'; self.render(); return; }
      self.plan(g, model.value.trim(), { max_workers: Number(workers.value), max_cost_usd: Number(cost.value) }, f.mode);
    }, 'convoy-plan');
    var row1 = this._el('div', 'convoy-form-row'); row1.appendChild(goal); row1.appendChild(model);
    var row2 = this._el('div', 'convoy-form-row');
    [['Worker budget', workers], ['Max $', cost]].forEach(function (p) { var l = self._el('label', 'convoy-field'); l.appendChild(self._el('span', null, p[0])); l.appendChild(p[1]); row2.appendChild(l); });
    row2.appendChild(go);
    // The control mode: OBSERVE reads only; LEARN also lets a verified outcome become Think Token candidates. SIMULATE proposes and verifies a change in a sandbox; AUTONOMOUS is shown but cannot be chosen yet.
    var modes = this._el('div', 'convoy-modes'); modes.setAttribute('role', 'radiogroup'); modes.setAttribute('aria-label', 'Think Token mode');
    [['observe', 'OBSERVE', 'Read-only. Nothing is changed and nothing is learned.', true], ['learn', 'LEARN', 'Read-only, and a verified outcome may become Think Token candidates (never auto-accepted).', true], ['simulate', 'SIMULATE', 'Proposes a change and verifies it in a sandbox. Never applied to your working tree; the run asks for your approval again.', true], ['autonomous', 'AUTONOMOUS', 'Not available yet.', false]].forEach(function (m) {
      var label = self._el('label', 'convoy-mode' + (m[3] ? '' : ' convoy-mode-off'));
      label.title = m[2];
      var radio = self._el('input'); radio.type = 'radio'; radio.name = 'convoy-mode'; radio.value = m[0]; radio.id = 'convoy-mode-' + m[0]; radio.disabled = !m[3]; radio.checked = f.mode === m[0];
      radio.addEventListener('change', function () { if (radio.checked) f.mode = m[0]; });
      label.appendChild(radio); label.appendChild(self._el('span', null, m[1] + (m[3] ? '' : ' (soon)')));
      modes.appendChild(label);
    });
    form.appendChild(row1); form.appendChild(modes); form.appendChild(row2);
    form.appendChild(this._el('div', 'convoy-hint', 'Planning only: the Mayor builds a plan. Nothing runs until a human approves it.'));
    return form;
  };

  ConvoyWindow.prototype._list = function () {
    var self = this;
    var wrap = this._el('div', 'convoy-list'); wrap.setAttribute('role', 'list');
    if (!this.convoys.length) { wrap.appendChild(this._el('div', 'convoy-empty', 'No convoys yet. Plan one above.')); return wrap; }
    this.convoys.forEach(function (c) {
      var row = self._el('button', 'convoy-row' + (c.id === self.selected ? ' convoy-row-selected' : ''));
      row.type = 'button'; row.setAttribute('role', 'listitem'); row.dataset.convoyId = c.id;
      var badge = modeBadge(c);
      row.appendChild(self._el('span', 'convoy-badge ' + badge.cls, badge.text));
      row.appendChild(self._el('span', 'convoy-row-goal', c.goal));
      row.appendChild(self._el('span', 'convoy-row-meta', c.state + (c.outcome ? ' · ' + c.outcome : '') + ' · ' + (c.workers ? c.workers.length : 0) + ' worker(s) · ' + usd(c.cost_usd) + (c.grounding ? ' · ' + c.grounding : '')));
      row.addEventListener('click', function () { self.selected = c.id; self.detail = null; self.refresh(); });
      wrap.appendChild(row);
    });
    return wrap;
  };

  ConvoyWindow.prototype._section = function (title) {
    var s = this._el('section', 'convoy-section');
    s.appendChild(this._el('h3', null, title));
    return s;
  };

  ConvoyWindow.prototype._detail = function (c) {
    var self = this;
    var box = this._el('div', 'convoy-detail'); box.id = 'convoy-detail';
    var badge = modeBadge(c);
    var head = this._el('div', 'convoy-detail-head');
    head.appendChild(this._el('span', 'convoy-badge convoy-badge-big ' + badge.cls, badge.text));
    head.appendChild(this._el('span', 'convoy-state', c.state + (c.outcome ? ' · ' + c.outcome : '')));
    box.appendChild(head);
    box.appendChild(this._el('div', 'convoy-goal-text', c.goal));
    box.appendChild(this._el('div', 'convoy-id', 'convoy ' + c.id + (c.chain && c.chain.ok ? ' · evidence chain verified' : ' · EVIDENCE CHAIN BROKEN')));

    // actions: the only way forward is an explicit human step
    var actions = this._el('div', 'convoy-actions');
    if (c.state === 'PLANNED') actions.appendChild(this._button('Submit for approval', 'btn-secondary convoy-submit', function () { self.act(c.id, 'submit'); }, 'convoy-submit'));
    if (c.state === 'PENDING') {
      actions.appendChild(this._button('Approve and run LIVE', 'btn-primary convoy-approve', function () { self.approve(c.id); }, 'convoy-approve'));
      actions.appendChild(this._button('Reject', 'btn-secondary convoy-reject', function () { self.act(c.id, 'reject'); }, 'convoy-reject'));
    }
    if (c.review && c.review.state === 'pending') {
      actions.appendChild(this._button('Accept outcome', 'btn-primary convoy-accept', function () { self.review(c.id, 'accept'); }, 'convoy-accept'));
      actions.appendChild(this._button('Reject outcome', 'btn-secondary convoy-reject-outcome', function () { self.review(c.id, 'reject'); }, 'convoy-reject-outcome'));
    }
    if (c.state === 'RUNNING') actions.appendChild(this._button('Stop convoy', 'btn-danger convoy-stop', function () { self.stop(c.id); }, 'convoy-stop'));
    if (c.state === 'PLANNED' || c.state === 'PENDING') actions.appendChild(this._button('Cancel', 'btn-secondary convoy-cancel', function () { self.act(c.id, 'cancel'); }, 'convoy-cancel'));
    if (actions.firstChild) box.appendChild(actions);

    // Think Token: the job state, the existing 100-cell cube replayed from this convoy's real facts
    if (c.job_state) box.appendChild(this._jobState(c));

    // plan
    var plan = this._section('Plan');
    var table = this._el('table', 'convoy-table');
    var th = this._el('tr'); ['Worker', 'Model', 'Tools', 'Permission', 'Wave', 'Est. cost'].forEach(function (h) { th.appendChild(self._el('th', null, h)); }); table.appendChild(th);
    (c.plan && c.plan.workers || []).forEach(function (w) {
      var tr = self._el('tr');
      [w.name, w.model || 'none', (w.tools || []).join(', ') || '—', w.permission, w.wave, usd(w.estimated_cost_usd)].forEach(function (v) { tr.appendChild(self._el('td', null, v)); });
      table.appendChild(tr);
    });
    plan.appendChild(table);
    var use = c.plan && c.plan.budget_use || {};
    var bud = c.worker_budget || {};
    plan.appendChild(this._el('div', 'convoy-line', 'Worker budget: ' + (use.worst_case_workers || 0) + ' of ' + bud.max_workers + ' worker(s) possible · est. ' + usd(use.estimated_cost_usd) + ' (worst case ' + usd(use.worst_case_cost_usd) + ') of $' + bud.max_cost_usd + ' · up to ' + (use.estimated_tool_calls || 0) + ' of ' + bud.max_tool_calls + ' tool calls'));
    (c.plan && c.plan.added_by_mayor || []).forEach(function (a) { plan.appendChild(self._el('div', 'convoy-line', 'Added by the Mayor: ' + a.id + ' (' + a.reason + ')')); });
    if (c.plan && c.plan.escalation) plan.appendChild(this._el('div', 'convoy-line', 'Fallback: ' + c.plan.escalation.model + ' if ' + c.plan.escalation.when));
    plan.appendChild(this._el('div', 'convoy-line', 'Expected: 1 dashboard row, ' + (c.plan && c.plan.expected_convoy ? c.plan.expected_convoy.children : 0) + ' child run(s), ' + (c.plan && c.plan.expected_convoy ? c.plan.expected_convoy.waves : 0) + ' wave(s)'));
    (c.plan && c.plan.warnings || []).forEach(function (w) { plan.appendChild(self._el('div', 'convoy-line', 'Note: ' + w)); });
    (c.plan && c.plan.blocked_reasons || []).forEach(function (r) { plan.appendChild(self._el('div', 'convoy-blocked', 'Blocked: ' + r)); });
    box.appendChild(plan);

    // policy
    var pol = this._section('Policy · risk ' + (c.policy ? c.policy.risk : '?') + ' · ' + (c.policy ? c.policy.decision : ''));
    (c.policy && c.policy.rules || []).forEach(function (r) { pol.appendChild(self._el('div', 'convoy-rule convoy-rule-' + r.effect, '[' + r.effect + '] ' + r.reason + (r.workers ? ' (' + r.workers.join(', ') + ')' : ''))); });
    box.appendChild(pol);

    // outcome review: the second human look, at what the convoy produced
    if (c.review && c.review.state !== 'not_required') {
      var rv = this._section('Outcome review · ' + c.review.state);
      rv.id = 'convoy-review';
      rv.appendChild(this._el('div', 'convoy-line', c.review.state === 'pending' ? 'The result is waiting in REVIEW: a human accepts or rejects it. Rejecting also retires the Think Token candidates this convoy created.' : (c.review.state === 'accepted' ? 'Accepted' : 'Rejected') + ' by ' + (c.review.decided_by || 'human') + (c.review.note ? ': ' + c.review.note : '')));
      box.appendChild(rv);
    }

    // approval
    if (c.approval) {
      var ap = this._section('Approval · ' + c.approval.state);
      ap.appendChild(this._el('div', 'convoy-line', 'Requested ' + new Date(c.approval.requested_at).toISOString() + ' · expires ' + new Date(c.approval.expires_at).toISOString() + (c.approval.decided_by ? ' · decided by ' + c.approval.decided_by : '')));
      box.appendChild(ap);
    }

    // outcome
    if (c.final_answer || c.grounding || c.error) {
      var out = this._section('Result');
      if (c.grounding && c.grounding.status === 'GROUNDED') out.appendChild(this._el('div', 'convoy-grounded', 'GROUNDED — every number, link, id, branch and state claim was found in the tool evidence'));
      if (c.grounding && c.grounding.status !== 'GROUNDED') {
        out.appendChild(this._el('div', 'convoy-grounding-failed', 'GROUNDING FAILED — the answer was not shown as verified'));
        (c.grounding.unsupported || []).forEach(function (u) { out.appendChild(self._el('div', 'convoy-unsupported', u.kind + ': ' + u.claim + ' (' + u.why + ')')); });
      }
      if (c.final_answer) out.appendChild(this._el('div', 'convoy-answer', c.final_answer));
      if (c.error) out.appendChild(this._el('div', 'convoy-blocked', c.error));
      box.appendChild(out);
    }

    // SIMULATE: the proposed change and the sandbox's verdict (the verdict is the report's, never the model's words)
    if (c.simulation) {
      var sm0 = c.simulation;
      var simBox = this._section('Proposed change · ' + (sm0.verified === true ? 'VERIFIED in the sandbox' : sm0.verified === false ? 'NOT verified: the sandbox checks failed' : 'NOT verified: the checks were not run'));
      simBox.appendChild(this._el('div', 'convoy-line', 'Commit ' + String(sm0.sha).slice(0, 12) + ' · patch ' + String(sm0.patch_sha256).slice(0, 12) + ' · ' + (sm0.files || []).join(', ') + ' · proposed by ' + sm0.proposed_by));
      if (sm0.flags && sm0.flags.length) simBox.appendChild(this._el('div', 'convoy-blocked', 'Flags: ' + sm0.flags.join(', ') + (sm0.flags.indexOf('touches_tests') >= 0 ? ' — the proposal edits tests, which are what judge it' : '') + (sm0.flags.indexOf('touches_ci_or_gates') >= 0 ? ' — the proposal edits CI, gates or configuration' : '')));
      if (sm0.note) simBox.appendChild(this._el('div', 'convoy-blocked', sm0.note));
      var patchDetails = this._el('details', 'convoy-run');
      patchDetails.appendChild(this._el('summary', null, 'The patch (not applied to your working tree)'));
      patchDetails.appendChild(this._el('pre', 'convoy-patch', sm0.patch));
      simBox.appendChild(patchDetails);
      box.appendChild(simBox);
    }

    // totals + drill-down
    if (c.mode === 'live' || (c.runs && c.runs.length)) {
      var runs = this._section('Runs · ' + usd(c.cost_usd) + ' · ' + c.tool_calls + ' tool call(s) · ' + c.tokens + ' tokens · ' + ms(c.worker_duration_ms) + ' worker time');
      (c.workers || []).forEach(function (w) {
        var run = (c.runs || []).find(function (r) { return r.id === w.run_id; });
        var d = self._el('details', 'convoy-run');
        var sm = self._el('summary', null, w.name + ' · ' + (w.model || '') + ' · ' + w.status + ' · ' + usd(w.cost_usd) + ' · ' + w.tool_calls + ' tool(s)' + (w.failure ? ' · FAILED: ' + w.failure.kind : ''));
        d.appendChild(sm);
        if (w.failure) d.appendChild(self._el('div', 'convoy-blocked', w.failure.kind + ': ' + w.failure.message));
        if (w.grounding) d.appendChild(self._el('div', w.grounding.status === 'GROUNDED' ? 'convoy-grounded' : 'convoy-grounding-failed', w.grounding.status + ' (' + w.grounding.classification + ')'));
        if (run) (run.steps || []).filter(function (s) { return s.kind === 'tool'; }).forEach(function (s) {
          d.appendChild(self._el('div', 'convoy-tool', 'tool ' + s.name + ' · ' + (s.ok ? 'ok' : 'FAILED') + ' · ' + ms(s.latency_ms) + (s.approval ? ' · approval ' + s.approval : '')));
          d.appendChild(self._el('pre', 'convoy-tool-output', s.output || s.error || ''));
        });
        runs.appendChild(d);
      });
      (c.evidence || []).forEach(function (e) {
        var d = self._el('details', 'convoy-evidence');
        d.appendChild(self._el('summary', null, 'Evidence · ' + e.recipe + ' · ' + (e.items || []).length + ' item(s) · ' + e.latency_ms + ' ms · ' + e.source_url));
        (e.items || []).forEach(function (i) { d.appendChild(self._el('div', 'convoy-item', i.kind === 'branch' ? i.name : i.kind === 'run' ? (i.name + ' on ' + i.branch + ': ' + (i.conclusion || i.status) + ' (run ' + i.run_number + ')') : ('#' + i.number + ' ' + i.title + ' (' + i.state + ') ' + i.url))); });
        runs.appendChild(d);
      });
      box.appendChild(runs);
    }

    // evidence chain
    var chain = this._section('Evidence chain');
    (c.events || []).forEach(function (e) { chain.appendChild(self._el('div', 'convoy-event', e.seq + '. ' + new Date(e.at).toISOString() + ' · ' + e.state + ' · by ' + e.by + ' · ' + e.note + ' · #' + String(e.hash).slice(0, 8))); });
    box.appendChild(chain);
    return box;
  };

  root.ConvoyWindow = ConvoyWindow;
  root.convoyModeBadge = modeBadge;
  if (root.document && root.document.addEventListener) {
    root.convoyWindow = new ConvoyWindow({});
    var start = function () { root.convoyWindow.mount(); };
    if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', start); else start();
  }
})(typeof window !== 'undefined' ? window : globalThis);
