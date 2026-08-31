/**
 * Think Box AI — Job Detail page
 */

const JOB_DETAIL = {
  job_dogi_split_001: {
    title: "DOGI Indexer Split",
    intent: "Verify the Doginals indexer-split case for DOGI (21M vs 2.1B deploys) against live public APIs.",
    hat: "researcher",
    verdict: "unproven",
    reason: "Public APIs do not show both DOGI deploys. Cannot verify indexer split.",
    execution: [
      { step: 1, tool: "indexer_health", status: "ok", result: "Checked 5 sources" },
      { step: 2, tool: "compare_inscription", status: "blocked", result: "doginals_org: 404" },
      { step: 3, tool: "compare_inscription", status: "blocked", result: "dogechain: 403" },
      { step: 4, tool: "compare_inscription", status: "blocked", result: "ordinalsdotcom: timeout" },
      { step: 5, tool: "fs_write", status: "ok", result: "Finding written" },
    ],
    cost: { box_minutes: 0, gpu_minutes: 0, http_calls: 6 },
  },
  job_compare_dogi_dbit: {
    title: "DOGI vs DBIT Compare",
    intent: "Compare DOGI (claimed 21M) and DBIT (claimed 2.1T) as separate tickers across public indexers.",
    hat: "researcher",
    verdict: "unproven",
    reason: "Public APIs cannot fetch inscription content for either ticker.",
    execution: [
      { step: 1, tool: "indexer_health", status: "ok", result: "Checked 5 sources" },
      { step: 2, tool: "compare_inscription", status: "blocked", result: "doginals_org: 404" },
      { step: 3, tool: "compare_inscription", status: "blocked", result: "dogechain: 403" },
    ],
    cost: { box_minutes: 0, gpu_minutes: 0, http_calls: 6 },
  },
};

function renderJobDetail() {
  const params = new URLSearchParams(window.location.search);
  const jobId = params.get("id") || "job_dogi_split_001";
  const job = JOB_DETAIL[jobId] || JOB_DETAIL["job_dogi_split_001"];

  const container = document.getElementById("job-detail");
  container.innerHTML = `
    <div style="margin-bottom: var(--space-8);">
      <a href="../jobs/" class="btn btn-ghost">← Back to Jobs</a>
    </div>
    <div class="card card-elevated" style="margin-bottom: var(--space-8);">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: var(--space-6);">
        <div>
          <h1 style="margin-bottom: var(--space-2);">${job.title}</h1>
          <p class="mono text-muted">${jobId}</p>
        </div>
        <span class="badge badge-${job.verdict}">${job.verdict.toUpperCase()}</span>
      </div>
      <p style="font-size: var(--text-lg); margin-bottom: var(--space-6);">${job.intent}</p>
      <div style="display: flex; gap: var(--space-4);">
        <span class="badge badge-${job.hat}">${job.hat}</span>
        <span class="badge">${job.cost.http_calls} HTTP calls</span>
      </div>
    </div>

    <h2 style="margin-bottom: var(--space-6);">Execution</h2>
    <div class="timeline" style="margin-bottom: var(--space-8);">
      ${job.execution.map(e => `
        <div class="timeline-item ${e.status}">
          <strong>Step ${e.step}:</strong> ${e.tool}
          <span class="text-muted">— ${e.result}</span>
        </div>
      `).join("")}
    </div>

    <div class="card">
      <h3 style="margin-bottom: var(--space-4);">Verdict</h3>
      <div class="verdict">
        <strong class="badge badge-${job.verdict}">${job.verdict.toUpperCase()}</strong>
        <p style="margin-top: var(--space-2);">${job.reason}</p>
      </div>
    </div>
  `;
}

document.addEventListener("DOMContentLoaded", renderJobDetail);
