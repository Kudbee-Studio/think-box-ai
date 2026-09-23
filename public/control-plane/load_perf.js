/**
 * Control-plane load helpers (PR #135): visibility-aware polling + conditional GET.
 */
(function (global) {
  function isDocumentVisible() {
    return typeof document === "undefined" || document.visibilityState !== "hidden";
  }

  function createVisibilityPoller(fn, intervalMs, hiddenIntervalMs) {
    let timer = null;
    const hidden = hiddenIntervalMs || Math.max(intervalMs * 3, 15000);
    function schedule() {
      if (timer) clearInterval(timer);
      const ms = isDocumentVisible() ? intervalMs : hidden;
      timer = setInterval(function () {
        if (!isDocumentVisible()) return;
        fn();
      }, ms);
    }
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", schedule);
    }
    schedule();
    return {
      stop: function () {
        if (timer) clearInterval(timer);
        document.removeEventListener("visibilitychange", schedule);
      },
      runNow: fn,
    };
  }

  async function fetchJsonConditional(url, options, etagStore) {
    const headers = Object.assign({}, (options && options.headers) || {});
    const key = url;
    if (etagStore && etagStore[key]) {
      headers["If-None-Match"] = etagStore[key];
    }
    const res = await fetch(url, Object.assign({}, options || {}, { headers }));
    if (res.status === 304 && etagStore && etagStore[key + ":body"]) {
      return { cached: true, data: etagStore[key + ":body"], response: res };
    }
    if (!res.ok) {
      throw new Error("HTTP " + res.status);
    }
    const data = await res.json();
    const etag = res.headers.get("ETag");
    if (etagStore && etag) {
      etagStore[key] = etag;
      etagStore[key + ":body"] = data;
    }
    return { cached: false, data, response: res };
  }

  global.TBLoadPerf = {
    isDocumentVisible,
    createVisibilityPoller,
    fetchJsonConditional,
  };
})(typeof window !== "undefined" ? window : globalThis);
