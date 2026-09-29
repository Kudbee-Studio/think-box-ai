// kudbEE Advanced Search — Semantic + keyword search across all memory layers

class AdvancedSearch {
  constructor() {
    this.searchIndex = [];
    this.results = [];
    this.filters = {
      layer: 'all',
      type: 'all',
      dateFrom: null,
      dateTo: null,
      tags: [],
      status: 'all'
    };

    this.setupEventListeners();
    this.buildSearchIndex();
  }

  setupEventListeners() {
    const searchBtn = document.getElementById('advanced-search-button');
    if (searchBtn) {
      searchBtn.addEventListener('click', () => this.openSearchModal());
    }

    // Real-time search in modal
    window.addEventListener('DOMContentLoaded', () => {
      const input = document.getElementById('search-query-input');
      if (input) {
        input.addEventListener('input', (e) => this.performSearch(e.target.value));
      }
    });
  }

  buildSearchIndex() {
    // Index memories
    const memoryItems = document.querySelectorAll('.memory-item');
    if (!memoryItems) return;

    this.searchIndex = Array.from(memoryItems).map((el, idx) => ({
      id: `mem-${idx}`,
      type: 'memory',
      title: el.querySelector('strong')?.textContent || '',
      content: el.textContent || '',
      layer: el.querySelector('.memory-layer')?.textContent?.trim() || 'org',
      tags: el.querySelector('small')?.textContent?.split(',').map(t => t.trim()) || [],
      createdAt: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000),
      relevance: 0
    }));

