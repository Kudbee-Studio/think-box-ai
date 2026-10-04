// Actions button — enables the task panel's "⋯ Actions" button and opens a menu of saved workflows.
//
// The button shipped permanently disabled. This mounts a small dropdown that lists the workflows stored by
// workflow-store.js; picking one dispatches `workflow:run` on the window, which app.js turns into a run_goal.
// It also offers "New workflow", which opens the workflow builder.
//
// Classic script. The menu is built with createElement/textContent (no HTML strings), so a workflow name cannot inject markup.
(function (root) {
  'use strict';

  function ActionMenu(options) {
    options = options || {};
    this.doc = options.document || root.document;
    this.win = options.window || root;
    this.storage = options.storage || root.localStorage;
    this.buttonId = options.buttonId || 'bulk-actions';
    this.button = null;
    this.menu = null;
    this.mounted = false;
  }

  ActionMenu.prototype.mount = function () {
    if (this.mounted) return true;
    var button = this.doc.getElementById ? this.doc.getElementById(this.buttonId) : null;
    if (!button) return false;
    this.button = button;
    button.disabled = false;
    if (button.removeAttribute) button.removeAttribute('disabled');
    var self = this;
    button.addEventListener('click', function (e) {
      if (e && e.stopPropagation) e.stopPropagation();
      self.toggle();
    });
    if (this.doc.addEventListener) this.doc.addEventListener('click', function () { self.close(); });
    var onKey = function (e) { if (e && e.key === 'Escape') self.close(); };
    if (this.doc.addEventListener) this.doc.addEventListener('keydown', onKey);
    else if (this.win.addEventListener) this.win.addEventListener('keydown', onKey);
    this.mounted = true;
    return true;
  };

  ActionMenu.prototype.workflows = function () {
    var store = this.win.WorkflowStore || root.WorkflowStore;
    return store ? store.listWorkflows(this.storage) : [];
  };

  ActionMenu.prototype.toggle = function () {
    if (this.menu) this.close();
    else this.openMenu();
  };

  ActionMenu.prototype.openMenu = function () {
    this.close();
    var self = this;
    var doc = this.doc;
    var menu = doc.createElement('div');
    menu.className = 'action-menu';
    menu.setAttribute('role', 'menu');

    var header = doc.createElement('div');
    header.className = 'action-menu-header';
    header.textContent = 'Run a workflow';
    menu.appendChild(header);

    var list = this.workflows();
    if (!list.length) {
      var empty = doc.createElement('div');
      empty.className = 'action-menu-empty';
      empty.textContent = 'No saved workflows yet';
      menu.appendChild(empty);
    } else {
      list.forEach(function (wf) {
        var item = doc.createElement('button');
        item.type = 'button';
        item.className = 'action-menu-item';
        item.setAttribute('role', 'menuitem');
        item.setAttribute('title', 'Run ' + wf.name);
        item.textContent = wf.name + '  ·  ' + (wf.nodes ? wf.nodes.length : 0) + ' step(s)';
        item.addEventListener('click', function (e) {
          if (e && e.stopPropagation) e.stopPropagation();
          self.run(wf);
        });
        menu.appendChild(item);
      });
    }

    var sep = doc.createElement('div');
    sep.className = 'action-menu-sep';
    menu.appendChild(sep);

    var create = doc.createElement('button');
    create.type = 'button';
    create.className = 'action-menu-item action-menu-new';
    create.setAttribute('role', 'menuitem');
    create.textContent = '\uFF0B New workflow';
    create.addEventListener('click', function (e) {
      if (e && e.stopPropagation) e.stopPropagation();
      self.close();
      var builderButton = self.doc.getElementById ? self.doc.getElementById('create-workflow') : null;
      if (builderButton && typeof builderButton.click === 'function') builderButton.click();
    });
    menu.appendChild(create);

    menu.style.position = 'fixed';
    menu.style.zIndex = '9500';
    if (this.button && typeof this.button.getBoundingClientRect === 'function') {
      var rect = this.button.getBoundingClientRect();
      if (rect) {
        menu.style.left = Math.max(8, (rect.left || 0)) + 'px';
        menu.style.top = ((rect.bottom || 0) + 4) + 'px';
      }
    }
    if (doc.body) doc.body.appendChild(menu);
    this.menu = menu;
  };

  ActionMenu.prototype.run = function (workflow) {
    this.close();
    if (!workflow) return;
    var EventCtor = this.win.CustomEvent || root.CustomEvent;
    var target = this.win.dispatchEvent ? this.win : root;
    if (EventCtor && target && typeof target.dispatchEvent === 'function') {
      target.dispatchEvent(new EventCtor('workflow:run', { detail: workflow }));
    }
  };

  ActionMenu.prototype.close = function () {
    if (this.menu) {
      if (typeof this.menu.remove === 'function') this.menu.remove();
      else if (this.menu.parentNode && this.menu.parentNode.removeChild) this.menu.parentNode.removeChild(this.menu);
      this.menu = null;
    }
  };

  root.ActionMenu = ActionMenu;
  if (root.document && root.document.addEventListener) {
    root.document.addEventListener('DOMContentLoaded', function () {
      var menu = new ActionMenu({});
      if (menu.mount()) root.actionMenu = menu;
    });
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
