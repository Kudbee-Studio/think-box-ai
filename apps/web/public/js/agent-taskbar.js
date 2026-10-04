// Taskbar agent list — fills the window manager's Agents slot with a live count and a dropdown of tracked agents.
//
// The window manager builds #wm-taskbar-agents with a "none running" placeholder; this script takes that element over,
// rebuilds it whenever agent-registry dispatches `agents:changed`, and opens a governance window when an agent is picked.
//
// Classic script. Built with createElement/textContent only.
(function (root) {
  'use strict';

  function AgentTaskbar(options) {
    options = options || {};
    this.doc = options.document || root.document;
    this.win = options.window || root;
    this.container = null;
    this.menuOpen = false;
    this.mounted = false;
  }

  AgentTaskbar.prototype.mount = function () {
    if (this.mounted) return true;
    var doc = this.doc;
    this.container = doc.getElementById ? doc.getElementById('wm-taskbar-agents') : null;
    if (!this.container) {
      var bar = doc.getElementById ? doc.getElementById('wm-taskbar') : null;
      if (!bar) return false;
      this.container = doc.createElement('div');
      this.container.id = 'wm-taskbar-agents';
      this.container.className = 'wm-taskbar-agents';
      bar.appendChild(this.container);
    }
    var self = this;
    if (this.win.addEventListener) this.win.addEventListener('agents:changed', function (e) { self.render(e && e.detail); });
    if (doc.addEventListener) doc.addEventListener('click', function () { self.closeMenu(); });
    if (doc.addEventListener) doc.addEventListener('keydown', function (e) { if (e && e.key === 'Escape') self.closeMenu(); });
    this.render(this._snapshot());
    this.mounted = true;
    return true;
  };

  AgentTaskbar.prototype._registry = function () { return this.win.agentRegistry || root.agentRegistry || null; };

  AgentTaskbar.prototype._snapshot = function () {
    var registry = this._registry();
    if (!registry) return { agents: [], runningCount: 0 };
    return { agents: registry.list(), runningCount: registry.runningCount() };
  };

  AgentTaskbar.prototype.render = function (detail) {
    if (!this.container) return;
    detail = detail || this._snapshot();
    var self = this;
    var doc = this.doc;
    while (this.container.firstChild) this.container.removeChild(this.container.firstChild);

    var label = doc.createElement('span');
    label.className = 'wm-agent-label';
    label.textContent = 'Agents';
    this.container.appendChild(label);

    var count = detail.runningCount || 0;
    var badge = doc.createElement('button');
    badge.type = 'button';
    badge.className = 'wm-agent-badge' + (count ? ' is-running' : '');
    badge.textContent = count + ' running';
    badge.setAttribute('aria-label', count + ' agents running');
    badge.setAttribute('aria-expanded', this.menuOpen ? 'true' : 'false');
    badge.addEventListener('click', function (e) { if (e && e.stopPropagation) e.stopPropagation(); self.toggleMenu(detail); });
    this.container.appendChild(badge);

    if (this.menuOpen) this._renderMenu(detail);
  };

  AgentTaskbar.prototype.toggleMenu = function (detail) {
    this.menuOpen = !this.menuOpen;
    this.render(detail || this._snapshot());
  };

  AgentTaskbar.prototype.closeMenu = function () {
    if (!this.menuOpen) return;
    this.menuOpen = false;
    this.render(this._snapshot());
  };

  AgentTaskbar.prototype._renderMenu = function (detail) {
    var self = this;
    var doc = this.doc;
    var menu = doc.createElement('div');
    menu.className = 'agent-menu';
    menu.setAttribute('role', 'menu');

    var agents = detail.agents || [];
    if (!agents.length) {
      var empty = doc.createElement('div');
      empty.className = 'agent-menu-empty';
      empty.textContent = 'No agents tracked yet';
      menu.appendChild(empty);
    } else {
      agents.forEach(function (agent) {
        var item = doc.createElement('button');
        item.type = 'button';
        item.className = 'agent-menu-item agent-status-' + String(agent.status || 'idle');
        item.setAttribute('role', 'menuitem');
        var goal = agent.goal ? String(agent.goal) : String(agent.id || 'agent');
        var run = agent.run_id ? ' · ' + String(agent.run_id).slice(0, 8) : '';
        item.textContent = goal + ' · ' + String(agent.status || 'idle') + run;
        item.addEventListener('click', function (e) {
          if (e && e.stopPropagation) e.stopPropagation();
          self.openAgent(agent.id);
        });
        menu.appendChild(item);
      });
    }
    this.container.appendChild(menu);
  };

  AgentTaskbar.prototype.openAgent = function (id) {
    this.closeMenu();
    if (!id) return;
    var EventCtor = this.win.CustomEvent || root.CustomEvent;
    var target = this.win.dispatchEvent ? this.win : root;
    if (EventCtor && target) target.dispatchEvent(new EventCtor('agent:open', { detail: { id: id } }));
  };

  root.AgentTaskbar = AgentTaskbar;
  if (root.document && root.document.addEventListener) {
    root.document.addEventListener('DOMContentLoaded', function () {
      var bar = new AgentTaskbar({});
      if (bar.mount()) root.agentTaskbar = bar;
    });
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
