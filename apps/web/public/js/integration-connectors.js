// kudbEE Integration Connectors — Connect Slack, GitHub, Jira, Linear, etc.

class IntegrationConnectors {
  constructor() {
    this.integrations = readStoredJson('kudbee-integrations', {});
    this.connectors = {
      slack: { icon: '💬', name: 'Slack', description: 'Post updates to Slack channels' },
      github: { icon: '🐙', name: 'GitHub', description: 'Sync issues and pull requests' },
      jira: { icon: '📋', name: 'Jira', description: 'Create and update tickets' },
      linear: { icon: '➡️', name: 'Linear', description: 'Track issues in Linear' },
      discord: { icon: '🎮', name: 'Discord', description: 'Send alerts to Discord' },
      email: { icon: '📧', name: 'Email', description: 'Send notifications via email' },
      webhook: { icon: '🔗', name: 'Webhook', description: 'Custom HTTP webhooks' },
      zapier: { icon: '⚡', name: 'Zapier', description: '9000+ integrations' }
    };
    this.setupEventListeners();
  }

  setupEventListeners() {
    // Instances are created on DOMContentLoaded, so wire the header button now (a nested
    // DOMContentLoaded listener would never fire and the button would do nothing).
    const intBtn = document.getElementById('integrations-button');
    if (intBtn) {
      intBtn.addEventListener('click', () => this.openConnectors());
    }

    window.addEventListener('integration:trigger', (e) => {
      this.triggerIntegration(e.detail);
    });
  }

  openConnectors() {
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.id = 'integrations-modal';
    modal.innerHTML = `
      <section class="modal modal-wide" role="dialog" aria-modal="true">
        <div class="modal-header">
          <div>
            <span class="modal-eyebrow">INTEGRATIONS · DEMO</span>
            <h2>Integrations</h2>
          </div>
          <button class="btn-icon" data-action="close">×</button>
        </div>

        <div class="demo-banner" role="note">Demo data - not connected to real services</div>

        <div class="integrations-container">
          <div class="connectors-grid">
            ${Object.entries(this.connectors).map(([key, connector]) => `
                <div class="connector-card" data-connector="${escapeHtml(key)}">
                  <div class="connector-icon">${connector.icon}</div>
                  <h3>${escapeHtml(connector.name)}</h3>
                  <p>${escapeHtml(connector.description)}</p>
                  <div class="connector-status">
                    <span class="status-badge disconnected">○ Not connected</span>
                    <button class="btn-secondary" type="button" disabled title="Demo only: kudbEE has no ${escapeHtml(connector.name)} integration yet">Simulated (demo)</button>
                  </div>
                </div>
              `).join('')}
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" data-action="close">Close</button>
        </div>
      </section>
    `;

    modal.addEventListener('click', (e) => {
      if (e.target === modal) { modal.remove(); return; }
      this.handleModalAction(e, modal);
    });

    document.body.appendChild(modal);
  }

  handleModalAction(e, modal) {
    const el = e.target.closest ? e.target.closest('[data-action]') : null;
    if (!el || !modal.contains(el)) return;
    const action = el.dataset.action;
    if (action === 'close') modal.remove();
    else if (action === 'save-config') this.saveConfig(el.dataset.service);
    else if (action === 'save-automation') this.saveAutomation();
    else if (action === 'update-automation') this.updateAutomation(el.dataset.service, Number(el.dataset.index));
    else if (action === 'template') {
      const msg = document.getElementById('automation-message');
      if (msg) msg.value = el.dataset.template;
    }
  }

  disconnect(service) {
    if (confirm(`Disconnect from ${this.connectors[service].name}?`)) {
      delete this.integrations[service];
      localStorage.setItem('kudbee-integrations', JSON.stringify(this.integrations));
      this.openConnectors();
    }
  }

  configureConnector(service) {
    if (!this.integrations[service]) return;
    const connector = this.integrations[service];
    const configModal = document.createElement('div');
    configModal.className = 'modal-backdrop';
    configModal.innerHTML = `
      <section class="modal" role="dialog" aria-modal="true">
        <div class="modal-header">
          <h2>Configure ${escapeHtml(this.connectors[service].name)}</h2>
          <button class="btn-icon" data-action="close">×</button>
        </div>

        <div class="config-form">
          <fieldset>
            <legend>Notification Settings</legend>
            <label>
              <input type="checkbox" ${connector.config?.notifyOnSuccess ? 'checked' : ''}>
              Notify on success
            </label>
            <label>
              <input type="checkbox" ${connector.config?.notifyOnError ? 'checked' : ''}>
              Notify on error
            </label>
            <label>
              <input type="checkbox" ${connector.config?.autoSync ? 'checked' : ''}>
              Auto-sync enabled
            </label>
          </fieldset>

          <fieldset>
            <legend>Advanced</legend>
            <label>
              Sync interval (minutes):
              <input type="number" value="${Number(connector.config?.syncInterval) || 15}" min="1" max="1440">
            </label>
          </fieldset>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" data-action="close">Cancel</button>
          <button class="btn-primary" data-action="save-config" data-service="${escapeHtml(service)}">Save</button>
        </div>
      </section>
    `;

    configModal.addEventListener('click', (e) => {
      if (e.target === configModal) { configModal.remove(); return; }
      this.handleModalAction(e, configModal);
    });

    document.body.appendChild(configModal);
  }

