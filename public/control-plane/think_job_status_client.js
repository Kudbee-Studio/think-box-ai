/**
 * Think Job status subscribe + poll fallback (PR #138, #139, #140).
 * Receipt-keyed watch + jobs digest multiplex; shared etag via TBControlPlaneEtag.
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
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        if (!res.body || !res.body.getReader) throw new Error("sse_body_unsupported");
        var reader = res.body.getReader();
        var decoder = new TextDecoder();
        var buf = "";
        function pump() {
          return reader.read().then(function (chunk) {
            if (self._stopped) return;
            if (chunk.done) {
              self.watch.telemetry.sseDisconnectCount += 1;
              self._startPollLoop(plan, false);
              return;
            }
            buf += decoder.decode(chunk.value, { stream: true });
            var parsed = parseSseBuffer(buf);
            buf = parsed.rest;
            parsed.events.forEach(function (event) {
              var changed = applyEvent(self.watch, event);
              if (changed) self.onUpdate(self.watch, event);
              if (event.kind === "think_job_stream_close") {
                abort.abort();
                self._startPollLoop(plan, false);
              }
            });
            return pump();
          });
        }
        return pump();
      })
      .catch(function (err) {
        if (self._stopped || err.name === "AbortError") return;
        self.watch.telemetry.sseDisconnectCount += 1;
        self.watch.telemetry.lastError = String(err);
        self.onError(err, self.watch);
        var delay = backoffDelayMs(self._reconnectAttempt);
        self._reconnectAttempt += 1;
        if (self._reconnectAttempt > 3) {
          self._startPollLoop(plan, true);
          return;
        }
        setTimeout(function () {
          if (!self._stopped) self._consumeFetchSse(plan, url);
        }, delay);
      });
  };

  ThinkJobStatusWatcher.prototype._attachSse = function (plan) {
    var self = this;
    self._consumeFetchSse(plan, plan.streamUrl);
  };

  ThinkJobStatusWatcher.prototype._beginWatch = async function (target) {
    this.stop();
    this._stopped = false;
    this._reconnectAttempt = 0;
    this.watch = createWatch(target.kind === "engine" ? target.key : "", target);
    var pollUrl = pollPathForTarget(target);
    var doc;
    try {
      doc = await this._fetchPoll(pollUrl);
    } catch (err) {
      this.watch.telemetry.lastError = String(err);
      this.onError(err, this.watch);
      throw err;
    }
    this.watch.engineId = docEngineId(doc) || this.watch.engineId;
    this.watch.summary = doc;
    if (target.kind === "receipt" && doc.receipt && doc.receipt.receipt_id) {
      this.watch.receiptId = doc.receipt.receipt_id;
    }
    this.onUpdate(this.watch, { kind: "initial_poll", document: doc, target: target });
    var plan = streamPlanForTarget(target, doc);
    if (!plan.streamAvailable) {
      this._startPollLoop(plan, true);
      return this.watch;
    }
    var sseUrl = target.kind === "receipt" && plan.receiptStreamUrl
      ? plan.receiptStreamUrl
      : plan.streamUrl;
    this._consumeFetchSse(plan, sseUrl);
    return this.watch;
  };

  ThinkJobStatusWatcher.prototype.watchEngine = async function (engineId) {
    return this._beginWatch(resolveWatchTarget(engineId, ""));
  };

  ThinkJobStatusWatcher.prototype.watchReceipt = async function (receiptId) {
    return this._beginWatch(resolveWatchTarget("", receiptId));
  };

  ThinkJobStatusWatcher.prototype.watchTarget = async function (engineId, receiptId) {
    return this._beginWatch(resolveWatchTarget(engineId, receiptId));
  };

  /**
   * Jobs digest multiplex: digest counts + job list poll, optional digest SSE.
   */
  function JobsDigestMultiplexer(options) {
    this.apiKey = options.apiKey || "";
    this.bearer = options.bearer || "";
    this.onPanelUpdate = options.onPanelUpdate || function () {};
    this.onDigestMode = options.onDigestMode || function () {};
    this.onError = options.onError || function () {};
    this.panel = createMultiplexPanel();
    this._etagStore = options.etagStore || {};
    this._pollTimer = null;
    this._sseAbort = null;
    this._stopped = true;
    this._listLimit = options.listLimit || 30;
  }

  JobsDigestMultiplexer.prototype._headers = function () {
    return apiHeaders(this.apiKey, this.bearer);
  };

  JobsDigestMultiplexer.prototype.stop = function () {
    this._stopped = true;
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
    if (this._sseAbort) {
      this._sseAbort.abort();
      this._sseAbort = null;
    }
    this.panel.digestTransport = "idle";
    this.onDigestMode("idle", this.panel);
  };

  JobsDigestMultiplexer.prototype._refreshList = async function () {
    var url = formatJobsListPollPath(this._listLimit, "summary");
    var result = await global.TBLoadPerf.fetchJsonConditional(
      url,
      { headers: this._headers() },
      this._etagStore
    );
    this.panel.digestJobs = result.data.jobs || [];
    if (result.data.dashboard_revision) {
      this.panel.dashboardRevision = result.data.dashboard_revision;
    }
    this.onPanelUpdate(this.panel, { kind: "jobs_list_poll", document: result.data });
  };

  JobsDigestMultiplexer.prototype._refreshDigestCounts = async function () {
    var result = await global.TBLoadPerf.fetchJsonConditional(
      formatJobsDigestPollPath(),
      { headers: this._headers() },
      this._etagStore
    );
    this.panel.digestDocument = result.data;
    if (result.data.dashboard_revision) {
      this.panel.dashboardRevision = result.data.dashboard_revision;
    }
    this.onPanelUpdate(this.panel, { kind: "digest_poll", document: result.data });
  };

  JobsDigestMultiplexer.prototype._startDigestPoll = function (degraded) {
    var self = this;
    if (self._pollTimer) clearInterval(self._pollTimer);
    self.panel.digestTransport = degraded ? "degraded_poll" : "poll";
    self.onDigestMode(self.panel.digestTransport, self.panel);
    async function tick() {
      if (self._stopped || !global.TBLoadPerf.isDocumentVisible()) return;
      try {
        await self._refreshDigestCounts();
        await self._refreshList();
      } catch (err) {
        self.panel.lastDigestError = String(err);
        self.onError(err, self.panel);
      }
    }
    tick();
    self._pollTimer = setInterval(tick, 8000);
  };

  JobsDigestMultiplexer.prototype._attachDigestSse = function () {
    var self = this;
    var url = buildStreamUrl("/api/v1/run/jobs/status/stream", { max_events: "16", timeout_s: "90" });
    var headers = Object.assign({}, self._headers(), { Accept: "text/event-stream" });
    self.panel.digestTransport = "sse";
    self.onDigestMode("sse", self.panel);
    var abort = new AbortController();
    self._sseAbort = abort;
    fetch(url, { headers: headers, signal: abort.signal })
      .then(function (res) {
        if (!res.ok) throw new Error("digest_sse_http_" + res.status);
        if (!res.body || !res.body.getReader) throw new Error("digest_sse_body_unsupported");
        var reader = res.body.getReader();
        var decoder = new TextDecoder();
        var buf = "";
        function pump() {
          return reader.read().then(function (chunk) {
            if (self._stopped) return;
            if (chunk.done) {
              self._startDigestPoll(false);
              return;
            }
            buf += decoder.decode(chunk.value, { stream: true });
            var parsed = parseSseBuffer(buf);
            buf = parsed.rest;
            parsed.events.forEach(function (ev) {
              if (applyDigestEvent(self.panel, ev)) {
                self.onPanelUpdate(self.panel, ev);
              }
            });
            return pump();
          });
        }
        return pump();
      })
      .catch(function (err) {
        if (self._stopped || err.name === "AbortError") return;
        self.panel.lastDigestError = String(err);
        self.onError(err, self.panel);
        self._startDigestPoll(true);
      });
  };

  JobsDigestMultiplexer.prototype.start = async function () {
    this.stop();
    this._stopped = false;
    this.panel = createMultiplexPanel();
    try {
      await this._refreshDigestCounts();
      await this._refreshList();
    } catch (err) {
      this.panel.lastDigestError = String(err);
      this.onError(err, this.panel);
      throw err;
    }
    this._attachDigestSse();
    return this.panel;
  };

  JobsDigestMultiplexer.prototype.setActiveWatch = function (target, watchMode) {
    this.panel.activeTarget = target;
    this.panel.watchTransport = watchMode || "idle";
    this.onPanelUpdate(this.panel, { kind: "active_watch", target: target, mode: watchMode });
  };

  global.TBThinkJobStatus = {
    apiHeaders: apiHeaders,
    buildStreamUrl: buildStreamUrl,
    streamPlanFromPoll: streamPlanFromPoll,
    streamPlanForTarget: streamPlanForTarget,
    resolveWatchTarget: resolveWatchTarget,
    normalizeReceiptKey: normalizeReceiptKey,
    formatReceiptPollPath: formatReceiptPollPath,
    formatJobsDigestPollPath: formatJobsDigestPollPath,
    formatJobsListPollPath: formatJobsListPollPath,
    backoffDelayMs: backoffDelayMs,
    parseSseMessage: parseSseMessage,
    parseSseBuffer: parseSseBuffer,
    applyEvent: applyEvent,
    applyDigestEvent: applyDigestEvent,
    createWatch: createWatch,
    createMultiplexPanel: createMultiplexPanel,
    multiplexChipLabel: multiplexChipLabel,
    ThinkJobStatusWatcher: ThinkJobStatusWatcher,
    JobsDigestMultiplexer: JobsDigestMultiplexer,
  };
})(typeof window !== "undefined" ? window : globalThis);
