/**
 * Think Box AI — Jobs page logic
 */

function filterJobs(filter) {
  const buttons = document.querySelectorAll('.jobs-filters .btn');
  buttons.forEach(b => {
    b.classList.remove('active');
    b.classList.toggle('btn-secondary', b.textContent.toLowerCase() === filter || (filter === 'all' && b.textContent === 'All'));
    b.classList.toggle('btn-ghost', b.textContent.toLowerCase() !== filter && !(filter === 'all' && b.textContent === 'All'));
  });

  let filtered = JOBS;
  if (filter === 'done') filtered = JOBS.filter(j => j.verdict !== 'blocked');
  else if (filter === 'blocked') filtered = JOBS.filter(j => j.verdict === 'blocked');
  else if (filter === 'researcher') filtered = JOBS.filter(j => j.hat === 'researcher');
  else if (filter === 'runner') filtered = JOBS.filter(j => j.hat === 'runner');

  renderJobs(filtered);
}

function renderJobs(jobs) {
  const grid = document.getElementById("jobs-grid");
  if (!grid) return;

  if (jobs.length === 0) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column: 1/-1;">
        <div class="empty-state-icon">◎</div>
        <p>No jobs match this filter.</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = jobs.map(job => `
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

function searchJobs(query) {
  if (!query) {
    renderJobs(JOBS);
    return;
  }
  const q = query.toLowerCase();
  const filtered = JOBS.filter(j =>
    j.title.toLowerCase().includes(q) ||
    j.intent.toLowerCase().includes(q) ||
    j.id.toLowerCase().includes(q)
  );
  renderJobs(filtered);
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("jobs-grid")) {
    renderJobs(JOBS);
  }

  // Search functionality
  const searchInput = document.getElementById("job-search");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => searchJobs(e.target.value));
  }
});
