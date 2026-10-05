// Governance window — a per-agent floating window showing status, approvals and a Think Box view.
//
// Opens when the taskbar dispatches `agent:open` (or by calling open(id)); refreshes on `agents:changed`. It is a normal
// .modal-backdrop, so the window manager adopts it like any other panel. Approving/rejecting dispatches `approval:resolved`;
// app.js turns that into the WebSocket approval_response. Built with createElement/textContent only.
(function (root) {
  'use strict';

  function safeId(id) { return 'governance-' + String(id).replace(/[^a-zA-Z0-9_-]/g, '_'); }

  function GovernanceWindow(options) {
    options = options || {};
    this.doc = options.document || root.document;
    this.win = options.window || root;
    this.mounted = false;
  }

  GovernanceWindow.prototype.mount = function () {
    if (this.mounted) return true;
    var self = this;
    if (this.win.addEventListener) {
      this.win.addEventListener('agent:open', function (e) { self.open(e && e.detail && e.detail.id); });
      this.win.addEventListener('agents:changed', function () { self.refresh(); });
    }
    this.mounted = true;
    return true;
  };

  GovernanceWindow.prototype._registry = function () { return this.win.agentRegistry || root.agentRegistry || null; };

  GovernanceWindow.prototype.open = function (id) {
    if (!id) return false;
    var registry = this._registry();
    var agent = registry && registry.get(String(id));
    if (!agent) return false;
    // A convoy worker has its own layered process window (Agent > Run > Tool > Evidence) instead of the generic governance view.
    var pw = this.win.processWindows || root.processWindows;
    if (agent.convoy_id && pw) { pw.open('agent', { convoyId: agent.convoy_id, workerId: agent.worker_id }); return true; }
    var el = this.doc.getElementById ? this.doc.getElementById(safeId(id)) : null;
    if (!el) el = this._create(id);
    this._render(el, agent);
    el.hidden = false;
    return true;
  };

  GovernanceWindow.prototype.close = function (id) {
    var el = this.doc.getElementById ? this.doc.getElementById(safeId(id)) : null;
    if (!el) return;
    if (el.remove) el.remove();
    else el.hidden = true;
  };

  GovernanceWindow.prototype._create = function (id) {
    var doc = this.doc;
    var self = this;
    var el = doc.createElement('div');
    el.className = 'modal-backdrop governance-window';
    el.id = safeId(id);
    if (el.dataset) { el.dataset.agentId = String(id); el.dataset.wmSize = '520x560'; } // tall enough for the Approve/Reject row without scrolling

    var section = doc.createElement('section');
    section.className = 'modal modal-wide governance-modal';
    section.setAttribute('role', 'dialog');
    section.setAttribute('aria-modal', 'true');

    var header = doc.createElement('div');
    header.className = 'modal-header';
    var titleWrap = doc.createElement('div');
    var eyebrow = doc.createElement('span');
    eyebrow.className = 'modal-eyebrow';
    eyebrow.textContent = 'GOVERNANCE';
    var h2 = doc.createElement('h2');
    h2.className = 'gov-title';
    h2.textContent = 'Agent';
    titleWrap.appendChild(eyebrow);
    titleWrap.appendChild(h2);
    var close = doc.createElement('button');
    close.className = 'btn-icon gov-close';
    close.setAttribute('title', 'Close');
    close.setAttribute('aria-label', 'Close governance window');
    close.textContent = '\u00D7';
    close.addEventListener('click', function () { self.close(id); });
    header.appendChild(titleWrap);
    header.appendChild(close);

    var body = doc.createElement('div');
    body.className = 'gov-body';

    section.appendChild(header);
    section.appendChild(body);
    el.appendChild(section);
    doc.body.appendChild(el);
    return el;
  };

  GovernanceWindow.prototype._row = function (label, value) {
    var doc = this.doc;
    var row = doc.createElement('div');
    row.className = 'gov-row';
    var l = doc.createElement('span');
    l.className = 'gov-label';
    l.textContent = label;
    var v = doc.createElement('span');
    v.className = 'gov-value';
    v.textContent = String(value);
    row.appendChild(l);
    row.appendChild(v);
    return row;
  };

  GovernanceWindow.prototype._approval = function (approval) {
    var doc = this.doc;
    var self = this;
    var box = doc.createElement('div');
    box.className = 'gov-approval';
    var text = doc.createElement('div');
    text.className = 'gov-approval-text';
    text.textContent = '\u26A0\uFE0F Approval required: ' + String(approval.reason || 'action needs approval');
    box.appendChild(text);
    var actions = doc.createElement('div');
    actions.className = 'gov-approval-actions';
    var approve = doc.createElement('button');
    approve.type = 'button';
    approve.className = 'btn-primary gov-approve';
    approve.textContent = 'Approve';
    approve.addEventListener('click', function () { self.resolve(approval.id, true); });
    var reject = doc.createElement('button');
    reject.type = 'button';
    reject.className = 'btn-secondary gov-reject';
    reject.textContent = 'Reject';
    reject.addEventListener('click', function () { self.resolve(approval.id, false); });
    actions.appendChild(approve);
    actions.appendChild(reject);
    box.appendChild(actions);
    return box;
  };

  GovernanceWindow.prototype.resolve = function (approvalId, approved) {
    var registry = this._registry();
    if (registry) registry.resolveApproval(approvalId, approved);
    var EventCtor = this.win.CustomEvent || root.CustomEvent;
    var target = this.win.dispatchEvent ? this.win : root;
    if (EventCtor && target) target.dispatchEvent(new EventCtor('approval:resolved', { detail: { id: approvalId, approved: !!approved } }));
  };

  GovernanceWindow.prototype._thinkBox = function (agent) {
    var doc = this.doc;
    var box = doc.createElement('div');
    box.className = 'gov-thinkbox';
    var h4 = doc.createElement('h4');
    h4.textContent = 'Think Box';
    box.appendChild(h4);
    if (!agent.think_box_id) {
      var none = doc.createElement('div');
      none.className = 'gov-thinkbox-empty';
      none.textContent = 'No think box attached yet.';
      box.appendChild(none);
      return box;
    }
    var host = doc.createElement('div');
    host.className = 'gov-thinkbox-host';
    box.appendChild(host);
    if (typeof root.ThinkCubeRenderer === 'function') {
      try { root.ThinkCubeRenderer.render(host, { thinkBoxId: agent.think_box_id, tokens: agent.tokens_used }); return box; } catch (err) { /* fall back to the tree below */ }
    }
    var tree = doc.createElement('ul');
    tree.className = 'gov-thinkbox-tree';
    [['Think Box', agent.think_box_id], ['Tokens used', agent.tokens_used || 0], ['Steps', agent.steps_completed || 0]].forEach(function (pair) {
      var li = doc.createElement('li');
      li.textContent = pair[0] + ': ' + String(pair[1]);
      tree.appendChild(li);
    });
    box.appendChild(tree);
    return box;
  };

  GovernanceWindow.prototype._render = function (el, agent) {
    var doc = this.doc;
    var title = el.querySelector && el.querySelector('.gov-title');
    if (title) title.textContent = 'Agent ' + String(agent.id).slice(0, 12);
    var body = el.querySelector && el.querySelector('.gov-body');
    if (!body) return;
    while (body.firstChild) body.removeChild(body.firstChild);

    body.appendChild(this._row('Status', agent.status || 'idle'));
    body.appendChild(this._row('Goal', agent.goal || '\u2014'));
    body.appendChild(this._row('Current step', agent.steps_completed || 0));
    body.appendChild(this._row('Run', agent.run_id ? String(agent.run_id).slice(0, 12) : '\u2014'));
    body.appendChild(this._row('Tokens used', agent.tokens_used || 0));

    (agent.approvals || []).filter(function (a) { return !a.resolved; }).forEach(function (a) {
      body.appendChild(this._approval(a));
    }, this);

    body.appendChild(this._thinkBox(agent));
  };

  GovernanceWindow.prototype.refresh = function () {
    var registry = this._registry();
    if (!registry || !this.doc.querySelectorAll) return;
    var nodes = this.doc.querySelectorAll('.governance-window');
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      var id = el.dataset && el.dataset.agentId;
      var agent = id ? registry.get(id) : null;
      if (agent) this._render(el, agent);
    }
  };

  root.GovernanceWindow = GovernanceWindow;
  if (root.document && root.document.addEventListener) {
    root.document.addEventListener('DOMContentLoaded', function () {
      var w = new GovernanceWindow({});
      w.mount();
      root.governanceWindow = w;
    });
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
