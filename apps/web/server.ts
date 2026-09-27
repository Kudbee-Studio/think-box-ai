import express, { type Request, type Response } from 'express';
import { createServer } from 'http';
import { randomUUID } from 'node:crypto';
import { WebSocketServer, WebSocket, type RawData } from 'ws';
import { XMLParser } from 'fast-xml-parser';
import multer from 'multer';
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
import { SDK_VERSION, loadConfigFromEnv } from './sdk/index.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const server = createServer(app);
const wss = new WebSocketServer({ server });
const ollamaBaseUrl = process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434';
const janusBaseUrl = process.env.JANUS_BASE_URL || 'http://127.0.0.1:8001';
const workspaceRoot = path.join(__dirname, 'workspaces');
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 50 * 1024 * 1024, files: 500 } });
const imageUpload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 12 * 1024 * 1024, files: 1 } });

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// ─── In-memory state ───────────────────────────────────────────
const sessions = new Map<string, AgentSession>();
const plugins = new Map<string, Plugin>();
const files = new Map<string, unknown>();
const monitorAgent = {
  id: randomUUID(),
  name: 'connection-monitor',
  status: 'monitoring',
  checks: 0,
  last_check: null as string | null,
};
const serverStartedAt = Date.now();
fs.mkdirSync(workspaceRoot, { recursive: true });

function sessionWorkspace(sessionId: string): string {
  return path.join(workspaceRoot, sessionId);
}

function safeWorkspacePath(sessionId: string, relativePath: string): string {
  const normalized = relativePath.replaceAll('\\', '/').replace(/^\/+/, '');
  if (!normalized || normalized.split('/').some(part => part === '..')) throw new Error('Invalid workspace path');
  const root = path.resolve(sessionWorkspace(sessionId));
  const destination = path.resolve(root, normalized);
  if (destination !== root && !destination.startsWith(`${root}${path.sep}`)) throw new Error('Path escapes workspace');
  return destination;
}

// ─── Ollama integration ────────────────────────────────────────
interface OllamaTag {
  name: string;
  [key: string]: unknown;
}

async function listOllamaModels(): Promise<OllamaTag[]> {
  try {
    const res = await fetch(`${ollamaBaseUrl}/api/tags`);
    const data = (await res.json()) as { models?: OllamaTag[] };
    return data.models ?? [];
  } catch {
    return [];
  }
}

