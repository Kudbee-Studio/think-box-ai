/**
 * Autonomous Decision Loop Dashboard Client.
 *
 * Consumes REST API endpoints from /api/v1/autonomous-loop to render
 * active loops, telemetry metrics, component health, and convergence status.
 */

(function () {
  "use strict";

  let pollingInterval = null;
  let isPolling = true;
  let selectedLoopId = null;

  const ALL_COMPONENTS = [
    "bootstrap",
    "experiment_manager",
    "decomposer",
    "execution",
    "feedback",
    "opportunity",
    "loop_tracer",
    "auto_tuner",
    "generalizer",
    "session_manager"
  ];

  async function fetchStatus() {
    try {
      const res = await fetch("/api/v1/autonomous-loop/status");
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  async function fetchLoops() {
    try {
      const res = await fetch("/api/v1/autonomous-loop/loops");
      if (!res.ok) return [];
      return await res.json();
    } catch (e) {
      return [];
    }
  }

  async function fetchLoopDetail(loopId) {
    if (!loopId) return null;
    try {
      const res = await fetch(`/api/v1/autonomous-loop/loops/${encodeURIComponent(loopId)}`);
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  async function fetchLoopTelemetry(loopId) {
    if (!loopId) return null;
    try {
      const res = await fetch(`/api/v1/autonomous-loop/telemetry/${encodeURIComponent(loopId)}`);
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  async function fetchSessions() {
    try {
      const res = await fetch("/api/v1/autonomous-loop/sessions");
      if (!res.ok) return [];
      return await res.json();
    } catch (e) {
      return [];
    }
  }

  async function fetchSessionSummary() {
    try {
      const res = await fetch("/api/v1/autonomous-loop/sessions/summary");
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      return null;
    }

  function renderStatusOverview(statusData) {
    if (!statusData) {
      document.getElementById("statusVal").textContent = "OFFLINE";
      document.getElementById("statusVal").className = "al-value al-status-warn";
      return;
    }
    const statusVal = document.getElementById("statusVal");
    statusVal.textContent = (statusData.status || "IDLE").toUpperCase();
    if (statusData.status === "healthy") {
      statusVal.className = "al-value al-status-ok";
    } else {
      statusVal.className = "al-value al-status-idle";
    }

    document.getElementById("totalLoopsVal").textContent = statusData.total_loops || 0;
    document.getElementById("activeLoopsVal").textContent = statusData.active_loops || 0;
    document.getElementById("bootstrappedVal").textContent = statusData.bootstrapped_loops || 0;

    const telSummary = statusData.telemetry_summary || {};
    document.getElementById("totalIterationsVal").textContent = telSummary.total_iterations || 0;

    const sessSummary = statusData.loop_session_summary || {};
    document.getElementById("totalSessionsVal").textContent = sessSummary.total_sessions || 0;

    document.getElementById("lastUpdated").textContent = "Updated: " + new Date().toLocaleTimeString();
  }

  function renderLoopList(loops) {
    const listEl = document.getElementById("loopList");
    if (!loops || loops.length === 0) {
      listEl.innerHTML = '<li style="color: var(--color-text-tertiary); cursor: default;">No loops registered</li>';
      selectedLoopId = null;
      renderSelectedLoop(null, null);
      return;
    }

    if (!selectedLoopId || !loops.some(l => l.loop_id === selectedLoopId)) {
      selectedLoopId = loops[0].loop_id;
    }

    listEl.innerHTML = "";
    loops.forEach(loop => {
      const li = document.createElement("li");
      li.dataset.loopId = loop.loop_id;
      if (loop.loop_id === selectedLoopId) {
        li.className = "selected";
      }

      const idSpan = document.createElement("span");
      idSpan.textContent = loop.loop_id;

      const badge = document.createElement("span");
      badge.className = "al-badge " + (loop.status === "running" ? "al-comp-active" : "al-comp-inactive");
      badge.textContent = loop.status || "idle";

      li.appendChild(idSpan);
      li.appendChild(badge);

      li.addEventListener("click", () => {
        selectedLoopId = loop.loop_id;
        document.querySelectorAll("#loopList li").forEach(el => el.classList.remove("selected"));
        li.classList.add("selected");
        refreshSelectedDetail();
      });

      listEl.appendChild(li);
    });
  }

  function renderComponents(componentsMap) {
    const gridEl = document.getElementById("componentsGrid");
    gridEl.innerHTML = "";
    ALL_COMPONENTS.forEach(comp => {
      const pill = document.createElement("div");
      const isWired = componentsMap && componentsMap[comp] === true;
      pill.className = "al-component-pill " + (isWired ? "al-comp-active" : "al-comp-inactive");
      pill.textContent = (isWired ? "✓ " : "✗ ") + comp;
      gridEl.appendChild(pill);
    });
  }

  function renderConvergenceHistory(telemetry) {
    var el = document.getElementById("convergenceHistory");
    if (!telemetry || !telemetry.convergence_history || !telemetry.convergence_history.length) {
      el.textContent = "[]";
      return;
    }
    el.textContent = JSON.stringify(telemetry.convergence_history, null, 2);
  }

  function renderLearningCurve(telemetry) {
    var canvas = document.getElementById("learningCurveCanvas");
    var note = document.getElementById("learningCurveNote");
    if (!canvas) return;
    var points = (telemetry && telemetry.learning_curve_points) || [];
    if (!points.length) {
      note.textContent = "No learning curve data";
      _clearCanvas(canvas);
      return;
    }
    note.textContent = points.length + " iterations tracked";
    _drawLearningCurve(canvas, points);
  }

  function _clearCanvas(canvas) {
    var ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  function _drawLearningCurve(canvas, points) {
    var ctx = canvas.getContext("2d");
    var w = canvas.width;
    var h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    var maxThroughput = Math.max.apply(null, points.map(function(p) { return p.throughput || 0; })) || 1;
    var maxLatency = Math.max.apply(null, points.map(function(p) { return p.avg_p50_latency || 0; })) || 1;

    ctx.strokeStyle = "#4b5563";
    ctx.fillStyle = "#374151";
    ctx.lineWidth = 1;

    var padding = 30;
    var chartW = w - padding - 20;
    var chartH = h - padding - 20;

    ctx.beginPath();
    ctx.moveTo(padding, h - 10);
    ctx.lineTo(w - 10, h - 10);
    ctx.lineTo(w - 10, 10);
    ctx.stroke();

    ctx.fillStyle = "#9ca3af";
    ctx.font = "10px monospace";
    ctx.fillText("throughput", w - 10 - 40, h - 10 - 5);

    var n = points.length;
    var stepX = chartW / Math.max(n - 1, 1);

    ctx.beginPath();
    points.forEach(function(p, i) {
      var x = padding + i * stepX;
      var y = h - 10 - ((p.throughput || 0) / maxThroughput) * chartH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = "#5b9cff";
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = "#5b9cff";
    points.forEach(function(p, i) {
      var x = padding + i * stepX;
      var y = h - 10 - ((p.throughput || 0) / maxThroughput) * chartH;
      ctx.beginPath();
      ctx.arc(x, y, 2.5, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  function renderSessions(sessions) {
    var listEl = document.getElementById("sessionList");
    if (!listEl) return;
    if (!sessions || !sessions.length) {
      listEl.innerHTML = '<li style="color: var(--color-text-tertiary); cursor: default;">No sessions closed</li>';
      return;
    }
    listEl.innerHTML = "";
    sessions.slice(0, 10).forEach(function(sess) {
      var li = document.createElement("li");
      li.style.display = "flex";
      li.style.justifyContent = "space-between";
      li.style.alignItems = "center";

      var info = document.createElement("div");
      info.style.fontFamily = "var(--font-mono)";
      info.style.fontSize = "var(--text-sm)";
      var nameSpan = document.createElement("span");
      nameSpan.style.fontWeight = "bold";
      nameSpan.textContent = sess.session_id;
      var metaSpan = document.createElement("span");
      metaSpan.style.display = "block";
      metaSpan.style.fontSize = "var(--text-xs)";
      metaSpan.style.color = "var(--color-text-tertiary)";
      metaSpan.textContent = "iterations: " + (sess.iterations_count || 0) + " | throughput: " + (sess.avg_throughput || 0).toFixed(3);
      info.appendChild(nameSpan);
      info.appendChild(metaSpan);

      var badge = document.createElement("span");
      badge.className = "al-badge";
      badge.style.background = sess.improved_over_baseline ? "#142e20" : "#20242c";
      badge.style.borderColor = sess.improved_over_baseline ? "#276749" : "#2d3748";
      badge.style.color = sess.improved_over_baseline ? "var(--color-success)" : "var(--color-text-tertiary)";
      badge.textContent = sess.improved_over_baseline ? "improved" : "baseline";

      li.appendChild(info);
      li.appendChild(badge);
      listEl.appendChild(li);
    });
  }

  function renderSelectedLoop(loopData, telemetryData) {
    const headerEl = document.getElementById("selectedLoopHeader");
    const jsonEl = document.getElementById("jsonPayload");
    const telThroughput = document.getElementById("telThroughput");
    const telAvgCycle = document.getElementById("telAvgCycle");
    const telConvergence = document.getElementById("telConvergence");

    if (!loopData) {
      headerEl.textContent = "Select a loop from the list";
      renderComponents({});
      telThroughput.textContent = "—";
      telAvgCycle.textContent = "—";
      telConvergence.textContent = "—";
      jsonEl.textContent = '{ "status": "No loop selected" }';
      return;
    }

    headerEl.textContent = `Loop: ${loopData.loop_id} (${loopData.status || "idle"})`;
    renderComponents(loopData.components || {});

    const tel = telemetryData || loopData.telemetry || {};
    telThroughput.textContent = tel.throughput != null ? tel.throughput : "0.0";
    telAvgCycle.textContent = tel.avg_cycle_time_s != null ? `${tel.avg_cycle_time_s}s` : "0.0s";

    const conv = tel.convergence_status || "pending";
    telConvergence.textContent = conv.toUpperCase();
    if (conv === "converged") {
      telConvergence.className = "al-value al-status-ok";
    } else if (conv === "improving") {
      telConvergence.className = "al-value al-status-info";
    } else {
      telConvergence.className = "al-value al-status-idle";
    }

    renderLearningCurve(tel);
    renderConvergenceHistory(tel);

    jsonEl.textContent = JSON.stringify({
      loop: loopData,
      telemetry: tel
    }, null, 2);
  }

  async function refreshSelectedDetail() {
    if (!selectedLoopId) {
      renderSelectedLoop(null, null);
      return;
    }
    const [detail, telemetry] = await Promise.all([
      fetchLoopDetail(selectedLoopId),
      fetchLoopTelemetry(selectedLoopId)
    ]);
    renderSelectedLoop(detail, telemetry);
  }

  async function refreshAll() {
    const [statusData, loopsData, sessionsData] = await Promise.all([
      fetchStatus(),
      fetchLoops(),
      fetchSessions()
    ]);
    renderStatusOverview(statusData);
    renderLoopList(loopsData);
    renderSessions(sessionsData);
    await refreshSelectedDetail();
  }

  function setupControls() {
    const btnRefresh = document.getElementById("btnRefresh");
    if (btnRefresh) {
      btnRefresh.addEventListener("click", () => {
        refreshAll();
      });
    }

    const btnTogglePolling = document.getElementById("btnTogglePolling");
    const pollStatus = document.getElementById("pollStatus");
    if (btnTogglePolling) {
      btnTogglePolling.addEventListener("click", () => {
        isPolling = !isPolling;
        if (pollStatus) {
          pollStatus.textContent = isPolling ? "ON" : "OFF";
        }
        if (isPolling) {
          startPolling();
        } else {
          stopPolling();
        }
      });
    }
  }

  function startPolling() {
    stopPolling();
    pollingInterval = setInterval(() => {
      refreshAll();
    }, 5000);
  }

  function stopPolling() {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
  }

  window.addEventListener("DOMContentLoaded", () => {
    setupControls();
    refreshAll();
    startPolling();
  });

  // Export helper for headless/unit verification
  if (typeof window !== "undefined") {
    window.TBAutonomousLoopClient = {
      refreshAll,
      renderStatusOverview,
      renderLoopList,
      renderComponents,
      renderLearningCurve,
      renderSessions,
      fetchSessions,
      fetchSessionSummary,
      ALL_COMPONENTS
    };
  }
})();
