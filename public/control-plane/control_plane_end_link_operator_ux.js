/**
 * END LINK operator UX deepen (PR #159).
 * Batch summary table, chain filters, four-state honesty copy.
 * Hermetic dashboard bind — live_api_called=false.
 */
(function (global) {
  var OPERATOR_UX = "end-link-operator-ux";
  var END_LINK_DEEPEN = "end-link-deepen";
  var FOUR_STATE_MAX = "TEST_VERIFIED";

  function four_state_honesty() {
    return {
      code_complete: "CODE COMPLETE",
      test_verified: "TEST VERIFIED",
      live_verified: "not claimed",
      live_api_called: "false",
      four_state_max: FOUR_STATE_MAX,
      operator_note: "Hermetic dashboard bind only — no Box/Mercury HTTP in this gate.",
    };
  }

  function endLinkBatchSummary(batch) {
    batch = batch || {};
    var items = batch.items || [];
    var valid = Number(batch.valid_count || 0);
    var invalid = Number(batch.invalid_count || 0);
    var total = Number(batch.total || items.length);
    var failClosed = invalid > 0 || total === 0;
    var label =
      total === 0
        ? "batch empty (no receipt ids)"
        : "batch " + valid + "/" + total + " valid" + (invalid ? " — " + invalid + " fail-closed" : "");
    return {
      operator_ux: OPERATOR_UX,
      summary_label: label,
      valid_count: valid,
      invalid_count: invalid,
      total: total,
      fail_closed: failClosed,
      live_api_called: false,
      four_state_max: FOUR_STATE_MAX,
      rows: items.map(function (item) {
        return batchItemRow(item);
      }),
    };
  }

  function batchItemRow(detail) {
    detail = detail || {};
    var valid = !!detail.valid;
    var code = detail.failure_code || null;
    var integrity = detail.link_integrity || "unknown";
    var chip = valid && integrity === "ok" ? "OK" : code ? "FAIL:" + code : "INTEGRITY:" + integrity;
    return {
      receipt_id: detail.receipt_id || "",
      valid: valid,
      failure_code: code,
      link_integrity: integrity,
      prev_receipt_id: detail.prev_receipt_id || null,
      status_chip: chip,
    };
  }

  function renderBatchResults(container, summary) {
    if (!container) return;
    container.innerHTML = "";
    var rows = (summary && summary.rows) || [];
    if (!rows.length) {
      container.textContent = "No batch rows (empty or not run)";
      return;
    }
    var table = document.createElement("table");
    table.className = "rc-mono";
    table.style.width = "100%";
    table.innerHTML =
      "<thead><tr><th>Receipt</th><th>Chip</th><th>integrity</th><th>prev_receipt_id</th><th>failure_code</th></tr></thead>";
    var tbody = document.createElement("tbody");
    rows.forEach(function (row) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        (row.receipt_id || "—") +
        "</td><td>" +
        (row.status_chip || "—") +
        "</td><td>" +
        (row.link_integrity || "—") +
        "</td><td>" +
        (row.prev_receipt_id || "—") +
        "</td><td>" +
        (row.failure_code || "—") +
        "</td>";
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);
  }

  function readChainFilters(form) {
    form = form || {};
    return {
      status: (form.chainFilterStatus && form.chainFilterStatus.value) || "",
      evidence_label: (form.chainFilterEvidenceLabel && form.chainFilterEvidenceLabel.value) || "",
    };
  }

  function applyChainFiltersToFetchOpts(opts, filters) {
    opts = opts || {};
    filters = filters || {};
    if (filters.status) opts.status = filters.status;
    if (filters.evidence_label) opts.evidence_label = filters.evidence_label;
    return opts;
  }

  function formatEndLinkPanelDetail(result) {
    result = result || {};
    return {
      receipt_id: result.receipt_id,
      valid: result.valid,
      link_integrity: result.link_integrity,
      prev_receipt_id: result.prev_receipt_id,
      failure_code: result.failure_code,
      four_state_max: FOUR_STATE_MAX,
      live_api_called: false,
    };
  }

  global.TBEndLinkOperatorUx = {
    OPERATOR_UX: OPERATOR_UX,
    four_state_honesty: four_state_honesty,
    endLinkBatchSummary: endLinkBatchSummary,
    batchItemRow: batchItemRow,
    renderBatchResults: renderBatchResults,
    readChainFilters: readChainFilters,
    applyChainFiltersToFetchOpts: applyChainFiltersToFetchOpts,
    formatEndLinkPanelDetail: formatEndLinkPanelDetail,
  };
})(typeof window !== "undefined" ? window : globalThis);