async function requestJanus(endpoint: 'analyze' | 'generate', payload: Record<string, string>): Promise<Record<string, string>> {
  const response = await fetch(`${janusBaseUrl}/${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(10 * 60 * 1000),
  });
  const result = await response.json() as Record<string, string>;
  if (!response.ok) throw new Error(result.detail || `Janus service returned HTTP ${response.status}`);
  return result;
}

async function streamOllama(
  model: string,
  messages: ChatMessage[],
  onToken: (token: string) => void,
  onDone: (result: OllamaTokenMessage) => void,
): Promise<void> {
  try {
    const res = await fetch(`${ollamaBaseUrl}/api/chat`, {
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

registerPlugin('rss_feed', {
  type: 'tool',
  permission: 'network',
  description: 'Fetch and normalize an RSS or Atom feed',
  icon: '📰',
  execute: async (input: PluginInput): Promise<PluginResult> => {
    const url = String(input.url ?? '').trim();
    const limit = Math.min(Math.max(Number(input.limit) || 20, 1), 50);
    let parsedUrl: URL;
    try {
      parsedUrl = new URL(url);
      if (!['http:', 'https:'].includes(parsedUrl.protocol)) throw new Error('Only HTTP(S) feed URLs are supported');
    } catch (err) {
      return { success: false, error: errorMessage(err) };
    }

    try {
      const response = await fetch(parsedUrl, {
        headers: { Accept: 'application/rss+xml, application/atom+xml, application/xml, text/xml' },
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) return { success: false, error: `Feed returned HTTP ${response.status}` };
      const xml = await response.text();
      const document = new XMLParser({ ignoreAttributes: false, attributeNamePrefix: '@_' }).parse(xml) as Record<string, any>;
      const rss = document.rss?.channel;
      const atom = document.feed;
      const source = rss || atom;
      if (!source) return { success: false, error: 'Response is not a supported RSS or Atom feed' };
      const rawItems = rss ? (Array.isArray(source.item) ? source.item : source.item ? [source.item] : []) : (Array.isArray(source.entry) ? source.entry : source.entry ? [source.entry] : []);
      const items = rawItems.slice(0, limit).map((item: Record<string, any>) => {
        const links = Array.isArray(item.link) ? item.link : item.link ? [item.link] : [];
        const link = rss ? links[0] : links.find((candidate) => typeof candidate === 'object' && candidate['@_rel'] === 'alternate') || links[0];
        return {
          id: String(item.guid ?? item.id ?? link?.['@_href'] ?? link ?? ''),
          title: String(item.title ?? ''),
          url: String(link?.['@_href'] ?? link ?? ''),
          published_at: String(item.pubDate ?? item.published ?? item.updated ?? ''),
          summary: String(item.description ?? item.summary ?? item.content ?? '').slice(0, 4000),
        };
      });
      return { success: true, feed: { title: String(source.title ?? ''), url }, items, count: items.length };
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

registerPlugin('image_analyze', {
  type: 'tool',
  permission: 'read_only',
  description: 'Analyze an image with the local Janus-Pro vision model; input requires image_base64 and may include a prompt',
  icon: '🖼',
  execute: async (input: PluginInput): Promise<PluginResult> => {
    try {
      const result = await requestJanus('analyze', {
        image_base64: String(input.image_base64 ?? ''),
        prompt: String(input.prompt || 'Describe this image.'),
      });
      return { success: true, answer: result.answer };
    } catch (err) {
      return { success: false, error: errorMessage(err) };
    }
  },
});

registerPlugin('image_generate', {
  type: 'tool',
  permission: 'read_write',
  description: 'Generate a PNG image from a text prompt with the local Janus-Pro model',
  icon: '🎨',
  execute: async (input: PluginInput): Promise<PluginResult> => {
    try {
      const result = await requestJanus('generate', { prompt: String(input.prompt ?? '') });
      return { success: true, image_base64: result.image_base64, mime_type: 'image/png' };
    } catch (err) {
      return { success: false, error: errorMessage(err) };
    }
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

    const recordedInput = { ...input };
    if (typeof recordedInput.image_base64 === 'string') {
      recordedInput.image_base64 = `[omitted image payload: ${Math.floor(recordedInput.image_base64.length * 0.75)} bytes]`;
    }
    this.addThought({ type: 'plugin_call', plugin: name, input: recordedInput, status: 'running' });

    try {
      let result = await plugin.execute(input);
      if (name === 'image_generate' && typeof result.image_base64 === 'string') {
        const relativePath = `images/plugin-generated-${Date.now()}-${randomUUID().slice(0, 8)}.png`;
        const destination = safeWorkspacePath(this.id, relativePath);
        await fs.promises.mkdir(path.dirname(destination), { recursive: true });
        await fs.promises.writeFile(destination, Buffer.from(result.image_base64, 'base64'));
        result = {
          ...result,
          image_base64: undefined,
          path: relativePath,
          image_url: `/api/sessions/${this.id}/files/raw?path=${encodeURIComponent(relativePath)}`,
        };
      }
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
        input: recordedInput,
        result,
      });

      return result;
    } catch (err) {
      const message = errorMessage(err);
      this.addThought({ type: 'plugin_result', plugin: name, error: message, status: 'error' });
      this.memory.push({
        timestamp: Date.now(),
        type: 'plugin_result',
        plugin: name,
        input: recordedInput,
        result: { success: false, error: message },
      });
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
  void fs.promises.mkdir(sessionWorkspace(sessionId), { recursive: true });

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
async function monitorEndpoint(name: string, url: string): Promise<Record<string, unknown>> {
  const startedAt = Date.now();
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(3000) });
    const body = await response.text();
    let details: unknown = body.slice(0, 500);
    try {
      details = JSON.parse(body);
    } catch {
      // Keep non-JSON API responses as bounded text.
    }
    return {
      name,
      url,
      status: response.ok ? 'ok' : 'error',
      http_status: response.status,
      latency_ms: Date.now() - startedAt,
      details,
    };
  } catch (err) {
    return {
      name,
      url,
      status: 'offline',
      latency_ms: Date.now() - startedAt,
      error: errorMessage(err),
    };
  }
}

app.get('/api/health', (_req: Request, res: Response) => {
  const sdkConfig = loadConfigFromEnv();
  const memory = process.memoryUsage();
  res.json({
    status: 'ok',
    ready: true,
    sessions: sessions.size,
    plugins: plugins.size,
    sdk_version: SDK_VERSION,
    dry_run: sdkConfig.dryRun,
    uptime_seconds: Math.floor((Date.now() - serverStartedAt) / 1000),
    memory_mb: Math.round(memory.rss / 1024 / 1024),
    node_version: process.version,
  });
});

app.get('/api/monitor', async (_req: Request, res: Response) => {
  const baseUrl = `http://127.0.0.1:${PORT}`;
  const checks = await Promise.all([
    monitorEndpoint('Agent OS API', `${baseUrl}/api/health`),
    monitorEndpoint('SDK capabilities', `${baseUrl}/api/sdk/capabilities`),
    monitorEndpoint('Ollama models', `${ollamaBaseUrl}/api/tags`),
    monitorEndpoint('Janus image service', `${janusBaseUrl}/health`),
  ]);
  monitorAgent.checks += 1;
  monitorAgent.last_check = new Date().toISOString();
  res.json({
    checked_at: new Date().toISOString(),
    agent: monitorAgent,
    websocket_sessions: sessions.size,
    checks,
  });
});

