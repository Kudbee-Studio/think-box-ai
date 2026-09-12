import { execSync, type ExecException } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

import type { Plugin, PluginConfig, PluginInput, PluginResult } from '../types.ts';
import { errorMessage } from '../types.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

class PluginManager {
  private readonly plugins: Map<string, Plugin>;

  constructor() {
    this.plugins = new Map();
    this.loadBuiltinPlugins();
  }

  loadBuiltinPlugins(): void {
    this.register({
      name: 'file_read',
      type: 'tool',
      permission: 'read_only',
      description: 'Read file contents',
      icon: '📄',
      execute: async (input: PluginInput): Promise<PluginResult> => {
        const filePath = String(input.path);
        try {
          const content = await fs.promises.readFile(filePath, 'utf-8');
          return { success: true, content, path: filePath };
        } catch (err) {
          return { success: false, error: errorMessage(err) };
        }
      },
    });

    this.register({
      name: 'file_write',
      type: 'tool',
      permission: 'read_write',
      description: 'Write file contents',
      icon: '✏️',
      execute: async (input: PluginInput): Promise<PluginResult> => {
        const filePath = String(input.path);
        const content = String(input.content ?? '');
        try {
          await fs.promises.writeFile(filePath, content, 'utf-8');
          return { success: true, path: filePath };
        } catch (err) {
          return { success: false, error: errorMessage(err) };
        }
      },
    });

    this.register({
      name: 'file_list',
      type: 'tool',
      permission: 'read_only',
      description: 'List directory contents',
      icon: '📁',
      execute: async (input: PluginInput): Promise<PluginResult> => {
        const dirPath = String(input.path);
        try {
          const items = await fs.promises.readdir(dirPath, { withFileTypes: true });
          return {
            success: true,
            files: items.map((item) => ({
              name: item.name,
              isDirectory: item.isDirectory(),
              isFile: item.isFile(),
            })),
          };
        } catch (err) {
          return { success: false, error: errorMessage(err) };
        }
      },
    });

    this.register({
      name: 'shell_exec',
      type: 'tool',
      permission: 'exec',
      description: 'Execute shell command',
      icon: '⚡',
      execute: async (input: PluginInput): Promise<PluginResult> => {
        const command = String(input.command);
        const cwd = input.cwd ? String(input.cwd) : process.cwd();
        try {
          const output = execSync(command, {
            cwd,
            encoding: 'utf-8',
            timeout: 30000,
          });
          return { success: true, stdout: output, stderr: '', returnCode: 0 };
        } catch (err) {
          const execErr = err as ExecException & { status?: number };
          return {
            success: false,
            stdout: execErr.stdout ?? '',
            stderr: execErr.stderr ?? '',
            returnCode: execErr.status,
          };
        }
      },
    });

    this.register({
      name: 'http_request',
      type: 'tool',
      permission: 'network',
      description: 'Make HTTP request',
      icon: '🌐',
      execute: async (input: PluginInput): Promise<PluginResult> => {
        const url = String(input.url);
        const method = input.method ? String(input.method) : 'GET';
        try {
          const res = await fetch(url, { method });
          const text = await res.text();
          return { success: true, status: res.status, body: text };
        } catch (err) {
          return { success: false, error: errorMessage(err) };
        }
      },
    });

    this.register({
      name: 'memory_query',
      type: 'tool',
      permission: 'read_only',
      description: 'Query agent memory',
      icon: '🧠',
      execute: async (input: PluginInput): Promise<PluginResult> => {
        const session = input.session as { memory?: unknown[] } | undefined;
        if (!session) return { success: false, error: 'No session provided' };
        return { success: true, memory: session.memory ?? [] };
      },
    });

    this.register({
      name: 'web_search',
      type: 'tool',
      permission: 'network',
      description: 'Search the web',
      icon: '🔍',
      execute: async (input: PluginInput): Promise<PluginResult> => {
        const query = String(input.query);
        try {
          const res = await fetch(
            `https://html.duckduckgo.com/html/?q=${encodeURIComponent(query)}`,
            { headers: { 'User-Agent': 'Mozilla/5.0' } },
          );
          const text = await res.text();
          return { success: true, results: text.slice(0, 5000) };
        } catch (err) {
          return { success: false, error: errorMessage(err) };
        }
      },
    });

    this.register({
      name: 'code_analyzer',
      type: 'tool',
      permission: 'read_only',
      description: 'Analyze code structure',
      icon: '🔬',
      execute: async (input: PluginInput): Promise<PluginResult> => {
        const code = String(input.code ?? '');
        const language = input.language ? String(input.language) : 'unknown';
        return {
          success: true,
          analysis: {
            language,
            lines: code.split('\n').length,
            functions: (code.match(/def |function |const |let /g) ?? []).length,
            complexity: 'medium',
          },
        };
      },
    });

    this.register({
      name: 'git_status',
      type: 'tool',
      permission: 'read_only',
      description: 'Check git status',
      icon: '📦',
      execute: async (_input: PluginInput): Promise<PluginResult> => {
        try {
          const status = execSync('git status --short', { encoding: 'utf-8' });
          return { success: true, status: status || 'clean' };
        } catch (err) {
          return { success: false, error: errorMessage(err) };
        }
      },
    });
  }

  register(plugin: PluginConfig): void {
    this.plugins.set(plugin.name, {
      ...plugin,
      enabled: true,
      callCount: 0,
    });
  }

  get(name: string): Plugin | undefined {
    return this.plugins.get(name);
  }

  getAll(): Plugin[] {
    return Array.from(this.plugins.values());
  }

  getEnabled(): Plugin[] {
    return this.getAll().filter((p) => p.enabled);
  }

  execute(name: string, input: PluginInput, session: unknown): Promise<PluginResult> {
    const plugin = this.plugins.get(name);
    if (!plugin) {
      return Promise.resolve({ success: false, error: `Plugin not found: ${name}` });
    }
    if (!plugin.enabled) {
      return Promise.resolve({ success: false, error: `Plugin disabled: ${name}` });
    }
    return plugin.execute({ ...input, session });
  }
}

export const pluginManager = new PluginManager();
