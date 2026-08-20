import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

class PluginManager {
  constructor() {
    this.plugins = new Map();
    this.loadBuiltinPlugins();
  }

  loadBuiltinPlugins() {
    this.register({
      name: 'file_read',
      type: 'tool',
      permission: 'read_only',
      description: 'Read file contents',
      icon: '📄',
      execute: async (input) => {
        const { path: filePath } = input;
        try {
          const content = await fs.promises.readFile(filePath, 'utf-8');
          return { success: true, content, path: filePath };
        } catch (err) {
          return { success: false, error: err.message };
        }
      },
    });

    this.register({
      name: 'file_write',
      type: 'tool',
      permission: 'read_write',
      description: 'Write file contents',
      icon: '✏️',
      execute: async (input) => {
        const { path: filePath, content } = input;
        try {
          await fs.promises.writeFile(filePath, content, 'utf-8');
          return { success: true, path: filePath };
        } catch (err) {
          return { success: false, error: err.message };
        }
      },
    });

    this.register({
      name: 'file_list',
      type: 'tool',
      permission: 'read_only',
      description: 'List directory contents',
      icon: '📁',
      execute: async (input) => {
        const { path: dirPath } = input;
        try {
          const items = await fs.promises.readdir(dirPath, { withFileTypes: true });
          return {
            success: true,
            files: items.map(item => ({
              name: item.name,
              isDirectory: item.isDirectory(),
              isFile: item.isFile(),
            })),
          };
        } catch (err) {
          return { success: false, error: err.message };
        }
      },
    });

    this.register({
      name: 'shell_exec',
      type: 'tool',
      permission: 'exec',
      description: 'Execute shell command',
      icon: '⚡',
      execute: async (input) => {
        const { command, cwd } = input;
        try {
          const output = execSync(command, {
            cwd: cwd || process.cwd(),
            encoding: 'utf-8',
            timeout: 30000,
          });
          return { success: true, stdout: output, stderr: '', returnCode: 0 };
        } catch (err) {
          return {
            success: false,
            stdout: err.stdout?.toString() || '',
            stderr: err.stderr?.toString() || '',
            returnCode: err.status,
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
      execute: async (input) => {
        const { url, method = 'GET' } = input;
        try {
          const res = await fetch(url, { method });
          const text = await res.text();
          return { success: true, status: res.status, body: text };
        } catch (err) {
          return { success: false, error: err.message };
        }
      },
    });

    this.register({
      name: 'memory_query',
      type: 'tool',
      permission: 'read_only',
      description: 'Query agent memory',
      icon: '🧠',
      execute: async (input) => {
        const session = input.session;
        if (!session) return { success: false, error: 'No session provided' };
        return { success: true, memory: session.memory || [] };
      },
    });

    this.register({
      name: 'web_search',
      type: 'tool',
      permission: 'network',
      description: 'Search the web',
      icon: '🔍',
      execute: async (input) => {
        const { query } = input;
        try {
          const res = await fetch(`https://html.duckduckgo.com/html/?q=${encodeURIComponent(query)}`, {
            headers: { 'User-Agent': 'Mozilla/5.0' },
          });
          const text = await res.text();
          return { success: true, results: text.slice(0, 5000) };
        } catch (err) {
          return { success: false, error: err.message };
        }
      },
    });

    this.register({
      name: 'code_analyzer',
      type: 'tool',
      permission: 'read_only',
      description: 'Analyze code structure',
      icon: '🔬',
      execute: async (input) => {
        const { code, language } = input;
        return {
          success: true,
          analysis: {
            language,
            lines: code.split('\n').length,
            functions: (code.match(/def |function |const |let /g) || []).length,
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
      execute: async (input) => {
        try {
          const status = execSync('git status --short', { encoding: 'utf-8' });
          return { success: true, status: status || 'clean' };
        } catch (err) {
          return { success: false, error: err.message };
        }
      },
    });
  }

  register(plugin) {
    this.plugins.set(plugin.name, {
      ...plugin,
      enabled: true,
      callCount: 0,
    });
  }

  get(name) {
    return this.plugins.get(name);
  }

  getAll() {
    return Array.from(this.plugins.values());
  }

  getEnabled() {
    return this.getAll().filter(p => p.enabled);
  }

  execute(name, input, session) {
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
