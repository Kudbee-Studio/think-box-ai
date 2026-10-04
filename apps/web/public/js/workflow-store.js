// Workflow store — localStorage persistence and plan composition for the workflow builder and the Actions menu.
//
// Workflows are UI data only: an id, a name, a description, an ordered list of steps (nodes) and created/updated
// timestamps. No server persistence and no backend execution — running a workflow dispatches a normal goal.
//
// Pure logic (no DOM): loaded as a classic script in the browser (window.WorkflowStore) and, in node tests, by
// importing the file (the guard below sets globalThis.WorkflowStore and module.exports).
(function (root) {
  'use strict';

  var PREFIX = 'kudbee:workflows:';
  var TYPES = { sequential: true, parallel: true, conditional: true, loop: true };

  function keyFor(id) { return PREFIX + String(id); }

  function genId() {
    return 'workflow-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7);
  }

  function normalizeNode(raw) {
    if (!raw || typeof raw !== 'object') return null;
    var type = String(raw.type || 'sequential');
    if (!TYPES[type]) type = 'sequential';
    var name = String(raw.name == null ? '' : raw.name).trim();
    return { id: String(raw.id || ('node-' + Math.random().toString(36).slice(2, 8))), type: type, name: name };
  }

  // A stored record is only trusted for the fields this module writes; unknown keys are dropped.
  function normalize(raw) {
    if (!raw || typeof raw !== 'object') return null;
    var name = String(raw.name == null ? '' : raw.name).trim();
    if (!name) return null;
    var nodes = Array.isArray(raw.nodes) ? raw.nodes.map(normalizeNode).filter(Boolean) : [];
    var created = raw.created_at || raw.createdAt;
    var updated = raw.updated_at || raw.updatedAt || created;
    return {
      id: String(raw.id || genId()),
      name: name,
      description: String(raw.description == null ? '' : raw.description),
      nodes: nodes,
      created_at: typeof created === 'string' && created ? created : new Date().toISOString(),
      updated_at: typeof updated === 'string' && updated ? updated : new Date().toISOString()
    };
  }

  function listWorkflows(storage) {
    var out = [];
    if (!storage || typeof storage.key !== 'function' || typeof storage.length !== 'number') return out;
    for (var i = 0; i < storage.length; i++) {
      var key = storage.key(i);
      if (!key || key.indexOf(PREFIX) !== 0) continue;
      try {
        var rec = normalize(JSON.parse(storage.getItem(key)));
        if (rec) out.push(rec);
      } catch (err) {
        // A corrupt entry is skipped; it stays on disk until overwritten.
      }
    }
    out.sort(function (a, b) { return String(b.updated_at).localeCompare(String(a.updated_at)); });
    return out;
  }

  function getWorkflow(storage, id) {
    if (!storage || !id) return null;
    try {
      return normalize(JSON.parse(storage.getItem(keyFor(id))));
    } catch (err) {
      return null;
    }
  }

  // Save (create or update). Updating an existing id keeps its created_at and refreshes updated_at.
  function saveWorkflow(storage, raw) {
    var existing = raw && raw.id ? getWorkflow(storage, raw.id) : null;
    var now = new Date().toISOString();
    var rec = normalize({
      id: (raw && raw.id) || genId(),
      name: raw && raw.name,
      description: raw && raw.description,
      nodes: raw && raw.nodes,
      created_at: (existing && existing.created_at) || (raw && (raw.created_at || raw.createdAt)) || now,
      updated_at: now
    });
    if (!rec || !storage) return rec;
    try { storage.setItem(keyFor(rec.id), JSON.stringify(rec)); } catch (err) { /* quota/blocked: the workflow is still returned for a run */ }
    return rec;
  }

  function deleteWorkflow(storage, id) {
    if (!storage || !id) return false;
    try { storage.removeItem(keyFor(id)); return true; } catch (err) { return false; }
  }

  // The plain-text plan a workflow turns into. Composed with string concatenation (no HTML), so it is safe as a goal.
  function composeGoal(workflow) {
    if (!workflow) return '';
    var lines = ['Run this saved workflow: ' + String(workflow.name || 'untitled')];
    if (workflow.description) lines.push(String(workflow.description));
    lines.push('Steps:');
    var nodes = Array.isArray(workflow.nodes) ? workflow.nodes : [];
    for (var i = 0; i < nodes.length; i++) {
      var label = nodes[i].name || ('step ' + (i + 1));
      lines.push((i + 1) + '. [' + nodes[i].type + '] ' + label);
    }
    lines.push('Execute the steps in order and report the result.');
    return lines.join('\n');
  }

  var api = {
    PREFIX: PREFIX,
    keyFor: keyFor,
    genId: genId,
    normalize: normalize,
    normalizeNode: normalizeNode,
    listWorkflows: listWorkflows,
    getWorkflow: getWorkflow,
    saveWorkflow: saveWorkflow,
    deleteWorkflow: deleteWorkflow,
    composeGoal: composeGoal
  };

  root.WorkflowStore = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
