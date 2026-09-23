/**
 * Deep-link helpers: receipts.html → think_job_status receipt watch (PR #140).
 */
(function (global) {
  var RECEIPT_KEYS = ["receipt_id", "watch_receipt", "receipt"];
  var ENGINE_KEYS = ["engine_id", "watch_engine", "engine"];

  function firstParam(params, keys) {
    for (var i = 0; i < keys.length; i++) {
      var v = params.get(keys[i]);
      if (v && String(v).trim()) return String(v).trim();
    }
    return "";
  }

  function truthy(raw) {
    return ["1", "true", "yes", "on"].indexOf(String(raw || "").toLowerCase()) >= 0;
  }

  function parseQueryString(qs) {
    var s = (qs || "").replace(/^\?/, "");
    return new URLSearchParams(s);
  }

  function parseLocation(loc) {
    loc = loc || (typeof window !== "undefined" ? window.location : { search: "", hash: "" });
    var params = parseQueryString(loc.search || "");
    var receipt = firstParam(params, RECEIPT_KEYS);
    var engine = firstParam(params, ENGINE_KEYS);
    var autoWatch = truthy(firstParam(params, ["auto_watch", "watch"]));
    var fromPage = firstParam(params, ["from"]);
    if (!receipt && loc.hash) {
      var hash = String(loc.hash || "").replace(/^#/, "");
      if (hash.indexOf("=") >= 0) {
        var hp = parseQueryString(hash);
        receipt = receipt || firstParam(hp, RECEIPT_KEYS);
        engine = engine || firstParam(hp, ENGINE_KEYS);
        autoWatch = autoWatch || truthy(firstParam(hp, ["auto_watch", "watch"]));
      } else if (hash) {
        receipt = hash;
        autoWatch = true;
      }
    }
    if (receipt && global.TBThinkJobStatus) {
      try {
        receipt = global.TBThinkJobStatus.normalizeReceiptKey(receipt);
      } catch (e) {
        return { error: String(e), receipt_id: "", engine_id: "", auto_watch: false, from: fromPage };
      }
    }
    if (engine && global.TBThinkJobStatus) {
      try {
        engine = global.TBThinkJobStatus.normalizeEngineKey(engine);
      } catch (e) {
        return { error: String(e), receipt_id: receipt, engine_id: "", auto_watch: false, from: fromPage };
      }
    }
    if (!autoWatch && receipt) autoWatch = true;
    return {
      receipt_id: receipt,
      engine_id: engine,
      auto_watch: autoWatch,
      from: fromPage,
      error: "",
    };
  }

  function buildWatchHref(receiptId, opts) {
    opts = opts || {};
    var rec = receiptId || "";
    if (global.TBThinkJobStatus) {
      rec = global.TBThinkJobStatus.normalizeReceiptKey(rec);
    }
    var params = new URLSearchParams();
    params.set("receipt_id", rec);
    if (opts.autoWatch !== false) params.set("auto_watch", "1");
    if (opts.from) params.set("from", opts.from);
    if (opts.engineId) params.set("engine_id", opts.engineId);
    if (opts.useHash) {
      return "think_job_status.html#" + params.toString();
    }
    return "think_job_status.html?" + params.toString();
  }

  global.TBControlPlaneDeepLink = {
    parseLocation: parseLocation,
    buildWatchHref: buildWatchHref,
    RECEIPT_KEYS: RECEIPT_KEYS,
  };
})(typeof window !== "undefined" ? window : globalThis);
