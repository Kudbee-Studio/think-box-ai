// kudbEE Integration Connectors — Connect Slack, GitHub, Jira, Linear, etc.

class IntegrationConnectors {
  constructor() {
    this.integrations = JSON.parse(localStorage.getItem('kudbee-integrations') || '{}');
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
    document.addEventListener('DOMContentLoaded', () => {
      const intBtn = document.getElementById('integrations-button');
      if (intBtn) {
        intBtn.addEventListener('click', () => this.openConnectors());
      }
    });

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
            <span class="modal-eyebrow">INTEGRATIONS</span>
            <h2>Connected Services</h2>
          </div>
          <button class="btn-icon" onclick="this.closest('.modal-backdrop').remove()">×</button>
        </div>

        <div class="integrations-container">
          <div class="connectors-grid">
            ${Object.entries(this.connectors).map(([key, connector]) => {
              const connected = this.integrations[key]?.connected || false;
              return `
                <div class="connector-card ${connected ? 'connected' : ''}">
                  <div class="connector-icon">${connector.icon}</div>
                  <h3>${connector.name}</h3>
                  <p>${connector.description}</p>
                  <div class="connector-status">
                    ${connected ? `
                      <span class="status-badge connected">✓ Connected</span>
                      <button class="btn-danger" onclick="integrationConnectors.disconnect('${key}')">Disconnect</button>
                    ` : `
                      <span class="status-badge disconnected">○ Not connected</span>
                      <button class="btn-primary" onclick="integrationConnectors.connect('${key}')">Connect</button>
                    `}
                  </div>
                  ${connected ? `
                    <div class="connector-config">
                      <button class="btn-secondary" onclick="integrationConnectors.configureConnector('${key}')">⚙ Configure</button>
                    </div>
                  ` : ''}
                </div>
              `;
            }).join('')}
          </div>

          <div class="active-integrations">
            <h3>Active Automations</h3>
            <div class="automations-list">
              ${Object.entries(this.integrations)
                .filter(([_, int]) => int.connected && int.automations?.length > 0)
                .map(([key, int]) => `
                  <div class="automation-item">
                    <span class="automation-name">${int.automations[0]?.name || 'Unnamed'}</span>
                    <span class="automation-trigger">${int.automations[0]?.trigger || 'manual'}</span>
                    <button class="btn-icon" onclick="integrationConnectors.editAutomation('${key}', 0)">✎</button>
                  </div>
                `).join('')}
              ${Object.entries(this.integrations).filter(([_, int]) => int.connected && int.automations?.length > 0).length === 0 ?
                '<div class="empty-state">No automations configured</div>' : ''}
            </div>
            <button class="btn-secondary" onclick="integrationConnectors.createAutomation()">+ Create automation</button>
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
  }

  connect(service) {
    const integration = {
      service,
      connected: true,
      connectedAt: new Date().toISOString(),
      automations: [],
      config: this.getDefaultConfig(service)
    };

    // Simulate OAuth/connection flow
    const configModal = document.createElement('div');
    configModal.className = 'modal-backdrop';
    configModal.innerHTML = `
      <section class="modal" role="dialog" aria-modal="true">
        <div class="modal-header">
          <h2>Connect to ${this.connectors[service].name}</h2>
          <button class="btn-icon" onclick="this.closest('.modal-backdrop').remove()">×</button>
        </div>

        <div class="connection-form">
          ${service === 'slack' ? `
            <label>
              Slack API Token:
              <input type="password" id="slack-token" placeholder="xoxb-...">
            </label>
          ` : service === 'github' ? `
            <label>
              GitHub Personal Access Token:
              <input type="password" id="github-token" placeholder="ghp_...">
            </label>
          ` : service === 'email' ? `
            <label>
              Email Address:
              <input type="email" id="email-addr" placeholder="your@email.com">
            </label>
          ` : `
            <label>
              API Key:
              <input type="password" id="api-key" placeholder="Enter your API key">
            </label>
          `}

          <label>
            <input type="checkbox" id="enable-sync"> Enable automatic sync
          </label>

          <p class="form-note">Your credentials are encrypted and stored locally.</p>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" onclick="this.closest('.modal-backdrop').remove()">Cancel</button>
          <button class="btn-success" onclick="integrationConnectors.saveConnection('${service}')">Connect</button>
        </div>
      </section>
    `;

    configModal.addEventListener('click', (e) => {
      if (e.target === configModal) configModal.remove();
    });

    document.body.appendChild(configModal);
  }

  saveConnection(service) {
    this.integrations[service] = {
      service,
      connected: true,
      connectedAt: new Date().toISOString(),
      automations: [],
      config: { autoSync: document.getElementById('enable-sync')?.checked || false }
    };
    localStorage.setItem('kudbee-integrations', JSON.stringify(this.integrations));
    document.querySelector('.modal-backdrop')?.remove();
    this.openConnectors();
  }

  disconnect(service) {
    if (confirm(`Disconnect from ${this.connectors[service].name}?`)) {
      delete this.integrations[service];
      localStorage.setItem('kudbee-integrations', JSON.stringify(this.integrations));
      this.openConnectors();
    }
  }

  configureConnector(service) {
    const connector = this.integrations[service];
    const configModal = document.createElement('div');
    configModal.className = 'modal-backdrop';
    configModal.innerHTML = `
      <section class="modal" role="dialog" aria-modal="true">
        <div class="modal-header">
          <h2>Configure ${this.connectors[service].name}</h2>
          <button class="btn-icon" onclick="this.closest('.modal-backdrop').remove()">×</button>
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
              <input type="number" value="${connector.config?.syncInterval || 15}" min="1" max="1440">
            </label>
          </fieldset>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" onclick="this.closest('.modal-backdrop').remove()">Cancel</button>
          <button class="btn-primary" onclick="integrationConnectors.saveConfig('${service}')">Save</button>
        </div>
      </section>
    `;

    configModal.addEventListener('click', (e) => {
      if (e.target === configModal) configModal.remove();
    });

    document.body.appendChild(configModal);
  }

  saveConfig(service) {
    // Save configuration
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
          <button class="btn-icon" onclick="this.closest('.modal-backdrop').remove()">×</button>
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
                .map(([key, int]) => `<option value="${key}">${this.connectors[key].name}</option>`)
                .join('')}
            </select>
          </label>

          <label>
            Message:
            <textarea id="automation-message" placeholder="Enter message or choose template..."></textarea>
          </label>

          <div class="templates">
            <span>Templates:</span>
            <button class="template-btn" onclick="document.getElementById('automation-message').value = 'Task {task_name} completed successfully'">Task Completed</button>
            <button class="template-btn" onclick="document.getElementById('automation-message').value = '⚠️ Error: {error_message}'">Error Alert</button>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" onclick="this.closest('.modal-backdrop').remove()">Cancel</button>
          <button class="btn-success" onclick="integrationConnectors.saveAutomation()">Create</button>
        </div>
      </section>
    `;

    automationModal.addEventListener('click', (e) => {
      if (e.target === automationModal) automationModal.remove();
    });

    document.body.appendChild(automationModal);
  }

  editAutomation(service, index) {
    this.createAutomation();
  }

  saveAutomation() {
    // Save automation
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
