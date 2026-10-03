// Template Browser UI - Workflow template discovery and management

import { getTemplateManager } from '../services/template-manager.js';

export class TemplateBrowserUI {
  constructor() {
    this.templateManager = getTemplateManager();
    this.templatePanel = document.getElementById('template-panel');
    this.container = document.getElementById('template-container');
    this.templateButton = document.getElementById('templates-button');
    this.closeButton = document.getElementById('close-templates');

    this.searchQuery = '';
    this.filterCategory = 'all';
    this.sortBy = 'rating';

    this.init();
  }

  init() {
    if (!this.templateButton) return;

    this.templateButton.addEventListener('click', () => this.toggleTemplates());
    if (this.closeButton) {
      this.closeButton.addEventListener('click', () => this.closeTemplates());
    }
  }

  toggleTemplates() {
    if (this.templatePanel.hidden) {
      this.openTemplates();
    } else {
      this.closeTemplates();
    }
  }

  openTemplates() {
    this.templatePanel.hidden = false;
    this.updateTemplates();
  }

  closeTemplates() {
    this.templatePanel.hidden = true;
  }

  updateTemplates() {
    if (this.templatePanel.hidden) return;

    const templates = this.templateManager.listTemplates();
    const filtered = this.filterAndSort(templates);

    this.container.innerHTML = `
      <div class="template-browser">
        <div class="template-header">
          <h4>Workflow Templates</h4>
          <span class="template-count">${filtered.length}</span>
        </div>

        <!-- Search and Filters -->
        <div class="template-controls">
          <div class="search-box">
            <input type="text" id="template-search" placeholder="Search templates..." class="input-search">
            <span class="search-icon">🔍</span>
          </div>

          <div class="filter-group">
            <select id="template-category" class="select-filter">
              <option value="all">All Categories</option>
              <option value="automation">Automation</option>
              <option value="analysis">Analysis</option>
              <option value="integration">Integration</option>
              <option value="testing">Testing</option>
              <option value="monitoring">Monitoring</option>
            </select>

            <select id="template-sort" class="select-filter">
              <option value="rating">Top Rated</option>
              <option value="usage">Most Used</option>
              <option value="recent">Recently Added</option>
              <option value="name">Name</option>
            </select>
          </div>
        </div>

        <!-- Templates List -->
        <div class="templates-list">
          ${filtered.length > 0
            ? filtered.map(t => this.buildTemplateCard(t)).join('')
            : '<div class="empty-state">No templates found</div>'
          }
        </div>
      </div>
    `;

    this.attachEventListeners();
  }

  buildTemplateCard(template) {
    const ratingStars = this.buildStars(template.rating || 0);
    const categoryColor = {
      'automation': '#06b6d4',
      'analysis': '#3b82f6',
      'integration': '#10b981',
      'testing': '#f59e0b',
      'monitoring': '#ef4444'
    }[template.category] || '#64748b';

    return `
      <div class="template-card">
        <div class="template-header-card">
          <h5>${this.escapeHtml(template.name)}</h5>
          <button class="template-action" data-template-id="${template.id}" title="Use template">➔</button>
        </div>

        <p class="template-desc">${this.escapeHtml(template.description)}</p>

        <div class="template-meta">
          <span class="category-badge" style="background-color: ${categoryColor}20; color: ${categoryColor}">
            ${template.category}
          </span>
          <span class="rating">${ratingStars} ${template.rating.toFixed(1)}</span>
          <span class="usage">${template.usageCount || 0} uses</span>
        </div>

        ${template.tags && template.tags.length > 0 ? `
          <div class="template-tags">
            ${template.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
          </div>
        ` : ''}

        <div class="template-details">
          <span class="detail">⚙️ ${template.steps || 0} steps</span>
          <span class="detail">⏱ ${template.avgDuration || 0}ms avg</span>
          <span class="detail">📅 ${this.formatDate(template.createdAt)}</span>
        </div>
      </div>
    `;
  }

  buildStars(rating) {
    const fullStars = Math.floor(rating);
    const hasHalf = rating % 1 >= 0.5;
    let stars = '★'.repeat(fullStars);
    if (hasHalf) stars += '½';
    stars += '☆'.repeat(5 - Math.ceil(rating));
    return stars;
  }

  filterAndSort(templates) {
    let filtered = templates;

    if (this.searchQuery) {
      const q = this.searchQuery.toLowerCase();
      filtered = filtered.filter(t =>
        t.name.toLowerCase().includes(q) ||
        t.description.toLowerCase().includes(q) ||
        (t.tags && t.tags.some(tag => tag.toLowerCase().includes(q)))
      );
    }

    if (this.filterCategory !== 'all') {
      filtered = filtered.filter(t => t.category === this.filterCategory);
    }

    // Sort
    const comparators = {
      'rating': (a, b) => (b.rating || 0) - (a.rating || 0),
      'usage': (a, b) => (b.usageCount || 0) - (a.usageCount || 0),
      'recent': (a, b) => new Date(b.createdAt) - new Date(a.createdAt),
      'name': (a, b) => a.name.localeCompare(b.name)
    };

    filtered.sort(comparators[this.sortBy] || comparators['rating']);
    return filtered;
  }

  attachEventListeners() {
    const searchInput = document.getElementById('template-search');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        this.searchQuery = e.target.value;
        this.updateTemplates();
      });
    }

    const categorySelect = document.getElementById('template-category');
    if (categorySelect) {
      categorySelect.addEventListener('change', (e) => {
        this.filterCategory = e.target.value;
        this.updateTemplates();
      });
    }

    const sortSelect = document.getElementById('template-sort');
    if (sortSelect) {
      sortSelect.addEventListener('change', (e) => {
        this.sortBy = e.target.value;
        this.updateTemplates();
      });
    }

    document.querySelectorAll('.template-action').forEach(btn => {
      btn.addEventListener('click', () => this.useTemplate(btn.dataset.templateId));
    });
  }

  async useTemplate(templateId) {
    const template = this.templateManager.getTemplate(templateId);
    if (!template) return;

    try {
      // Load template into editor or task system
      this.templateManager.trackUsage(templateId);
      this.showNotification(`Loaded template: ${template.name}`);
      this.updateTemplates();
    } catch (err) {
      this.showNotification(`Error: ${err.message}`, 'error');
    }
  }

  formatDate(date) {
    const d = new Date(date);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  showNotification(message, type = 'info') {
    // TODO: Implement notification system
    console.log(`[${type}] ${message}`);
  }
}
