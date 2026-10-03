// Example Plugin Implementation - Use as template for new plugins

export const plugin = {
  async activate(api) {
    const manifest = api.getManifest();
    api.log('info', `Activating ${manifest.name} v${manifest.version}`);

    // Register example panel
    await api.registerPanel({
      id: 'stats-panel',
      title: 'Plugin Stats',
      icon: '📊',
      async render(container) {
        container.innerHTML = `
          <div style="padding: 16px;">
            <h4 style="margin-bottom: 12px;">Plugin Information</h4>
            <dl style="font-size: 12px; line-height: 1.8;">
              <dt style="font-weight: 600;">Name:</dt>
              <dd>${manifest.name}</dd>
              <dt style="font-weight: 600;">Version:</dt>
              <dd>${manifest.version}</dd>
              <dt style="font-weight: 600;">Status:</dt>
              <dd>🟢 Active</dd>
            </dl>
          </div>
        `;
        api.log('info', 'Panel rendered');
      },
      async cleanup() {
        api.log('info', 'Panel cleanup');
      },
    });

    // Register example command
    await api.registerCommand({
      name: 'hello',
      description: 'Say hello from plugin',
      async execute(name = 'World') {
        const greeting = `Hello, ${name}! Message from ${manifest.name}`;
        api.log('info', greeting);
        return greeting;
      },
    });

    // Listen for messages from dashboard
    api.onMessage('refresh', (data) => {
      api.log('info', 'Received refresh message', data);
    });

    api.log('info', `${manifest.name} activated successfully`);
  },

  async deactivate() {
    console.log('Example plugin deactivated');
  },

  getCapabilities() {
    return ['panel', 'command'];
  },
};
