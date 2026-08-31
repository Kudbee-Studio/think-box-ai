/**
 * Think Box AI — Main JavaScript
 * Renders real job data into the landing page
 */

const JOBS = [
  {
    id: "job_dogi_split_001",
    title: "DOGI Indexer Split",
    intent: "Verify the Doginals indexer-split case for DOGI (21M vs 2.1B deploys) against live public APIs.",
    hat: "researcher",
    verdict: "unproven",
    sources: 3,
    calls: 6,
  },
  {
    id: "job_compare_dogi_dbit",
    title: "DOGI vs DBIT Compare",
    intent: "Compare DOGI (claimed 21M) and DBIT (claimed 2.1T) as separate tickers across public indexers.",
    hat: "researcher",
    verdict: "unproven",
    sources: 3,
    calls: 6,
  },
  {
    id: "job_inscription_001",
    title: "Inscription Lookup",
    intent: "Look up a single inscription across available indexers and record what each returns.",
    hat: "researcher",
    verdict: "unproven",
    sources: 3,
    calls: 3,
  },
  {
    id: "job_wallet_scan_001",
    title: "Wallet Scan DDCkpBDN",
    intent: "Scan public wallet DDCkpBDN5hkbYJyUqeyVmCV9s8mEoxGFc8 for known Doginals assets.",
    hat: "researcher",
    verdict: "blocked",
    sources: 0,
    calls: 0,
  },
  {
    id: "job_gpu_find_models",
    title: "Find GPU Models",
    intent: "When GPU is started, find 20B and 120B model weights on data disks.",
    hat: "runner",
    verdict: "blocked",
    sources: 0,
    calls: 0,
  },
  {
    id: "job_gpu_serve_20b",
    title: "Serve 20B Model",
    intent: "Serve the 20B model on the GPU via FreeToken and wire Think Box openai_compat to it.",
    hat: "runner",
    verdict: "blocked",
    sources: 0,
    calls: 0,
  },
  {
    id: "job_director_wallet_report_001",
    title: "Director Wallet Report",
    intent: "Orchestrate a full wallet provenance report by chaining researcher jobs.",
    hat: "director",
    verdict: "blocked",
    sources: 0,
    calls: 0,
  },
];

const VERDICTS = {
  succeeded: { label: "Succeeded", count: 0, desc: "Proof complete" },
  failed: { label: "Failed", count: 0, desc: "Proof failed" },
  unproven: { label: "Unproven", count: 3, desc: "APIs insufficient" },
  blocked: { label: "Blocked", count: 4, desc: "Needs human/GPU" },
};

function renderJobs() {
  const grid = document.getElementById("jobs-grid");
  if (!grid) return;

  grid.innerHTML = JOBS.map(job => `
    <div class="card job-card">
      <div class="job-card-header">
        <div>
          <div class="job-card-title">${job.title}</div>
          <div class="job-card-id mono">${job.id}</div>
        </div>
        <span class="badge badge-${job.verdict}">${job.verdict.toUpperCase()}</span>
      </div>
      <p class="job-card-intent">${job.intent}</p>
      <div class="job-card-footer">
        <span class="badge badge-${job.hat}">${job.hat}</span>
        <div class="job-card-meta">
          <span>${job.sources} sources</span>
          <span>${job.calls} calls</span>
        </div>
      </div>
    </div>
  `).join("");
}

function renderVerdicts() {
  const grid = document.getElementById("verdicts-grid");
  if (!grid) return;

  grid.innerHTML = Object.entries(VERDICTS).map(([key, v]) => `
    <div class="verdict-item">
      <div>
        <div class="verdict-item-name">${v.label}</div>
        <div class="text-muted" style="font-size: var(--text-xs);">${v.desc}</div>
      </div>
      <span class="badge badge-${key}">${v.count}</span>
    </div>
  `).join("");
}

function initScrollReveal() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll(".reveal").forEach(el => observer.observe(el));
}

document.addEventListener("DOMContentLoaded", () => {
  renderJobs();
  renderVerdicts();
  initScrollReveal();
});
