// Agent registry — an in-memory view of the workers the dashboard is tracking.
//
// The server already streams everything needed to see an agent work: run_update (a run's status + step), task/task_update
// (a task's status), think_token_cube / think_token_used (Think Box + token use), specialist_result (a specialist job) and
// approval_request / approval_resolved. app.js feeds each WebSocket message to `ingest`, which folds it into an agent record
// and dispatches `agents:changed` on the window when something actually changed. No server calls and no state of its own.
//
// Pure logic (no DOM): loaded as a classic script in the browser (window.agentRegistry) and, in node tests, by importing
// the file (the guard below sets globalThis.AgentRegistry / globalThis.agentRegistry).
(function (root) {
  'use strict';

  function normalizeStatus(value) {
    var s = String(value == null ? '' : value).toLowerCase();
    if (/^(running|started|in[_-]?progress|executing|active)$/.test(s)) return 'running';
    if (/^(completed|complete|success|succeeded|done|finished)$/.test(s)) return 'idle';
    if (/^(failed|failure|error|cancelled|canceled)$/.test(s)) return 'failed';
    if (/^(paused|queued|blocked|waiting|awaiting|approval|pending)$/.test(s)) return 'paused';
    if (/^(idle|ready)$/.test(s)) return 'idle';
    return s || 'idle';
  }

  function num(value, fallback) {
    var n = Number(value);
    return isFinite(n) ? n : fallback;
  }

  function AgentRegistry(options) {
    options = options || {};
    this.emit = typeof options.emit === 'function' ? options.emit : function () {};
    this.now = typeof options.now === 'function' ? options.now : function () { return Date.now(); };
    this.agents = {};
    this.order = [];
    this.owned = new Set();
  }

  AgentRegistry.prototype.get = function (id) { return id && this.agents[id] ? this.agents[id] : null; };

  AgentRegistry.prototype.list = function () {
    var self = this;
    return this.order.map(function (id) { return self.agents[id]; }).filter(Boolean);
  };

  AgentRegistry.prototype.runningCount = function () {
    return this.list().filter(function (a) { return a.status === 'running'; }).length;
  };

  AgentRegistry.prototype._ensure = function (id, seed) {
    if (!id) return null;
    if (!this.agents[id]) {
      this.agents[id] = {
        id: id,
        status: 'idle',
        run_id: null,
        goal: '',
        steps_completed: 0,
        tokens_used: 0,
        think_box_id: null,
        approval_pending: false,
        approvals: [],
        updated_at: this.now()
      };
      this.order.push(id);
    }
    if (seed) this._patch(this.agents[id], seed);
    return this.agents[id];
  };

  AgentRegistry.prototype._patch = function (agent, patch) {
    for (var k in patch) {
      if (!Object.prototype.hasOwnProperty.call(patch, k)) continue;
      var v = patch[k];
      if (v === undefined || v === null || v === '') continue;
      agent[k] = v;
    }
    agent.updated_at = this.now();
    agent.approval_pending = agent.approvals.some(function (a) { return !a.resolved; });
  };

  AgentRegistry.prototype.upsert = function (id, patch) {
    var agent = this._ensure(id, patch);
    return agent;
  };

  AgentRegistry.prototype._lastRunning = function () {
    for (var i = this.order.length - 1; i >= 0; i--) {
      var a = this.agents[this.order[i]];
      if (a && a.status === 'running') return a;
    }
    return null;
  };

  AgentRegistry.prototype._last = function () {
    for (var i = this.order.length - 1; i >= 0; i--) {
      var a = this.agents[this.order[i]];
      if (a) return a;
    }
    return null;
  };

  AgentRegistry.prototype.addApproval = function (agentId, approval) {
    if (!approval || !approval.id) return false;
    var agent = agentId ? this._ensure(agentId) : (this._lastRunning() || this._ensure('session'));
    if (!agent) return false;
    if (!agent.approvals.some(function (a) { return a.id === approval.id; })) {
      agent.approvals.push({ id: approval.id, reason: String(approval.reason || approval.action || 'Approval required'), resolved: false, created_at: this.now() });
    }
    agent.approval_pending = true;
    agent.updated_at = this.now();
    return true;
  };

  AgentRegistry.prototype.resolveApproval = function (approvalId, approved) {
    var changed = false;
    for (var i = 0; i < this.order.length; i++) {
      var agent = this.agents[this.order[i]];
      if (!agent) continue;
      for (var j = 0; j < agent.approvals.length; j++) {
        if (agent.approvals[j].id === approvalId) {
          agent.approvals[j].resolved = approved === undefined ? true : !!approved;
          changed = true;
        }
      }
      if (changed) {
        agent.approval_pending = agent.approvals.some(function (a) { return !a.resolved; });
        agent.updated_at = this.now();
      }
    }
    return changed;
  };

  AgentRegistry.prototype._fromRun = function (d) {
    var id = d.id || d.run_id || d.runId;
    if (!id) return false;
    // A convoy worker owns its child run: the worker agent (driven by the board lane) is the one agent, so the run is never a second one.
    if (this.owned.has(String(id))) return false;
    this._ensure(String(id), {
      run_id: String(id),
      status: normalizeStatus(d.status),
      goal: d.goal || d.current_action || d.currentAction,
      steps_completed: num(d.current_step || d.currentStep || d.steps_completed || d.steps, undefined),
      tokens_used: num(d.tokens_used || d.tokensUsed || d.tokens, undefined),
      think_box_id: d.thinkBoxId || d.think_box_id || d.boxId
    });
    return true;
  };

  AgentRegistry.prototype._fromTask = function (d) {
    var id = d.id || d.taskId || d.task_id;
    if (!id) return false;
    var label = d.title || d.description || d.goal;
    this._ensure(String(id), {
      status: normalizeStatus(d.status),
      goal: label,
      steps_completed: Array.isArray(d.activity) ? d.activity.length : undefined,
      run_id: d.run_id || d.runId
    });
    return true;
  };

  AgentRegistry.prototype._fromCube = function (d) {
    var agent = (d.agentId && this.get(String(d.agentId))) || this._lastRunning() || this._last() || this._ensure('session');
    if (!agent) return false;
    var tokens = Array.isArray(d.tokens) ? d.tokens.length : num(d.tokenCount || d.totalTokens, undefined);
    this._patch(agent, { think_box_id: d.thinkBoxId || d.boxId || d.think_box_id, tokens_used: tokens });
    return true;
  };

  AgentRegistry.prototype._fromTokenUsed = function (d) {
    var agent = (d.agentId && this.get(String(d.agentId))) || this._lastRunning() || this._last();
    if (!agent) return false;
    agent.tokens_used = num(agent.tokens_used, 0) + 1;
    agent.updated_at = this.now();
    return true;
  };

  AgentRegistry.prototype._fromSpecialist = function (d) {
    var job = d.jobId || d.job_id || d.id;
    var runs = Array.isArray(d.specialistsExecuted) ? d.specialistsExecuted : [];
    if (!runs.length && !job) return false;
    if (job) this._ensure(String(job), { goal: d.intent || d.goal, status: normalizeStatus(d.status), run_id: String(job) });
    runs.forEach(function (run, i) {
      var id = run.specialistId || run.thinkBoxId || (job ? String(job) + '-' + i : 'specialist-' + i);
      this._ensure(String(id), {
        goal: run.contract || d.intent || d.goal,
        status: normalizeStatus(run.status),
        run_id: job ? String(job) : undefined,
        think_box_id: run.thinkBoxId
      });
    }, this);
    return true;
  };

  AgentRegistry.prototype._fromStatus = function (d) {
    var status = normalizeStatus(d);
    // The server sends `status: running` just BEFORE the run record exists. Attaching it to the last finished agent revived it as a
    // ghost that never finished ("2 running" for one goal), so only a currently running agent is updated here.
    var agent = this._lastRunning();
    if (!agent) return false;
    agent.status = status;
    agent.updated_at = this.now();
    return true;
  };

  // A convoy's workers are agents too: each carries its lane on the agent board (READY / OPEN / REVIEW / FINISHED) and its bead id, so the taskbar, the
  // governance window and the layered process windows all speak about the same worker.
  AgentRegistry.prototype._fromConvoy = function (d) {
    if (!d || !d.id || !Array.isArray(d.workers)) return false;
    var self = this;
    d.workers.forEach(function (w) {
      var lane = w.lane || 'none';
      var status = lane === 'open' ? 'running' : lane === 'review' ? 'paused' : lane === 'ready' ? 'idle' : lane === 'finished' ? (w.status === 'failed' ? 'failed' : 'idle') : 'paused';
      self._ensure('convoy:' + String(d.id).slice(0, 8) + ':' + w.id, { goal: d.goal, status: status, lane: lane, bead: w.bead, convoy_id: d.id, worker_id: w.id, worker_name: w.name, model: w.model, run_id: w.run_id, think_mode: d.think_mode });
      var agent = self.agents['convoy:' + String(d.id).slice(0, 8) + ':' + w.id];
      agent.status = status; agent.lane = lane;
      if (w.run_id) self._claimRun(String(w.run_id));
    });
    return true;
  };

  // Fold a standalone run entry into the convoy worker that owns it, and remember the claim so later run updates for it are ignored.
  AgentRegistry.prototype._claimRun = function (runId) {
    this.owned.add(String(runId));
    if (this.agents[runId]) {
      delete this.agents[runId];
      this.order = this.order.filter(function (id) { return id !== runId; });
    }
  };

  AgentRegistry.prototype._fromResult = function (d) {
    var agent = this._lastRunning() || this._last();
    if (!agent) return false;
    agent.status = d && d.success === false ? 'failed' : 'idle';
    if (d && d.tokens !== undefined) agent.tokens_used = num(d.tokens, agent.tokens_used);
    agent.updated_at = this.now();
    return true;
  };

  AgentRegistry.prototype.ingest = function (message) {
    if (!message || typeof message !== 'object') return false;
    var before = this._signature();
    var data = message.data == null ? {} : message.data;
    var handled = true;
    switch (message.type) {
      case 'run_update':
      case 'think-cube:run':
      case 'think_cube:run':
        handled = this._fromRun(data);
        break;
      case 'task':
      case 'task_update':
        handled = this._fromTask(data);
        break;
      case 'think_token_cube':
        handled = this._fromCube(data);
        break;
      case 'think_token_used':
        handled = this._fromTokenUsed(data);
        break;
      case 'specialist_result':
        handled = this._fromSpecialist(data);
        break;
      case 'convoy_update':
        handled = this._fromConvoy(data);
        break;
      case 'approval_request':
        handled = this.addApproval(data.agentId || data.agent_id || data.sessionId, data);
        break;
      case 'approval_resolved':
        handled = this.resolveApproval(data.id, data.approved);
        break;
      case 'status':
        handled = this._fromStatus(data);
        break;
      case 'result':
        handled = this._fromResult(data);
        break;
      default:
        return false;
    }
    if (!handled) return false;
    if (this._signature() !== before) {
      this.emit({ agents: this.list(), runningCount: this.runningCount() });
      return true;
    }
    return false;
  };

  // A stable view of the agent fields the UI renders; updated_at and approval timestamps are ignored so a re-sent
  // message does not count as a change.
  AgentRegistry.prototype._signature = function () {
    return JSON.stringify(this.list().map(function (a) {
      return {
        id: a.id, status: a.status, lane: a.lane, bead: a.bead, run_id: a.run_id, goal: a.goal, steps_completed: a.steps_completed,
        tokens_used: a.tokens_used, think_box_id: a.think_box_id, approval_pending: a.approval_pending,
        approvals: (a.approvals || []).map(function (x) { return { id: x.id, reason: x.reason, resolved: x.resolved }; })
      };
    }));
  };

  AgentRegistry.prototype.clear = function () {
    this.agents = {};
    this.order = [];
    this.owned = new Set();
    this.emit({ agents: [], runningCount: 0 });
  };

  root.AgentRegistry = AgentRegistry;
  if (typeof module !== 'undefined' && module.exports) { module.exports = { AgentRegistry: AgentRegistry, normalizeStatus: normalizeStatus }; }

  if (root.document && root.document.addEventListener && root.CustomEvent) {
    root.agentRegistry = new AgentRegistry({
      emit: function (detail) { root.dispatchEvent(new root.CustomEvent('agents:changed', { detail: detail })); }
    });
  } else if (!root.agentRegistry) {
    root.agentRegistry = new AgentRegistry({});
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
