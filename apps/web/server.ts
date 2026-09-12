import express, { type Request, type Response } from 'express';
import { createServer } from 'http';
import { randomUUID } from 'node:crypto';
import { WebSocketServer, WebSocket, type RawData } from 'ws';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

import type {
  AgentSessionConfig,
  ChatMessage,
  MemoryEntry,
  OllamaTokenMessage,
  Plugin,
  PluginConfig,
  PluginInput,
  PluginResult,
  SessionConfigInput,
  Task,
  Thought,
  WsMessage,
} from './types.ts';
import { errorMessage } from './types.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const server = createServer(app);
const wss = new WebSocketServer({ server });

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// ─── In-memory state ───────────────────────────────────────────
const sessions = new Map<string, AgentSession>();
const plugins = new Map<string, Plugin>();
const files = new Map<string, unknown>();

// ─── Ollama integration ────────────────────────────────────────
interface OllamaTag {
  name: string;
  [key: string]: unknown;
}

async function listOllamaModels(): Promise<OllamaTag[]> {
  try {
    const res = await fetch('http://localhost:11434/api/tags');
    const data = (await res.json()) as { models?: OllamaTag[] };
    return data.models ?? [];
  } catch {
    return [];
  }
}

async function streamOllama(
  model: string,
  messages: ChatMessage[],
  onToken: (token: string) => void,
  onDone: (result: OllamaTokenMessage) => void,
): Promise<void> {
  try {
    const res = await fetch('http://localhost:11434/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, messages, stream: true }),
    });

    if (!res.body) {
      throw new Error('Ollama response has no body');
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';
      for (const line of lines) {
        if (!line.trim()) continue;
        const json = JSON.parse(line) as OllamaTokenMessage;
        if (json.message?.content) {
          onToken(json.message.content);
        }
        if (json.done) {
          onDone(json);
        }
      }
    }
  } catch (err) {
    const message = errorMessage(err);
    onToken(`[Error: ${message}]`);
    onDone({ error: message });
  }
}

// ─── Plugin system ─────────────────────────────────────────────
function registerPlugin(name: string, config: Omit<PluginConfig, 'name'>): void {
  plugins.set(name, {
    ...config,
    name,
    enabled: true,
    callCount: 0,
  });
}

function getPlugins(): Plugin[] {
  return Array.from(plugins.values());
}