app.get('/api/middleware/test', async (_req: Request, res: Response) => {
  const baseUrl = `http://127.0.0.1:${PORT}`;
  const checks = await Promise.all([
    monitorEndpoint('API middleware', `${baseUrl}/api/health`),
    monitorEndpoint('SDK middleware', `${baseUrl}/api/sdk/capabilities`),
    monitorEndpoint('Ollama middleware', `${ollamaBaseUrl}/api/tags`),
  ]);
  const passed = checks.every((check) => check.status === 'ok');
  const sessionId = typeof _req.query.session_id === 'string' ? _req.query.session_id : '';
  const session = sessions.get(sessionId);
  if (session) {
    const timestamp = Date.now();
    session.memory.push({ timestamp, type: 'middleware_test', passed, checks });
    session.addThought({
      type: 'middleware_test',
      content: `Middleware test ${passed ? 'passed' : 'failed'} (${checks.length} checks)`,
      status: passed ? 'success' : 'error',
    });
  }
  res.status(passed ? 200 : 503).json({
    passed,
    checked_at: new Date().toISOString(),
    websocket_sessions: sessions.size,
    checks,
  });
});

app.get('/api/sdk/capabilities', (_req: Request, res: Response) => {
  res.json({
    sdk_version: SDK_VERSION,
    api_version: 2,
    sdk_followup_version: '0.2.0',
    capabilities: ['sessions', 'tasks', 'plugins', 'websocket', 'health', 'pagination'],
  });
});

app.get('/api/sdk/version', (_req: Request, res: Response) => {
  res.json({
    sdk_version: SDK_VERSION,
    sdk_followup_version: '0.2.0',
    api_version: 2,
    live_api_called: false,
  });
});

app.get('/api/sdk/sessions', (req: Request, res: Response) => {
  const limit = Math.min(Number(req.query.limit) || 20, 100);
  res.json({ items: [], next_cursor: null, limit });
});

app.get('/api/sdk/tasks', (req: Request, res: Response) => {
  const status = String(req.query.status || 'all');
  res.json({ items: [], next_cursor: null, status });
});

app.get('/api/models', async (_req: Request, res: Response) => {
  const models = await listOllamaModels();
  res.json(models);
});

app.get('/api/sessions/:id/files', async (req: Request, res: Response) => {
  if (!sessions.has(req.params.id)) return res.status(404).json({ error: 'Session not found' });
  const root = sessionWorkspace(req.params.id);
  const files: Array<{ path: string; size: number; modified_at: string }> = [];
  async function walk(directory: string): Promise<void> {
    for (const entry of await fs.promises.readdir(directory, { withFileTypes: true })) {
      const absolute = path.join(directory, entry.name);
      if (entry.isDirectory()) await walk(absolute);
      else {
        const stat = await fs.promises.stat(absolute);
        files.push({ path: path.relative(root, absolute).replaceAll(path.sep, '/'), size: stat.size, modified_at: stat.mtime.toISOString() });
      }
    }
  }
  await fs.promises.mkdir(root, { recursive: true });
  await walk(root);
  res.json({ files: files.sort((a, b) => a.path.localeCompare(b.path)) });
});

app.get('/api/sessions/:id/files/content', async (req: Request, res: Response) => {
  if (!sessions.has(req.params.id)) return res.status(404).json({ error: 'Session not found' });
  try {
    const filePath = safeWorkspacePath(req.params.id, String(req.query.path || ''));
    const stat = await fs.promises.stat(filePath);
    if (!stat.isFile() || stat.size > 2 * 1024 * 1024) return res.status(413).json({ error: 'File is too large to preview' });
    res.json({ path: String(req.query.path), content: await fs.promises.readFile(filePath, 'utf8') });
  } catch (err) {
    res.status(400).json({ error: errorMessage(err) });
  }
});

