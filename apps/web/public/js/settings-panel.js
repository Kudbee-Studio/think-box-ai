// kudbEE Settings & Preferences — User configuration panel

class SettingsPanel {
  constructor() {
    this.settings = this.loadSettings();
    this.setupEventListeners();
  }

  loadSettings() {
    const stored = localStorage.getItem('kudbee-settings');
    return stored ? JSON.parse(stored) : {
      theme: 'auto',
      fontSize: 'medium',
      notifications: true,
      autoSave: true,
      soundEnabled: false,
      commandPalette: true,
      darkMode: true,
      compactMode: false,
      showTips: true,
      language: 'en'
    };
  }

  saveSettings() {
    localStorage.setItem('kudbee-settings', JSON.stringify(this.settings));
    this.applySettings();
  }

  setupEventListeners() {
    const settingsBtn = document.getElementById('settings-button');
    if (settingsBtn) {
      settingsBtn.addEventListener('click', () => this.openSettings());
    }

    window.addEventListener('settings:open', () => this.openSettings());
  }

  openSettings() {
    const modal = this.createSettingsModal();
    document.body.appendChild(modal);
    modal.focus();
  }

  createSettingsModal() {
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.id = 'settings-modal';
    modal.innerHTML = `
      <section class="modal" role="dialog" aria-modal="true" aria-labelledby="settings-title">
        <div class="modal-header">
          <div>
            <span class="modal-eyebrow">PREFERENCES</span>
            <h2 id="settings-title">Settings & Preferences</h2>
          </div>
          <button class="btn-icon" onclick="this.closest('.modal-backdrop').remove()">×</button>
        </div>

        <div class="settings-tabs">
          <button class="settings-tab active" data-tab="appearance">🎨 Appearance</button>
          <button class="settings-tab" data-tab="notifications">🔔 Notifications</button>
          <button class="settings-tab" data-tab="shortcuts">⌨ Shortcuts</button>
          <button class="settings-tab" data-tab="advanced">⚙ Advanced</button>
        </div>

        <div class="settings-content">
          <div class="settings-section active" data-section="appearance">
            <h3>Appearance</h3>
            <label>
              Theme
              <select id="theme-select" onchange="settingsPanel.updateSetting('theme', this.value)">
                <option value="auto" ${this.settings.theme === 'auto' ? 'selected' : ''}>Auto (system)</option>
                <option value="light" ${this.settings.theme === 'light' ? 'selected' : ''}>Light</option>
                <option value="dark" ${this.settings.theme === 'dark' ? 'selected' : ''}>Dark</option>
              </select>
            </label>
            <label>
              Font Size
              <select id="font-select" onchange="settingsPanel.updateSetting('fontSize', this.value)">
                <option value="small" ${this.settings.fontSize === 'small' ? 'selected' : ''}>Small</option>
                <option value="medium" ${this.settings.fontSize === 'medium' ? 'selected' : ''}>Medium</option>
                <option value="large" ${this.settings.fontSize === 'large' ? 'selected' : ''}>Large</option>
              </select>
            </label>
            <label>
              <input type="checkbox" id="compact-mode" ${this.settings.compactMode ? 'checked' : ''}
                onchange="settingsPanel.updateSetting('compactMode', this.checked)">
              Compact mode
            </label>
          </div>

          <div class="settings-section" data-section="notifications">
            <h3>Notifications</h3>
            <label>
              <input type="checkbox" id="notifications-enabled" ${this.settings.notifications ? 'checked' : ''}
                onchange="settingsPanel.updateSetting('notifications', this.checked)">
              Enable notifications
            </label>
            <label>
              <input type="checkbox" id="sound-enabled" ${this.settings.soundEnabled ? 'checked' : ''}
                onchange="settingsPanel.updateSetting('soundEnabled', this.checked)">
              Sound effects
            </label>
            <label>
              <input type="checkbox" id="show-tips" ${this.settings.showTips ? 'checked' : ''}
                onchange="settingsPanel.updateSetting('showTips', this.checked)">
              Show helpful tips
            </label>
          </div>

          <div class="settings-section" data-section="shortcuts">
            <h3>Keyboard Shortcuts</h3>
            <div class="shortcuts-list">
              <div class="shortcut-item">
                <span class="shortcut-key">Cmd/Ctrl + K</span>
                <span class="shortcut-desc">Open command palette</span>
              </div>
              <div class="shortcut-item">
                <span class="shortcut-key">Cmd/Ctrl + /</span>
                <span class="shortcut-desc">Toggle sidebar</span>
              </div>
              <div class="shortcut-item">
                <span class="shortcut-key">Cmd/Ctrl + .</span>
                <span class="shortcut-desc">Open settings</span>
              </div>
              <div class="shortcut-item">
                <span class="shortcut-key">Escape</span>
                <span class="shortcut-desc">Close modals</span>
              </div>
            </div>
          </div>

          <div class="settings-section" data-section="advanced">
            <h3>Advanced</h3>
            <label>
              <input type="checkbox" id="auto-save" ${this.settings.autoSave ? 'checked' : ''}
                onchange="settingsPanel.updateSetting('autoSave', this.checked)">
              Auto-save drafts
            </label>
            <label>
              Language
              <select id="language-select" onchange="settingsPanel.updateSetting('language', this.value)">
                <option value="en" ${this.settings.language === 'en' ? 'selected' : ''}>English</option>
                <option value="es" ${this.settings.language === 'es' ? 'selected' : ''}>Español</option>
                <option value="fr" ${this.settings.language === 'fr' ? 'selected' : ''}>Français</option>
                <option value="de" ${this.settings.language === 'de' ? 'selected' : ''}>Deutsch</option>
              </select>
            </label>
            <button class="btn-danger" onclick="settingsPanel.resetSettings()">Reset to defaults</button>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" onclick="this.closest('.modal-backdrop').remove()">Done</button>
        </div>
      </section>
    `;

    // Setup tab switching
    modal.querySelectorAll('.settings-tab').forEach(tab => {
      tab.addEventListener('click', (e) => {
        modal.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
        modal.querySelectorAll('.settings-section').forEach(s => s.classList.remove('active'));
        e.target.classList.add('active');
        modal.querySelector(`[data-section="${e.target.dataset.tab}"]`)?.classList.add('active');
      });
    });

    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });

    return modal;
  }

  updateSetting(key, value) {
    this.settings[key] = value;
    this.saveSettings();
    window.dispatchEvent(new CustomEvent('settings:changed', { detail: { key, value } }));
  }

  applySettings() {
    const root = document.documentElement;

    // Apply theme
    if (this.settings.theme === 'light') {
      root.style.colorScheme = 'light';
    } else if (this.settings.theme === 'dark') {
      root.style.colorScheme = 'dark';
    }

    // Apply font size
    const fontSizes = {
      small: '12px',
      medium: '13px',
      large: '14px'
    };
    root.style.setProperty('--font-size-body', fontSizes[this.settings.fontSize] || '13px');

    // Apply compact mode
    if (this.settings.compactMode) {
      root.classList.add('compact-mode');
    } else {
      root.classList.remove('compact-mode');
    }
  }

  resetSettings() {
    if (confirm('Reset all settings to defaults? This cannot be undone.')) {
      this.settings = this.loadSettings();
      localStorage.removeItem('kudbee-settings');
      location.reload();
    }
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.settingsPanel = new SettingsPanel();
});
