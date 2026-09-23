/**
 * END LINK + receipt-chain dashboard client (PR #156).
 * Proprietary END_LINK API: GET /api/v1/control-plane/receipts/{receipt_id}/validate
 * Conditional: If-None-Match → 304, If-Match mismatch → 412
 */
(function (global) {
  var API_PREFIX = "/api/v1/control-plane";
  var END_LINK_API = "END_LINK";

  function chainPaths() {
    return {
      chain: API_PREFIX + "/receipts/chain",
      page: API_PREFIX + "/receipts/chain/page",
      head: API_PREFIX + "/receipts/chain/head",
      tail: API_PREFIX + "/receipts/chain/tail",
      end_link_template: API_PREFIX + "/receipts/{receipt_id}/validate",
      end_link_api: END_LINK_API,
    };
  }

  function buildEndLinkPath(receiptId) {
    var rid = String(receiptId || "").trim();
    if (!rid) throw new Error("receipt_id_required");
    return API_PREFIX + "/receipts/" + encodeURIComponent(rid) + "/validate";
  }

  function unwrapEnvelope(json) {
    if (json && json.data && typeof json.data === "object") return json.data;
    return json || {};
  }

  async function fetchJsonWithEtag(url, options, etagStore) {
    if (global.TBLoadPerf && global.TBLoadPerf.fetchJsonConditional) {
      return global.TBLoadPerf.fetchJsonConditional(url, options, etagStore);
    }
    var res = await fetch(url, options || {});
    if (!res.ok) {
      return { cached: false, data: null, response: res, error: "HTTP " + res.status };
    }
    var data = await res.json();
    return { cached: false, data: data, response: res };
  }

  async function fetchChainPage(opts, etagStore, authHeaders) {
    opts = opts || {};
    var paths = chainPaths();
    var params = new URLSearchParams();
    if (opts.limit) params.set("limit", String(opts.limit));
    if (opts.cursor) params.set("cursor", opts.cursor);
    if (opts.action) params.set("action", opts.action);
    if (opts.agent_id) params.set("agent_id", opts.agent_id);
    var url = paths.page + (params.toString() ? "?" + params.toString() : "");
    var result = await fetchJsonWithEtag(
      url,
      { headers: Object.assign({}, authHeaders || {}) },
      etagStore,
    );
    if (result.response && result.response.status === 304) {
      return { cached: true, not_modified: true, page: unwrapEnvelope(result.data), url: url };
    }
    return {
      cached: !!result.cached,
      not_modified: false,
      page: unwrapEnvelope(result.data),
      url: url,
      etag: result.response && result.response.headers.get("ETag"),
    };
  }

  async function fetchChainProbe(kind, etagStore, authHeaders) {
    var paths = chainPaths();
    var url = kind === "head" ? paths.head : paths.tail;
    var result = await fetchJsonWithEtag(
      url,
      { headers: Object.assign({}, authHeaders || {}) },
      etagStore,
    );
    return {
      kind: kind,
      cached: !!result.cached,
      body: unwrapEnvelope(result.data),
      url: url,
    };
  }

  async function endLinkValidate(receiptId, opts, etagStore, authHeaders) {
    opts = opts || {};
    var url = buildEndLinkPath(receiptId);
    var headers = Object.assign({}, authHeaders || {});
    if (opts.ifMatch) headers["If-Match"] = opts.ifMatch;
    var res = await fetch(url, { headers: headers });
    if (res.status === 412) {
      return {
        api: END_LINK_API,
        valid: false,
        http_status: 412,
        precondition_failed: true,
        url: url,
      };
    }
    if (res.status === 304) {
      return {
        api: END_LINK_API,
        valid: true,
        http_status: 304,
        not_modified: true,
        url: url,
      };
    }
    if (!res.ok) {
      return {
        api: END_LINK_API,
        valid: false,
        http_status: res.status,
        url: url,
        error: "HTTP " + res.status,
      };
    }
    var json = await res.json();
    var data = unwrapEnvelope(json);
    var etag = res.headers.get("ETag");
    if (etagStore && etag) {
      etagStore[url] = etag;
      if (etagStore.__tbPersist) etagStore.__tbPersist();
    }
    return {
      api: END_LINK_API,
      valid: !!data.valid,
      receipt_id: data.receipt_id || receiptId,
      http_status: res.status,
      etag: etag,
      url: url,
      body: data,
    };
  }

  function buildDashboardHref(receiptId) {
    var params = new URLSearchParams();
    if (receiptId) params.set("receipt_id", receiptId);
    params.set("from", "receipts");
    return "receipt_chain_dashboard.html?" + params.toString();
  }

  global.TBEndLink = {
    END_LINK_API: END_LINK_API,
    API_PREFIX: API_PREFIX,
    chainPaths: chainPaths,
    buildEndLinkPath: buildEndLinkPath,
    fetchChainPage: fetchChainPage,
    fetchChainProbe: fetchChainProbe,
    endLinkValidate: endLinkValidate,
    buildDashboardHref: buildDashboardHref,
  };
})(typeof window !== "undefined" ? window : globalThis);
