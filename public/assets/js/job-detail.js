/**
 * Think Box AI — Job Detail page
 * Secure rendering with XSS protection
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

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function renderJobDetail() {
  const params = new URLSearchParams(window.location.search);
  const jobId = params.get("id") || "job_dogi_split_001";
  const job = JOB_DETAIL[jobId] || JOB_DETAIL["job_dogi_split_001"];

  const container = document.getElementById("job-detail");
  if (!container) return;

  const backLink = document.createElement("div");
  backLink.style.marginBottom = "var(--space-8)";
  backLink.innerHTML = '<a href="../jobs/" class="btn btn-ghost">← Back to Jobs</a>';
  container.appendChild(backLink);

  const headerCard = document.createElement("div");
  headerCard.className = "card card-elevated";
  headerCard.style.marginBottom = "var(--space-8)";

  const headerFlex = document.createElement("div");
  headerFlex.style.display = "flex";
  headerFlex.style.justifyContent = "space-between";
  headerFlex.style.alignItems = "flex-start";
  headerFlex.style.marginBottom = "var(--space-6)";

  const titleGroup = document.createElement("div");
  const title = document.createElement("h1");
  title.style.marginBottom = "var(--space-2)";
  title.textContent = job.title;
  const idPara = document.createElement("p");
  idPara.className = "mono text-muted";
  idPara.textContent = jobId;
  titleGroup.appendChild(title);
  titleGroup.appendChild(idPara);

  const verdictBadge = document.createElement("span");
  verdictBadge.className = "badge badge-" + job.verdict;
  verdictBadge.textContent = job.verdict.toUpperCase();

  headerFlex.appendChild(titleGroup);
  headerFlex.appendChild(verdictBadge);
  headerCard.appendChild(headerFlex);

  const intentPara = document.createElement("p");
  intentPara.style.fontSize = "var(--text-lg)";
  intentPara.style.marginBottom = "var(--space-6)";
  intentPara.textContent = job.intent;
  headerCard.appendChild(intentPara);

  const badgeGroup = document.createElement("div");
  badgeGroup.style.display = "flex";
  badgeGroup.style.gap = "var(--space-4)";

  const hatBadge = document.createElement("span");
  hatBadge.className = "badge badge-" + job.hat;
  hatBadge.textContent = job.hat;
  badgeGroup.appendChild(hatBadge);

  const costBadge = document.createElement("span");
  costBadge.className = "badge";
  costBadge.textContent = job.cost.http_calls + " HTTP calls";
  badgeGroup.appendChild(costBadge);

  headerCard.appendChild(badgeGroup);
  container.appendChild(headerCard);

  const execTitle = document.createElement("h2");
  execTitle.style.marginBottom = "var(--space-6)";
  execTitle.textContent = "Execution";
  container.appendChild(execTitle);

  const timeline = document.createElement("div");
  timeline.className = "timeline";
  timeline.style.marginBottom = "var(--space-8)";

  for (const e of job.execution) {
    const item = document.createElement("div");
    item.className = "timeline-item " + e.status;
    const strong = document.createElement("strong");
    strong.textContent = "Step " + e.step + ": ";
    item.appendChild(strong);
    item.appendChild(document.createTextNode(e.tool));
    const span = document.createElement("span");
    span.className = "text-muted";
    span.textContent = " — " + e.result;
    item.appendChild(span);
    timeline.appendChild(item);
  }
  container.appendChild(timeline);

  const verdictCard = document.createElement("div");
  verdictCard.className = "card";
  const verdictTitle = document.createElement("h3");
  verdictTitle.style.marginBottom = "var(--space-4)";
  verdictTitle.textContent = "Verdict";
  verdictCard.appendChild(verdictTitle);

  const verdictDiv = document.createElement("div");
  verdictDiv.className = "verdict";
  const verdictStrong = document.createElement("strong");
  verdictStrong.className = "badge badge-" + job.verdict;
  verdictStrong.textContent = job.verdict.toUpperCase();
  verdictDiv.appendChild(verdictStrong);

  const reasonPara = document.createElement("p");
  reasonPara.style.marginTop = "var(--space-2)";
  reasonPara.textContent = job.reason;
  verdictDiv.appendChild(reasonPara);

  verdictCard.appendChild(verdictDiv);
  container.appendChild(verdictCard);
}

document.addEventListener("DOMContentLoaded", renderJobDetail);
