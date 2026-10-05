import { bridgeConfigFromEnv, submitGovernedRun, getGovernedRun } from './governed-bridge.ts';
import { createGitRouter } from './git-api-routes.ts';
import { fetchChecked, targetsPrivateNetwork } from './net-guard.ts';
import { rateLimit, rejectCrossOriginWrites, securityHeaders } from './http-security.ts';
import { describeError, installProcessHandlers, jsonErrorHandler } from './error-handling.ts';
import { sanitizeConfigPatch } from './config-patch.ts';
import { discoverMCPSkills, filterSkills, groupSkillsByCategory } from './mcp-skills.ts';
import { createModelClients } from './ollama-client.ts';
import { registerDiagnosticsRoutes } from './routes/diagnostics.ts';
import { registerMemoryRoutes } from './routes/memory.ts';
import { registerProfileRoutes } from './routes/profiles.ts';
import { registerConvoyRoutes } from './routes/convoys.ts';
import { registerRunsRoutes } from './routes/runs.ts';
import { FileTooLargeError, WorkspacePathError, assertRealInside, assertRealInsideSync, readConfined, unlinkConfined, writeConfined } from './workspace-fs.ts';
import express, { type Request as ExpressRequest, type Response } from 'express';
// Express 5 types route params as string | string[]; every route here uses plain named params, which are always strings.
type Request = ExpressRequest<Record<string, string>>;
import type { IncomingMessage } from 'node:http';
import { createRequire } from 'node:module';
import { randomUUID } from 'node:crypto';
import { stripTypeScriptTypes } from 'node:module';
import { execFile } from 'node:child_process';
import { WebSocketServer, WebSocket, type RawData } from 'ws';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