app.get('/api/sessions/:id/files/raw', async (req: Request, res: Response) => {
  if (!sessions.has(req.params.id)) return res.status(404).json({ error: 'Session not found' });
  try {
    const relativePath = String(req.query.path || '');
    if (!['.png', '.jpg', '.jpeg', '.webp', '.gif'].includes(path.extname(relativePath).toLowerCase())) {
      return res.status(415).json({ error: 'Only raster images can be served by this endpoint' });
    }
    const filePath = safeWorkspacePath(req.params.id, relativePath);
    if (!(await fs.promises.stat(filePath)).isFile()) return res.status(404).json({ error: 'File not found' });
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.type(path.extname(filePath));
    res.sendFile(filePath);
  } catch (err) {
    res.status(400).json({ error: errorMessage(err) });
  }
});

app.post('/api/sessions/:id/images/analyze', imageUpload.single('image'), async (req: Request, res: Response) => {
  const session = sessions.get(req.params.id);
  if (!session) return res.status(404).json({ error: 'Session not found' });
  const image = req.file;
  if (!image) return res.status(400).json({ error: 'Choose an image to analyze' });
  if (!['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(image.mimetype)) {
    return res.status(415).json({ error: 'Use a PNG, JPEG, WebP, or GIF image' });
  }
  try {
    const relativePath = `images/${randomUUID()}-${path.basename(image.originalname)}`;
    const destination = safeWorkspacePath(session.id, relativePath);
    await fs.promises.mkdir(path.dirname(destination), { recursive: true });
    await fs.promises.writeFile(destination, image.buffer);
    const result = await requestJanus('analyze', {
      image_base64: image.buffer.toString('base64'),
      prompt: String(req.body.prompt || 'Describe this image.'),
    });
    const imageUrl = `/api/sessions/${session.id}/files/raw?path=${encodeURIComponent(relativePath)}`;
    session.addThought({ type: 'image_analysis', content: result.answer, image: relativePath, status: 'success' });
    session.memory.push({ timestamp: Date.now(), type: 'image_analysis', image: relativePath, answer: result.answer });
    res.json({ success: true, answer: result.answer, path: relativePath, imageUrl });
  } catch (err) {
    const message = errorMessage(err);
    session.addThought({ type: 'image_analysis', content: message, status: 'error' });
    res.status(503).json({ error: message });
  }
});

app.post('/api/sessions/:id/images/generate', async (req: Request, res: Response) => {
  const session = sessions.get(req.params.id);
  if (!session) return res.status(404).json({ error: 'Session not found' });
  const prompt = typeof req.body.prompt === 'string' ? req.body.prompt.trim() : '';
  if (!prompt || prompt.length > 4000) return res.status(400).json({ error: 'Prompt must contain 1 to 4000 characters' });
  session.addThought({ type: 'image_generation', content: prompt, status: 'thinking' });
  try {
    const result = await requestJanus('generate', { prompt });
    const relativePath = `images/generated-${Date.now()}-${randomUUID().slice(0, 8)}.png`;
    const destination = safeWorkspacePath(session.id, relativePath);
    await fs.promises.mkdir(path.dirname(destination), { recursive: true });
    await fs.promises.writeFile(destination, Buffer.from(result.image_base64, 'base64'));
    const imageUrl = `/api/sessions/${session.id}/files/raw?path=${encodeURIComponent(relativePath)}`;
    session.addThought({ type: 'image_generation', content: prompt, path: relativePath, status: 'success' });
    session.memory.push({ timestamp: Date.now(), type: 'image_generation', prompt, path: relativePath });
    res.json({ success: true, prompt, path: relativePath, imageUrl });
  } catch (err) {
    const message = errorMessage(err);
    session.addThought({ type: 'image_generation', content: message, status: 'error' });
    res.status(503).json({ error: message });
  }
});

app.post('/api/sessions/:id/files', upload.array('files', 500), async (req: Request, res: Response) => {
  if (!sessions.has(req.params.id)) return res.status(404).json({ error: 'Session not found' });
  const uploaded: Array<{ path: string; size: number }> = [];
  try {
    for (const file of (req.files ?? []) as Express.Multer.File[]) {
      const destination = safeWorkspacePath(req.params.id, file.originalname);
      await fs.promises.mkdir(path.dirname(destination), { recursive: true });
      await fs.promises.writeFile(destination, file.buffer);
      uploaded.push({ path: path.relative(sessionWorkspace(req.params.id), destination).replaceAll(path.sep, '/'), size: file.size });
    }
    res.status(201).json({ uploaded });
  } catch (err) {
    res.status(400).json({ error: errorMessage(err) });
  }
});

app.delete('/api/sessions/:id/files', async (req: Request, res: Response) => {
  if (!sessions.has(req.params.id)) return res.status(404).json({ error: 'Session not found' });
  try {
    await fs.promises.unlink(safeWorkspacePath(req.params.id, String(req.body.path || '')));
    res.json({ success: true });
  } catch (err) {
    res.status(400).json({ error: errorMessage(err) });
  }
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