    // Index runs
    const runItems = document.querySelectorAll('.run-item');
    if (runItems) {
      Array.from(runItems).forEach((el, idx) => {
        this.searchIndex.push({
          id: `run-${idx}`,
          type: 'run',
          title: el.querySelector('.goal')?.textContent || 'Unnamed run',
          content: el.textContent || '',
          status: el.querySelector('.run-dot')?.className || 'unknown',
          createdAt: new Date(),
          relevance: 0
        });
      });
    }
  }

  openSearchModal() {
    this.buildSearchIndex();
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.id = 'search-modal';
    modal.innerHTML = `
      <section class="modal modal-wide" role="dialog" aria-modal="true" aria-labelledby="search-title">
        <div class="modal-header">
          <div>
            <span class="modal-eyebrow">SEARCH</span>
            <h2 id="search-title">Advanced Search</h2>
          </div>
          <button class="btn-icon" onclick="this.closest('.modal-backdrop').remove()">×</button>
        </div>

        <div class="search-container">
          <div class="search-input-area">
            <input
              id="search-query-input"
              type="text"
              class="search-input"
              placeholder="Search by keyword, tag, or semantic meaning..."
              autocomplete="off"
            >
            <button class="btn-primary" onclick="advancedSearch.performSearch(document.getElementById('search-query-input').value)">
              Search
            </button>
          </div>

          <div class="search-filters">
            <label>
              Layer:
              <select id="filter-layer" onchange="advancedSearch.updateFilter('layer', this.value)">
                <option value="all">All layers</option>
                <option value="verified">Verified only</option>
                <option value="org">Organization</option>
                <option value="task">Tasks</option>
                <option value="session">Session</option>
              </select>
            </label>

            <label>
              Type:
              <select id="filter-type" onchange="advancedSearch.updateFilter('type', this.value)">
                <option value="all">All types</option>
                <option value="memory">Memories</option>
                <option value="run">Runs</option>
                <option value="task">Tasks</option>
              </select>
            </label>

            <label>
              Tags:
              <input
                type="text"
                id="filter-tags"
                placeholder="Comma-separated tags"
                onchange="advancedSearch.updateFilter('tags', this.value.split(',').map(t => t.trim()))"
              >
            </label>
          </div>

          <div class="search-results" id="search-results">
            <div class="empty-state">Enter a search query to begin</div>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" onclick="this.closest('.modal-backdrop').remove()">Close</button>
        </div>
      </section>
    `;

    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });

    document.body.appendChild(modal);
    setTimeout(() => document.getElementById('search-query-input')?.focus(), 100);
  }

  performSearch(query) {
    if (!query || query.length < 2) {
      this.results = [];
      this.renderResults();
      return;
    }

    const queryLower = query.toLowerCase();
    this.results = this.searchIndex
      .map(item => ({
        ...item,
        relevance: this.calculateRelevance(item, queryLower)
      }))
      .filter(item => item.relevance > 0)
      .filter(item => this.passesFilters(item))
      .sort((a, b) => b.relevance - a.relevance)
      .slice(0, 50);

    this.renderResults();
  }

  calculateRelevance(item, query) {
    let score = 0;

    // Title match (highest weight)
    if (item.title?.toLowerCase().includes(query)) {
      score += 50;
      // Exact word match
      if (item.title?.toLowerCase().split(' ').includes(query)) {
        score += 50;
      }
    }

    // Content match
    if (item.content?.toLowerCase().includes(query)) {
      score += 20;
    }

    // Tag match
    if (item.tags?.some(tag => tag.toLowerCase().includes(query))) {
      score += 30;
    }

    // Recency bonus
    const daysOld = (Date.now() - item.createdAt) / (1000 * 60 * 60 * 24);
    const recencyScore = Math.max(0, 20 - (daysOld * 0.5));
    score += recencyScore;

    return score;
  }

  passesFilters(item) {
    if (this.filters.layer !== 'all' && item.layer !== this.filters.layer) {
      return false;
    }

    if (this.filters.type !== 'all' && item.type !== this.filters.type) {
      return false;
    }

    if (this.filters.tags.length > 0 && item.tags) {
      const hasAnyTag = this.filters.tags.some(tag =>
        item.tags.some(itemTag => itemTag.toLowerCase().includes(tag.toLowerCase()))
      );
      if (!hasAnyTag) return false;
    }

    return true;
  }

  updateFilter(filterName, value) {
    this.filters[filterName] = value;
    const query = document.getElementById('search-query-input')?.value || '';
    if (query.length >= 2) {
      this.performSearch(query);
    }
  }

  renderResults() {
    const resultsEl = document.getElementById('search-results');
    if (!resultsEl) return;

    if (this.results.length === 0) {
      resultsEl.innerHTML = '<div class="empty-state">No results found. Try different keywords.</div>';
      return;
    }

    resultsEl.innerHTML = `
      <div class="search-results-header">Found ${this.results.length} results</div>
      ${this.results.map(result => `
        <div class="search-result-item">
          <div class="result-header">
            <span class="result-icon">${this.getTypeIcon(result.type)}</span>
            <h4>${this.highlightQuery(result.title)}</h4>
            ${result.layer ? `<span class="memory-layer ${result.layer}">${result.layer}</span>` : ''}
          </div>
          <p class="result-content">${this.escapeHtml(result.content.substring(0, 120))}...</p>
          <div class="result-meta">
            <span class="result-score">Relevance: ${Math.round(result.relevance)}%</span>
            ${result.tags?.length > 0 ? `<span class="result-tags">${result.tags.slice(0, 2).join(', ')}</span>` : ''}
          </div>
        </div>
      `).join('')}
    `;
  }

  getTypeIcon(type) {
    const icons = {
      memory: '💭',
      run: '⚡',
      task: '✓',
      default: '📄'
    };
    return icons[type] || icons.default;
  }

  highlightQuery(text) {
    const query = document.getElementById('search-query-input')?.value;
    if (!query) return this.escapeHtml(text);
    const safe = this.escapeHtml(text);
    const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return safe.replace(new RegExp(`(${escapedQuery})`, 'gi'), '<mark>$1</mark>');
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
  }

  exportResults() {
    const csv = this.results.map(r =>
      `"${r.title}","${r.type}","${r.layer || 'N/A'}",${r.relevance}`
    ).join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'search-results.csv';
    a.click();
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.advancedSearch = new AdvancedSearch();
});