import type {
  AgentSessionConfig,
  ChatMessage,
  MemoryEntry,
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
import { SDK_VERSION } from './sdk/index.ts';
import { AGENT_PROFILES, INCEPTION_MODELS, TOOLS, inceptionConfigured, isInceptionModel, newRunContext, runGovernedTool, runToolAgent, type AgentHooks } from './agent.ts';
import { ConvoyError, ConvoyStore } from './convoy.ts';
import { executeConvoy, summarize as summarizeConvoy, type RunnerDeps } from './convoy-runner.ts';
import { evaluatePolicy, planConvoy } from './mayor.ts';
import { agentRoute, escalatedRoute, localChatRoute, recipeRoute, refusedRoute, type RouteDecision } from './route-decision.ts';
import { validateGrounding, presentAnswer, type GroundingResult } from './grounding.ts';
import { renderFacts, type LookupEvidence } from './live-lookup.ts';
import { isGithubRecipe, buildFacts, buildPrompt, groundedAnswer, matchRecipe, recipeAvailable, recipeToolArgs, sentenceRule, type RecipeMatch } from './local-recipes.ts';
import { needsToolsOrLiveData } from './goal-routing.ts';
import { RunStore, classifyFailure, type RunRecord } from './runs.ts';
import { MemoryStore, profileMemoryRoot } from './memory.ts';
import { ProfileManager } from './profile-manager.ts';
import { createMemorySemantic } from './memory-semantic.ts';
import { detectRepo, repoContextLine } from './repo-context.ts';
import { algorandQuery } from './algorand.ts';
import PersistenceLayer from './persistence.ts';
import { LearningStore } from './learning-store.ts';
import { ThinkTokenCollection } from './think-token.ts';
import { ThinkTokenPropagator } from './think-token-propagation.ts';
import { ServerLearningIntegration } from './server-learning-integration.ts';
import { DEFAULT_RANKER, RANKERS, SqliteTokenStore, formatTokensForPrompt, type RankerName } from './think-token-store.ts';
import { processFinishedRun, rechallengeScoredTokens } from './think-token-pipeline.ts';
import { embedderState, ensureEmbeddings, peekEmbedder } from './think-token-embed.ts';
import { createLiveStateClassifier } from './evidence.ts';
import { TOKEN_HEADER, ensureLocalToken, tokensMatch } from './local-token.ts';
import { createTokenModels } from './think-token-model.ts';
import { readTokenCube, readTokens } from './think-token-reader.ts';
import { resolveLocalModel } from './local-model.ts';
import { validateTokenMessage } from './think-token-ws.ts';
import { SPECIALISTS, selectSpecialists, validateComposition } from './specialist-contracts.ts';
import {
  allocateSpecialistJobs,
  completeSpecialistJob,
  createRunToolAgentExecutor,
  evidenceFromSpecialistExecutions,
  executeSpecialistPlan,
  replaySpecialistEvents,
  replaySpecialistJobEvents,
  validateSpecialistEvidence,
} from './specialist-executor.ts';
import { createInitialCubeState, applyEvent as applyThinkCubeEvent } from './public/js/think-cube-state.js';
import { installCoverageFlush } from './coverage-flush.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// A spawned server is stopped by a signal; make that a clean exit so NODE_V8_COVERAGE is written (test coverage only).
installCoverageFlush();

// Secrets stay server-side: the repo-root .env is read here and never sent to the browser.
for (const envPath of [path.join(__dirname, '.env'), path.resolve(__dirname, '../../.env')]) {
  try {
    process.loadEnvFile(envPath);
  } catch {
    // Missing .env is fine; the runtime falls back to Ollama-only mode.
  }
}

const PORT = process.env.PORT || 3000;
const PORT_NUM = typeof PORT === 'string' ? parseInt(PORT, 10) : PORT;

// ─── Local-only request gate ───────────────────────────────────
// The dashboard has no login (deferred), and a loopback bind alone does not stop a web page in the
// operator's browser from reaching 127.0.0.1: WebSocket upgrades are not bound by same-origin policy,
// and DNS rebinding makes an attacker's hostname resolve here. So every HTTP request and WebSocket
// upgrade must name a loopback Host on our port, and WebSocket upgrades must come from our own origin.
const LOOPBACK_HOSTNAMES = ['127.0.0.1', 'localhost', '[::1]'];

export function isAllowedHost(host: string | undefined, port: number): boolean {
  const h = (host ?? '').trim().toLowerCase();
  return LOOPBACK_HOSTNAMES.some((name) => h === `${name}:${port}` || (port === 80 && h === name));
}

export function isAllowedOrigin(origin: string | undefined, port: number): boolean {
  const o = (origin ?? '').trim().toLowerCase();
  return LOOPBACK_HOSTNAMES.some((name) => o === `http://${name}:${port}` || (port === 80 && o === `http://${name}`));
}

const LOCAL_TOKEN = ensureLocalToken(process.env.KUDBEE_DATA_DIR || path.join(path.dirname(fileURLToPath(import.meta.url)), 'data'));
const app = express();
// `import { createServer } from 'http'` makes Node build an ES-module facade of node:http, which evaluates every lazy getter on it
// and loads undici (~55 ms at startup). A require() of the same builtin does not.
const { createServer } = createRequire(import.meta.url)('node:http') as typeof import('node:http');
const server = createServer(app);
// CLI identity: a client that sends the local token (see local-token.ts) is the kudbee CLI. An invalid token is refused; no token means a browser/dashboard.
const cliUpgrades = new WeakSet<IncomingMessage>();
// Dashboards that asked to see runs started elsewhere (the CLI); they receive `mirror` messages, never approval requests.
const mirrors = new Set<WebSocket>();
const MIRRORED_TYPES = new Set(['thought', 'result', 'queued', 'run_update', 'think_token_learned', 'think_token_used']);
const wss = new WebSocketServer({
  server,
  // Browsers always send Origin on a WebSocket upgrade. A missing Origin means a non-browser client;
  // the kudbee CLI and tests send ours, so no-Origin clients are refused unless explicitly allowed.
  verifyClient: ({ origin, req }: { origin: string; req: IncomingMessage }) => {
    if (!(isAllowedHost(req.headers.host, PORT_NUM) && (isAllowedOrigin(origin, PORT_NUM) || (!origin && process.env.DASHBOARD_ALLOW_NO_ORIGIN === '1')))) return false;
    const given = req.headers[TOKEN_HEADER];
    if (given === undefined) return true;
    if (!tokensMatch(LOCAL_TOKEN, Array.isArray(given) ? given[0] : given)) return false;
    cliUpgrades.add(req);
    return true;
  },
});
const ollamaBaseUrl = process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434';
// A local Ollama model is a plain chat here: no tools are attached. Telling a small model to "use the available plugins" made it invent a
// tool plan (fake http requests and plugin names) for goals like "what is 2 plus 2".
// A local Ollama model is a plain chat, exactly like `ollama run <model>` in a terminal (see LOCAL_CHAT_OPTIONS in local-model.ts).
const janusBaseUrl = process.env.JANUS_BASE_URL || 'http://127.0.0.1:8001';

/** Janus is opt-in (default off). CVE-2026-69112 in pinned `accelerate`; see docs/SECURITY.md. */
function janusEnabled(): boolean {
  const v = process.env.KUDBEE_JANUS_ENABLED;
  return v === '1' || v === 'true';
}
// Cheap local route default (Feature 5 token-aware routing). THINKBOX_LOCAL_MODEL (or the older KUDBEE_LOCAL_MODEL) names an
// already-installed Ollama model; the app never pulls models. See local-model.ts.
const defaultLocalModel = resolveLocalModel();
const workspaceRoot = process.env.KUDBEE_WORKSPACE_DIR || path.join(__dirname, 'workspaces');
/** multer (~35 ms to load) is only needed when someone uploads: build the instance on the first upload request. */
function lazyUpload(limits: { fileSize: number; files: number }) {
  let instance: Promise<import('multer').Multer> | undefined;
  const get = () => (instance ??= import('multer').then(({ default: multer }) => multer({ storage: multer.memoryStorage(), limits })));
  const wrap = (pick: (m: import('multer').Multer) => import('express').RequestHandler): import('express').RequestHandler =>
    (req, res, next) => { get().then((m) => pick(m)(req, res, next), next); };
  return {
    single: (field: string) => wrap((m) => m.single(field)),
    array: (field: string, max: number) => wrap((m) => m.array(field, max)),
  };
}
const upload = lazyUpload({ fileSize: 50 * 1024 * 1024, files: 500 });
const imageUpload = lazyUpload({ fileSize: 12 * 1024 * 1024, files: 1 });

app.use((req: Request, res: Response, next) => {
  if (isAllowedHost(req.headers.host, PORT_NUM)) return next();
  res.status(421).json({ error: 'misdirected_request', detail: 'The dashboard is local-only; use http://127.0.0.1 on its port' });
});
app.disable('x-powered-by');
app.use(securityHeaders(PORT_NUM));
app.use(rejectCrossOriginWrites((origin) => isAllowedOrigin(origin, PORT_NUM)));
// Caps (10 s windows). The whole API is generous (the dashboard polls); the file-system routes walk or write the workspace, so they are tighter.
app.use('/api', rateLimit({ windowMs: 10_000, max: 1000 }));
app.use('/api/sessions/:id/files', rateLimit({ windowMs: 10_000, max: 120 }));
app.use('/services', rateLimit({ windowMs: 10_000, max: 120 }));
app.use(express.json());
// Express 5 leaves req.body undefined for body-less requests (v4 gave {}); keep v4 behavior so handlers answer 400, not 500.
app.use((req: Request, _res: Response, next) => { if (req.body === undefined) req.body = {}; next(); });
// Dashboard modules import these browser-side services as ../services/<name>.js; the sources are TypeScript, so serve them with types stripped.
const BROWSER_SERVICES = ['analytics', 'run-sharing', 'template-manager', 'timeline'];
const browserServiceJs = new Map<string, string>();
app.get('/services/:name.js', (req: Request, res: Response) => {
  const name = req.params.name;
  if (!BROWSER_SERVICES.includes(name)) return res.status(404).end();
  let js = browserServiceJs.get(name);
  if (js === undefined) {
    js = stripTypeScriptTypes(fs.readFileSync(path.join(__dirname, 'services', `${name}.ts`), 'utf8'));
    browserServiceJs.set(name, js);
  }
  res.type('application/javascript').send(js);
});
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
// Profiles: named operating contexts. Each profile owns its memory folder and run file; the active
// profile decides which the server reads/writes. The manager is created first so the stores can be
// scoped to the currently active profile.
const profilesDir = path.join(dataDir, 'profiles');
const profileManager = new ProfileManager(profilesDir, dataDir);
const activeProfileId = profileManager.getActiveId();
const runStore = new RunStore(path.join(profilesDir, activeProfileId, 'runs.json'), activeProfileId);
/** Abort controllers of running convoys, so convoy_stop can stop exactly one. */
const convoyAborts = new Map<string, AbortController>();
const convoyStore = new ConvoyStore(path.join(profilesDir, activeProfileId, 'convoys.json'), activeProfileId);
const memoryStore = new MemoryStore(profileMemoryRoot(profilesDir, activeProfileId), process.env, activeProfileId);
void memoryStore.syncVectors();

/**
 * Switch the active profile everywhere the server reads memory and runs. The stores keep their object
 * identity (route modules and the agent session captured them once), so this only re-points them.
 */
function activateProfile(profileId: string): void {
  const profile = profileManager.setActive(profileId);
  runStore.setProfile(profile.id);
  convoyStore.setProfile(profile.id);
  memoryStore.switchTo(profileMemoryRoot(profilesDir, profile.id), profile.id);
  void memoryStore.syncVectors();
  for (const session of sessions.values()) session.broadcast({ type: 'profile_changed', data: { id: profile.id, name: profile.name } });
}

// ─── Persistent storage (SQLite) ────────────────────────────────
const persistence = new PersistenceLayer(dataDir);

// ─── Think Token persistence (#288) ──────────────────────────────
// Bridges a finished agent run into the existing #288 Think Token chain: a successful run's
// thoughts are checked against ThinkTokenFactory's quality gate, and anything that passes is
// persisted as a learned_patterns row via LearningStore (see server-learning-integration.ts and
// think-token-propagation.ts for why each step is needed — several links here were previously
// unreachable dead code).
const learningStore = new LearningStore(process.env.KUDBEE_LEARNING_DB || undefined);
const thinkTokenPropagator = new ThinkTokenPropagator(learningStore, new ThinkTokenCollection());
const learningIntegration = new ServerLearningIntegration(thinkTokenPropagator, undefined, learningStore);
// ADR 028 Think Tokens: reusable learning units in their own SQLite file (never learning.db). Writes are admitted and
// receipted by the store; use and extraction are wired into runAgentGoal below.
const tokenStore = new SqliteTokenStore(process.env.KUDBEE_THINK_TOKEN_DB || path.join(dataDir, 'think-tokens.db'));
// Start loading the embedding model in the background at boot (no-op when THINKBOX_EMBEDDINGS=off or the optional package is missing).
peekEmbedder(); // always: a first goal right after a restart should not be ranked lexically while the model loads
const dailyBudgetUsd = Number(process.env.KUDBEE_DAILY_BUDGET_USD) || 0;
const APPROVAL_TIMEOUT_MS = 120_000;
fs.mkdirSync(workspaceRoot, { recursive: true });

const SESSION_ID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function sessionWorkspace(sessionId: string): string {
  // Session ids are server-made UUIDs; refuse anything else here so no caller can build a workspace path from a stray string.
  if (!SESSION_ID_RE.test(sessionId)) throw new Error('Invalid session id');
  return path.join(workspaceRoot, sessionId);
}

/** Live or past session: run history keeps pointing at workspaces after the socket closes. */
function workspaceExists(sessionId: string): boolean {
  return SESSION_ID_RE.test(sessionId) && (sessions.has(sessionId) || fs.existsSync(sessionWorkspace(sessionId)));
}

function safeWorkspacePath(sessionId: string, relativePath: string): string {
  const normalized = relativePath.replaceAll('\\', '/').replace(/^\/+/, '');
  if (!normalized || normalized.split('/').some(part => part === '..')) throw new Error('Invalid workspace path');
  const root = path.resolve(sessionWorkspace(sessionId));
  const destination = path.resolve(root, normalized);
  if (destination === root) return destination;
  if (!destination.startsWith(`${root}${path.sep}`)) throw new Error('Path escapes workspace');
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
const { requestJanus, listModels, streamOllama, chatOnce, modelCapabilities } = createModelClients({ ollamaBaseUrl, janusBaseUrl, janusEnabled });
// ─── Plugin system ─────────────────────────────────────────────
function registerPlugin(name: string, config: Omit<PluginConfig, 'name'>, enabled = true): void {
  plugins.set(name, {
    ...config,
    name,
    enabled,
    callCount: 0,
  });
}

/**
 * Resolve a plugin path inside the session workspace. Absolute paths are refused, `..` is refused by
 * safeWorkspacePath, and the real path (nearest existing ancestor) must stay inside the workspace.
 * Reads and writes then go through workspace-fs.ts, which opens the resolved path, not this one.
 */
async function confinedWorkspacePath(sessionId: string, requested: string): Promise<string> {
  if (!workspaceExists(sessionId)) throw new Error('Session not found');
  if (path.isAbsolute(requested) || path.win32.isAbsolute(requested)) {
    throw new WorkspacePathError('Absolute paths are not allowed; use a path inside the session workspace');
  }
  const destination = safeWorkspacePath(sessionId, requested);
  await assertRealInside(sessionWorkspace(sessionId), destination);
  return destination;
}

/** HTTP status for a workspace file error: a path that leads out is 403, not a client typo. */
function fileErrorStatus(err: unknown): number {
  if (err instanceof WorkspacePathError) return 403;
  if (err instanceof FileTooLargeError) return 413;
  return 400;
}

/** Why an operator-initiated plugin call (WebSocket plugin_execute / git_action) needs human approval, or null. */
async function operatorApprovalReason(name: string, input: PluginInput): Promise<string | null> {
  const plugin = plugins.get(name);
  if (!plugin) return null;
  if (plugin.permission === 'exec') return 'executes a shell command on this machine';
  if (plugin.permission === 'read_write') return 'writes to the session workspace';
  if (name === 'git_repository' && String(input.action ?? '') === 'clone') return 'clones a repository from the network';
  if (name === 'http_request' && !['GET', 'HEAD'].includes(String(input.method ?? 'GET').toUpperCase())) {
    return 'sends a state-changing HTTP request';
  }
  if ((name === 'http_request' || name === 'rss_feed') && await targetsPrivateNetwork(String(input.url ?? ''))) {
    return 'reaches a local or private network address';
  }
  return null;
}

function getPlugins(): Plugin[] {
  return Array.from(plugins.values());
}

// Default plugins
registerPlugin('file_read', {
  type: 'tool',
  permission: 'read_only',
  description: 'Read a file from the session workspace',
  icon: '📄',
  execute: async (input: PluginInput): Promise<PluginResult> => {
    const filePath = String(input.path ?? '');
    try {
      const sessionId = String(input.sessionId ?? '');
      const content = (await readConfined(sessionWorkspace(sessionId), await confinedWorkspacePath(sessionId, filePath))).toString('utf-8');
      return { success: true, content, path: filePath };
    } catch (err) {
      return { success: false, error: errorMessage(err) };
    }
  },
});

registerPlugin('file_write', {
  type: 'tool',
  permission: 'read_write',
  description: 'Write a file in the session workspace',
  icon: '✏️',
  execute: async (input: PluginInput): Promise<PluginResult> => {
    const filePath = String(input.path ?? '');
    const content = String(input.content ?? '');
    try {
      const sessionId = String(input.sessionId ?? '');
      await writeConfined(sessionWorkspace(sessionId), await confinedWorkspacePath(sessionId, filePath), content);
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
// Unrestricted local shell: off unless the operator opts in, and even then every call needs approval.
}, process.env.DASHBOARD_ENABLE_SHELL_EXEC === '1');

registerPlugin('http_request', {
  type: 'tool',
  permission: 'network',
  description: 'Make HTTP request',
  icon: '🌐',
  execute: async (input: PluginInput): Promise<PluginResult> => {
    const url = String(input.url);
    const method = input.method ? String(input.method) : 'GET';
    try {
      const res = await fetchChecked(url, { method }, input.allowPrivateNetwork === true);
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
      const response = await fetchChecked(parsedUrl.toString(), {
        headers: { Accept: 'application/rss+xml, application/atom+xml, application/xml, text/xml' },
        signal: AbortSignal.timeout(10000),
      }, input.allowPrivateNetwork === true);
      if (!response.ok) return { success: false, error: `Feed returned HTTP ${response.status}` };
      const xml = await response.text();
      const { XMLParser } = await import('fast-xml-parser'); // loaded on first feed read, not at startup
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
/** The validated, size-limited payload for think_token_learned / think_token_used. Built only from a stored row, so no event exists without a database row behind it. */
function tokenEvent(row: { id: string; kind: string; status: string; score: number; uses: number; title: string }, runId: string, delta: number) {
  return { token_id: row.id, run_id: runId.slice(0, 80), kind: row.kind, status: row.status, score: row.score, delta: Math.round(delta * 10_000) / 10_000, uses: row.uses, title: row.title.slice(0, 120) };
}

/**
 * Semantic retrieval input: the goal's embedding (and the model name), after embedding any accepted lesson that has no vector yet.
 * It never waits for the model to load (the first goals after a start are ranked lexically while it loads in the background), only starts
 * loading when there is at least one accepted lesson to embed, and falls back to lexical on any problem.
 */
async function goalEmbedding(goal: string): Promise<{ goalVector?: Float32Array; embedModel?: string; why?: string }> {
  try {
    if (!tokenStore.list({ status: 'accepted', limit: 1 }).length) return { why: 'no accepted lessons' };
    if (process.env.THINKBOX_EMBEDDINGS === 'off' || process.env.THINKBOX_EMBEDDINGS === '0') return { why: 'embeddings off' };
    const embedder = peekEmbedder();
    if (!embedder) {
      const st = embedderState();
      return { why: st.state === 'failed' ? `embedding model failed to load: ${st.error}` : 'embedding model still loading' };
    }
    await ensureEmbeddings(tokenStore, embedder);
    const [goalVector] = await embedder.embed([goal]);
    return goalVector ? { goalVector, embedModel: embedder.model } : { why: 'no goal vector' };
  } catch (err) {
    return { why: `embedding error: ${describeError(err)}` };
  }
}

// Only read when a goal runs, so the `git remote get-url` spawn is not paid at startup.
let knownRepo: string | null | undefined;
const getKnownRepo = (): string | null => (knownRepo === undefined ? (knownRepo = detectRepo()) : knownRepo);
memoryStore.semantic = createMemorySemantic({ memory: memoryStore, tokens: tokenStore, peek: () => peekEmbedder(), state: () => embedderState() });

let liveClassifier: Promise<((texts: string[]) => Promise<boolean[]>) | null> | null = null;
/**
 * Which recalled memories/lessons describe live state (so they can be dated and marked STALE), by embedding similarity to fixed examples
 * (evidence.ts; 15/20 vs 12/20 for the old keyword list on hand-labeled memories). undefined = embedder not ready: the keyword list is used.
 */
async function liveStateFlags(entries: Array<{ key: string; text: string }>): Promise<Map<string, boolean> | undefined> {
  try {
    const embedder = peekEmbedder();
    if (!embedder || !entries.length) return undefined;
    liveClassifier ??= createLiveStateClassifier(embedder).catch((err) => { console.warn(`[memory] live-state classifier unavailable, recalled memories will not be labeled: ${describeError(err)}`); return null; });
    const classify = await liveClassifier;
    if (!classify) return undefined;
    const flags = await classify(entries.map((e) => e.text));
    return new Map(entries.map((e, i) => [e.key, flags[i]!]));
  } catch {
    return undefined;
  }
}

export class AgentSession {
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
  /** The routing decision of the goal being drained; newRun() copies it onto the run record. */
  private route: RouteDecision | null = null;
  readonly queue: Array<{ goal: string; model?: string; task: Task; routeTelemetry?: Record<string, any>; agentProfile?: string }> = [];
  private busy = false;
  readonly approvedDomains = new Set<string>();
  readonly pendingApprovals = new Map<string, { resolve: (approved: boolean) => void; timer: NodeJS.Timeout }>();
  readonly specialistAborts = new Map<string, AbortController>();
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
    const kept = this.thoughts[this.thoughts.length - 1]!;
    // A specialist's own Think Box also receives a copy of the thought the orchestrating session already recorded: keep one.
    if (!(thought.thinkBoxId && thought.thinkBoxId === this.id)) persistence.saveThought(profileManager.getActiveId(), this.id, kept as unknown as { id: string; timestamp: number });
    this.broadcast({ type: 'thought', data: kept });
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

  /** Who started this session: the kudbee CLI (authenticated by the local token) or a dashboard/browser. */
  client: 'cli' | 'dashboard' = 'dashboard';

  broadcast(message: unknown): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
    // Live link: runs started from the CLI also show up in every dashboard that subscribed (labeled with who and which session).
    const type = (message as { type?: string } | null)?.type;
    if (this.client === 'cli' && type && MIRRORED_TYPES.has(type)) {
      const frame = JSON.stringify({ type: 'mirror', data: { client: 'cli', session: this.id.slice(0, 8), message } });
      for (const peer of mirrors) if (peer !== this.ws && peer.readyState === WebSocket.OPEN) peer.send(frame);
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

    // Plugins act on this session only (workspace, memory); a caller-supplied sessionId is overwritten.
    const scopedInput: PluginInput = { ...input, sessionId: this.id };
    const recordedInput = { ...scopedInput };
    if (typeof recordedInput.image_base64 === 'string') {
      recordedInput.image_base64 = `[omitted image payload: ${Math.floor(recordedInput.image_base64.length * 0.75)} bytes]`;
    }
    this.addThought({ type: 'plugin_call', plugin: name, input: recordedInput, status: 'running' });

    try {
      let result = await plugin.execute(scopedInput);
      if (name === 'image_generate' && typeof result.image_base64 === 'string') {
        const relativePath = `images/plugin-generated-${Date.now()}-${randomUUID().slice(0, 8)}.png`;
        const destination = safeWorkspacePath(this.id, relativePath);
        await writeConfined(sessionWorkspace(this.id), destination, Buffer.from(result.image_base64, 'base64'), { mkdirs: true });
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
   * Operator-initiated plugin call from the WebSocket. Anything that executes, writes or clones waits
   * for the same human approval the agent loop uses (requestApproval / approval_response).
   */
  async executeOperatorPlugin(name: string, input: PluginInput): Promise<PluginResult> {
    const plugin = plugins.get(name);
    if (plugin && !plugin.enabled) return { success: false, error: `Plugin disabled: ${name}` };
    const { allowPrivateNetwork: _ignored, ...cleanInput } = input;
    const reason = await operatorApprovalReason(name, cleanInput);
    if (reason && !(await this.requestApproval(`plugin:${name}`, name, { ...cleanInput }, reason))) {
      return { success: false, error: `Denied by human reviewer (${reason})` };
    }
    const approvedPrivate = reason === 'reaches a local or private network address';
    return this.executePlugin(name, approvedPrivate ? { ...cleanInput, allowPrivateNetwork: true } : cleanInput);
  }

  /**
   * Single entry point for goals. A session runs one goal at a time: concurrent runs would share the
   * abort controller and approval map, so extra goals wait in `queue` as visible "queued" tasks.
   */
  submitGoal(goal: string, model?: string, routeTelemetry?: Record<string, unknown>, agentProfile?: string): { queued: boolean; position: number; task_id?: string } {
    if (this.busy) {
      const task = this.addTask({ description: goal, status: 'queued' });
      this.queue.push({ goal, model, task, routeTelemetry, agentProfile });
      this.broadcast({ type: 'queued', data: { task_id: task.id, goal, position: this.queue.length } });
      return { queued: true, position: this.queue.length, task_id: task.id };
    }
    void this.drain({ goal, model, routeTelemetry, agentProfile });
    return { queued: false, position: 0 };
  }

  private async drain(first: { goal: string; model?: string; task?: Task; routeTelemetry?: Record<string, unknown>; agentProfile?: string }): Promise<void> {
    this.busy = true;
    let next: { goal: string; model?: string; task?: Task; routeTelemetry?: Record<string, unknown>; agentProfile?: string } | undefined = first;
    try {
      while (next) {
        // A common live question on a local model runs as a recipe (the code makes the lookup, the model words the answer).
        const recipe = next.model && !isInceptionModel(next.model) ? matchRecipe(next.goal) : null;
        if (recipe && next.model && recipeAvailable(recipe, getKnownRepo())) {
          this.config.model = next.model;
          this.route = recipeRoute(next.model, recipe.id, recipe.label);
          this.config.provider = 'ollama';
          this.broadcast({ type: 'status', data: 'running' });
          const result = await this.runRecipeGoal(next.goal, recipe, next.task);
          this.broadcast({ type: 'result', data: { ...result, route: this.route ?? undefined } });
          this.route = null;
          next = this.queue.shift();
          continue;
        }
        // A local chat has no tools: any other goal that needs tools or live state goes to the worker agent, or fails plainly. It is never answered from the model's head.
        const escalation = next.model && !isInceptionModel(next.model) ? this.escalateLocalGoal(next.goal, next.model) : null;
        if (escalation?.error) {
          if (next.task) this.updateTask(next.task.id, { status: 'failed', error: escalation.error });
          this.broadcast({ type: 'result', data: { success: false, error: escalation.error, route: refusedRoute(next.model!, escalation.error) } });
          next = this.queue.shift();
          continue;
        }
        const requested = next.model;
        if (escalation?.model) next = { ...next, model: escalation.model };
        if (next.model) {
          this.config.model = next.model;
          this.config.provider = isInceptionModel(next.model) ? 'inception' : 'ollama';
        }
        this.route = escalation?.model && requested ? escalatedRoute(requested, escalation.model, escalation.why ?? 'it needs tools or live data')
          : isInceptionModel(this.config.model) ? agentRoute(this.config.model) : localChatRoute(this.config.model);
        this.broadcast({ type: 'status', data: 'running' });
        const result = await this.runGoal(next.goal, next.task, next.routeTelemetry, next.agentProfile);
        this.broadcast({ type: 'result', data: { ...result, route: this.route ?? undefined } });
        this.route = null;
        next = this.queue.shift();
      }
    } finally {
      this.busy = false;
    }
  }

  /**
   * A goal picked for a local model that needs tools or live data (a repo, files, the web, today's date...). With a worker agent configured it is
   * sent there and the thought line says why; without one it fails with an explanation instead of a confident made-up answer. null = stay local.
   */
  private escalateLocalGoal(goal: string, localModel: string): { model?: string; error?: string; why?: string } | null {
    const why = needsToolsOrLiveData(goal);
    if (!why) return null;
    if (!inceptionConfigured()) {
      return { error: `This goal needs tools or live data (${why}), which ${localModel} cannot use, and no worker agent is configured. Set INCEPTION_API_KEY to run it with ${INCEPTION_MODELS[0]}.` };
    }
    const model = INCEPTION_MODELS[0];
    this.addThought({ type: 'routing', content: `Routed to ${model} instead of ${localModel}: ${why}. A local chat has no tools and cannot check live state.`, status: 'info' });
    return { model, why };
  }

  /**
   * A local-model goal that matches a recipe: the tool runs in code through the same governed path as the worker agent (approval, confinement,
   * audit), the local model words a sentence from the result, and the sentence is shown only if everything it states is in the data. $0; the
   * answer always includes the data itself so it can be checked.
   */
  private async runRecipeGoal(goal: string, recipe: RecipeMatch, queuedTask?: Task): Promise<PluginResult> {
    const model = this.config.model;
    this.status = 'running';
    this.abort = new AbortController();
    const task = this.beginTask(goal, queuedTask);
    const record = this.newRun(goal, task.id);
    this.addThought({ type: 'goal', content: `Local recipe "${recipe.label}" (${model}): the lookup runs in code, ${model} only words the answer. ${goal}`, status: 'info', run_id: record.id });
    this.broadcast({ type: 'run_update', data: record });
    const fail = (error: string): PluginResult => {
      runStore.finish(record, { status: 'failed', error, failure_kind: classifyFailure(error, false) });
      this.updateTask(task.id, { status: 'failed', error });
      this.status = 'idle';
      return { success: false, error, run_id: record.id };
    };
    try {
      const hooks = this.agentHooks(record, this.abort.signal);
      // The GitHub recipes use the one shared live_lookup tool (normalized evidence); the file recipes keep their own tools.
      const lookup = isGithubRecipe(recipe);
      const gov = lookup
        ? await runGovernedTool('live_lookup', { recipe: recipe.id }, hooks, newRunContext(), 1)
        : await runGovernedTool(recipe.tool, recipeToolArgs(recipe, getKnownRepo(), process.env.KUDBEE_GITHUB_API), hooks, newRunContext(), 1);
      if (gov.output.ok !== true) return fail(String(gov.output.error ?? 'the lookup failed'));
      const evidence = lookup ? ((gov.output as { evidence?: LookupEvidence }).evidence ?? null) : null;
      const built = evidence ? { facts: renderFacts(evidence) } : buildFacts(recipe, gov.output, getKnownRepo());
      if ('error' in built) return fail(built.error);
      const rule = sentenceRule(recipe, built.facts);
      let reply = '';
      let modelError = '';
      const askedAt = Date.now();
      if (!rule.skipModel) {
        await streamOllama(model, [{ role: 'user', content: buildPrompt(goal, built.facts, recipe) }], (token) => { reply += token; }, (done) => { if (done.error) modelError = done.error; });
      }
      let grounding: GroundingResult | null = null;
      let checked: { ok: true; text: string } | { ok: false; why: string };
      if (rule.skipModel) checked = { ok: false, why: 'there was nothing to word' };
      else if (modelError) checked = { ok: false, why: `the model call failed (${modelError})` };
      else if (evidence) {
        grounding = validateGrounding(reply, [evidence]);
        checked = grounding.status === 'GROUNDED' ? { ok: true, text: reply.replace(/\s+/g, ' ').trim() } : { ok: false, why: grounding.unsupported.map((u) => `${u.kind} ${u.claim}`).join('; ') };
      } else checked = groundedAnswer(reply, built.facts, { cite: rule.cite === 'file' ? 'file' : undefined });
      this.addThought({
        type: 'reasoning',
        content: checked.ok
          ? `${model} wrote the sentence${rule.cite ? '; it names a listed item and every number and link in it is in the data.' : '; only the numbers and links in it can be checked.'}`
          : rule.skipModel ? 'Nothing to summarise: showing the data itself.' : grounding ? `GROUNDING FAILED: ${model}'s sentence was not used (${checked.why}). Showing the evidence itself.` : `${model}'s sentence was not used: ${checked.why}. Showing the data itself.`,
        status: checked.ok ? 'success' : 'info',
      });
      const sentence = checked.ok ? (rule.uncheckedLabel ? `Summary by ${model} (only numbers and links in it are checked):\n${checked.text}` : checked.text) : '';
      const final = grounding && !checked.ok ? presentAnswer(reply, [evidence!], grounding).display : sentence ? `${sentence}\n\n${built.facts}` : built.facts;
      if (grounding) record.grounding = { ...grounding, evidence_recipe: recipe.id };
      this.broadcast({ type: 'stream', data: final });
      runStore.addEvent(record, { kind: 'model', step: 2, latency_ms: Date.now() - askedAt, prompt_tokens: 0, completion_tokens: 0, cost_usd: 0, tool_calls: [], content: final.slice(0, 2000) });
      runStore.finish(record, { status: 'completed', result: final });
      this.updateTask(task.id, { status: 'completed', result: final });
      this.status = 'idle';
      return { success: true, result: final, streamed: true, recipe: recipe.id, grounded: checked.ok, ...(grounding ? { grounding } : {}), run_id: record.id, duration_ms: record.duration_ms, steps: 2, tool_calls: 1, tokens: 0, cost_usd: 0 };
    } catch (err) {
      if (this.abort?.signal.aborted) {
        runStore.finish(record, { status: 'stopped', error: 'Stopped by user' });
        this.updateTask(task.id, { status: 'failed', error: 'Stopped by user' });
        this.status = 'idle';
        return { success: false, error: 'Stopped by user', run_id: record.id };
      }
      return fail(errorMessage(err));
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
        // Only earlier plain-chat answers, as the assistant's own turns. Replaying raw tool/run records as JSON "user" messages confused small models.
        ...this.memory
          .filter((m) => m.type === 'response' && typeof (m as { content?: unknown }).content === 'string')
          .slice(-6)
          .map((m): ChatMessage => ({ role: 'assistant', content: String((m as { content?: unknown }).content).slice(0, 1500) })),
        {
          role: 'user',
          content: goal,
        },
      ];

      this.addThought({ type: 'reasoning', content: 'Planning execution...', status: 'thinking' });

      let fullResponse = '';
      let streamError: string | undefined;
      await streamOllama(
        this.config.model,
        messages,
        (token) => {
          fullResponse += token;
          this.broadcast({ type: 'stream', data: token });
        },
        (done) => {
          if (done.error) { streamError = done.error; return; }
          // The text was already streamed token by token and comes back in the result: do not print it again as a thought.
          this.addThought({ type: 'reasoning', content: `Answered by ${this.config.model} (local chat, no tools).`, status: 'complete' });
          this.memory.push({ timestamp: Date.now(), type: 'response', content: fullResponse });
        },
      );
      // A model that failed (missing, crashed, cut off) is a failed run, not a "completed" one with an empty or "[Error: ...]" answer.
      if (streamError) throw new Error(streamError);

      runStore.addEvent(record, {
        kind: 'model', step: 1, latency_ms: Date.now() - modelStartedAt, prompt_tokens: 0, completion_tokens: 0,
        cost_usd: 0, tool_calls: [], content: fullResponse.slice(0, 2000),
      });
      runStore.finish(record, { status: 'completed', result: fullResponse });
      this.updateTask(task.id, { status: 'completed', result: fullResponse });
      this.status = 'idle';
      return { success: true, result: fullResponse, streamed: true, run_id: record.id, duration_ms: record.duration_ms, steps: 1, tool_calls: 0, tokens: 0, cost_usd: 0 };
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
      route: this.route ?? undefined,
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

  /** The hooks every tool run gets: workspace confinement, approvals, budget, memory. The worker agent and the local recipes share them. */
  private agentHooks(record: RunRecord, signal: AbortSignal, profile?: (typeof AGENT_PROFILES)[string]): AgentHooks {
    return {
      workspace: sessionWorkspace(this.id),
      resolvePath: (relativePath) => {
        // The agent's file tools must not follow a symlink out (e.g. one inside a cloned repository).
        const destination = safeWorkspacePath(this.id, relativePath);
        assertRealInsideSync(sessionWorkspace(this.id), destination);
        return destination;
      },
      onThought: (thought) => this.addThought(thought),
      onEvent: (event) => {
        runStore.addEvent(record, event);
        this.broadcast({ type: 'run_update', data: { ...record, steps: undefined } });
      },
      onFilesChanged: () => this.broadcast({ type: 'files_changed' }),
      signal,
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
    };
  }

  async runAgentGoal(goal: string, queuedTask?: Task, routeTelemetry?: Record<string, any>, agentProfile?: string): Promise<PluginResult> {
    this.status = 'running';
    this.abort = new AbortController();
    // Snapshot so the Think Token bridge below only sees this run's own thoughts, not a prior
    // queued goal's (this.thoughts accumulates for the whole session).
    const thoughtsStart = this.thoughts.length;
    const profile = agentProfile ? AGENT_PROFILES[agentProfile] : undefined;
    if (agentProfile && !profile) throw new Error(`Unknown agent profile '${agentProfile}'`);
    const task = this.beginTask(goal, queuedTask);
    const record = this.newRun(goal, task.id);
    this.addThought({ type: 'goal', content: `${profile ? `${profile.name} agent` : 'Worker agent'} (${this.config.model}) starting: ${goal}`, status: 'info', run_id: record.id });
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
      // ADR 028/029: accepted Think Tokens relevant to this goal join the planner context, with their ids cited.
      // THINKBOX_TOKEN_RETRIEVAL=0|off disables retrieval for A/B proof runs.
      const retrievalOff = process.env.THINKBOX_TOKEN_RETRIEVAL === '0' || process.env.THINKBOX_TOKEN_RETRIEVAL === 'off';
      const retrievalStarted = Date.now();
      const semantic = retrievalOff ? {} : await goalEmbedding(goal);
      const thinkTokens = retrievalOff ? [] : tokenStore.retrieve(goal, 3, { knownTools: TOOLS.map((t) => t.function.name), goalVector: semantic.goalVector, embedModel: semantic.embedModel });
      if (!retrievalOff) {
        const ranker = semantic.goalVector ? `${process.env.THINKBOX_RETRIEVER && RANKERS.includes(process.env.THINKBOX_RETRIEVER as RankerName) ? process.env.THINKBOX_RETRIEVER : DEFAULT_RANKER} (${semantic.embedModel})` : `lexical (${semantic.why ?? 'no vectors'})`;
        this.addThought({ type: 'think_token', content: `Think Token ranking: ${ranker}, ${Date.now() - retrievalStarted} ms, ${thinkTokens.length} found`, status: 'info' });
      }
      if (retrievalOff) {
        this.addThought({ type: 'think_token', content: 'Think Token retrieval OFF (THINKBOX_TOKEN_RETRIEVAL)', status: 'info' });
      } else if (thinkTokens.length) {
        record.think_tokens = thinkTokens.map((t) => t.id);
        tokenStore.recordUse(record.think_tokens, record.id, `agent:${record.id.slice(0, 8)}`);
        for (const before of thinkTokens) {
          const after = tokenStore.get(before.id);
          if (after) this.broadcast({ type: 'think_token_used', data: tokenEvent(after, record.id, after.score - before.score) });
        }
        this.addThought({ type: 'think_token', content: `Using ${thinkTokens.length} Think Token${thinkTokens.length === 1 ? '' : 's'}: ${thinkTokens.map((t) => `tt:${t.id}`).join(', ')}`, status: 'info' });
      }
      const liveFlags = await liveStateFlags([...recalled.hits.map((h) => ({ key: h.item.id, text: `${h.item.title} ${h.item.content}` })), ...thinkTokens.map((t) => ({ key: t.id, text: `${t.title} ${t.content}` }))]);
      const plannerContext = [repoContextLine(getKnownRepo()), MemoryStore.formatForPrompt(recalled.hits, Date.now(), liveFlags), formatTokensForPrompt(thinkTokens, Date.now(), liveFlags)].filter(Boolean).join('\n\n');
      const run = await runToolAgent(goal, this.config.model, this.config.maxIterations, this.config.temperature, this.history, this.agentHooks(record, this.abort.signal, profile), plannerContext);
      const status = run.success ? 'completed' : run.stopped ? 'stopped' : 'failed';
      runStore.finish(record, { status, result: run.result, error: run.error, failure_kind: classifyFailure(run.error, Boolean(run.stopped)), ...(run.evidence_conflicts ? { evidence_conflicts: run.evidence_conflicts } : {}) });
      await this.recordEpisode(record);
      if (!run.stopped) await this.saveThinkTokens(record, run.success);

      // Think Token bridge (#288): only a successful run can mint a token; a failed or stopped
      // run still has its session recorded (for later analysis) but produces no token.
      try {
        const learning = learningIntegration.recordGoalExecution(this.id, goal, run.success, {
          thoughts: this.thoughts.slice(thoughtsStart),
          duration: record.duration_ms ?? 0,
        });
        if (learning.tokensAffected > 0) {
          this.addThought({ type: 'memory', content: `Recorded ${learning.tokensAffected} learned pattern${learning.tokensAffected === 1 ? '' : 's'} in the legacy #288 store (separate from the Think Tokens above)`, status: 'success' });
        }
      } catch (err) {
        // Learning capture must never fail the run it's capturing.
        this.addThought({ type: 'memory', content: `Could not record learned patterns: ${errorMessage(err)}`, status: 'error' });
      }

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
            tokens: record.prompt_tokens + record.completion_tokens,
            cost_usd: record.cost_usd,
            duration_ms: record.duration_ms,
            tool_calls: record.tool_calls,
            approvals_approved: record.approvals.approved,
            approvals_denied: record.approvals.denied,
            // Feature 5: Token telemetry
            model_selected: record.routeTelemetry?.modelSelected ?? this.config.model,
            route_reason: record.routeTelemetry?.routeReason ?? 'auto',
            estimated_tokens_if_full_model: record.routeTelemetry?.estimatedTokensIfFullModel ?? (record.prompt_tokens + record.completion_tokens),
            estimated_tokens_actual: record.routeTelemetry?.estimatedTokensActual ?? (record.prompt_tokens + record.completion_tokens),
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
        ...(run.evidence_conflicts ? { evidence_conflicts: run.evidence_conflicts } : {}),
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

  /**
   * Run an APPROVED convoy with the real workers (convoy-runner.ts). The tool approvals of each worker go to THIS session's human, exactly like any
   * other run; an approved convoy never bypasses the runtime gates.
   */
  async runConvoy(id: string): Promise<void> {
    const convoy = convoyStore.get(id);
    const first = convoy?.plan.workers[0];
    if (first?.model && first.kind === 'specialist') { this.config.model = first.model; this.config.provider = isInceptionModel(first.model) ? 'inception' : 'ollama'; }
    // One abort controller per convoy, so an operator can stop exactly this convoy (convoy_stop).
    const stopper = new AbortController();
    convoyAborts.set(id, stopper);
    this.abort = stopper;
    const deps: RunnerDeps = {
      store: convoyStore, runStore, chat: { chatOnce, modelCapabilities }, repo: getKnownRepo(),
      isLocalModel: (model) => !isInceptionModel(model),
      newChildRun: (goal, runId, model, convoyId, workerId) => {
        const record = this.newRun(goal, runId);
        record.model = model;
        record.provider = isInceptionModel(model) ? 'inception' : 'ollama';
        record.jobId = convoyId;
        record.specialistId = workerId;
        return record;
      },
      hooksFor: (record, signal, allowedTools) => ({ ...this.agentHooks(record, signal), allowedTools }),
      runAgent: (goal, model, hooks) => runToolAgent(goal, model, this.config.maxIterations, this.config.temperature, [], hooks, repoContextLine(getKnownRepo())),
      runSpecialists: (goal, convoyId, specialists) => this.runSpecialistJob(goal, undefined, {}, { jobId: convoyId, specialists }),
      broadcast: (message) => this.broadcast(message as Parameters<AgentSession['broadcast']>[0]),
      signal: stopper.signal,
      // LEARN mode: the existing Think Token pipeline with NO model, so it can only write deterministic candidates (never auto-accepted, no model spend).
      learn: async (run) => {
        const actor = `convoy:${id.slice(0, 8)}`;
        tokenStore.recordOutcome(run.id, true, actor);
        const result = await processFinishedRun({ store: tokenStore, models: { mercury: null, local: null }, knownTools: TOOLS.map((t) => t.function.name) },
          { id: run.id, goal: run.goal, success: true, steps: run.steps, files: run.files, result: run.result }, actor);
        const out: Array<{ id: string; kind: string; status: string; title: string; duplicate?: boolean }> = [];
        for (const t of result.tokens) {
          const row = tokenStore.get(t.id);
          if (!row) continue;
          out.push({ id: row.id, kind: row.kind, status: row.status, title: row.title, ...(t.duplicate ? { duplicate: true } : {}) });
          if (!t.duplicate) this.broadcast({ type: 'think_token_learned', data: tokenEvent(row, run.id, 0) });
        }
        return out;
      },
    };
    try { await executeConvoy(deps, id); } finally { this.abort = null; convoyAborts.delete(id); }
  }

  async runSpecialistJob(intent: string, opportunity?: string, jobContext: Record<string, unknown> = {}, options: { jobId?: string; specialists?: string[] } = {}): Promise<Record<string, unknown>> {
    const jobId = options.jobId ?? randomUUID();
    const startedAt = Date.now();
    // A convoy runs EXACTLY the specialists its approved plan named (the Director's text match must not add or drop any); a plain job still selects from the text.
    const planned = options.specialists?.filter((id) => id in SPECIALISTS);
    const selection = planned?.length
      ? { selected: [...new Set(planned)].sort(), rationale: Object.fromEntries(planned.map((id) => [id, 'named by the approved convoy plan'])), blocked: false }
      : selectSpecialists(intent, opportunity);
    const eventLog: Array<Record<string, unknown>> = [];
    let sequence = 0;
    const recordEvent = (event: Record<string, unknown>): void => {
      const entry = { sequence: ++sequence, timestamp: Date.now(), jobId, ...event };
      eventLog.push(entry);
      this.broadcast({ type: 'specialist_event', data: entry });
    };

    this.addThought({ type: 'goal', content: `Specialist job ${jobId}: ${intent}`, status: 'info', jobId, run_id: jobId });
    if (selection.blocked) {
      const blocked = { jobId, intent, status: 'BLOCKED', selection, specialistsSelected: [], specialistsExecuted: [], events: eventLog };
      this.broadcast({ type: 'specialist_result', data: blocked });
      return blocked;
    }

    const executionContracts = selection.selected.map((id) => SPECIALISTS[id]).filter((contract) => contract.modelRequirements !== 'none');
    const handledByOrchestrator = selection.selected.filter((id) => SPECIALISTS[id].modelRequirements === 'none');
    const allocations = executionContracts.length ? allocateSpecialistJobs({
      jobId,
      intent,
      specialists: executionContracts,
      jobContext,
    }) : [];
    const compositionCheck = validateComposition(Object.fromEntries(allocations.map((item) => [item.specialistId, item.thinkBoxId])));
    if (!compositionCheck.ok) {
      const blocked = { jobId, intent, status: 'BLOCKED', selection, compositionCheck, specialistsSelected: selection.selected, specialistsExecuted: [], events: eventLog };
      this.broadcast({ type: 'specialist_result', data: blocked });
      return blocked;
    }

    const boxIds = allocations.map((item) => item.thinkBoxId);
    this.addThought({
      type: 'specialist_wave_started',
      content: `Allocated ${allocations.length} independent specialist workspace(s)`,
      status: 'info',
      jobId,
      run_id: jobId,
      specialistIds: allocations.map((item) => item.specialistId),
      thinkBoxIds: boxIds,
    });
    recordEvent({ phase: 'allocation', selection, allocations: allocations.map(({ specialistId, thinkBoxId, input }) => ({ specialistId, thinkBoxId, input })) });

    const runtimeExecutor = createRunToolAgentExecutor({
      model: this.config.model,
      maxIterations: this.config.maxIterations,
      temperature: this.config.temperature,
      createHooks: (allocation, runId) => {
        const worker = new AgentSession(allocation.thinkBoxId, { ...this.config });
        fs.mkdirSync(sessionWorkspace(allocation.thinkBoxId), { recursive: true });
        const record = worker.newRun(`${allocation.contract.name}: ${intent}`, runId);
        record.jobId = jobId;
        record.specialistId = allocation.specialistId;
        record.thinkBoxId = allocation.thinkBoxId;
        const abort = new AbortController();
        const abortKey = `${jobId}:${allocation.thinkBoxId}`;
        this.specialistAborts.set(abortKey, abort);
        recordEvent({ phase: 'run_started', runId, specialistId: allocation.specialistId, thinkBoxId: allocation.thinkBoxId });
        return {
          workspace: sessionWorkspace(allocation.thinkBoxId),
          resolvePath: (relativePath: string) => {
            const destination = safeWorkspacePath(allocation.thinkBoxId, relativePath);
            assertRealInsideSync(sessionWorkspace(allocation.thinkBoxId), destination);
            return destination;
          },
          onThought: (thought: Record<string, unknown>) => {
            const attributed = { ...thought, jobId, run_id: runId, specialistId: allocation.specialistId, thinkBoxId: allocation.thinkBoxId };
            worker.addThought(attributed);
            this.addThought(attributed);
            recordEvent({ phase: 'thought', runId, specialistId: allocation.specialistId, thinkBoxId: allocation.thinkBoxId, thought: attributed });
          },
          onEvent: (event: import('./agent.ts').AgentEvent) => {
            runStore.addEvent(record, event);
            recordEvent({ phase: 'run_event', runId, specialistId: allocation.specialistId, thinkBoxId: allocation.thinkBoxId, event });
          },
          onFilesChanged: () => this.broadcast({ type: 'files_changed', data: { sessionId: allocation.thinkBoxId, jobId, specialistId: allocation.specialistId } }),
          signal: abort.signal,
          checkBudget: () => dailyBudgetUsd > 0 && runStore.costToday() >= dailyBudgetUsd
            ? `Daily budget of $${dailyBudgetUsd < 0.01 ? dailyBudgetUsd.toFixed(4) : dailyBudgetUsd.toFixed(2)} reached (KUDBEE_DAILY_BUDGET_USD)`
            : null,
          approvedDomains: worker.approvedDomains,
          requestApproval: (tool: string, args: Record<string, unknown>, reason: string) => this.requestApproval(runId, tool, { ...args, specialistId: allocation.specialistId, thinkBoxId: allocation.thinkBoxId }, reason),
          remember: async (title: string, content: string, tags: string[]) => {
            const item = await memoryStore.write('org', { title, content, tags, source: `specialist:${allocation.specialistId}:run:${runId.slice(0, 8)}` });
            this.broadcast({ type: 'memory_changed', data: { id: item.id } });
            return { id: item.id, layer: item.layer, path: item.path };
          },
          recall: async (query: string, limit: number) => {
            const { hits, backend } = await memoryStore.search(query, { topK: limit });
            return { backend, results: hits.map(({ item, score }) => ({ id: item.id, layer: item.layer, title: item.title, score, content: item.content.slice(0, 800) })) };
          },
          rssFeed: async (url: string, limit: number) => {
            const rss = plugins.get('rss_feed');
            if (!rss) throw new Error('rss_feed plugin missing');
            const result = await rss.execute({ url, limit });
            if (!result.success) throw new Error(String(result.error));
            return result as Record<string, unknown>;
          },
        };
      },
    });

    const wave = await executeSpecialistPlan(allocations, async (allocation) => {
      const result = await runtimeExecutor(allocation);
      const record = runStore.get(result.runId);
      if (record) {
        runStore.finish(record, {
          status: result.success ? 'completed' : 'failed',
          result: result.output,
          error: result.failure,
          failure_kind: classifyFailure(result.failure, false),
        });
      }
      this.specialistAborts.delete(`${jobId}:${allocation.thinkBoxId}`);
      return result;
    }, {
      onEvent: (event) => {
        recordEvent({ phase: 'specialist_event', event });
        this.addThought({
          type: `specialist_${event.type}`,
          content: `${event.specialistId} ${event.type}`,
          status: event.type === 'failed' ? 'error' : event.type === 'completed' ? 'success' : 'info',
          jobId,
          run_id: event.execution?.runId ?? jobId,
          specialistId: event.specialistId,
          thinkBoxId: event.thinkBoxId,
          execution: event.execution,
        });
      },
      prepareWave: async (waveAllocations, completed) => {
        for (const allocation of waveAllocations) {
          const wantsArtifact = allocation.contract.allowedInputs.includes('artifact_path')
            || allocation.contract.allowedInputs.includes('claims_with_evidence');
          if (!wantsArtifact) continue;
          const write = completed.flatMap((execution) => execution.events)
            .find((event) => event.kind === 'tool' && event.ok && event.name === 'write_file' && typeof event.args.path === 'string');
          if (!write || write.kind !== 'tool') continue;
          const artifactPath = String(write.args.path);
          const sourceExecution = completed.find((execution) => execution.events.includes(write));
          if (!sourceExecution || sourceExecution.thinkBoxId === allocation.thinkBoxId) continue;
          const sourceRoot = sessionWorkspace(sourceExecution.thinkBoxId);
          const targetRoot = sessionWorkspace(allocation.thinkBoxId);
          fs.mkdirSync(targetRoot, { recursive: true });
          const sourcePath = await confinedWorkspacePath(sourceExecution.thinkBoxId, artifactPath);
          const targetPath = await confinedWorkspacePath(allocation.thinkBoxId, artifactPath);
          const content = await readConfined(sourceRoot, sourcePath);
          await writeConfined(targetRoot, targetPath, content, { mkdirs: true });
          recordEvent({ phase: 'artifact_handoff', fromThinkBoxId: sourceExecution.thinkBoxId, toThinkBoxId: allocation.thinkBoxId, specialistId: allocation.specialistId, artifactPath });
        }
      },
    });

    const evidence = evidenceFromSpecialistExecutions(wave.executions).filter((item) => item.specialistId !== 'validator');
    const validation = validateSpecialistEvidence(evidence, wave.executions);
    const resourceUsage = wave.executions.reduce((total, execution) => ({
      tokens: total.tokens + (execution.resourceUsage?.tokens ?? 0),
      costUsd: total.costUsd + (execution.resourceUsage?.costUsd ?? 0),
      durationMs: total.durationMs + (execution.resourceUsage?.durationMs ?? 0),
    }), { tokens: 0, costUsd: 0, durationMs: 0 });
    const completion = completeSpecialistJob({ jobId, claim: intent, executions: wave.executions, resourceUsage });
    recordEvent({ phase: 'validation', validation });
    this.addThought({ type: 'specialist_validation', content: validation.reason, status: validation.valid ? 'success' : 'error', jobId, run_id: jobId });
    recordEvent({ phase: completion.proof.ok ? 'proof_accepted' : 'proof_refused', proof: completion.proof });
    this.addThought({ type: completion.proof.ok ? 'proof_accepted' : 'proof_refused', content: completion.proof.ok ? 'Proof Keeper accepted validated specialist evidence' : completion.proof.reason, status: completion.proof.ok ? 'success' : 'error', jobId, run_id: jobId });

    let createdTokens: Array<{ id: string; type: string; content: string; confidence: number }> = [];
    try {
      if (completion.proof.ok) {
        const candidates: Array<{ id: string; type: string; content: string; confidence: number }> = [];
        for (const execution of wave.executions.filter((item) => item.status === 'completed')) {
          const previousTokenIds = new Set(thinkTokenPropagator.getRelevantTokensForGoal(intent, 100).map((token) => token.id));
          learningIntegration.recordGoalExecution(execution.thinkBoxId, intent, true, {
            thoughts: execution.thoughts,
            duration: execution.resourceUsage?.durationMs ?? 0,
            specialistId: execution.specialistId,
            jobId,
          });
          const persistedIds = new Set(learningStore.getTopPatterns(500).map((pattern) => pattern.id));
          candidates.push(...thinkTokenPropagator.getRelevantTokensForGoal(intent, 100)
            .filter((token) => !previousTokenIds.has(token.id) && persistedIds.has(token.id))
            .map((token) => ({ id: token.id, type: token.content.type, content: token.content.text, confidence: token.confidence })));
        }
        createdTokens = [...new Map(candidates.map((token) => [token.id, token])).values()];
        for (const token of createdTokens) {
          recordEvent({ phase: 'think_token', token });
          this.addThought({ type: 'think_token', content: token.content, status: 'success', jobId, run_id: jobId, tokenId: token.id, tokenType: token.type, tokenConfidence: token.confidence, specialistIds: selection.selected });
        }
      } else {
        for (const execution of wave.executions) {
          learningStore.storeSessionLearning({
            sessionId: execution.thinkBoxId,
            goal: intent,
            outcome: execution.status === 'failed' ? 'failure' : 'partial',
            duration: execution.resourceUsage?.durationMs ?? 0,
            thoughts: execution.thoughts,
            patterns: [],
            metadata: { jobId, specialistId: execution.specialistId, status: execution.status },
          });
        }
      }
    } catch (err) {
      this.addThought({ type: 'think_token', content: `Could not capture specialist Think Tokens: ${errorMessage(err)}`, status: 'error', jobId, run_id: jobId });
    }

    const replayed = replaySpecialistEvents(wave.events);
    const replayCompletion = completeSpecialistJob({ jobId, claim: intent, executions: replayed, resourceUsage });
    const cubeStateFor = (executions: typeof wave.executions, proofAccepted: boolean) => {
      let state = createInitialCubeState();
      state = applyThinkCubeEvent(state, { stage: 'intent', payload: { tokenId: jobId } });
      state = applyThinkCubeEvent(state, {
        stage: 'swarm',
        payload: { boxIds: executions.map((execution) => execution.thinkBoxId), specialistIds: executions.map((execution) => execution.specialistId) },
      });
      const toolEvents = executions.flatMap((execution) => execution.events.filter((event) => event.kind === 'tool'));
      const failedEvidenceEvents = toolEvents.filter((event) => event.kind === 'tool' && !event.ok).length
        + executions.filter((execution) => execution.status === 'failed').length;
      if (toolEvents.length) state = applyThinkCubeEvent(state, { stage: 'execution', payload: { step: toolEvents.length } });
      const evidenceCount = evidenceFromSpecialistExecutions(executions).filter((item) => item.specialistId !== 'validator').length;
      if (evidenceCount) state = applyThinkCubeEvent(state, { stage: 'evidence', payload: { evidenceCount } });
      if (failedEvidenceEvents) state = applyThinkCubeEvent(state, { stage: 'challenge', payload: { vulnerabilities: failedEvidenceEvents } });
      state = applyThinkCubeEvent(state, { stage: 'jury', payload: { passed: proofAccepted } });
      if (proofAccepted) state = applyThinkCubeEvent(state, { stage: 'proof' });
      if (createdTokens.length) state = applyThinkCubeEvent(state, { stage: 'think_token', payload: { tokenId: createdTokens[0].id } });
      return state;
    };
    const cubeFinalState = cubeStateFor(wave.executions, completion.proof.ok);
    const replayCubeState = cubeStateFor(replayed, replayCompletion.proof.ok);
    recordEvent({ phase: 'cube_final_state', state: cubeFinalState });
    const fullReplay = replaySpecialistJobEvents(eventLog as import('./specialist-executor.ts').SpecialistJobEvent[]);
    const replayResult = {
      mode: 'complete-event-log reduction; no model re-execution',
      sameEvents: JSON.stringify(fullReplay.events) === JSON.stringify(eventLog),
      sameSpecialistStates: JSON.stringify(fullReplay.executions) === JSON.stringify(wave.executions),
      sameEvidenceRelationships: JSON.stringify(fullReplay.evidence.filter((item) => item.specialistId !== 'validator')) === JSON.stringify(evidence),
      sameProofResult: JSON.stringify(fullReplay.proof) === JSON.stringify(completion.proof),
      sameCubeState: JSON.stringify(fullReplay.cubeFinalState) === JSON.stringify(cubeFinalState)
        && JSON.stringify(replayCubeState) === JSON.stringify(cubeFinalState),
    };
    const artifact = {
      jobId,
      intent,
      status: wave.executions.every((execution) => execution.status === 'completed') && completion.proof.ok ? 'COMPLETED' : 'FAILED',
      specialistsSelected: selection.selected,
      specialistsHandledByOrchestrator: handledByOrchestrator,
      selectionRationale: selection.rationale,
      specialistsExecuted: wave.executions,
      thinkBoxIds: boxIds,
      executionOrder: wave.events.filter((event) => event.type === 'started').map((event) => ({ specialistId: event.specialistId, thinkBoxId: event.thinkBoxId, sequence: event.sequence })),
      events: eventLog,
      evidence,
      failures: wave.executions.filter((execution) => execution.status === 'failed').map((execution) => ({ specialistId: execution.specialistId, thinkBoxId: execution.thinkBoxId, runId: execution.runId, failure: execution.failure })),
      validation,
      proof: completion.proof,
      thinkToken: createdTokens,
      cubeFinalState,
      resourceUsage,
      replayResult,
      classification: {
        multiSpecialistExecution: 'CODE COMPLETE / TEST VERIFIED',
        multiBoxConcurrentSwarm: 'UNPROVEN: independent in-process workspaces, not separate processes or remote compute boxes',
        liveVerified: false,
        productionReady: false,
      },
      durationMs: Date.now() - startedAt,
    };
    const artifactPath = path.join(dataDir, 'specialist-jobs', `${jobId}.json`);
    await fs.promises.mkdir(path.dirname(artifactPath), { recursive: true });
    await fs.promises.writeFile(artifactPath, `${JSON.stringify(artifact, null, 2)}\n`, { mode: 0o600 });
    const result = { ...artifact, artifactPath };
    this.broadcast({ type: 'specialist_result', data: result });
    return result;
  }

  /**
   * ADR 029 P1 save path: fold the outcome into tokens this run used, then run the lifecycle pipeline (extract with Mercury 2 or the
   * local model, write a TT- candidate, score, challenge, accept or reject). Template-only tokens stay candidates.
   */
  private async saveThinkTokens(record: RunRecord, success: boolean): Promise<void> {
    try {
      const actor = `agent:${record.id.slice(0, 8)}`;
      tokenStore.recordOutcome(record.id, success, actor);
      const deps = { store: tokenStore, models: createTokenModels(), knownTools: TOOLS.map((t) => t.function.name) };
      const result = await processFinishedRun(
        deps,
        { id: record.id, goal: record.goal, success, steps: record.steps, files: record.files, result: record.result, evidence_conflicts: record.evidence_conflicts },
        actor,
      );
      // A token whose challenge could not run earlier (model down) is retried now that a run has finished; at most 3 per run.
      const earlier = await rechallengeScoredTokens(deps, (id) => { const r = runStore.get(id); return r ? { id: r.id, goal: r.goal, success: r.status === 'completed', steps: r.steps, files: r.files, result: r.result } : undefined; }, actor, 3);
      for (const r of earlier) {
        const row = r.result === 'left_scored' ? null : tokenStore.get(r.id);
        if (row) this.broadcast({ type: 'think_token_learned', data: tokenEvent(row, row.source_run_id, 0) });
      }
      const fresh = result.tokens.filter((t) => !t.duplicate);
      for (const token of fresh) {
        const row = tokenStore.get(token.id);
        if (!row) continue;
        this.addThought({
          type: 'think_token',
          content: row.content,
          status: 'success',
          run_id: record.id,
          tokenId: row.id,
          tokenType: row.kind,
          title: row.title,
          tokenStatus: row.status,
          tokenScore: row.score,
          extractor: row.extractor,
          model: row.extract_model ?? undefined,
          receiptId: token.receipt_id ?? undefined,
        });
        this.broadcast({ type: 'think_token_learned', data: tokenEvent(row, record.id, 0) });
      }
      if (fresh.length) {
        const tally = (status: string) => fresh.filter((t) => t.status === status).length;
        this.addThought({
          type: 'think_token',
          content: `Saved ${fresh.length} Think Token${fresh.length === 1 ? '' : 's'} from this run: ${fresh.map((t) => t.id).join(', ')} (accepted ${tally('accepted')}, rejected ${tally('rejected')}, other ${fresh.length - tally('accepted') - tally('rejected')})`,
          status: 'success',
          run_id: record.id,
        });
        this.broadcast({ type: 'think_tokens_changed', data: { count: fresh.length } });
      } else if (result.dropped.length) {
        this.addThought({ type: 'think_token', content: `No Think Token saved: ${result.dropped.length} lesson${result.dropped.length === 1 ? '' : 's'} failed grounding/specificity checks`, status: 'info', run_id: record.id });
      } else if (success && !result.tokens.length) {
        this.addThought({ type: 'think_token', content: 'No new Think Token from this run: nothing new beyond the lessons already saved', status: 'info', run_id: record.id });
      } else if (success) {
        this.addThought({ type: 'think_token', content: `No new Think Token from this run: ${result.tokens.length} lesson${result.tokens.length === 1 ? '' : 's'} already saved (seen again)`, status: 'info', run_id: record.id });
      }
    } catch (err) {
      // Learning capture must never fail the run it is capturing.
      this.addThought({ type: 'think_token', content: `Could not save Think Tokens: ${errorMessage(err)}`, status: 'error', run_id: record.id });
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
    for (const controller of this.specialistAborts.values()) controller.abort();
    this.specialistAborts.clear();
    for (const id of [...this.pendingApprovals.keys()]) this.resolveApproval(id, false);
    this.status = 'idle';
    this.broadcast({ type: 'status', data: 'idle' });
  }
}

// ─── WebSocket handling ────────────────────────────────────────
wss.on('connection', async (ws: WebSocket, req: IncomingMessage) => {
  const sessionId = randomUUID();
  const session = new AgentSession(sessionId);
  session.ws = ws;
  if (cliUpgrades.has(req)) session.client = 'cli';
  sessions.set(sessionId, session);
  fs.promises.mkdir(sessionWorkspace(sessionId), { recursive: true }).catch((err) => console.error(`[session ${sessionId.slice(0, 8)}] could not create the workspace: ${describeError(err)}`));

  // The active profile's settings are the baseline for a session; a saved per-session patch wins.
  try {
    Object.assign(session.config, sanitizeConfigPatch(profileManager.active().settings));
  } catch (err) {
    console.warn(`[session ${sessionId.slice(0, 8)}] ignoring active profile settings: ${describeError(err)}`);
  }
  // Restore dashboard state from persistent storage
  const savedState = await persistence.restoreDashboardState(sessionId);
  if (savedState?.settings) {
    try {
      Object.assign(session.config, sanitizeConfigPatch(savedState.settings));
    } catch (err) {
      // Saved settings from before validation (or edited on disk) are ignored, not applied.
      console.warn(`[session ${sessionId.slice(0, 8)}] ignoring saved dashboard settings: ${describeError(err)}`);
    }
  }

  ws.send(
    JSON.stringify({
      type: 'init',
      data: {
        sessionId,
        config: session.config,
        profiles: profileManager.list(),
        activeProfile: profileManager.active(),
        models: await listModels(),
        plugins: getPlugins(),
        files: Array.from(session.files.entries()),
        tasks: session.tasks,
        // This session's own thoughts, or (a fresh session after a reload or restart) the profile's saved history.
        thoughts: session.thoughts.length ? session.thoughts : persistence.recentThoughts(profileManager.getActiveId(), 300),
        restoredState: savedState,
      },
    }),
  );

  ws.on('message', async (raw: RawData) => {
    try {
      // Defensive: Limit message size to prevent DoS; 1MB should be plenty for any legitimate message
      const rawStr = raw.toString();
      if (rawStr.length > 1_000_000) {
        ws.send(JSON.stringify({ type: 'error', data: 'Message too large (max 1MB)' }));
        return;
      }

      const msg = JSON.parse(rawStr) as WsMessage;
      if (!msg || typeof msg !== 'object' || !msg.type) {
        ws.send(JSON.stringify({ type: 'error', data: 'Invalid message format' }));
        return;
      }

      // Helper to safely truncate strings
      const safeString = (v: unknown, maxLen: number = 50000): string => {
        if (typeof v !== 'string') return '';
        return v.slice(0, maxLen);
      };

      switch (msg.type) {
        case 'subscribe_runs': {
          if (session.client === 'dashboard') mirrors.add(ws);
          break;
        }

        case 'run_goal': {
          const telemetry = msg.routeTelemetry && typeof msg.routeTelemetry === 'object' ? (msg.routeTelemetry as Record<string, unknown>) : undefined;
          const agentProfile = typeof msg.agent === 'string' && msg.agent in AGENT_PROFILES ? msg.agent : undefined;
          if (typeof msg.agent === 'string' && msg.agent && !agentProfile) {
            // Respond via the same 'result' contract client.run() already awaits —
            // a bare top-level 'error' message has no handler on the CLI side and
            // would leave `kudbee --agent <typo> "goal"` hanging forever.
            // Defensive: Escape agent name to prevent injection in error message
            const safeAgent = String(msg.agent).replace(/[<>"&]/g, '?');
            ws.send(JSON.stringify({ type: 'result', data: { success: false, error: `Unknown agent '${safeAgent}'. Available: ${Object.keys(AGENT_PROFILES).join(', ')}` } }));
            break;
          }
          // Defensive: Truncate goal to prevent memory issues
          session.submitGoal(safeString(msg.goal), typeof msg.model === 'string' && msg.model ? msg.model : undefined, telemetry, agentProfile);
          break;
        }

        // Emergency stop for ONE convoy: its workers stop at their next step and the convoy ends FAILED ("stopped by operator"), keeping the evidence so far.
        case 'convoy_stop': {
          const id = typeof msg.id === 'string' ? msg.id : '';
          const controller = convoyAborts.get(id);
          if (!controller) { ws.send(JSON.stringify({ type: 'convoy_error', data: { id, error: 'that convoy is not running' } })); break; }
          controller.abort();
          session.addThought({ type: 'routing', content: `Convoy ${id.slice(0, 8)} stopped by the operator.`, status: 'info', jobId: id });
          break;
        }

        case 'clear_thoughts': {
          const removed = persistence.clearThoughts(profileManager.getActiveId());
          session.thoughts.length = 0;
          ws.send(JSON.stringify({ type: 'thoughts_cleared', data: { removed } }));
          break;
        }

        // Approving AND running a convoy only happens here: this socket passed the origin/token check at upgrade, so it is a human operator's session.
        case 'convoy_approve': {
          const id = typeof msg.id === 'string' ? msg.id : '';
          try {
            const c = convoyStore.decide(id, 'approve', 'human', safeString(msg.note).slice(0, 300));
            session.broadcast({ type: 'convoy_update', data: summarizeConvoy(c) });
            void session.runConvoy(id).catch((err) => ws.send(JSON.stringify({ type: 'convoy_error', data: { id, error: errorMessage(err) } })));
          } catch (err) {
            ws.send(JSON.stringify({ type: 'convoy_error', data: { id, error: errorMessage(err), code: err instanceof ConvoyError ? err.code : undefined } }));
          }
          break;
        }

        case 'run_specialists': {
          const intentRaw = msg.intent ?? msg.goal ?? '';
          const intent = safeString(intentRaw).trim();
          const opportunity = safeString(msg.opportunity);
          const jobContext = msg.jobContext && typeof msg.jobContext === 'object' && !Array.isArray(msg.jobContext)
            ? msg.jobContext as Record<string, unknown>
            : {};
          if (!intent) {
            ws.send(JSON.stringify({ type: 'specialist_result', data: { status: 'BLOCKED', error: 'intent is required' } }));
            break;
          }
          void session.runSpecialistJob(intent, opportunity, jobContext).catch((err) => {
            ws.send(JSON.stringify({ type: 'specialist_result', data: { status: 'FAILED', error: errorMessage(err) } }));
          });
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
          try {
            const input = (msg.input && typeof msg.input === 'object' ? msg.input : {}) as PluginInput;
            const pluginName = safeString(msg.plugin, 200);
            if (!pluginName) {
              ws.send(JSON.stringify({ type: 'plugin_result', data: { plugin: msg.plugin, error: 'Plugin name required' } }));
              break;
            }
            const result = await session.executeOperatorPlugin(pluginName, input);
            ws.send(JSON.stringify({ type: 'plugin_result', data: { plugin: msg.plugin, result } }));
          } catch (err) {
            ws.send(JSON.stringify({ type: 'plugin_result', data: { plugin: msg.plugin, error: errorMessage(err) } }));
          }
          break;
        }

        case 'task_action': {
          try {
            const action = safeString(msg.action ?? '', 200);
            const payload = msg.payload && typeof msg.payload === 'object' ? msg.payload as Record<string, unknown> : {};
            if (!action) {
              ws.send(JSON.stringify({ type: 'task_action_result', data: { error: 'Action required' } }));
              break;
            }
            const result = session.executeTaskAction(action, payload);
            ws.send(JSON.stringify({ type: 'task_action_result', data: result }));
          } catch (err) {
            ws.send(JSON.stringify({ type: 'task_action_result', data: { error: errorMessage(err) } }));
          }
          break;
        }

        case 'git_action': {
          const result = await session.executeOperatorPlugin('git_repository', {
            action: String(msg.action ?? ''),
            ...(msg.payload && typeof msg.payload === 'object' ? msg.payload as Record<string, unknown> : {}),
          });
          ws.send(JSON.stringify({ type: 'git_action_result', data: result }));
          break;
        }

        case 'update_config': {
          let patch: Partial<AgentSessionConfig>;
          try {
            patch = sanitizeConfigPatch(msg.config);
          } catch (err) {
            ws.send(JSON.stringify({ type: 'config_error', data: { error: errorMessage(err) } }));
            break;
          }
          Object.assign(session.config, patch);
          // Save config to persistent storage (debounced)
          Promise.resolve(persistence.saveDashboardState({
            sessionId,
            settings: session.config,
            lastUpdate: Date.now(),
            createdAt: Date.now()
          })).catch((err) => console.error(`[session ${sessionId.slice(0, 8)}] could not save dashboard settings: ${describeError(err)}`));
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

        case 'think_tokens_list':
        case 'think_token_cube':
        case 'think_token_action': {
          const checked = validateTokenMessage(msg);
          if (!checked.ok) {
            ws.send(JSON.stringify({ type: 'think_token_error', data: { error: checked.error } }));
            break;
          }
          const req = checked.req;
          if (req.type === 'think_token_cube') {
            const cube = readTokenCube(tokenStore, req.id);
            ws.send(JSON.stringify(cube ? { type: 'think_token_cube', data: cube } : { type: 'think_token_error', data: { error: `No Think Token ${req.id}` } }));
            break;
          }
          if (req.type === 'think_tokens_list') {
            ws.send(JSON.stringify({ type: 'think_tokens', data: { tokens: readTokens(tokenStore, { query: req.query, status: req.status, limit: req.limit, run_id: req.run_id }), ledger: tokenStore.verifyLedger() } }));
            break;
          }
          // Every mutation needs the same human approval the agent loop uses; denial and timeout change nothing.
          const approved = await session.requestApproval(`think-token:${req.id}`, `think_token_${req.action}`, { id: req.id }, `Apply "${req.action}" to Think Token ${req.id}`);
          if (!approved) {
            ws.send(JSON.stringify({ type: 'think_token_result', data: { ok: false, id: req.id, action: req.action, error: 'Not approved' } }));
            break;
          }
          const actor = `operator:${sessionId.slice(0, 8)}`;
          const result = req.action === 'accept' ? tokenStore.setStatus(req.id, 'accepted', actor)
            : req.action === 'retire' ? tokenStore.setStatus(req.id, 'retired', actor)
            : tokenStore.feedback(req.id, req.action === 'thumb_up' ? 'up' : 'down', actor);
          ws.send(JSON.stringify({ type: 'think_token_result', data: { ok: result.ok, id: req.id, action: req.action, error: result.ok ? undefined : result.reason, receipt: result.receipt } }));
          break;
        }

        case 'list_models': {
          const models = await listModels();
          ws.send(JSON.stringify({ type: 'models', data: models }));
          break;
        }

        case 'list_mcp_skills': {
          try {
            const skills = await discoverMCPSkills();
            const byCategory = groupSkillsByCategory(skills);
            let output = '🔌 AVAILABLE MCP SKILLS\n\n';
            for (const [cat, items] of Object.entries(byCategory).sort()) {
              output += `${cat}\n`;
              for (const s of items) {
                output += `  ${s.name} — ${s.description}\n`;
                if (s.tags?.length) {
                  output += `    Tags: ${s.tags.join(', ')}\n`;
                }
              }
            }
            ws.send(JSON.stringify({ type: 'terminal_message', data: { role: 'system', content: output } }));
          } catch (err) {
            ws.send(JSON.stringify({ type: 'terminal_message', data: { role: 'error', content: `Failed to fetch MCP skills: ${errorMessage(err)}` } }));
          }
          break;
        }

        case 'search_mcp_skills': {
          try {
            const query = (msg.query as string | undefined) || '';
            const skills = await discoverMCPSkills();
            const matches = filterSkills(skills, query);
            if (matches.length === 0) {
              ws.send(JSON.stringify({ type: 'terminal_message', data: { role: 'system', content: 'No MCP skills found matching that search.' } }));
            } else if (matches.length === 1) {
              const s = matches[0];
              ws.send(JSON.stringify({ type: 'terminal_message', data: { role: 'system', content: `✓ Found: ${s.name}\n${s.description}\n${s.capabilities?.length ? `Capabilities: ${s.capabilities.join(', ')}` : ''}` } }));
            } else {
              let output = `Found ${matches.length} MCP skills:\n\n`;
              matches.forEach((m, i) => {
                output += `${i + 1}. ${m.name} — ${m.description}\n`;
              });
              ws.send(JSON.stringify({ type: 'terminal_message', data: { role: 'system', content: output } }));
            }
          } catch (err) {
            ws.send(JSON.stringify({ type: 'terminal_message', data: { role: 'error', content: `Failed to search MCP skills: ${errorMessage(err)}` } }));
          }
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
    try {
      mirrors.delete(ws);
      // Nobody is watching or able to approve any more, so stop spending tokens.
      try {
        session.stop();
      } catch (err) {
        console.error(`Error stopping session ${sessionId}:`, errorMessage(err));
      }
      if (sessions.has(sessionId)) {
        sessions.delete(sessionId);
      }
    } catch (err) {
      // Ensure close handler never crashes
      console.error('Error in WebSocket close handler:', errorMessage(err));
    }
  });

  // Defensive: Handle unexpected errors and socket errors
  ws.on('error', (err) => {
    console.error(`WebSocket error for session ${sessionId}:`, errorMessage(err));
  });
});

// ─── REST API ──────────────────────────────────────────────────
// ─── REST routes moved to routes/*.ts (explicit dependencies, no behaviour change) ───
registerDiagnosticsRoutes(app, { sessions, plugins, serverStartedAt, monitorAgent, port: PORT, ollamaBaseUrl, janusBaseUrl, janusEnabled, runStore, memoryStore, dailyBudgetUsd });
registerRunsRoutes(app, { runStore, persistence });
registerMemoryRoutes(app, { memoryStore, persistence, sessions });
registerProfileRoutes(app, { profileManager, runStore, sessions, activateProfile, profilesDir });

/** The measured average cost of a completed run on this model, or null: a plan never invents a number. */
function costOfModel(model: string | null, kindIn: 'lookup' | 'specialist' | 'repo' = 'lookup'): { usd: number | null; basis: string } {
  if (!model) return { usd: null, basis: 'no model' };
  if (!isInceptionModel(model)) return { usd: 0, basis: 'local model, no API cost' };
  // A lookup costs a fraction of a specialist job; averaging them together made estimates 10x off. Estimate from runs of the same kind of worker.
  const kind = kindIn === 'repo' ? 'lookup' : kindIn;
  const isLookup = (r: { specialistId?: string }): boolean => String(r.specialistId ?? '').startsWith('lookup') || String(r.specialistId ?? '').startsWith('escalation');
  const costs = runStore.list(500).filter((r) => r.model === model && r.status === 'completed' && r.cost_usd > 0 && Boolean(r.jobId) && isLookup(r) === (kind === 'lookup')).map((r) => r.cost_usd);
  return costs.length ? { usd: Math.round((costs.reduce((a, b) => a + b, 0) / costs.length) * 1e6) / 1e6, basis: `average of ${costs.length} measured ${model} ${kind} run(s)` } : { usd: null, basis: `no measured ${model} ${kind} runs yet` };
}

registerConvoyRoutes(app, {
  convoyStore,
  runStore,
  plan: (goal, model, budget, mode) => {
    const agentModel = inceptionConfigured() ? INCEPTION_MODELS[0]! : null;
    const result = planConvoy({
      goal, budget, mode, lookupModel: model || agentModel || resolveLocalModel(), agentModel, isLocalModel: (m) => !isInceptionModel(m),
      availableTools: TOOLS.map((t) => t.function.name), costOf: costOfModel, now: Date.now(),
    });
    if (!result.ok) return result;
    return { ok: true, convoy: convoyStore.create(result.plan.goal, result.plan, evaluatePolicy(result.plan)) };
  },
  isHuman: (req) => isAllowedOrigin(typeof req.headers.origin === 'string' ? req.headers.origin : undefined, PORT_NUM) || tokensMatch(LOCAL_TOKEN, String(req.headers[TOKEN_HEADER] ?? '')),
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
        const stat = await fs.promises.lstat(absolute); // never stat a symlink's (possibly outside) target
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
    const content = await readConfined(sessionWorkspace(req.params.id), filePath, 2 * 1024 * 1024);
    res.json({ path: String(req.query.path), content: content.toString('utf8') });
  } catch (err) {
    res.status(fileErrorStatus(err)).json({ error: errorMessage(err) });
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
    const image = await readConfined(sessionWorkspace(req.params.id), filePath);
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.type(path.extname(filePath));
    res.send(image);
  } catch (err) {
    res.status(fileErrorStatus(err)).json({ error: errorMessage(err) });
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
    await writeConfined(sessionWorkspace(session.id), destination, image.buffer, { mkdirs: true });
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
    await writeConfined(sessionWorkspace(session.id), destination, Buffer.from(result.image_base64, 'base64'), { mkdirs: true });
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
    await writeConfined(sessionWorkspace(session.id), destination, image.buffer, { mkdirs: true });
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
      await writeConfined(sessionWorkspace(req.params.id), destination, file.buffer, { mkdirs: true });
      uploaded.push({ path: path.relative(sessionWorkspace(req.params.id), destination).replaceAll(path.sep, '/'), size: file.size });
    }
    res.status(201).json({ uploaded });
  } catch (err) {
    res.status(fileErrorStatus(err)).json({ error: errorMessage(err) });
  }
});

app.delete('/api/sessions/:id/files', async (req: Request, res: Response) => {
  if (!sessions.has(req.params.id)) return res.status(404).json({ error: 'Session not found' });
  try {
    await unlinkConfined(sessionWorkspace(req.params.id), safeWorkspacePath(req.params.id, String(req.body.path || '')));
    res.json({ success: true });
  } catch (err) {
    res.status(fileErrorStatus(err)).json({ error: errorMessage(err) });
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

// Git repository integration (#289): public github.com clones under <workspaceRoot>/_git, file access confined there.
const gitRoot = path.join(workspaceRoot, '_git');
fs.mkdirSync(gitRoot, { recursive: true });
app.use('/api/git', createGitRouter(gitRoot));

// Governed remote execution (dashboard → backend → upcloud-ssh). See governed-bridge.ts.
const governedBridge = bridgeConfigFromEnv();
app.post('/api/governed/run', submitGovernedRun(governedBridge));
app.get('/api/governed/run/:engineId', getGovernedRun(governedBridge));

app.post('/api/sessions/:id/stop', (req: Request, res: Response) => {
  const session = sessions.get(req.params.id);
  if (!session) return res.status(404).json({ error: 'Session not found' });
  session.stop();
  res.json({ success: true });
});

// ─── Start server ──────────────────────────────────────────────
// SECURITY: Bind to localhost only, not all interfaces (§1.4.1 AGENTS.md). The dashboard is a local-only
// operator console with no user authentication, so a non-loopback bind is refused unless explicitly
// acknowledged. Dashboard authentication is a deferred requirement for any remote/shared deployment.
const LISTEN_ADDR = process.env.LISTEN_ADDR || '127.0.0.1';
if (!isLoopbackAddress(LISTEN_ADDR) && process.env.KUDBEE_ALLOW_NON_LOOPBACK !== '1') {
  console.error(`Refusing to listen on ${LISTEN_ADDR}: the dashboard has no user authentication and is local-only.`);
  console.error('Bind to 127.0.0.1 (default). Set KUDBEE_ALLOW_NON_LOOPBACK=1 only if you accept exposing an unauthenticated dashboard.');
  process.exit(1);
}
// The net under every handler: an unknown /api path answers JSON, a rejected or throwing handler answers JSON without a stack, and a stray
// rejection is logged instead of killing the server (see error-handling.ts).
app.use('/api', (_req: Request, res: Response) => { res.status(404).json({ error: 'not_found' }); });
app.use(jsonErrorHandler());
installProcessHandlers(process);

server.listen(PORT_NUM, LISTEN_ADDR, () => {
  console.log(`\n🚀 THINK BOX AI — Devin-like Interface`);
  console.log(`   Backend:  http://${LISTEN_ADDR}:${PORT}`);
  console.log(`   WebSocket: ws://${LISTEN_ADDR}:${PORT}`);
  console.log(`   Models:   Ollama ${ollamaBaseUrl}${inceptionConfigured() ? ' + Inception mercury-2 (worker agent)' : ''}`);
  console.log(`\n   Ready.\n`);
});

void files;

export function isLoopbackAddress(addr: string): boolean {
  const a = addr.trim().toLowerCase().replace(/^\[|\]$/g, '');
  return a === 'localhost' || a === '::1' || /^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(a);
}
