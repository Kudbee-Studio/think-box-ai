/**
 * Think Job status subscribe + poll fallback (PR #138).
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

  function createWatch(engineId) {
    return {
      engineId: engineId,
      summary: null,
      lastSequence: 0,
      telemetry: {
        lastError: "",
        sseDisconnectCount: 0,
        pollErrorCount: 0,
        mode: "idle",
        eventsReceived: 0,
      },
    };
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

  ThinkJobStatusWatcher.prototype.watchEngine = async function (engineId) {
    this.stop();
    this._stopped = false;
    this._reconnectAttempt = 0;
    this.watch = createWatch(engineId);
    var pollUrl = "/api/v1/run/job/" + engineId + "/status";
    var doc;
    try {
      doc = await this._fetchPoll(pollUrl);
    } catch (err) {
      this.watch.telemetry.lastError = String(err);
      this.onError(err, this.watch);
      throw err;
    }
    this.watch.summary = doc;
    this.onUpdate(this.watch, { kind: "initial_poll", document: doc });
    var plan = streamPlanFromPoll(doc);
    if (!plan.streamAvailable) {
      this._startPollLoop(plan, true);
      return this.watch;
    }
    this._attachSse(plan);
    return this.watch;
  };

  global.TBThinkJobStatus = {
    apiHeaders: apiHeaders,
    buildStreamUrl: buildStreamUrl,
    streamPlanFromPoll: streamPlanFromPoll,
    backoffDelayMs: backoffDelayMs,
    parseSseMessage: parseSseMessage,
    parseSseBuffer: parseSseBuffer,
    applyEvent: applyEvent,
    createWatch: createWatch,
    ThinkJobStatusWatcher: ThinkJobStatusWatcher,
  };
})(typeof window !== "undefined" ? window : globalThis);
