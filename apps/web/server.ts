import express, { type Request, type Response } from 'express';
import { createServer } from 'http';
import { randomUUID } from 'node:crypto';
import { execFile } from 'node:child_process';
import { WebSocketServer, WebSocket, type RawData } from 'ws';
import { XMLParser } from 'fast-xml-parser';
import multer from 'multer';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';
import os from 'os';

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
import { AGENT_PROFILES, INCEPTION_MODELS, inceptionConfigured, isInceptionModel, runToolAgent } from './agent.ts';
import { RunStore, classifyFailure, type RunRecord } from './runs.ts';
import { MemoryStore, MEMORY_LAYERS, type MemoryLayer } from './memory.ts';
import { algorandQuery } from './algorand.ts';
import PersistenceLayer from './persistence.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Secrets stay server-side: the repo-root .env is read here and never sent to the browser.
for (const envPath of [path.join(__dirname, '.env'), path.resolve(__dirname, '../../.env')]) {
  try {
    process.loadEnvFile(envPath);
  } catch {
    // Missing .env is fine; the runtime falls back to Ollama-only mode.
  }
}

const app = express();
const server = createServer(app);
const wss = new WebSocketServer({ server });
const ollamaBaseUrl = process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434';
const janusBaseUrl = process.env.JANUS_BASE_URL || 'http://127.0.0.1:8001';
// Cheap local route default (Feature 5 token-aware routing). 'smollm2' is accepted
// as a legacy alias so old configs pointing at the earlier model name still resolve.
const LEGACY_LOCAL_MODEL_ALIASES: Record<string, string> = { smollm2: 'qwen2.5:1.5b', 'smollm2:135m': 'qwen2.5:1.5b' };
const rawDefaultLocalModel = process.env.KUDBEE_LOCAL_MODEL || 'qwen2.5:1.5b';
const defaultLocalModel = LEGACY_LOCAL_MODEL_ALIASES[rawDefaultLocalModel.toLowerCase()] || rawDefaultLocalModel;
const workspaceRoot = process.env.KUDBEE_WORKSPACE_DIR || path.join(__dirname, 'workspaces');
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
const dataDir = process.env.KUDBEE_DATA_DIR || path.join(__dirname, 'data');
const runStore = new RunStore(path.join(dataDir, 'runs.json'));
const memoryStore = new MemoryStore(process.env.KUDBEE_MEMORY_DIR || path.join(dataDir, 'memory'));
void memoryStore.syncVectors();

// ─── Persistent storage (SQLite) ────────────────────────────────
const persistence = new PersistenceLayer(dataDir);
const dailyBudgetUsd = Number(process.env.KUDBEE_DAILY_BUDGET_USD) || 0;
const APPROVAL_TIMEOUT_MS = 120_000;
fs.mkdirSync(workspaceRoot, { recursive: true });

function sessionWorkspace(sessionId: string): string {
  return path.join(workspaceRoot, sessionId);
}

/** Live or past session: run history keeps pointing at workspaces after the socket closes. */
function workspaceExists(sessionId: string): boolean {
  return /^[0-9a-f-]{36}$/.test(sessionId) && (sessions.has(sessionId) || fs.existsSync(sessionWorkspace(sessionId)));
}

function safeWorkspacePath(sessionId: string, relativePath: string): string {
  const normalized = relativePath.replaceAll('\\', '/').replace(/^\/+/, '');
  if (!normalized || normalized.split('/').some(part => part === '..')) throw new Error('Invalid workspace path');
  const root = path.resolve(sessionWorkspace(sessionId));
  const destination = path.resolve(root, normalized);
  if (destination !== root && !destination.startsWith(`${root}${path.sep}`)) throw new Error('Path escapes workspace');
  return destination;
}

function runGit(args: string[], cwd?: string): Promise<{ stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    execFile('git', args, { cwd, encoding: 'utf8', timeout: 120000, maxBuffer: 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) reject(err);
      else resolve({ stdout, stderr });
    });
  });
}

async function runGitAction(sessionId: string, action: string, input: PluginInput): Promise<PluginResult> {
  if (!sessions.has(sessionId)) return { success: false, error: 'Session not found' };
  const root = await fs.promises.realpath(sessionWorkspace(sessionId));
  if (action === 'clone') {
    let repositoryUrl: URL;
    try {
      repositoryUrl = new URL(String(input.url ?? ''));
    } catch {
      return { success: false, error: 'Provide a valid public Git HTTPS URL' };
    }
    const allowedHosts = new Set(['github.com', 'gitlab.com', 'bitbucket.org', 'codeberg.org']);
    if (repositoryUrl.protocol !== 'https:' || !allowedHosts.has(repositoryUrl.hostname.toLowerCase())
      || (repositoryUrl.port && repositoryUrl.port !== '443') || repositoryUrl.username || repositoryUrl.password) {
      return { success: false, error: 'Clone is limited to credential-free HTTPS repositories on GitHub, GitLab, Bitbucket, or Codeberg' };
    }
    const repositoryName = decodeURIComponent(repositoryUrl.pathname.split('/').filter(Boolean).at(-1) || '').replace(/\.git$/i, '');
    if (!/^[a-zA-Z0-9._-]{1,100}$/.test(repositoryName) || repositoryName === '.' || repositoryName === '..') {
      return { success: false, error: 'Repository URL must end in a valid repository name' };
    }
    const relativePath = `repositories/${repositoryName}`;
    const destination = safeWorkspacePath(sessionId, relativePath);
    try {
      await fs.promises.access(destination);
      return { success: false, error: `Repository already exists at ${relativePath}` };
    } catch (err) {
      if ((err as NodeJS.ErrnoException).code !== 'ENOENT') throw err;
    }
    await fs.promises.mkdir(path.dirname(destination), { recursive: true });
    try {
      const result = await runGit(['clone', '--depth', '1', '--', repositoryUrl.toString(), destination], root);
      return { success: true, action, path: relativePath, output: result.stdout.trim() || `Cloned ${repositoryUrl.host}/${repositoryName}` };
    } catch (err) {
      await fs.promises.rm(destination, { recursive: true, force: true });
      return { success: false, error: errorMessage(err) };
    }
  }

  if (!['status', 'log', 'diff', 'branch'].includes(action)) {
    return { success: false, error: 'Allowed Git actions: clone, status, log, diff, branch' };
  }
  try {
    const relativePath = String(input.path ?? '').trim();
    const requestedPath = safeWorkspacePath(sessionId, relativePath);
    const repositoryRoot = await fs.promises.realpath(requestedPath);
    if (repositoryRoot !== root && !repositoryRoot.startsWith(`${root}${path.sep}`)) {
      return { success: false, error: 'Repository path escapes the session workspace' };
    }
    const topLevel = (await runGit(['rev-parse', '--show-toplevel'], repositoryRoot)).stdout.trim();
    const canonicalTopLevel = await fs.promises.realpath(topLevel);
    if (canonicalTopLevel !== root && !canonicalTopLevel.startsWith(`${root}${path.sep}`)) {
      return { success: false, error: 'Git repository is outside the session workspace' };
    }
    const commandArgs: Record<string, string[]> = {
      status: ['status', '--short', '--branch'],
      log: ['log', '-5', '--oneline'],
      diff: ['diff', '--stat'],
      branch: ['branch', '--show-current'],
    };
    const result = await runGit(commandArgs[action], canonicalTopLevel);
    return { success: true, action, path: path.relative(root, canonicalTopLevel).replaceAll(path.sep, '/'), output: result.stdout.trim() || '(no changes)' };
  } catch (err) {
    return { success: false, error: errorMessage(err) };
  }
}