  saveConfig(service) {
    if (!this.integrations[service]) return;
    const config = this.integrations[service].config || {};
    config.notifyOnSuccess = document.querySelector('input:checked')?.value === 'success' || false;
    config.notifyOnError = document.querySelectorAll('input:checked').length > 1 || false;
    config.autoSync = Array.from(document.querySelectorAll('input[type="checkbox"]:checked')).some(el => el.id === 'auto-sync');
    const interval = document.querySelector('input[type="number"]')?.value;
    if (interval) config.syncInterval = parseInt(interval, 10);
    this.integrations[service].config = config;
    localStorage.setItem('kudbee-integrations', JSON.stringify(this.integrations));
    document.querySelector('.modal-backdrop')?.remove();
  }

  createAutomation() {
    const automationModal = document.createElement('div');
    automationModal.className = 'modal-backdrop';
    automationModal.innerHTML = `
      <section class="modal" role="dialog" aria-modal="true">
        <div class="modal-header">
          <h2>Create Automation</h2>
          <button class="btn-icon" data-action="close">×</button>
        </div>

        <div class="automation-form">
          <label>
            When:
            <select id="trigger-select">
              <option value="task-completed">Task completes</option>
              <option value="error-occurs">Error occurs</option>
              <option value="daily">Daily at time</option>
              <option value="manual">Manual trigger</option>
            </select>
          </label>

          <label>
            Then notify:
            <select id="service-select">
              <option value="">Choose service...</option>
              ${Object.entries(this.integrations)
                .filter(([_, int]) => int.connected)
                .map(([key, int]) => `<option value="${escapeHtml(key)}">${escapeHtml(this.connectors[key]?.name || key)}</option>`)
                .join('')}
            </select>
          </label>

          <label>
            Message:
            <textarea id="automation-message" placeholder="Enter message or choose template..."></textarea>
          </label>

          <div class="templates">
            <span>Templates:</span>
            <button class="template-btn" data-action="template" data-template="Task {task_name} completed successfully">Task Completed</button>
            <button class="template-btn" data-action="template" data-template="⚠️ Error: {error_message}">Error Alert</button>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" data-action="close">Cancel</button>
          <button class="btn-success" data-action="save-automation">Create</button>
        </div>
      </section>
    `;

    automationModal.addEventListener('click', (e) => {
      if (e.target === automationModal) { automationModal.remove(); return; }
      this.handleModalAction(e, automationModal);
    });

    document.body.appendChild(automationModal);
  }

  editAutomation(service, index) {
    if (!this.integrations[service]?.automations?.[index]) return;
    const automation = this.integrations[service].automations[index];
    const automationModal = document.createElement('div');
    automationModal.className = 'modal-backdrop';
    automationModal.innerHTML = `
      <section class="modal" role="dialog" aria-modal="true">
        <div class="modal-header">
          <h2>Edit Automation</h2>
          <button class="btn-icon" data-action="close">×</button>
        </div>
        <div class="automation-form">
          <label>
            When:
            <select id="trigger-select">
              <option value="task-completed" ${automation.trigger === 'task-completed' ? 'selected' : ''}>Task completes</option>
              <option value="error-occurs" ${automation.trigger === 'error-occurs' ? 'selected' : ''}>Error occurs</option>
              <option value="daily" ${automation.trigger === 'daily' ? 'selected' : ''}>Daily at time</option>
              <option value="manual" ${automation.trigger === 'manual' ? 'selected' : ''}>Manual trigger</option>
            </select>
          </label>
          <label>
            Message:
            <textarea id="automation-message" placeholder="Enter message...">${escapeHtml(automation.message || '')}</textarea>
          </label>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" data-action="close">Cancel</button>
          <button class="btn-success" data-action="update-automation" data-service="${escapeHtml(service)}" data-index="${Number(index) || 0}">Update</button>
        </div>
      </section>
    `;
    automationModal.addEventListener('click', (e) => {
      if (e.target === automationModal) { automationModal.remove(); return; }
      this.handleModalAction(e, automationModal);
    });
    document.body.appendChild(automationModal);
  }

  updateAutomation(service, index) {
    if (!this.integrations[service]?.automations?.[index]) return;
    this.integrations[service].automations[index].trigger = document.getElementById('trigger-select')?.value || 'manual';
    this.integrations[service].automations[index].message = document.getElementById('automation-message')?.value || '';
    localStorage.setItem('kudbee-integrations', JSON.stringify(this.integrations));
    document.querySelector('.modal-backdrop')?.remove();
  }

  saveAutomation() {
    const serviceSelect = document.getElementById('service-select');
    const service = serviceSelect?.value;
    if (!service) return;
    if (!this.integrations[service]) return;

    const automation = {
      id: `automation-${Date.now()}`,
      trigger: document.getElementById('trigger-select')?.value || 'manual',
      service: service,
      message: document.getElementById('automation-message')?.value || '',
      createdAt: new Date().toISOString()
    };

    if (!this.integrations[service].automations) {
      this.integrations[service].automations = [];
    }
    this.integrations[service].automations.push(automation);
    localStorage.setItem('kudbee-integrations', JSON.stringify(this.integrations));
    document.querySelector('.modal-backdrop')?.remove();
    this.openConnectors();
  }

  triggerIntegration(data) {
    Object.entries(this.integrations).forEach(([service, integration]) => {
      if (integration.connected && integration.automations?.some(a => a.trigger === data.trigger)) {
        this.sendToService(service, data);
      }
    });
  }

  sendToService(service, data) {
    console.log(`[${service.toUpperCase()}] Sending:`, data);
    window.dispatchEvent(new CustomEvent('integration:sent', { detail: { service, data } }));
  }

  getDefaultConfig(service) {
    return {
      autoSync: false,
      notifyOnSuccess: false,
      notifyOnError: true,
      syncInterval: 15
    };
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.integrationConnectors = new IntegrationConnectors();
});
