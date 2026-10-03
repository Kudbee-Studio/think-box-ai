// Plugin Protocol - Enterprise Dashboard Extension System

export type PluginCapability = 'panel' | 'toolbar' | 'command' | 'theme' | 'analytics' | 'integration';
export type PluginPermission = 'read_only' | 'read_write' | 'exec' | 'restricted';

export interface PluginManifest {
  id: string;
  name: string;
  version: string;
  description: string;
  author?: string;
  permissions: PluginPermission[];
  capabilities: PluginCapability[];
  entrypoint?: string;
  homepage?: string;
  minDashboardVersion?: string;
  config?: Record<string, any>;
}

export interface PluginContext {
  manifest: PluginManifest;
  enabled: boolean;
  installedAt: number;
  lastUpdated: number;
  settings: Record<string, any>;
}

export interface PluginPanel {
  id: string;
  title: string;
  icon: string;
  render(container: HTMLElement, context: PluginContext): Promise<void>;
  cleanup?(): Promise<void>;
}

export interface PluginCommand {
  name: string;
  description: string;
  execute(...args: any[]): Promise<any>;
}

export interface PluginAPI {
  // Manifest & Lifecycle
  getManifest(): PluginManifest;
  setEnabled(enabled: boolean): Promise<void>;

  // Storage
  getStorage(): Record<string, any>;
  updateStorage(data: Record<string, any>): Promise<void>;

  // Events
  onMessage(type: string, handler: (data: any) => void): void;
  sendMessage(type: string, data: any): void;

  // Dashboard integration
  registerPanel(panel: PluginPanel): Promise<void>;
  registerCommand(cmd: PluginCommand): Promise<void>;
  unregisterPanel(panelId: string): Promise<void>;

  // Telemetry
  log(level: 'info' | 'warn' | 'error', message: string, data?: any): void;
}

export interface Plugin {
  activate(api: PluginAPI): Promise<void>;
  deactivate?(): Promise<void>;
  getCapabilities?(): PluginCapability[];
}