// ─── Ollama integration ────────────────────────────────────────
interface OllamaTag {
  name: string;
  [key: string]: unknown;
}

async function listOllamaModels(): Promise<OllamaTag[]> {
  try {
    const res = await fetch(`${ollamaBaseUrl}/api/tags`, { signal: AbortSignal.timeout(3000) });
    const data = (await res.json()) as { models?: OllamaTag[] };
    return (data.models ?? []).map((m) => ({ ...m, provider: 'ollama' }));
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

async function listModels(): Promise<OllamaTag[]> {
  const cloud = inceptionConfigured()
    ? INCEPTION_MODELS.map((name) => ({ name, provider: 'inception', agent: true }))
    : [];
  return [...cloud, ...(await listOllamaModels())];
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
          id: String(item.guid?.['#text'] ?? item.guid ?? item.id ?? link?.['@_href'] ?? link ?? ''),
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

registerPlugin('git_repository', {
  type: 'tool',
  permission: 'network',
  description: 'Clone public HTTPS repositories and inspect session-workspace Git status, recent commits, diff summary, or current branch',
  icon: '⑂',
  execute: async (input: PluginInput): Promise<PluginResult> => runGitAction(String(input.sessionId ?? ''), String(input.action ?? ''), input),
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
  abort: AbortController | null = null;
  /** Goals waiting behind the running one; drained strictly in order, one at a time per session. */
  readonly queue: Array<{ goal: string; model?: string; task: Task; routeTelemetry?: Record<string, any>; agentProfile?: string }> = [];
  private busy = false;
  readonly approvedDomains = new Set<string>();
  readonly pendingApprovals = new Map<string, { resolve: (approved: boolean) => void; timer: NodeJS.Timeout }>();
  history: Array<{ goal: string; result: string }> = [];
  currentTask: Task | null = null;
  ws: WebSocket | null = null;

  constructor(id: string, config: SessionConfigInput = {}) {
    this.id = id;
    this.config = {
      model: config.model ?? (inceptionConfigured() ? INCEPTION_MODELS[0] : defaultLocalModel),
      provider: config.provider ?? (inceptionConfigured() ? 'inception' : 'ollama'),
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
    const timestamp = Date.now();
    this.tasks.push({
      id: randomUUID(),
      timestamp,
      status: 'pending',
      title: String(task.title || task.description || 'Untitled task'),
      priority: 'medium',
      tags: [],
      attachments: [],
      activity: [{ timestamp, actor: 'agent', action: 'created' }],
      ...task,
    } as Task);
    const created = this.tasks[this.tasks.length - 1] as Task;
    this.broadcast({ type: 'task', data: created });
    return created;
  }

  updateTask(id: string, updates: Partial<Task>, actor = 'agent'): Task | undefined {
    const task = this.tasks.find((t) => t.id === id);
    if (task) {
      Object.assign(task, updates);
      task.activity = [
        ...(task.activity ?? []),
        { timestamp: Date.now(), actor, action: Object.keys(updates).join(', ') || 'updated' },
      ].slice(-50);
      this.broadcast({ type: 'task_update', data: task });
    }
    return task;
  }

  executeTaskAction(action: string, payload: Record<string, unknown>): Record<string, unknown> {
    const normalizedAction = action.toLowerCase();
    const reference = String(payload.id ?? '').trim();
    const matches = reference
      ? this.tasks.filter((task) => task.id === reference || task.id.startsWith(reference))
      : [];
    const task = matches.length === 1 ? matches[0] : undefined;
    const resolveTask = (): Task => {
      if (matches.length > 1) throw new Error('Task ID prefix is ambiguous; use more characters');
      if (!task) throw new Error(`Task not found: ${reference || '(missing ID)'}`);
      return task;
    };
    const priority = (value: unknown): Task['priority'] => {
      const normalized = String(value ?? '').toLowerCase();
      if (!['low', 'medium', 'high', 'critical'].includes(normalized)) throw new Error('Priority must be low, medium, high, or critical');
      return normalized as Task['priority'];
    };
    const dueDate = (value: unknown): string | undefined => {
      const date = String(value ?? '').trim();
      if (!date || date.toLowerCase() === 'none') return undefined;
      const parsed = new Date(`${date}T00:00:00Z`);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== date) {
        throw new Error('Due date must be a real date in YYYY-MM-DD format');
      }
      return date;
    };
    const tags = (value: unknown): string[] => {
      const values = Array.isArray(value) ? value : String(value ?? '').split(',');
      return Array.from(new Set(values.map((tag) => String(tag).trim().toLowerCase()).filter(Boolean))).slice(0, 12);
    };

    switch (normalizedAction) {
      case 'create': {
        const title = String(payload.title ?? '').trim();
        if (!title || title.length > 300) throw new Error('Task title must contain 1 to 300 characters');
        const created = this.addTask({
          title,
          description: title,
          priority: payload.priority ? priority(payload.priority) : 'medium',
          assignee: String(payload.assignee ?? '').trim() || undefined,
          dueDate: dueDate(payload.dueDate),
          tags: tags(payload.tags),
        });
        created.activity = [{ timestamp: created.timestamp, actor: 'terminal', action: 'created' }];
        this.broadcast({ type: 'task_update', data: created });
        return { success: true, action: normalizedAction, task: created };
      }
      case 'list': {
        const statusFilter = String(payload.status ?? '').toLowerCase();
        const priorityFilter = String(payload.priority ?? '').toLowerCase();
        const query = String(payload.query ?? '').toLowerCase();
        const items = this.tasks.filter((item) => {
          const statusMatches = !statusFilter || statusFilter === 'all'
            || (statusFilter === 'open' ? ['pending', 'running', 'blocked'].includes(item.status) : item.status === statusFilter);
          const priorityMatches = !priorityFilter || item.priority === priorityFilter;
          const textMatches = !query || `${item.title} ${item.description} ${item.assignee} ${(item.tags ?? []).join(' ')}`.toLowerCase().includes(query);
          return statusMatches && priorityMatches && textMatches;
        });
        return { success: true, action: normalizedAction, tasks: items };
      }
      case 'show':
        return { success: true, action: normalizedAction, task: resolveTask() };
      case 'start':
        return { success: true, action: normalizedAction, task: this.updateTask(resolveTask().id, { status: 'running', blockedReason: undefined }, 'terminal') };
      case 'done':
        return { success: true, action: normalizedAction, task: this.updateTask(resolveTask().id, { status: 'completed', blockedReason: undefined }, 'terminal') };
      case 'block': {
        const reason = String(payload.reason ?? '').trim();
        if (!reason) throw new Error('Add a reason after the task ID');
        return { success: true, action: normalizedAction, task: this.updateTask(resolveTask().id, { status: 'blocked', blockedReason: reason }, 'terminal') };
      }
      case 'priority':
        return { success: true, action: normalizedAction, task: this.updateTask(resolveTask().id, { priority: priority(payload.value) }, 'terminal') };
      case 'assign': {
        const assignee = String(payload.value ?? '').trim();
        return { success: true, action: normalizedAction, task: this.updateTask(resolveTask().id, { assignee: !assignee || assignee.toLowerCase() === 'none' ? undefined : assignee }, 'terminal') };
      }
      case 'due':
        return { success: true, action: normalizedAction, task: this.updateTask(resolveTask().id, { dueDate: dueDate(payload.value) }, 'terminal') };
      case 'tag':
        return { success: true, action: normalizedAction, task: this.updateTask(resolveTask().id, { tags: tags(payload.value) }, 'terminal') };
      case 'note': {
        const note = String(payload.value ?? '').trim();
        if (!note || note.length > 1000) throw new Error('Task note must contain 1 to 1000 characters');
        const updated = this.updateTask(resolveTask().id, { lastNote: note }, 'terminal');
        if (updated?.activity?.length) updated.activity[updated.activity.length - 1].note = note;
        return { success: true, action: normalizedAction, task: updated };
      }
      default:
        throw new Error(`Unknown task action: ${normalizedAction}`);
    }
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
    if (name === 'git_repository') recordedInput.sessionId = this.id;
    if (typeof recordedInput.image_base64 === 'string') {
      recordedInput.image_base64 = `[omitted image payload: ${Math.floor(recordedInput.image_base64.length * 0.75)} bytes]`;
    }
    this.addThought({ type: 'plugin_call', plugin: name, input: recordedInput, status: 'running' });

    try {
      let result = await plugin.execute(name === 'git_repository' ? { ...input, sessionId: this.id } : input);
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

  /**
   * Single entry point for goals. A session runs one goal at a time: concurrent runs would share the
   * abort controller and approval map, so extra goals wait in `queue` as visible "queued" tasks.
   */
  submitGoal(goal: string, model?: string, routeTelemetry?: Record<string, any>, agentProfile?: string): { queued: boolean; position: number; task_id?: string } {
    if (this.busy) {
      const task = this.addTask({ description: goal, status: 'queued' });
      this.queue.push({ goal, model, task, routeTelemetry, agentProfile });
      this.broadcast({ type: 'queued', data: { task_id: task.id, goal, position: this.queue.length } });
      return { queued: true, position: this.queue.length, task_id: task.id };
    }
    void this.drain({ goal, model, routeTelemetry, agentProfile });
    return { queued: false, position: 0 };
  }

  private async drain(first: { goal: string; model?: string; task?: Task; routeTelemetry?: Record<string, any>; agentProfile?: string }): Promise<void> {
    this.busy = true;
    let next: { goal: string; model?: string; task?: Task; routeTelemetry?: Record<string, any>; agentProfile?: string } | undefined = first;
    try {
      while (next) {
        if (next.model) {
          this.config.model = next.model;
          this.config.provider = isInceptionModel(next.model) ? 'inception' : 'ollama';
        }
        this.broadcast({ type: 'status', data: 'running' });
        const result = await this.runGoal(next.goal, next.task, next.routeTelemetry, next.agentProfile);
        this.broadcast({ type: 'result', data: result });
        next = this.queue.shift();
      }
    } finally {
      this.busy = false;
    }
  }

  /** Reuses the task created at enqueue time, or creates one for a goal that starts immediately. */
  private beginTask(goal: string, queued?: Task): Task {
    if (queued) return this.updateTask(queued.id, { status: 'running' }) ?? queued;
    return this.addTask({ description: goal, status: 'running' });
  }

  async runGoal(goal: string, queuedTask?: Task, routeTelemetry?: Record<string, any>, agentProfile?: string): Promise<PluginResult> {
    if (isInceptionModel(this.config.model)) return this.runAgentGoal(goal, queuedTask, routeTelemetry, agentProfile);
    this.status = 'running';
    this.addThought({ type: 'goal', content: `Starting goal: ${goal}`, status: 'info' });

    const task = this.beginTask(goal, queuedTask);
    const record = this.newRun(goal, task.id);
    const modelStartedAt = Date.now();

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

      runStore.addEvent(record, {
        kind: 'model', step: 1, latency_ms: Date.now() - modelStartedAt, prompt_tokens: 0, completion_tokens: 0,
        cost_usd: 0, tool_calls: [], content: fullResponse.slice(0, 2000),
      });
      runStore.finish(record, { status: 'completed', result: fullResponse });
      this.updateTask(task.id, { status: 'completed', result: fullResponse });
      this.status = 'idle';
      return { success: true, result: fullResponse, run_id: record.id, duration_ms: record.duration_ms, steps: 1, tool_calls: 0, tokens: 0, cost_usd: 0 };
    } catch (err) {
      const message = errorMessage(err);
      runStore.finish(record, { status: 'failed', error: message, failure_kind: classifyFailure(message, false) });
      this.updateTask(task.id, { status: 'failed', error: message });
      this.status = 'idle';
      return { success: false, error: message, run_id: record.id };
    }
  }

  newRun(goal: string, id: string): RunRecord {
    return runStore.create({
      id,
      session_id: this.id,
      goal,
      model: this.config.model,
      provider: this.config.provider,
      status: 'running',
      started_at: Date.now(),
      steps: [],
      current_step: 0,
      tool_calls: 0,
      prompt_tokens: 0,
      completion_tokens: 0,
      cost_usd: 0,
      approvals: { approved: 0, denied: 0 },
      files: [],
    });
  }

  requestApproval(runId: string, tool: string, args: Record<string, unknown>, reason: string): Promise<boolean> {
    const id = randomUUID();
    return new Promise((resolve) => {
      const timer = setTimeout(() => this.resolveApproval(id, false), APPROVAL_TIMEOUT_MS);
      this.pendingApprovals.set(id, { resolve, timer });
      this.broadcast({ type: 'approval_request', data: { id, run_id: runId, tool, args, reason, timeout_ms: APPROVAL_TIMEOUT_MS } });
    });
  }

  resolveApproval(id: string, approved: boolean): void {
    const pending = this.pendingApprovals.get(id);
    if (!pending) return;
    clearTimeout(pending.timer);
    this.pendingApprovals.delete(id);
    this.broadcast({ type: 'approval_resolved', data: { id, approved } });
    pending.resolve(approved);
  }

  async runAgentGoal(goal: string, queuedTask?: Task, routeTelemetry?: Record<string, any>, agentProfile?: string): Promise<PluginResult> {
    this.status = 'running';
    this.abort = new AbortController();
    const profile = agentProfile ? AGENT_PROFILES[agentProfile] : undefined;
    if (agentProfile && !profile) throw new Error(`Unknown agent profile '${agentProfile}'`);
    this.addThought({ type: 'goal', content: `${profile ? `${profile.name} agent` : 'Worker agent'} (${this.config.model}) starting: ${goal}`, status: 'info' });
    const task = this.beginTask(goal, queuedTask);
    const record = this.newRun(goal, task.id);
    if (routeTelemetry) record.routeTelemetry = routeTelemetry;
    if (agentProfile) record.agentProfile = agentProfile;
    this.broadcast({ type: 'run_update', data: record });
    try {
      // Knowledge and episodes are recalled separately so repeated goals cannot crowd out notes.
      // Parallelized: both searches run concurrently instead of sequentially.
      const [knowledge, episodes] = await Promise.all([
        memoryStore.search(goal, { layers: ['verified', 'org'], topK: 3 }),
        memoryStore.search(goal, { layers: ['task'], topK: 2 }),
      ]);
      const recalled = { hits: [...knowledge.hits, ...episodes.hits], backend: knowledge.backend };
      record.recalled = recalled.hits.map((hit) => hit.item.id);
      if (recalled.hits.length) {
        this.addThought({
          type: 'memory',
          content: `Recalled ${recalled.hits.length} memor${recalled.hits.length === 1 ? 'y' : 'ies'} (${recalled.backend}): ${recalled.hits.map((hit) => hit.item.title).join(' · ')}`,
          status: 'info',
        });
      }
      const run = await runToolAgent(goal, this.config.model, this.config.maxIterations, this.config.temperature, this.history, {
        workspace: sessionWorkspace(this.id),
        resolvePath: (relativePath) => safeWorkspacePath(this.id, relativePath),
        onThought: (thought) => this.addThought(thought),
        onEvent: (event) => {
          runStore.addEvent(record, event);
          this.broadcast({ type: 'run_update', data: { ...record, steps: undefined } });
        },
        onFilesChanged: () => this.broadcast({ type: 'files_changed' }),
        signal: this.abort.signal,
        checkBudget: () =>
          dailyBudgetUsd > 0 && runStore.costToday() >= dailyBudgetUsd
            ? `Daily budget of $${dailyBudgetUsd < 0.01 ? dailyBudgetUsd.toFixed(4) : dailyBudgetUsd.toFixed(2)} reached (KUDBEE_DAILY_BUDGET_USD)`
            : null,
        approvedDomains: this.approvedDomains,
        allowedTools: profile?.allowedTools,
        requestApproval: (tool, args, reason) => this.requestApproval(record.id, tool, args, reason),
        remember: async (title, content, tags) => {
          const item = await memoryStore.write('org', { title, content, tags, source: `agent run:${record.id.slice(0, 8)}` });
          this.broadcast({ type: 'memory_changed', data: { id: item.id } });
          return { id: item.id, layer: item.layer, path: item.path, note: 'Saved as unverified org memory; a human can promote it.' };
        },
        recall: async (query, limit) => {
          const { hits, backend } = await memoryStore.search(query, { topK: limit });
          return {
            backend,
            results: hits.map(({ item, score }) => ({ id: item.id, layer: item.layer, title: item.title, score: Math.round(score * 1000) / 1000, content: item.content.slice(0, 800) })),
          };
        },
        rssFeed: async (url, limit) => {
          const rss = plugins.get('rss_feed');
          if (!rss) throw new Error('rss_feed plugin missing');
          const result = await rss.execute({ url, limit });
          if (!result.success) throw new Error(String(result.error));
          return result as Record<string, unknown>;
        },
      }, MemoryStore.formatForPrompt(recalled.hits));
      const status = run.success ? 'completed' : run.stopped ? 'stopped' : 'failed';
      runStore.finish(record, { status, result: run.result, error: run.error, failure_kind: classifyFailure(run.error, Boolean(run.stopped)) });
      await this.recordEpisode(record);

      // Auto-save run metadata to persistent DB (Phase 3 + Feature 5 token telemetry)
      try {
        await persistence.saveRunMetadata({
          runId: record.id,
          sessionId: this.id,
          goal: record.goal,
          status: status as 'running' | 'completed' | 'failed' | 'stopped',
          startTime: record.started_at,
          endTime: Date.now(),
          metrics: {
            tokens: record.tokens,
            cost_usd: record.cost_usd,
            duration_ms: record.duration_ms,
            tool_calls: record.approvals.tool_calls,
            approvals_approved: record.approvals.approved,
            approvals_denied: record.approvals.denied,
            // Feature 5: Token telemetry
            model_selected: record.routeTelemetry?.modelSelected ?? this.config.model,
            route_reason: record.routeTelemetry?.routeReason ?? 'auto',
            estimated_tokens_if_full_model: record.routeTelemetry?.estimatedTokensIfFullModel ?? record.tokens,
            estimated_tokens_actual: record.routeTelemetry?.estimatedTokensActual ?? record.tokens,
            tokens_saved_est: record.routeTelemetry?.tokensSavedEst ?? 0,
            // HERMES etc: which tool-scoped agent profile ran this goal, if any
            agent_profile: record.agentProfile,
          },
          files: record.files,
          createdAt: record.started_at,
        });
      } catch (dbErr) {
        // Log but don't crash: DB write failure shouldn't block run completion
        console.error(`[persistence] Failed to save run metadata for ${record.id}:`, dbErr);
      }
      this.memory.push({ timestamp: Date.now(), type: 'agent_run', run_id: record.id, goal, status, cost_usd: record.cost_usd } as MemoryEntry);
      if (run.success) {
        this.history.push({ goal, result: run.result ?? '' });
        this.updateTask(task.id, { status: 'completed', result: run.result });
      } else {
        this.addThought({ type: 'error', content: run.error, status: 'error' });
        this.updateTask(task.id, { status: status === 'stopped' ? 'stopped' : 'failed', error: run.error } as Partial<Task>);
      }
      this.broadcast({ type: 'run_update', data: { ...record, steps: undefined } });
      return {
        success: run.success,
        result: run.result,
        error: run.error,
        run_id: record.id,
        steps: run.steps,
        tool_calls: run.tool_calls,
        tokens: run.tokens,
        cost_usd: run.cost_usd,
        duration_ms: record.duration_ms,
        model: this.config.model,
        files: record.files,
      };
    } catch (err) {
      const message = errorMessage(err);
      runStore.finish(record, { status: 'failed', error: message, failure_kind: classifyFailure(message, false) });
      this.addThought({ type: 'error', content: message, status: 'error' });
      this.updateTask(task.id, { status: 'failed', error: message });
      return { success: false, error: message, run_id: record.id, duration_ms: record.duration_ms };
    } finally {
      this.status = 'idle';
      this.abort = null;
    }
  }

  /** Task-layer memory: one Markdown episode per finished agent run, so later runs can learn from it. */
  async recordEpisode(run: RunRecord): Promise<void> {
    const tools = run.steps.filter((step) => step.kind === 'tool').map((step) => (step.kind === 'tool' ? `${step.name}${step.ok ? '' : ' ✗'}` : ''));
    const observed = run.steps.flatMap((step) =>
      step.kind === 'tool' && step.ok && ['fetch_url', 'read_rss', 'read_file'].includes(step.name) ? [step.name] : [],
    );
    const outcome = run.status === 'completed' ? 'completed' : `${run.status}${run.failure_kind ? ` (${run.failure_kind})` : ''}`;
    const content = [
      `Goal: ${run.goal}`,
      `Outcome: ${outcome}`,
      `When: ${new Date(run.started_at).toISOString()} · Model: ${run.model} · Steps: ${run.current_step} · Cost: $${run.cost_usd.toFixed(5)} · Duration: ${((run.duration_ms ?? 0) / 1000).toFixed(1)}s`,
      `Tools: ${tools.join(' → ') || 'none'}`,
      `Evidence gathered: ${observed.length ? `yes (${[...new Set(observed)].join(', ')})` : "none — any answer came from the model's own knowledge"}`,
      run.approvals.approved || run.approvals.denied ? `Approvals: ${run.approvals.approved} approved, ${run.approvals.denied} denied` : '',
      run.files.length ? `Files: ${run.files.join(', ')} (workspace ${run.session_id})` : '',
      run.recalled?.length ? `Recalled: ${run.recalled.join(', ')}` : '',
      '',
      run.error ? `Error: ${run.error}` : `Answer given (unverified):\n${(run.result ?? '').slice(0, 1500)}`,
    ].filter((line, i, all) => line !== '' || (i > 0 && all[i - 1] !== '')).join('\n');
    try {
      const item = await memoryStore.write('task', {
        title: run.goal.slice(0, 90),
        content,
        tags: [run.status, run.model],
        source: `run:${run.id}`,
        slug: `${new Date(run.started_at).toISOString().slice(0, 10)}-${run.id.slice(0, 8)}`,
      });
      this.addThought({ type: 'memory', content: `Saved episode to task memory: ${item.path}`, status: 'success' });
      this.broadcast({ type: 'memory_changed', data: { id: item.id } });
    } catch (err) {
      this.addThought({ type: 'memory', content: `Could not save episode: ${errorMessage(err)}`, status: 'error' });
    }
  }

  stop(): void {
    // Stop means stop everything: the running goal is aborted and nothing queued behind it starts.
    for (const waiting of this.queue.splice(0)) {
      this.updateTask(waiting.task.id, { status: 'cancelled', error: 'Cancelled by stop before it started' } as Partial<Task>);
      this.broadcast({ type: 'result', data: { success: false, cancelled: true, error: `Cancelled before it started: ${waiting.goal}` } });
    }
    this.abort?.abort();
    for (const id of [...this.pendingApprovals.keys()]) this.resolveApproval(id, false);
    this.status = 'idle';
    this.broadcast({ type: 'status', data: 'idle' });
  }
}

// ─── WebSocket handling ────────────────────────────────────────
wss.on('connection', async (ws: WebSocket) => {
  const sessionId = randomUUID();
  const session = new AgentSession(sessionId);
  session.ws = ws;
  sessions.set(sessionId, session);
  void fs.promises.mkdir(sessionWorkspace(sessionId), { recursive: true });

  // Restore dashboard state from persistent storage
  const savedState = await persistence.restoreDashboardState(sessionId);
  if (savedState?.settings) {
    Object.assign(session.config, savedState.settings);
  }

  ws.send(
    JSON.stringify({
      type: 'init',
      data: {
        sessionId,
        config: session.config,
        models: await listModels(),
        plugins: getPlugins(),
        files: Array.from(session.files.entries()),
        tasks: session.tasks,
        thoughts: session.thoughts,
        restoredState: savedState,
      },
    }),
  );

  ws.on('message', async (raw: RawData) => {
    try {
      const msg = JSON.parse(raw.toString()) as WsMessage;

      switch (msg.type) {
        case 'run_goal': {
          const telemetry = msg.routeTelemetry && typeof msg.routeTelemetry === 'object' ? msg.routeTelemetry : undefined;
          const agentProfile = typeof msg.agent === 'string' && msg.agent in AGENT_PROFILES ? msg.agent : undefined;
          if (typeof msg.agent === 'string' && msg.agent && !agentProfile) {
            // Respond via the same 'result' contract client.run() already awaits —
            // a bare top-level 'error' message has no handler on the CLI side and
            // would leave `kudbee --agent <typo> "goal"` hanging forever.
            ws.send(JSON.stringify({ type: 'result', data: { success: false, error: `Unknown agent '${msg.agent}'. Available: ${Object.keys(AGENT_PROFILES).join(', ')}` } }));
            break;
          }
          session.submitGoal(String(msg.goal), typeof msg.model === 'string' && msg.model ? msg.model : undefined, telemetry as any, agentProfile);
          break;
        }

        case 'stop': {
          session.stop();
          break;
        }

        case 'approval_response': {
          session.resolveApproval(String(msg.id), msg.approved === true);
          break;
        }

        case 'plugin_execute': {
          const result = await session.executePlugin(String(msg.plugin), msg.input as PluginInput);
          ws.send(JSON.stringify({ type: 'plugin_result', data: { plugin: msg.plugin, result } }));
          break;
        }

        case 'task_action': {
          const result = session.executeTaskAction(
            String(msg.action ?? ''),
            msg.payload && typeof msg.payload === 'object' ? msg.payload as Record<string, unknown> : {},
          );
          ws.send(JSON.stringify({ type: 'task_action_result', data: result }));
          break;
        }

        case 'git_action': {
          const result = await session.executePlugin('git_repository', {
            action: String(msg.action ?? ''),
            ...(msg.payload && typeof msg.payload === 'object' ? msg.payload as Record<string, unknown> : {}),
          });
          ws.send(JSON.stringify({ type: 'git_action_result', data: result }));
          break;
        }

        case 'update_config': {
          Object.assign(session.config, msg.config);
          // Save config to persistent storage (debounced)
          void persistence.saveDashboardState({
            sessionId,
            settings: session.config,
            lastUpdate: Date.now(),
            createdAt: Date.now()
          });
          ws.send(JSON.stringify({ type: 'config_updated', data: session.config }));
          break;
        }

        case 'state_save': {
          // Save full dashboard state on demand
          const state = {
            sessionId,
            panelState: (msg.panelState as Record<string, any>) || {},
            viewState: (msg.viewState as Record<string, any>) || {},
            settings: session.config,
            lastUpdate: Date.now(),
            createdAt: Date.now()
          };
          await persistence.saveDashboardState(state);
          ws.send(JSON.stringify({ type: 'state_saved', data: { success: true } }));
          break;
        }

        case 'list_models': {
          const models = await listModels();
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
    // Nobody is watching or able to approve any more, so stop spending tokens.
    session.stop();
    sessions.delete(sessionId);
  });
});

// ─── REST API ──────────────────────────────────────────────────
async function monitorEndpoint(name: string, url: string, headers: Record<string, string> = {}): Promise<Record<string, unknown>> {
  const startedAt = Date.now();
  try {
    const response = await fetch(url, { headers, signal: AbortSignal.timeout(5000) });
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
    inception_configured: inceptionConfigured(),
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
    ...(process.env.UPSTASH_VECTOR_REST_URL && process.env.UPSTASH_VECTOR_REST_TOKEN
      ? [monitorEndpoint('Upstash Vector (memory)', `${process.env.UPSTASH_VECTOR_REST_URL.replace(/\/+$/, '')}/info`, { Authorization: `Bearer ${process.env.UPSTASH_VECTOR_REST_TOKEN}` })]
      : []),
    ...(inceptionConfigured()
      ? [monitorEndpoint('Inception Mercury 2', 'https://api.inceptionlabs.ai/v1/models', { Authorization: `Bearer ${process.env.INCEPTION_API_KEY}` })]
      : []),
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

let lastCpu = { usage: process.cpuUsage(), at: Date.now() };
let statsCache = { data: null as any, at: 0 };

app.get('/api/stats', (_req: Request, res: Response) => {
  // Cache stats for 500ms to reduce computation on rapid dashboard polls
  const now = Date.now();
  if (statsCache.data && now - statsCache.at < 500) {
    return res.json(statsCache.data);
  }

  const usage = process.cpuUsage(lastCpu.usage);
  const elapsedMs = Math.max(1, now - lastCpu.at);
  lastCpu = { usage: process.cpuUsage(), at: now };
  const memory = process.memoryUsage();
  const running = [...sessions.values()].filter((session) => session.status === 'running').length;
  const stats = {
    ...runStore.stats(),
    budget_usd: dailyBudgetUsd || null,
    memory: { counts: memoryStore.counts(), vector: memoryStore.vectorStatus },
    capacity: {
      running_agents: running,
      queued_goals: [...sessions.values()].reduce((sum, session) => sum + session.queue.length, 0),
      connected_sessions: sessions.size,
      pending_approvals: [...sessions.values()].reduce((sum, session) => sum + session.pendingApprovals.size, 0),
      server_cpu_pct: Math.round(((usage.user + usage.system) / 1000 / elapsedMs) * 1000) / 10,
      server_rss_mb: Math.round(memory.rss / 1024 / 1024),
      system_mem_used_pct: Math.round((1 - os.freemem() / os.totalmem()) * 100),
      system_mem_total_gb: Math.round((os.totalmem() / 1024 ** 3) * 10) / 10,
      load_avg: os.loadavg().map((load) => Math.round(load * 100) / 100),
      cores: os.cpus().length,
    },
  };
  statsCache = { data: stats, at: now };
  res.json(stats);
});

let runsListCache = { data: null as any, at: 0 };
app.get('/api/runs', (req: Request, res: Response) => {
  const limit = Math.min(Number(req.query.limit) || 50, 500);
  const now = Date.now();
  // Cache runs list for 1s; on rapid polls this cuts response time significantly
  if (runsListCache.data && now - runsListCache.at < 1000 && (runsListCache.data as any).runs.length === runStore.list(1).length) {
    return res.json(runsListCache.data);
  }
  const data = { runs: runStore.list(limit).map((run) => ({ ...run, steps: undefined, step_count: run.steps.length })) };
  runsListCache = { data, at: now };
  res.json(data);
});

app.get('/api/runs/:id', (req: Request, res: Response) => {
  const run = runStore.get(req.params.id);
  if (!run) return res.status(404).json({ error: 'Run not found' });
  res.json(run);
});

// ─── Algorand (read-only, public AlgoNode endpoints) ───────────
app.get('/api/algorand', async (req: Request, res: Response) => {
  try {
    res.json(await algorandQuery(req.query));
  } catch (err) {
    const message = errorMessage(err);
    res.status(/must be|not a valid|Not found/.test(message) ? 400 : 502).json({ error: message });
  }
});

// ─── Memory layers (files + vector index) ──────────────────────
function memoryLayerParam(value: unknown): MemoryLayer | undefined {
  return MEMORY_LAYERS.includes(value as MemoryLayer) ? (value as MemoryLayer) : undefined;
}

app.get('/api/memory/status', (_req: Request, res: Response) => {
  res.json({ root: memoryStore.root, namespace: memoryStore.namespace, counts: memoryStore.counts(), vector: memoryStore.vectorStatus });
});

app.get('/api/memory', async (req: Request, res: Response) => {
  const layer = memoryLayerParam(req.query.layer);
  const limit = Math.min(Number(req.query.limit) || 50, 200);
  const query = typeof req.query.q === 'string' ? req.query.q.trim() : '';
  const preview = (item: { content: string }) => item.content.replace(/\s+/g, ' ').slice(0, 240);
  if (query) {
    const { hits, backend } = await memoryStore.search(query, { layers: layer ? [layer] : undefined, topK: Math.min(limit, 25) });
    return res.json({ backend, items: hits.map(({ item, score }) => ({ ...item, content: preview(item), score })) });
  }
  res.json({ backend: 'list', items: memoryStore.list(layer, limit).map((item) => ({ ...item, content: preview(item) })) });
});

app.get('/api/memory/item', (req: Request, res: Response) => {
  const item = memoryStore.get(String(req.query.id ?? ''));
  if (!item) return res.status(404).json({ error: 'Memory not found' });
  res.json(item);
});

app.post('/api/memory', async (req: Request, res: Response) => {
  const layer = memoryLayerParam(req.body?.layer) ?? 'org';
  const title = String(req.body?.title ?? '').trim();
  const content = String(req.body?.content ?? '').trim();
  if (!title || !content) return res.status(400).json({ error: 'title and content are required' });
  if (layer === 'task') return res.status(400).json({ error: 'Task memory is written automatically by runs' });
  const tags = Array.isArray(req.body?.tags) ? req.body.tags.map(String) : String(req.body?.tags ?? '').split(',');
  const item = await memoryStore.write(layer, { title, content, tags, source: 'human' });
  for (const session of sessions.values()) session.broadcast({ type: 'memory_changed', data: { id: item.id } });
  res.status(201).json(item);
});

app.post('/api/memory/promote', async (req: Request, res: Response) => {
  try {
    const item = await memoryStore.promote(String(req.body?.id ?? ''));
    for (const session of sessions.values()) session.broadcast({ type: 'memory_changed', data: { id: item.id } });
    res.json(item);
  } catch (err) {
    res.status(400).json({ error: errorMessage(err) });
  }
});

app.delete('/api/memory/item', async (req: Request, res: Response) => {
  const removed = await memoryStore.remove(String(req.query.id ?? ''));
  if (!removed) return res.status(404).json({ error: 'Memory not found' });
  for (const session of sessions.values()) session.broadcast({ type: 'memory_changed', data: {} });
  res.json({ success: true });
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
  const models = await listModels();
  res.json(models);
});

app.get('/api/agents', (_req: Request, res: Response) => {
  const agents = Object.entries(AGENT_PROFILES).map(([id, p]) => ({ id, name: p.name, description: p.description, allowedTools: p.allowedTools }));
  res.json({ agents });
});

app.get('/api/sessions/:id/files', async (req: Request, res: Response) => {
  if (!workspaceExists(req.params.id)) return res.status(404).json({ error: 'Session not found' });
  const root = sessionWorkspace(req.params.id);
  const files: Array<{ path: string; size: number; modified_at: string }> = [];
  async function walk(directory: string): Promise<void> {
    for (const entry of await fs.promises.readdir(directory, { withFileTypes: true })) {
      const absolute = path.join(directory, entry.name);
      if (entry.isDirectory() && entry.name !== '.git') await walk(absolute);
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
  if (!workspaceExists(req.params.id)) return res.status(404).json({ error: 'Session not found' });
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
  if (!workspaceExists(req.params.id)) return res.status(404).json({ error: 'Session not found' });
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

app.post('/api/sessions/:id/tasks/:taskId/attachments', imageUpload.single('image'), async (req: Request, res: Response) => {
  const session = sessions.get(req.params.id);
  if (!session) return res.status(404).json({ error: 'Session not found' });
  const task = session.tasks.find((item) => item.id === req.params.taskId || item.id.startsWith(req.params.taskId));
  if (!task) return res.status(404).json({ error: 'Task not found' });
  const image = req.file;
  if (!image) return res.status(400).json({ error: 'Choose an image to attach' });
  if (!['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(image.mimetype)) {
    return res.status(415).json({ error: 'Use a PNG, JPEG, WebP, or GIF image' });
  }
  const extension = ({
    'image/png': '.png',
    'image/jpeg': '.jpg',
    'image/webp': '.webp',
    'image/gif': '.gif',
  } as Record<string, string>)[image.mimetype];
  const filename = `${randomUUID()}${extension}`;
  const relativePath = `images/tasks/${task.id}/${filename}`;
  try {
    const destination = safeWorkspacePath(session.id, relativePath);
    await fs.promises.mkdir(path.dirname(destination), { recursive: true });
    await fs.promises.writeFile(destination, image.buffer);
    const attachment = {
      path: relativePath,
      filename: path.basename(image.originalname),
      imageUrl: `/api/sessions/${session.id}/files/raw?path=${encodeURIComponent(relativePath)}`,
      timestamp: Date.now(),
    };
    session.updateTask(task.id, { attachments: [...(task.attachments ?? []), attachment] }, 'terminal');
    session.addThought({ type: 'task_attachment', content: `Attached image to ${task.title}`, image: relativePath, status: 'success' });
    res.status(201).json({ success: true, attachment });
  } catch (err) {
    res.status(400).json({ error: errorMessage(err) });
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

  const goal = String(req.body?.goal ?? '').trim();
  if (!goal) return res.status(400).json({ error: 'goal is required' });
  // Goes through the session queue like WebSocket goals; follow progress via /api/runs.
  res.status(202).json(session.submitGoal(goal, typeof req.body.model === 'string' ? req.body.model : undefined));
});

app.post('/api/sessions/:id/stop', (req: Request, res: Response) => {
  const session = sessions.get(req.params.id);
  if (!session) return res.status(404).json({ error: 'Session not found' });
  session.stop();
  res.json({ success: true });
});

// ─── Memory Notes (Persistent Storage) ────────────────────────
app.get('/api/memory/notes', async (req: Request, res: Response) => {
  try {
    const sessionId = req.query.sessionId as string;
    const layer = req.query.layer as string | undefined;
    const limit = Math.min(parseInt(req.query.limit as string, 10) || 20, 200);

    if (!sessionId) {
      return res.status(400).json({ error: 'sessionId required' });
    }

    const notes = await persistence.listMemoryNotes(sessionId, layer, limit);
    res.json({ notes });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

app.post('/api/memory/notes', async (req: Request, res: Response) => {
  try {
    const sessionId = req.query.sessionId as string;
    const { title, content, layer = 'session' } = req.body as any;

    if (!sessionId || !title || !content) {
      return res.status(400).json({ error: 'sessionId, title, content required' });
    }

    const id = randomUUID();
    const now = Date.now();
    await persistence.saveMemoryNote({
      id,
      sessionId,
      layer: layer as any,
      title,
      content,
      createdAt: now,
      updatedAt: now
    });

    res.json({ id, title, layer, createdAt: now });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

app.delete('/api/memory/notes/:id', async (req: Request, res: Response) => {
  try {
    const id = req.params.id;
    // Phase 3: soft-delete tracking only; full DB delete in Phase 4
    res.json({ deleted: id });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

// ─── Run History (Persistent Storage) ──────────────────────────
app.get('/api/runs/history', async (req: Request, res: Response) => {
  try {
    const sessionId = req.query.sessionId as string;
    const limit = Math.min(parseInt(req.query.limit as string, 10) || 50, 500);

    if (!sessionId) {
      return res.status(400).json({ error: 'sessionId required' });
    }

    // Try persistent DB first
    const dbRuns = await persistence.listRuns(sessionId, limit);
    if (dbRuns.length > 0) {
      return res.json({ runs: dbRuns, source: 'db' });
    }

    // Fallback to JSON run store
    const allRuns = runStore.all().filter((r) => r.sessionId === sessionId);
    const runs = allRuns
      .slice(0, limit)
      .map((r) => ({
        runId: r.id,
        sessionId: r.sessionId,
        goal: r.goal,
        status: r.status,
        startTime: r.start_time,
        endTime: r.end_time,
        metrics: { tokens: (r.prompt_tokens ?? 0) + (r.completion_tokens ?? 0), cost: r.cost_usd },
        files: r.files,
        createdAt: r.start_time
      }));

    res.json({ runs, source: 'json' });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

// Feature 5: Token stats for KPI dashboard
app.get('/api/stats/tokens', async (req: Request, res: Response) => {
  try {
    const sessionId = req.query.sessionId as string;
    const limit = Math.min(parseInt(req.query.limit as string, 10) || 50, 500);

    if (!sessionId) {
      return res.status(400).json({ error: 'sessionId required' });
    }

    // listRuns() returns newest-first (createdAt DESC); a sparkline needs
    // chronological order (oldest→newest) or the trend line reads backwards.
    const runs = await persistence.listRuns(sessionId, limit);
    const chronological = [...runs].reverse();

    const savedPerRun = chronological.map((run) => (run.metrics?.tokens_saved_est as number) || 0);
    const totalTokensSavedEst = savedPerRun.reduce((sum, v) => sum + v, 0);

    const tokenStats = {
      totalTokensSavedEst,
      totalRunsTracked: runs.length,
      averageSavingsPerRun: runs.length > 0 ? Math.round(totalTokensSavedEst / runs.length) : 0,
      lastRunTokensSaved: runs.length > 0 ? ((runs[0].metrics?.tokens_saved_est as number) || 0) : 0,
      sparklineData: savedPerRun,
    };

    res.json(tokenStats);
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

// ─── Start server ──────────────────────────────────────────────
const PORT = process.env.PORT || 3000;
// SECURITY: Bind to localhost only, not all interfaces (§1.4.1 AGENTS.md)
const LISTEN_ADDR = process.env.LISTEN_ADDR || '127.0.0.1';
server.listen(PORT, LISTEN_ADDR, () => {
  console.log(`\n🚀 THINK BOX AI — Devin-like Interface`);
  console.log(`   Backend:  http://${LISTEN_ADDR}:${PORT}`);
  console.log(`   WebSocket: ws://${LISTEN_ADDR}:${PORT}`);
  console.log(`   Models:   Ollama ${ollamaBaseUrl}${inceptionConfigured() ? ' + Inception mercury-2 (worker agent)' : ''}`);
  console.log(`\n   Ready.\n`);
});

void files;
