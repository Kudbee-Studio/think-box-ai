// Plugin Manager - Registry, Lifecycle, and Event Bus

import type { Plugin, PluginAPI, PluginManifest, PluginContext, PluginPanel, PluginCommand } from '../types/plugin.js';

const STORAGE_KEY = 'kudbee_plugins';

export class PluginManager {
  private registry: Map<string, PluginContext> = new Map();
  private pluginInstances: Map<string, Plugin> = new Map();
  private panels: Map<string, PluginPanel> = new Map();
  private commands: Map<string, PluginCommand> = new Map();
  private eventHandlers: Map<string, Set<(data: any) => void>> = new Map();

  constructor() {
    this.loadFromStorage();
  }

  // Lifecycle: Install plugin
  async install(pluginPath: string, manifest: PluginManifest): Promise<void> {
    if (this.registry.has(manifest.id)) {
      throw new Error(`Plugin ${manifest.id} already installed`);
    }

    const context: PluginContext = {
      manifest,
      enabled: true,
      installedAt: Date.now(),
      lastUpdated: Date.now(),
      settings: manifest.config || {},
    };

    this.registry.set(manifest.id, context);
    await this.activate(manifest.id);
    this.saveToStorage();
  }

  // Lifecycle: Activate plugin
  async activate(pluginId: string): Promise<void> {
    const context = this.registry.get(pluginId);
    if (!context) throw new Error(`Plugin ${pluginId} not found`);
    if (context.enabled) return;

    try {
      const plugin = this.pluginInstances.get(pluginId);
      if (!plugin) throw new Error(`Plugin instance not loaded`);

      const api = this.createPluginAPI(pluginId);
      await plugin.activate(api);
      context.enabled = true;
      this.saveToStorage();
    } catch (err) {
      this.log(pluginId, 'error', `Activation failed: ${err}`);
      throw err;
    }
  }

  // Lifecycle: Deactivate plugin
  async deactivate(pluginId: string): Promise<void> {
    const context = this.registry.get(pluginId);
    if (!context) throw new Error(`Plugin ${pluginId} not found`);
    if (!context.enabled) return;

    try {
      const plugin = this.pluginInstances.get(pluginId);
      if (plugin?.deactivate) {
        await plugin.deactivate();
      }

      this.panels.forEach((panel) => {
        if (panel.id.startsWith(pluginId + ':')) {
          this.panels.delete(panel.id);
          panel.cleanup?.();
        }
      });

      this.commands.forEach((cmd, name) => {
        if (name.startsWith(pluginId + ':')) {
          this.commands.delete(name);
        }
      });

      context.enabled = false;
      this.saveToStorage();
    } catch (err) {
      this.log(pluginId, 'error', `Deactivation failed: ${err}`);
      throw err;
    }
  }

  // Lifecycle: Uninstall plugin
  async uninstall(pluginId: string): Promise<void> {
    const context = this.registry.get(pluginId);
    if (!context) throw new Error(`Plugin ${pluginId} not found`);

    if (context.enabled) {
      await this.deactivate(pluginId);
    }

    this.registry.delete(pluginId);
    this.pluginInstances.delete(pluginId);
    this.saveToStorage();
  }

  // Query: List installed plugins
  listPlugins(): PluginContext[] {
    return Array.from(this.registry.values());
  }

  // Query: Get plugin
  getPlugin(pluginId: string): PluginContext | undefined {
    return this.registry.get(pluginId);
  }

  // Query: Get panel
  getPanel(panelId: string): PluginPanel | undefined {
    return this.panels.get(panelId);
  }

  // Query: List panels
  listPanels(): PluginPanel[] {
    return Array.from(this.panels.values());
  }

  // Query: Get command
  getCommand(name: string): PluginCommand | undefined {
    return this.commands.get(name);
  }

  // Query: List commands
  listCommands(): Array<{ name: string; cmd: PluginCommand }> {
    return Array.from(this.commands.entries()).map(([name, cmd]) => ({ name, cmd }));
  }

  // Execute command
  async executeCommand(name: string, ...args: any[]): Promise<any> {
    const cmd = this.commands.get(name);
    if (!cmd) throw new Error(`Command ${name} not found`);
    return cmd.execute(...args);
  }

  // Private: Create plugin API for a plugin instance
  private createPluginAPI(pluginId: string): PluginAPI {
    return {
      getManifest: () => {
        const context = this.registry.get(pluginId);
        if (!context) throw new Error(`Plugin ${pluginId} not found`);
        return context.manifest;
      },

      setEnabled: async (enabled: boolean) => {
        if (enabled) {
          await this.activate(pluginId);
        } else {
          await this.deactivate(pluginId);
        }
      },

      getStorage: () => {
        const context = this.registry.get(pluginId);
        return context?.settings || {};
      },

      updateStorage: async (data: Record<string, any>) => {
        const context = this.registry.get(pluginId);
        if (context) {
          context.settings = { ...context.settings, ...data };
          this.saveToStorage();
        }
      },

      onMessage: (type: string, handler: (data: any) => void) => {
        const key = `${pluginId}:${type}`;
        if (!this.eventHandlers.has(key)) {
          this.eventHandlers.set(key, new Set());
        }
        this.eventHandlers.get(key)!.add(handler);
      },

      sendMessage: (type: string, data: any) => {
        const key = `${pluginId}:${type}`;
        const handlers = this.eventHandlers.get(key);
        if (handlers) {
          handlers.forEach((h) => {
            try {
              h(data);
            } catch (err) {
              this.log(pluginId, 'error', `Message handler failed: ${err}`);
            }
          });
        }
      },

      registerPanel: async (panel: PluginPanel) => {
        const panelId = `${pluginId}:${panel.id}`;
        this.panels.set(panelId, { ...panel, id: panelId });
      },

      registerCommand: async (cmd: PluginCommand) => {
        const name = `${pluginId}:${cmd.name}`;
        this.commands.set(name, cmd);
      },

      unregisterPanel: async (panelId: string) => {
        const fullId = `${pluginId}:${panelId}`;
        const panel = this.panels.get(fullId);
        if (panel?.cleanup) {
          await panel.cleanup();
        }
        this.panels.delete(fullId);
      },

      log: (level: 'info' | 'warn' | 'error', message: string, data?: any) => {
        this.log(pluginId, level, message, data);
      },
    };
  }

  // Private: Logging
  private log(pluginId: string, level: string, message: string, data?: any): void {
    const timestamp = new Date().toISOString();
    const prefix = `[${timestamp}] [${pluginId}] [${level.toUpperCase()}]`;
    if (data) {
      console.log(`${prefix} ${message}`, data);
    } else {
      console.log(`${prefix} ${message}`);
    }
  }

  // Private: Storage management
  private saveToStorage(): void {
    const data = {
      plugins: Array.from(this.registry.entries()).map(([id, context]) => ({
        id,
        context,
      })),
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  }

  private loadFromStorage(): void {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        const data = JSON.parse(stored);
        data.plugins.forEach((p: { id: string; context: PluginContext }) => {
          this.registry.set(p.id, p.context);
        });
      } catch (err) {
        console.error('Failed to load plugins from storage:', err);
      }
    }
  }
}

// Global instance
let pluginManager: PluginManager | null = null;

export function getPluginManager(): PluginManager {
  if (!pluginManager) {
    pluginManager = new PluginManager();
  }
  return pluginManager;
}