// Default plugins
registerPlugin('file_read', {
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

registerPlugin('file_write', {
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

registerPlugin('shell_exec', {
  type: 'tool',
  permission: 'exec',
  description: 'Execute shell command',
  icon: '⚡',
  execute: async (input: PluginInput): Promise<PluginResult> => {
    const command = String(input.command);
    const cwd = input.cwd ? String(input.cwd) : undefined;
    try {
      const { execSync } = await import('child_process');
      const output = execSync(command, { cwd, encoding: 'utf-8', timeout: 30000 });
      return { success: true, stdout: output, stderr: '', returnCode: 0 };
    } catch (err) {
      const execErr = err as { stdout?: Buffer | string; stderr?: Buffer | string; status?: number };
      return {
        success: false,
        stdout: execErr.stdout?.toString() ?? '',
        stderr: execErr.stderr?.toString() ?? '',
        returnCode: execErr.status,
      };
    }
  },
});

registerPlugin('http_request', {
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

registerPlugin('memory_query', {
  type: 'tool',
  permission: 'read_only',
  description: 'Query agent memory',
  icon: '🧠',
  execute: async (input: PluginInput): Promise<PluginResult> => {
    const session = sessions.get(String(input.sessionId));
    if (!session) return { success: false, error: 'Session not found' };
    return { success: true, memory: session.memory };
  },
});

// ─── Agent runtime ─────────────────────────────────────────────
class AgentSession {
  readonly id: string;
  readonly config: AgentSessionConfig;
  readonly memory: MemoryEntry[] = [];
  readonly thoughts: Thought[] = [];
  readonly tasks: Task[] = [];
  readonly files: Map<string, unknown> = new Map();
  readonly plugins: Map<string, Plugin> = new Map();
  status = 'idle';
  currentTask: Task | null = null;
  ws: WebSocket | null = null;

  constructor(id: string, config: SessionConfigInput = {}) {
    this.id = id;
    this.config = {
      model: config.model ?? 'deepseek-coder:6.7b',
      provider: config.provider ?? 'ollama',
      maxIterations: config.maxIterations ?? 20,
      temperature: config.temperature ?? 0.7,
    };
  }

  addThought(thought: Record<string, unknown>): void {
    this.thoughts.push({
      id: randomUUID(),
      timestamp: Date.now(),
      ...thought,
    } as Thought);
    this.broadcast({ type: 'thought', data: this.thoughts[this.thoughts.length - 1] });
  }

  addTask(task: Record<string, unknown>): Task {
    this.tasks.push({
      id: randomUUID(),
      timestamp: Date.now(),
      status: 'pending',
      ...task,
    } as Task);
    const created = this.tasks[this.tasks.length - 1] as Task;
    this.broadcast({ type: 'task', data: created });
    return created;
  }

  updateTask(id: string, updates: Partial<Task>): Task | undefined {
    const task = this.tasks.find((t) => t.id === id);
    if (task) {
      Object.assign(task, updates);
      this.broadcast({ type: 'task_update', data: task });
    }
    return task;
  }

  broadcast(message: unknown): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  async executePlugin(name: string, input: PluginInput): Promise<PluginResult> {
    const plugin = plugins.get(name);
    if (!plugin) {
      return { success: false, error: `Plugin not found: ${name}` };
    }
    if (!plugin.enabled) {
      return { success: false, error: `Plugin disabled: ${name}` };
    }

    this.addThought({ type: 'plugin_call', plugin: name, input, status: 'running' });

    try {
      const result = await plugin.execute(input);
      plugin.callCount = (plugin.callCount || 0) + 1;

      this.addThought({
        type: 'plugin_result',
        plugin: name,
        result,
        status: result.success ? 'success' : 'error',
      });

      this.memory.push({
        timestamp: Date.now(),
        type: 'plugin_result',
        plugin: name,
        input,
        result,
      });

      return result;
    } catch (err) {
      const message = errorMessage(err);
      this.addThought({ type: 'plugin_result', plugin: name, error: message, status: 'error' });
      return { success: false, error: message };
    }
  }

  async runGoal(goal: string): Promise<PluginResult> {
    this.status = 'running';
    this.addThought({ type: 'goal', content: `Starting goal: ${goal}`, status: 'info' });

    const task = this.addTask({ description: goal, status: 'running' });

    try {
      const messages: ChatMessage[] = [
        {
          role: 'system',
          content:
            'You are THINK BOX AI, an intelligent agent. Use the available plugins to accomplish tasks. Think step by step. Be concise and actionable.',
        },
        ...this.memory.slice(-10).map(
          (m): ChatMessage => ({ role: 'user', content: JSON.stringify(m) }),
        ),
        {
          role: 'user',
          content: `Goal: ${goal}\n\nAvailable plugins: ${Array.from(plugins.values())
            .filter((p) => p.enabled)
            .map((p) => p.name)
            .join(', ')}\n\nExecute this goal step by step.`,
        },
      ];

      this.addThought({ type: 'reasoning', content: 'Planning execution...', status: 'thinking' });

      let fullResponse = '';
      await streamOllama(
        this.config.model,
        messages,
        (token) => {
          fullResponse += token;
          this.broadcast({ type: 'stream', data: token });
        },
        () => {
          this.addThought({ type: 'reasoning', content: fullResponse, status: 'complete' });
          this.memory.push({ timestamp: Date.now(), type: 'response', content: fullResponse });
        },
      );

      this.updateTask(task.id, { status: 'completed', result: fullResponse });
      this.status = 'idle';
      return { success: true, result: fullResponse };
    } catch (err) {
      const message = errorMessage(err);
      this.updateTask(task.id, { status: 'failed', error: message });
      this.status = 'idle';
      return { success: false, error: message };
    }
  }

  stop(): void {
    this.status = 'idle';
    this.broadcast({ type: 'status', data: 'idle' });
  }
}

// ─── WebSocket handling ────────────────────────────────────────
wss.on('connection', (ws: WebSocket) => {
  const sessionId = randomUUID();
  const session = new AgentSession(sessionId);
  session.ws = ws;
  sessions.set(sessionId, session);

  ws.send(
    JSON.stringify({
      type: 'init',
      data: {
        sessionId,
        config: session.config,
        plugins: getPlugins(),
        files: Array.from(session.files.entries()),
        tasks: session.tasks,
        thoughts: session.thoughts,
      },
    }),
  );

  ws.on('message', async (raw: RawData) => {
    try {
      const msg = JSON.parse(raw.toString()) as WsMessage;

      switch (msg.type) {
        case 'run_goal': {
          session.config.model = typeof msg.model === 'string' ? msg.model : session.config.model;
          session.broadcast({ type: 'status', data: 'running' });
          const result = await session.runGoal(String(msg.goal));
          ws.send(JSON.stringify({ type: 'result', data: result }));
          break;
        }

        case 'stop': {
          session.stop();
          break;
        }

        case 'plugin_execute': {
          const result = await session.executePlugin(String(msg.plugin), msg.input as PluginInput);
          ws.send(JSON.stringify({ type: 'plugin_result', data: { plugin: msg.plugin, result } }));
          break;
        }

        case 'update_config': {
          Object.assign(session.config, msg.config);
          ws.send(JSON.stringify({ type: 'config_updated', data: session.config }));
          break;
        }

        case 'list_models': {
          const models = await listOllamaModels();
          ws.send(JSON.stringify({ type: 'models', data: models }));
          break;
        }

        default: {
          ws.send(JSON.stringify({ type: 'error', data: `Unknown message type: ${msg.type}` }));
        }
      }
    } catch (err) {
      ws.send(JSON.stringify({ type: 'error', data: errorMessage(err) }));
    }
  });

  ws.on('close', () => {
    sessions.delete(sessionId);
  });
});

// ─── REST API ──────────────────────────────────────────────────
app.get('/api/health', (_req: Request, res: Response) => {
  res.json({ status: 'ok', sessions: sessions.size, plugins: plugins.size });
});

app.get('/api/models', async (_req: Request, res: Response) => {
  const models = await listOllamaModels();
  res.json(models);
});

app.post('/api/sessions/:id/run', async (req: Request, res: Response) => {
  const session = sessions.get(req.params.id);
  if (!session) return res.status(404).json({ error: 'Session not found' });

  const result = await session.runGoal(String(req.body.goal));
  res.json(result);
});

app.post('/api/sessions/:id/stop', (req: Request, res: Response) => {
  const session = sessions.get(req.params.id);
  if (!session) return res.status(404).json({ error: 'Session not found' });
  session.stop();
  res.json({ success: true });
});

// ─── Start server ──────────────────────────────────────────────
const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`\n🚀 THINK BOX AI — Devin-like Interface`);
  console.log(`   Backend:  http://localhost:${PORT}`);
  console.log(`   WebSocket: ws://localhost:${PORT}`);
  console.log(`   Models:   http://localhost:11434 (Ollama)`);
  console.log(`\n   Ready.\n`);
});

void files;
