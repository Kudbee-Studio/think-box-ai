/* THINK BOX AI — Enterprise Features Module */

const Enterprise = {
  // 1. ADVANCED SESSION MANAGEMENT
  sessionManager: {
    sessions: [],
    currentSession: null,

    create(name) {
      const session = {
        id: Date.now(),
        name: name || `Session ${new Date().toLocaleTimeString()}`,
        created: new Date(),
        tasks: 0,
        messages: 0,
        status: 'active'
      };
      this.sessions.push(session);
      this.save();
      return session;
    },

    list() {
      return this.sessions;
    },

    save() {
      try {
        localStorage.setItem('enterprise_sessions', JSON.stringify(this.sessions));
      } catch (e) {
        console.error('Session save failed:', e);
      }
    },

    load() {
      try {
        const saved = localStorage.getItem('enterprise_sessions');
        if (saved) this.sessions = JSON.parse(saved);
      } catch (e) {
        console.error('Session load failed:', e);
      }
    }
  },

  // 2. REAL-TIME METRICS & MONITORING
  metrics: {
    data: {
      totalRequests: 0,
      totalLatency: 0,
      avgLatency: 0,
      successRate: 100,
      errorCount: 0,
      throughput: 0
    },

    record(latency, success = true) {
      this.data.totalRequests++;
      this.data.totalLatency += latency;
      this.data.avgLatency = this.data.totalLatency / this.data.totalRequests;
      if (!success) this.data.errorCount++;
      this.data.successRate = ((this.data.totalRequests - this.data.errorCount) / this.data.totalRequests * 100).toFixed(1);
      this.broadcast();
    },

    broadcast() {
      const event = new CustomEvent('metricsUpdated', { detail: this.data });
      document.dispatchEvent(event);
    },

    get() {
      return this.data;
    }
  },

  // 3. CAPACITY MANAGEMENT
  capacity: {
    limits: {
      maxConcurrent: 10,
      maxQueueSize: 100,
      maxSessionDuration: 3600000 // 1 hour
    },

    current: {
      activeAgents: 0,
      queuedTasks: 0,
      cpuUsage: 0,
      memoryUsage: 0
    },

    update(data) {
      Object.assign(this.current, data);
      const event = new CustomEvent('capacityUpdated', { detail: this.current });
      document.dispatchEvent(event);
    },

    getUtilization() {
      return {
        agents: (this.current.activeAgents / this.limits.maxConcurrent * 100).toFixed(1),
        queue: (this.current.queuedTasks / this.limits.maxQueueSize * 100).toFixed(1),
        cpu: this.current.cpuUsage,
        memory: this.current.memoryUsage
      };
    }
  },

  // 4. AUDIT LOG & ACTIVITY HISTORY
  auditLog: {
    logs: [],

    log(action, details, severity = 'info') {
      const entry = {
        id: Date.now(),
        timestamp: new Date(),
        action,
        details,
        severity,
        userId: 'system'
      };
      this.logs.unshift(entry);
      if (this.logs.length > 1000) this.logs.pop();
      this.save();
      return entry;
    },

    getRecent(limit = 50) {
      return this.logs.slice(0, limit);
    },

    export() {
      return JSON.stringify(this.logs, null, 2);
    },

    save() {
      try {
        localStorage.setItem('enterprise_audit', JSON.stringify(this.logs));
      } catch (e) {
        console.error('Audit log save failed:', e);
      }
    },

    load() {
      try {
        const saved = localStorage.getItem('enterprise_audit');
        if (saved) this.logs = JSON.parse(saved);
      } catch (e) {
        console.error('Audit log load failed:', e);
      }
    }
  },

  // 5. NOTIFICATIONS & ALERTS
  notifications: {
    queue: [],
    listeners: [],

    notify(type, title, message, duration = 5000) {
      const notification = {
        id: Date.now(),
        type, // 'success', 'error', 'warning', 'info'
        title,
        message,
        timestamp: new Date(),
        read: false
      };
      this.queue.unshift(notification);
      this.listeners.forEach(fn => fn(notification));

      if (duration > 0) {
        setTimeout(() => this.dismiss(notification.id), duration);
      }
      return notification;
    },

    dismiss(id) {
      this.queue = this.queue.filter(n => n.id !== id);
    },

    getUnread() {
      return this.queue.filter(n => !n.read);
    },

    subscribe(fn) {
      this.listeners.push(fn);
    }
  },

  // 6. ADVANCED FILTERING & SEARCH
  search: {
    filters: {
      status: 'all',
      type: 'all',
      timeRange: '24h',
      searchQuery: ''
    },

    applyFilters(items) {
      return items.filter(item => {
        if (this.filters.status !== 'all' && item.status !== this.filters.status) return false;
        if (this.filters.type !== 'all' && item.type !== this.filters.type) return false;
        if (this.filters.searchQuery && !item.name?.toLowerCase().includes(this.filters.searchQuery.toLowerCase())) return false;
        return true;
      });
    },

    setFilter(key, value) {
      this.filters[key] = value;
      const event = new CustomEvent('filtersChanged', { detail: this.filters });
      document.dispatchEvent(event);
    }
  },

  // 7. THEME MANAGEMENT (Dark/Light)
  theme: {
    current: 'dark',

    set(theme) {
      this.current = theme;
      document.documentElement.setAttribute('data-theme', theme);
      localStorage.setItem('theme', theme);
      const event = new CustomEvent('themeChanged', { detail: theme });
      document.dispatchEvent(event);
    },

    toggle() {
      const next = this.current === 'dark' ? 'light' : 'dark';
      this.set(next);
    },

    load() {
      const saved = localStorage.getItem('theme') || 'dark';
      this.set(saved);
    }
  },

  // 8. KEYBOARD SHORTCUTS & COMMAND PALETTE
  shortcuts: {
    registry: {
      'ctrl+k': () => Enterprise.commandPalette.open(),
      'ctrl+/': () => Enterprise.shortcuts.showHelp(),
      'alt+d': () => Enterprise.theme.toggle()
    },

    init() {
      document.addEventListener('keydown', (e) => {
        const combo = `${e.ctrlKey ? 'ctrl+' : ''}${e.altKey ? 'alt+' : ''}${e.key.toLowerCase()}`;
        if (this.registry[combo]) {
          e.preventDefault();
          this.registry[combo]();
        }
      });
    },

    showHelp() {
      const help = Object.keys(this.registry).map(key => `${key}: ${key}`).join('\n');
      console.log('Keyboard Shortcuts:\n' + help);
    }
  },

  // 9. COMMAND PALETTE
  commandPalette: {
    commands: [
      { id: 'new-session', label: 'New Session', action: () => console.log('New session') },
      { id: 'export', label: 'Export Session', action: () => Enterprise.export.exportSession() },
      { id: 'settings', label: 'Settings', action: () => console.log('Settings') },
      { id: 'help', label: 'Help', action: () => Enterprise.shortcuts.showHelp() },
      { id: 'clear-logs', label: 'Clear Logs', action: () => Enterprise.auditLog.logs = [] }
    ],

    open() {
      console.log('Command palette opened');
      console.log('Available commands:', this.commands.map(c => c.label).join(', '));
    },

    search(query) {
      return this.commands.filter(c => c.label.toLowerCase().includes(query.toLowerCase()));
    }
  },

  // 10. EXPORT/IMPORT & DATA MANAGEMENT
  export: {
    exportSession(sessionId) {
      const data = {
        session: Enterprise.sessionManager.currentSession,
        metrics: Enterprise.metrics.data,
        logs: Enterprise.auditLog.logs,
        timestamp: new Date()
      };

      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `session-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);

      Enterprise.notifications.notify('success', 'Export Complete', 'Session exported successfully');
      Enterprise.auditLog.log('export', 'Session data exported', 'info');
    },

    importSession(file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const data = JSON.parse(e.target.result);
          Enterprise.sessionManager.currentSession = data.session;
          Enterprise.auditLog.log('import', 'Session data imported', 'info');
          Enterprise.notifications.notify('success', 'Import Complete', 'Session imported successfully');
        } catch (err) {
          Enterprise.notifications.notify('error', 'Import Failed', err.message);
        }
      };
      reader.readAsText(file);
    }
  },

  // Initialize all enterprise features
  init() {
    this.sessionManager.load();
    this.auditLog.load();
    this.theme.load();
    this.shortcuts.init();
    this.sessionManager.create('Default');
    this.auditLog.log('system', 'Enterprise features initialized', 'info');
    console.log('✨ Enterprise features initialized');
  }
};

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => Enterprise.init());
} else {
  Enterprise.init();
}
