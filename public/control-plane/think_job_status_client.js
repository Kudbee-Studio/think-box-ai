/**
 * Think Job status subscribe + poll fallback (PR #138, #139).
 * Receipt-keyed watch + jobs digest multiplex panel (hermetic only).
 * Uses poll.stream hints from #137 — no parallel status plane.
 */
(function (global) {
  var DEFAULT_STREAM_QUERY = { max_events: "32", timeout_s: "120", heartbeat_s: "15" };
  var MIN_BACKOFF_MS = 500;
  var MAX_BACKOFF_MS = 30000;
  var BACKOFF_FACTOR = 1.8;

  function apiHeaders(apiKey, bearer) {
    var headers = { Accept: "application/json" };
    var key = (apiKey || "").trim();
    var tok = (bearer || "").trim();
    if (key) {
      headers["X-API-Key"] = key;
    } else if (tok) {
      headers.Authorization = tok.indexOf("Bearer ") === 0 ? tok : "Bearer " + tok;
    } else {
      throw new Error("api_key_or_bearer_required");
    }
    return headers;
  }

  function buildStreamUrl(path, query) {
    var params = Object.assign({}, DEFAULT_STREAM_QUERY, query || {});
    var qs = Object.keys(params)
      .map(function (k) {
        return encodeURIComponent(k) + "=" + encodeURIComponent(params[k]);
      })
      .join("&");
    return path + "?" + qs;
  }

  function streamPlanFromPoll(doc) {
    var poll = doc.poll || {};
    var stream = poll.stream || {};
    var engineId = String(doc.engine_id || doc.job_id || "");
    var jobTemplate = stream.job_path || "/api/v1/run/job/{engine_id}/status/stream";
    var streamPath = jobTemplate.replace("{engine_id}", engineId);
    var receipt = doc.receipt || {};
    var receiptId = String(receipt.receipt_id || "");
    var receiptTemplate = stream.receipt_path || "";
    var receiptStream = receiptId && receiptTemplate
      ? buildStreamUrl(receiptTemplate.replace("{receipt_id}", receiptId))
      : null;
    return {
      pollUrl: "/api/v1/run/job/" + engineId + "/status",
      streamUrl: buildStreamUrl(streamPath),
      receiptStreamUrl: receiptStream,
      recommendedIntervalMs: Math.max(500, poll.recommended_interval_ms || 5000),
      streamAvailable: stream.stream_available !== false,
    };
  }

  function backoffDelayMs(attempt) {
    var delay = MIN_BACKOFF_MS * Math.pow(BACKOFF_FACTOR, Math.max(0, attempt));
    return Math.min(MAX_BACKOFF_MS, Math.ceil(delay));
  }

  function parseSseMessage(data) {
    try {
      return JSON.parse(data);
    } catch (e) {
      return { kind: "parse_error", error: String(e) };
    }
  }

  function applyEvent(watch, event) {
    var kind = event.kind || "";
    watch.telemetry.eventsReceived += 1;
    if (kind === "think_job_stream_hello" && event.snapshot) {
      watch.summary = event.snapshot;
      watch.lastSequence = event.sequence || 0;
      return true;
    }
    if (kind === "think_job_status_delta") {
      var seq = event.sequence || 0;
      if (seq >= watch.lastSequence) watch.lastSequence = seq;
      watch.summary = Object.assign({}, watch.summary || {}, {
        status: event.status,
        phase: event.phase,
        progress: event.progress,
        job_id: event.job_id,
        engine_id: event.engine_id,
        receipt: event.receipt,
        tasks_total: event.tasks_total,
        tasks_completed: event.tasks_completed,
        poll: event.poll,
        four_state: event.four_state,
      });
      return true;
    }
    if (kind === "think_job_stream_close") {
      watch.telemetry.lastError = "stream_close:" + (event.reason || "closed");
      return false;
    }
    if (kind === "parse_error") {
      watch.telemetry.lastError = event.error || "sse_parse_error";
      watch.telemetry.pollErrorCount += 1;
    }
    return false;
  }

  function formatReceiptPollPath(receiptId) {
    return "/api/v1/run/job/by-receipt/" + receiptId + "/status";
  }

  function formatJobsDigestPollPath() {
    return "/api/v1/run/jobs/status/digest";
  }

  function formatJobsListPollPath(limit, detail) {
    var lim = Math.max(1, Math.min(limit || 50, 200));
    return "/api/v1/run/jobs/status?limit=" + lim + "&detail=" + (detail || "summary");
  }

  function normalizeReceiptKey(raw) {
    var key = String(raw || "").trim();
    if (!key) throw new Error("receipt_key_required");
    if (key.length > 256) throw new Error("receipt_key_too_long");
    if (key.toLowerCase().indexOf("receipt_missing") === 0) throw new Error("receipt_key_invalid");
    return key;
  }

  function normalizeEngineKey(raw) {
    var key = String(raw || "").trim();
    if (!key) throw new Error("engine_key_required");
    return key;
  }

  function resolveWatchTarget(engineId, receiptId) {
    var eng = String(engineId || "").trim();
    var rec = String(receiptId || "").trim();
    if (rec) return { kind: "receipt", key: normalizeReceiptKey(rec) };
    if (eng) return { kind: "engine", key: normalizeEngineKey(eng) };
    throw new Error("watch_target_required");
  }

  function pollPathForTarget(target) {
    if (target.kind === "receipt") return formatReceiptPollPath(target.key);
    return "/api/v1/run/job/" + target.key + "/status";
  }

  function streamPlanForTarget(target, doc) {
    if (target.kind === "receipt") {
      var receipt = doc.receipt || {};
      if (!receipt.receipt_id || receipt.receipt_id !== target.key) {
        throw new Error("receipt_key_mismatch");
      }
    }
    var plan = streamPlanFromPoll(doc);
    if (target.kind === "receipt") {
      var rUrl = plan.receiptStreamUrl || buildStreamUrl(
        "/api/v1/run/job/by-receipt/" + target.key + "/status/stream"
      );
      plan.pollUrl = formatReceiptPollPath(target.key);
      plan.streamUrl = rUrl;
      plan.receiptStreamUrl = rUrl;
    }
    return plan;
  }

  function createWatch(engineId, target) {
    var t = target || { kind: "engine", key: engineId };
    return {
      engineId: t.kind === "engine" ? t.key : String(engineId || ""),
      summary: null,
      lastSequence: 0,
      watchKind: t.kind,
      watchKey: t.key,
      receiptId: t.kind === "receipt" ? t.key : "",
      telemetry: {
        lastError: "",
        sseDisconnectCount: 0,
        pollErrorCount: 0,
        mode: "idle",
        eventsReceived: 0,
      },
    };
  }

  function docEngineId(doc) {
    if (!doc) return "";
    return String(doc.engine_id || doc.job_id || "");
  }

  function createMultiplexPanel() {
    return {
      digestDocument: null,
      digestJobs: [],
      dashboardRevision: 0,
      digestTransport: "idle",
      watchTransport: "idle",
      activeTarget: null,
      lastDigestError: "",
      lastWatchError: "",
    };
  }

  function applyDigestEvent(panel, event) {
    var kind = event.kind || "";
    if (kind === "think_jobs_stream_hello" && event.digest) {
      panel.digestDocument = event.digest;
      panel.dashboardRevision = event.digest.dashboard_revision || 0;
      return true;
    }
    if (kind === "think_jobs_digest_delta") {
      if (event.digest) panel.digestDocument = event.digest;
      if (event.dashboard_revision) panel.dashboardRevision = event.dashboard_revision;
      return true;
    }
    return false;
  }

  function multiplexChipLabel(panel) {
    var parts = [];
    if (panel.digestTransport && panel.digestTransport !== "idle") {
      parts.push("digest:" + panel.digestTransport);
    }
    if (panel.watchTransport && panel.watchTransport !== "idle") {
      parts.push("watch:" + panel.watchTransport);
    }
    if (panel.activeTarget) {
      parts.push(panel.activeTarget.kind + ":" + panel.activeTarget.key.slice(0, 12));
    }
    return parts.length ? parts.join(" · ") : "idle";
  }

  /**
   * Subscribe via EventSource; on error/disconnect invokes onFallback and polls.
   */
  function ThinkJobStatusWatcher(options) {
    this.apiKey = options.apiKey || "";
    this.bearer = options.bearer || "";
    this.onUpdate = options.onUpdate || function () {};
    this.onModeChange = options.onModeChange || function () {};
    this.onError = options.onError || function () {};
    this._eventSource = null;
    this._pollTimer = null;
    this._reconnectAttempt = 0;
    this._stopped = false;
    this.watch = null;
    this._etagStore = options.etagStore || {};
  }

  ThinkJobStatusWatcher.prototype._setMode = function (mode) {
    if (!this.watch) return;
    this.watch.telemetry.mode = mode;
    this.onModeChange(mode, this.watch);
  };

  ThinkJobStatusWatcher.prototype.stop = function () {
    this._stopped = true;
    if (this._sseAbort) {
      this._sseAbort.abort();
      this._sseAbort = null;
    }
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
    this._setMode("idle");
  };

  ThinkJobStatusWatcher.prototype._headers = function () {
    return apiHeaders(this.apiKey, this.bearer);
  };

  ThinkJobStatusWatcher.prototype._fetchPoll = async function (pollUrl) {
    var headers = this._headers();
    var result = await global.TBLoadPerf.fetchJsonConditional(pollUrl, { headers: headers }, this._etagStore);
    return result.data;
  };

  ThinkJobStatusWatcher.prototype._startPollLoop = function (plan, degraded) {
    var self = this;
    if (self._pollTimer) clearInterval(self._pollTimer);
    self._setMode(degraded ? "degraded_poll" : "poll");
    var interval = plan.recommendedIntervalMs || 5000;
    async function tick() {
      if (self._stopped || !global.TBLoadPerf.isDocumentVisible()) return;
      try {
        var doc = await self._fetchPoll(plan.pollUrl);
        self.watch.summary = doc;
        self.onUpdate(self.watch, { kind: "poll_snapshot", document: doc });
      } catch (err) {
        self.watch.telemetry.pollErrorCount += 1;
        self.watch.telemetry.lastError = String(err);
        self.onError(err, self.watch);
      }
    }
    tick();
    self._pollTimer = setInterval(tick, interval);
  };

  function parseSseBuffer(buffer) {
    var events = [];
    var parts = buffer.split("\n\n");
    var rest = "";
    if (parts.length) {
      rest = parts.pop() || "";
    }
    parts.forEach(function (block) {
      var dataLine = block.split("\n").filter(function (ln) {
        return ln.indexOf("data: ") === 0;
      })[0];
      if (dataLine) events.push(parseSseMessage(dataLine.slice(6)));
    });
    return { events: events, rest: rest };
  }

  ThinkJobStatusWatcher.prototype._consumeFetchSse = function (plan, url) {
    var self = this;
    var headers = Object.assign({}, self._headers(), { Accept: "text/event-stream" });
    self._setMode("sse");
    var abort = new AbortController();
    self._sseAbort = abort;
    fetch(url, { headers: headers, signal: abort.signal })
