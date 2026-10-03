// kudbEE CLI — terminal client for kudbEE Agent OS (same WebSocket runtime as the dashboard).
//   kudbee                 interactive shell
//   kudbee "<goal>"        run one goal with the worker agent and exit
//   kudbee --yes "<goal>"  same, auto-approving gated tool calls (overwrites, new domains)
//   kudbee tokens list|show  read Think Tokens from the same think-tokens.db the dashboard uses (no server needed)
import { spawn } from 'node:child_process';
import readline from 'node:readline';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';
import MCPRegistry from './mcp-registry.ts';
import { isComplexGoal } from './goal-routing.ts';
import { localModelHint, resolveLocalModel, sameLocalModel } from './local-model.ts';
import { formatCubeGrid, formatTokenDetail, formatTokenLine, openTokenReader, readToken, readTokenCube, readTokenLinks, readTokens, thinkTokenDbPath } from './think-token-reader.ts';
import { TOKEN_STATUSES, type TokenStatus } from './think-token-store.ts';
import { TOKEN_HEADER, isLoopbackUrl, readLocalToken } from './local-token.ts';

const HOST = process.env.KUDBEE_URL || 'http://127.0.0.1:3000';
const WS_URL = HOST.replace(/^http/, 'ws') + '/ws';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
// The same data directory the server uses (KUDBEE_DATA_DIR, else apps/web/data): the CLI reads its local token and the Think Token database from there.
const DATA_DIR = process.env.KUDBEE_DATA_DIR || path.join(__dirname, 'data');

// Cheap local route: the already-installed Ollama model named by THINKBOX_LOCAL_MODEL (older: KUDBEE_LOCAL_MODEL).
// The CLI never pulls models; see local-model.ts.
const LOCAL_MODEL = resolveLocalModel();
// Name of the enterprise agent model the "complex" route should prefer. The actual
// candidate list still comes from client.models (server-reported, `agent: true`);
// this only breaks ties when more than one agent model is available.
const COMPLEX_MODEL = process.env.KUDBEE_COMPLEX_MODEL || 'mercury-2';

const c = {
  dim: (s: string) => `\x1b[2m${s}\x1b[0m`,
  bold: (s: string) => `\x1b[1m${s}\x1b[0m`,
  yellow: (s: string) => `\x1b[33m${s}\x1b[0m`,
  green: (s: string) => `\x1b[32m${s}\x1b[0m`,
  red: (s: string) => `\x1b[31m${s}\x1b[0m`,
  cyan: (s: string) => `\x1b[36m${s}\x1b[0m`,
  magenta: (s: string) => `\x1b[35m${s}\x1b[0m`,
};

interface Model { name: string; provider?: string; agent?: boolean }
interface ApprovalRequest { id: string; tool: string; args: Record<string, unknown>; reason: string; timeout_ms: number }
type RouteReason = 'auto' | 'manual' | 'auto_fallback_no_local';
interface RouteTelemtry { modelSelected: string; routeReason: RouteReason; complexity: 'simple' | 'complex'; estimatedTokensIfFullModel: number; estimatedTokensActual: number; tokensSavedEst: number }

const usd = (v: number): string => (v >= 0.01 ? `$${v.toFixed(2)}` : `$${(v || 0).toFixed(4)}`);
interface Msg { type: string; data?: any }

async function serverUp(): Promise<boolean> {
  try {
    const res = await fetch(`${HOST}/api/health`, { signal: AbortSignal.timeout(1500) });
    return res.ok;
  } catch {
    return false;
  }
}

async function ensureServer(): Promise<void> {
  if (await serverUp()) {
    console.log(c.dim(`Connected to the running Agent OS at ${HOST}: same engine, database and memory as the dashboard; this run shows live in the dashboard terminal.`));
    return;
  }
  const logDir = path.join(os.homedir(), '.kudbee');
  fs.mkdirSync(logDir, { recursive: true });
  const log = fs.openSync(path.join(logDir, 'server.log'), 'a');
  // The fallback is the same engine, not a second one: the server process (apps/web/server.ts) owns the database, memory and ranker, so the CLI starts it
  // on 127.0.0.1 with the same data directory and talks to it like any other client. A separate in-process copy would be a second engine.
  console.log(c.yellow(`Agent OS is not running at ${HOST}: starting it on 127.0.0.1 with the same database (${DATA_DIR}); it stays up, so the dashboard shows this run too.`));
  process.stdout.write(c.dim('Starting kudbEE Agent OS… '));
  spawn(process.execPath, ['--experimental-strip-types', path.join(__dirname, 'server.ts')], {
    cwd: __dirname,
    detached: true,
    stdio: ['ignore', log, log],
  }).unref();
  for (let i = 0; i < 40; i++) {
    await new Promise((r) => setTimeout(r, 250));
    if (await serverUp()) {
      console.log(c.green('up'));
      return;
    }
  }
  throw new Error(`Server did not start; see ${path.join(logDir, 'server.log')}`);
}

function printThought(t: any): void {
  const text = String(t.content ?? t.plugin ?? '').replace(/\s+/g, ' ');
  switch (t.type) {
    case 'tool_call':
      console.log(c.cyan(`  ⚙ ${text}`));
      break;
    case 'tool_result':
      console.log(t.status === 'error' ? c.red(`  ✗ ${text}`) : c.green(`  ✓ ${text}`));
      break;
    case 'plan':
      console.log(c.magenta(`  ✎ ${text}`));
      break;
    case 'error':
      console.log(c.red(`  ! ${text}`));
      break;
    case 'plugin_call':
    case 'plugin_result':
      break;
    case 'think_token':
      // Same id, status and lesson text the dashboard shows; `kudbee tokens show <id>` prints the rest.
      console.log(t.tokenId ? c.green(`  🧩 ${t.tokenId} [${t.tokenStatus ?? 'saved'}] ${text}`) : c.dim(`  🧩 ${text}`));
      break;
    default:
      console.log(c.dim(`  · ${text}`));
  }
}

class Client {
  ws!: WebSocket;
  sessionId = '';
  model = '';
  models: Model[] = [];
  plugins: any[] = [];
  onApproval: (req: ApprovalRequest) => void = (req) => this.answer(req.id, false);
  routeTelemetry?: RouteTelemtry;
  /** Tool-scoped agent lane (e.g. 'hermes'). Undefined = full worker agent. */
  agent?: string;
  private waiters: Array<{ type: string; resolve: (m: Msg) => void }> = [];

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      // The server only accepts WebSocket upgrades from its own loopback origin. The local token (file, mode 0600; never printed) identifies this
      // client as the CLI, so the run is labeled and mirrored live in the dashboard terminal.
      const token = readLocalToken(DATA_DIR);
      this.ws = new WebSocket(WS_URL, { origin: new URL(HOST).origin, ...(token ? { headers: { [TOKEN_HEADER]: token } } : {}) });
      this.ws.on('error', reject);
      this.ws.on('message', (raw) => {
        const msg = JSON.parse(raw.toString()) as Msg;
        if (msg.type === 'init') {
          this.sessionId = msg.data.sessionId;
          this.models = msg.data.models ?? [];
          this.plugins = msg.data.plugins ?? [];
          this.model = msg.data.config?.model ?? this.models[0]?.name ?? '';
          resolve();
        } else if (msg.type === 'thought') {
          printThought(msg.data);
        } else if (msg.type === 'approval_request') {
          this.onApproval(msg.data as ApprovalRequest);
        } else if (msg.type === 'stream') {
          process.stdout.write(String(msg.data));
        }
        const i = this.waiters.findIndex((w) => w.type === msg.type);
        if (i >= 0) this.waiters.splice(i, 1)[0].resolve(msg);
      });
    });
  }

  wait(type: string): Promise<Msg> {
    return new Promise((resolve) => this.waiters.push({ type, resolve }));
  }

  send(msg: Record<string, unknown>): void {
    this.ws.send(JSON.stringify(msg));
  }

  answer(id: string, approved: boolean): void {
    this.send({ type: 'approval_response', id, approved });
    console.log(approved ? c.green('  ⚖ approved') : c.yellow('  ⚖ denied'));
  }

  async run(goal: string): Promise<boolean> {
    console.log(c.dim(`▶ ${this.agent ? `${this.agent} · ` : ''}${this.model} working…`));
    const done = this.wait('result');
    this.send({ type: 'run_goal', goal, model: this.model, routeTelemetry: this.routeTelemetry, agent: this.agent });
    const { data: r } = await done;
    console.log();
    // The final answer is always printed, including after an evidence-check retry or a FLAGGED replacement.
    if (Array.isArray(r.evidence_conflicts) && r.evidence_conflicts.length) {
      console.log(c.yellow(`  ⚖ evidence check: the first answer conflicted with this run's tool results (${String(r.evidence_conflicts[0]).slice(0, 200)}); final answer below.`));
    }
    // A streamed (local chat) answer is already on screen token by token; do not print it again.
    if (r.success) console.log(`${c.green('✓')} ${r.streamed ? 'done' : String(r.result ?? '').trim() || '(the agent returned no answer text)'}`);
    else console.log(c.red(`✗ ${r.error ?? 'the run failed without an error message'}`));
    if (r.steps !== undefined) {
      console.log(c.dim(`  ${r.steps} step(s) · ${r.tool_calls} tool call(s) · ${r.tokens} tokens · ${usd(r.cost_usd)} · ${((r.duration_ms ?? 0) / 1000).toFixed(1)}s · run ${String(r.run_id).slice(0, 8)}`));
    }
    await this.files(true);
    return Boolean(r.success);
  }

  async files(quiet = false): Promise<void> {
    const res = await fetch(`${HOST}/api/sessions/${this.sessionId}/files`);
    const { files } = (await res.json()) as { files: Array<{ path: string; size: number }> };
    if (!files.length) {
      if (!quiet) console.log(c.dim('  (workspace empty)'));
      return;
    }
    console.log(c.bold('  Workspace files:'));
    for (const f of files) console.log(`    ${f.path} ${c.dim(`${f.size} B`)}`);
    console.log(c.dim(`    ${path.join(__dirname, 'workspaces', this.sessionId)}`));
  }

  async cat(file: string): Promise<void> {
    const res = await fetch(`${HOST}/api/sessions/${this.sessionId}/files/content?path=${encodeURIComponent(file)}`);
    const body = (await res.json()) as { content?: string; error?: string };
    console.log(body.content ?? c.red(body.error ?? 'error'));
  }
}

function printApproval(req: ApprovalRequest): void {
  console.log(c.yellow(`\n  ⚖ APPROVAL: ${req.tool} — ${req.reason}`));
  console.log(c.dim(`    ${JSON.stringify(req.args).slice(0, 300)}`));
}

async function showRuns(): Promise<void> {
  const { runs } = (await (await fetch(`${HOST}/api/runs?limit=15`)).json()) as { runs: any[] };
  if (!runs.length) return console.log(c.dim('  (no runs yet)'));
  for (const r of runs) {
    const color = r.status === 'completed' ? c.green : r.status === 'running' ? c.cyan : r.status === 'stopped' ? c.yellow : c.red;
    console.log(`  ${r.id.slice(0, 8)} ${color(r.status.padEnd(9))} ${usd(r.cost_usd).padStart(8)} ${c.dim(`${((r.duration_ms ?? 0) / 1000).toFixed(1)}s`.padStart(6))}  ${r.goal.slice(0, 70)}`);
  }
}

async function showRun(prefix: string): Promise<void> {
  const { runs } = (await (await fetch(`${HOST}/api/runs?limit=500`)).json()) as { runs: any[] };
  const match = prefix && runs.find((r) => r.id.startsWith(prefix));
  if (!match) return console.log(c.red('Usage: /run ID (first characters from /runs)'));
  const run = (await (await fetch(`${HOST}/api/runs/${match.id}`)).json()) as any;
  console.log(c.bold(run.goal));
  console.log(c.dim(`  ${run.status} · ${run.model} · ${run.current_step} steps · ${run.tool_calls} tools · ${run.prompt_tokens + run.completion_tokens} tokens · ${usd(run.cost_usd)} · ${((run.duration_ms ?? 0) / 1000).toFixed(1)}s`));
  for (const step of run.steps) {
    if (step.kind === 'model') {
      console.log(c.magenta(`  🧠 step ${step.step} ${step.latency_ms}ms ${step.prompt_tokens}+${step.completion_tokens} tok ${usd(step.cost_usd)} → ${step.tool_calls.join(', ') || 'answer'}`));
    } else {
      const mark = step.ok ? c.green('✓') : c.red('✗');
      console.log(`     ${mark} ${step.name} ${c.dim(`${step.latency_ms}ms`)}${step.approval ? c.yellow(` [${step.approval}]`) : ''} ${c.dim(JSON.stringify(step.args).slice(0, 100))}`);
    }
  }
  if (run.result) console.log(`\n${run.result}`);
  if (run.error) console.log(c.red(`\n${run.error}`));
}

async function interactiveModelSelect(client: Client): Promise<boolean> {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    console.log(c.bold('\n🤖 SELECT MODEL\n'));
    const agents = client.models.filter((m) => m.agent);
    const local = client.models.filter((m) => !m.agent);

    if (agents.length) {
      console.log(c.bold('  Enterprise:'));
      agents.forEach((m, i) =>
        console.log(`    [${i + 1}] ${m.name} ${c.dim('(full toolkit, tool-using agent)')}`)
      );
    }
    if (local.length) {
      console.log(c.bold('\n  Local:'));
      local.forEach((m, i) =>
        console.log(`    [${agents.length + i + 1}] ${m.name} ${c.dim('(offline, lightweight)')}`)
      );
    }

    rl.question(c.cyan('\n  Choose (number or name): '), (input) => {
      rl.close();
      const choice = input.trim().toLowerCase();
      const idx = parseInt(choice, 10) - 1;
      const all = [...agents, ...local];

      if (idx >= 0 && idx < all.length) {
        const selected = all[idx];
        client.model = selected.name;
        client.routeTelemetry = {
          modelSelected: selected.name,
          routeReason: 'manual',
          complexity: 'simple',
          estimatedTokensIfFullModel: 2500,
          estimatedTokensActual: selected.agent ? 2500 : 800,
          tokensSavedEst: selected.agent ? 0 : 1700,
        };
        console.log(c.green(`\n  ✓ Selected: ${client.model}\n`));
        resolve(true);
      } else {
        const match = all.find((m) => m.name.toLowerCase().includes(choice));
        if (match) {
          client.model = match.name;
          client.routeTelemetry = {
            modelSelected: match.name,
            routeReason: 'manual',
            complexity: 'simple',
            estimatedTokensIfFullModel: 2500,
            estimatedTokensActual: match.agent ? 2500 : 800,
            tokensSavedEst: match.agent ? 0 : 1700,
          };
          console.log(c.green(`\n  ✓ Selected: ${client.model}\n`));
          resolve(true);
        } else {
          console.log(c.red(`\n  ✗ Invalid choice\n`));
          resolve(false);
        }
      }
    });
  });
}

const HELP = `${c.bold('kudbEE CLI')} — Enterprise agent control center

${c.bold('MODELS & AGENTS')}
  /models             list available models (enterprise & local)
  /model NAME         switch to model (Mercury-2, Qwen2.5 1.5B, etc)
  /select             interactive model picker 🎯
  /agents             list tool-scoped agent lanes (e.g. HERMES — Algorand read-only)
  /agent [NAME]       switch to an agent lane, or clear it (default worker, full tools)
  ${c.dim("kudbee run '<goal>'")}  one-shot goal (same as kudbee '<goal>'); ${c.dim("kudbee --agent hermes '<goal>'")} uses an agent lane
  ${c.dim('kudbee tokens list [--status S] [--run ID] [--json]')}  Think Tokens (same store as the dashboard)
  ${c.dim('kudbee token cube <TT-id> [--events] [--json]')}  the token's 100-cell grid (ASCII) and its recent cell changes
  ${c.dim('kudbee tokens show <TT-id> [--json]')}  one token: lesson, score breakdown, run, ledger receipt

${c.bold('OPERATIONS')}
  /plugins            list available tools and permissions
  /plugin NAME JSON   run a plugin with the given JSON input
  /skills             browse 100+ MCP servers from official registry
  /skill [SEARCH]     find a skill, or interactive menu (no args)
  /files              list workspace files
  /cat PATH           print file content
  /tokens [QUERY]     Think Tokens (lessons): list or search; /lessons is the same
  /token TT-ID        one Think Token in full
  /runs               run history (15 latest)
  /sessions           session history (same as /runs)
  /run ID             detailed step-by-step trace

${c.bold('MEMORY & KNOWLEDGE')}
  /memory [QUERY]     search organizational memory (Upstash + BM25)
  /notes [LAYER]      list persistent notes (session|task|org|verified)
  /remember TEXT      save note to persistent DB (default: session layer)
  /forget [ID|QUERY]  delete note by id or query
  /promote org/ID     promote note to verified knowledge

${c.bold('ANALYTICS & DEBUG')}
  /metrics            agent KPIs (runs, tokens, cost, success rate)
  /status             server health check
  /session            current session info (ID, model, agent, plugins)
  /plugin NAME JSON   run a plugin with JSON input
  /algo ACTION [ADDR] read-only Algorand queries

${c.bold('SYSTEM')}
  /open               show dashboard URL
  /stop               cancel current goal
  /help               this help
  /quit               exit

${c.bold('EXAMPLES')}
  ${c.cyan('Read https://hnrss.org/frontpage and write top5.md')}
  ${c.cyan('/select')} — pick Mercury-2 or the local model interactively
  ${c.cyan('/memory python tips')} — search memory for Python advice`;

async function handleCommand(client: Client, line: string, sessionId: string): Promise<boolean> {
  const [cmd, ...args] = line.split(/\s+/);
  switch (cmd) {
    case '/help':
      console.log(HELP);
      break;
    case '/models': {
      // Enterprise: show model categories with metadata
      const mercury = client.models.filter((m) => m.agent);
      const local = client.models.filter((m) => !m.agent);

      if (mercury.length) {
        console.log(c.bold('\n  🤖 Enterprise Worker Agents (tool-using)'));
        for (const m of mercury) {
          const mark = m.name === client.model ? c.green('●') : ' ';
          console.log(`    ${mark} ${m.name} ${c.dim(`[${m.provider ?? 'inference'}] · low-latency, full toolkit`)}`);
        }
      }
      if (local.length) {
        console.log(c.bold('\n  💻 Local Models (streaming, offline)'));
        for (const m of local) {
          const mark = m.name === client.model ? c.green('●') : ' ';
          const cheapRoute = sameLocalModel(LOCAL_MODEL, m.name) ? c.dim(' (cheap route)') : '';
          console.log(`    ${mark} ${m.name} ${c.dim(`[${m.provider ?? 'ollama'}] · lightweight, privacy-first`)}${cheapRoute}`);
        }
      }
      const localRouteReady = local.some((m) => sameLocalModel(LOCAL_MODEL, m.name));
      if (!localRouteReady) {
        console.log(c.bold('\n  💻 Local Models (streaming, offline)'));
        console.log(c.red(`    ✗ ${LOCAL_MODEL} is not installed — auto-routing falls back to Mercury-2 for simple goals`));
        console.log(c.dim('      Set THINKBOX_LOCAL_MODEL to a model from `ollama list` (nothing is pulled for you).'));
      }
      console.log(c.dim(`\n  Use: /model MERCURY-2  or  /model ${LOCAL_MODEL}`));
      break;
    }
    case '/model':
      if (!client.models.some((m) => m.name === args[0])) {
        console.log(c.red(`Unknown model "${args[0]}". Available:`));
        for (const m of client.models) console.log(`    ${m.name}`);
      } else {
        client.model = args[0];
        const selected = client.models.find((m) => m.name === args[0]);
        const icon = selected?.agent ? '🤖' : '💻';
        console.log(`${icon} Model → ${c.bold(client.model)}`);
      }
      break;
    case '/agents': {
      const res = await fetch(`${HOST}/api/agents`);
      const { agents } = (await res.json()) as { agents: Array<{ id: string; name: string; description: string; allowedTools: string[] }> };
      console.log(c.bold('\n  Worker agent (default)') + c.dim(' — full tool access'));
      for (const a of agents) {
        const mark = client.agent === a.id ? c.green('●') : ' ';
        console.log(`  ${mark} ${c.bold(a.name)} ${c.dim(`(/agent ${a.id})`)}`);
        console.log(c.dim(`      ${a.description}`));
        console.log(c.dim(`      tools: ${a.allowedTools.join(', ')}`));
      }
      console.log(c.dim('\n  Use: /agent NAME  or  /agent  (clears — back to default worker)'));
      break;
    }
    case '/agent':
      if (!args[0]) {
        client.agent = undefined;
        console.log(c.green('🤖 Agent → default worker (full tools)'));
      } else {
        const res = await fetch(`${HOST}/api/agents`);
        const { agents } = (await res.json()) as { agents: Array<{ id: string; name: string }> };
        const match = agents.find((a) => a.id === args[0].toLowerCase());
        if (!match) {
          console.log(c.red(`Unknown agent "${args[0]}". See /agents.`));
        } else {
          client.agent = match.id;
          console.log(c.green(`🤖 Agent → ${match.name} (read-only tool lane)`));
        }
      }
      break;
    case '/plugins':
      for (const p of client.plugins) console.log(`  ${p.icon ?? '🔌'} ${p.name} ${c.dim(`[${p.permission}] ${p.description}`)}`);
      break;
    case '/plugin': {
      const pluginName = args.shift();
      if (!pluginName) {
        console.log(c.red('Usage: /plugin NAME JSON'));
        console.log(c.dim('Example: /plugin my_tool {"key": "value"}'));
        break;
      }
      if (!args.length) {
        console.log(c.red(`Error: ${pluginName} requires JSON input`));
        console.log(c.dim('Example: /plugin my_tool {"key": "value"}'));
        break;
      }
      try {
        const input = JSON.parse(args.join(' '));
        const done = client.wait('plugin_result');
        client.send({ type: 'plugin_execute', plugin: pluginName, input });
        // Wait up to 30 seconds for plugin result
        let result: any;
        try {
          const response = await Promise.race<Msg>([
            done,
            new Promise<Msg>((_, reject) =>
              setTimeout(() => reject(new Error('Plugin execution timeout')), 30000)
            ),
          ]);
          result = response.data;
        } catch (timeoutErr) {
          console.log(c.red('Error: Plugin execution timed out (30s)'));
          break;
        }
        if (result.success) {
          console.log(c.green(`✓ ${pluginName} executed successfully`));
          if (result.output) {
            const formatted = typeof result.output === 'string'
              ? result.output
              : JSON.stringify(result.output, null, 2);
            console.log(c.dim('Output:'));
            console.log(`  ${formatted.split('\n').join('\n  ')}`);
          }
        } else {
          console.log(c.red(`✗ Plugin execution failed: ${pluginName}`));
          if (result.error) console.log(c.dim(`  Error: ${result.error}`));
        }
      } catch (err) {
        console.log(c.red('Error: Invalid JSON input'));
        console.log(c.dim(`Details: ${err instanceof Error ? err.message : String(err)}`));
      }
      break;
    }
    case '/files':
      await client.files();
      break;
    case '/cat':
      await client.cat(args.join(' '));
      break;
    case '/status':
      console.log(await (await fetch(`${HOST}/api/health`)).json());
      break;
    case '/session': {
      const wsStatus = client.ws?.readyState === 1;
      console.log([
        c.bold('🐝 kudbEE Agent OS — Session'),
        `  Session ID: ${c.cyan(sessionId || '(disconnected)')}`,
        `  Model: ${client.model ? c.green(client.model) : c.dim('(not selected)')}`,
        `  Agent: ${c.yellow(client.agent || 'default worker (full tools)')}`,
        `  Plugins: ${c.magenta(String(client.plugins.length))}`,
        `  WebSocket: ${wsStatus ? c.green('Connected') : c.red('Disconnected')}`,
        '',
        c.dim(`  Use /model NAME to switch · /agent NAME to select an agent profile`),
      ].join('\n'));
      break;
    }
    // Think Tokens are the lessons the agent learned: same store and formatter as `kudbee tokens ...` and the dashboard's Think Tokens view.
    case '/tokens':
    case '/lessons':
      tokensCommand(['list', ...args]);
      break;
    case '/token':
      tokensCommand(['show', ...args]);
      break;
    case '/runs':
    case '/sessions':
      await showRuns();
      break;
    case '/memory': {
      const query = args.join(' ').trim();
      const params = new URLSearchParams({ limit: '10', ...(query ? { q: query } : {}) });
      const { items, backend } = (await (await fetch(`${HOST}/api/memory?${params}`)).json()) as { items: any[]; backend: string };
      if (!items.length) console.log(c.dim(`  (no memories${query ? ` match "${query}"` : ''})`));
      if (query && items.length) console.log(c.dim(`  search backend: ${backend}`));
      const color: Record<string, (s: string) => string> = { verified: c.green, org: c.yellow, task: c.cyan };
      for (const item of items) {
        console.log(`  ${(color[item.layer] ?? c.dim)(item.layer.padEnd(8))} ${item.title}${item.score !== undefined ? c.dim(` · ${Number(item.score).toFixed(2)}`) : ''}`);
        console.log(c.dim(`           ${item.id} — ${item.content.slice(0, 110)}`));
      }
      break;
    }
    case '/notes': {
      const layer = args[0] || '';
      const params = new URLSearchParams({ limit: '20', sessionId });
      if (layer && ['session', 'task', 'org', 'verified'].includes(layer)) {
        params.set('layer', layer);
      }
      const res = await fetch(`${HOST}/api/memory/notes?${params}`);
      const data = (await res.json()) as any;
      if (!res.ok || !data.notes?.length) {
        console.log(c.dim(`  (no notes${layer ? ` in ${layer}` : ''})`));
        break;
      }
      for (const note of data.notes as any[]) {
        const layerColor = { session: c.cyan, task: c.magenta, org: c.yellow, verified: c.green }[note.layer as string] || c.dim;
        console.log(`  ${layerColor(note.layer.padEnd(8))} ${note.title}`);
        console.log(c.dim(`    ${note.id} — ${note.content.slice(0, 80)}`));
      }
      break;
    }

    case '/remember': {
      const text = args.join(' ').trim();
      if (!text) {
        console.log(c.red('Usage: /remember TEXT'));
        break;
      }
      const [title, ...rest] = text.split(/\s+[-—:]\s+/);
      const layer = args.includes('--org') ? 'org' : args.includes('--task') ? 'task' : 'session';
      const res = await fetch(`${HOST}/api/memory/notes?sessionId=${encodeURIComponent(sessionId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title || text.slice(0, 40),
          content: rest.join(' - ') || text,
          layer
        }),
      });
      const item = (await res.json()) as any;
      console.log(res.ok ? c.green(`  ✓ saved ${layer} note: ${item.id}`) : c.red(`  ✗ ${item.error}`));
      break;
    }

    case '/forget': {
      const query = args.join(' ').trim();
      if (!query) {
        console.log(c.red('Usage: /forget ID|QUERY'));
        break;
      }
      const res = await fetch(`${HOST}/api/memory/notes/${encodeURIComponent(query)}?sessionId=${encodeURIComponent(sessionId)}`, { method: 'DELETE' });
      const result = (await res.json()) as any;
      console.log(res.ok ? c.green(`  ✓ deleted: ${result.deleted ?? 'note'}`) : c.red(`  ✗ ${result.error}`));
      break;
    }
    case '/algo': {
      const [action = 'status', target, maybeNetwork] = args;
      const network = [target, maybeNetwork].find((v) => v === 'mainnet' || v === 'testnet') ?? 'testnet';
      const aliases: Record<string, string> = { app: 'application', tx: 'transaction', txs: 'account_transactions', history: 'account_transactions' };
      const resolved = aliases[action] ?? action;
      const params = new URLSearchParams({ action: resolved, network });
      if (target && target !== network) {
        params.set(['account', 'account_transactions'].includes(resolved) ? 'address' : resolved === 'transaction' ? 'txid' : 'id', target);
      }
      const res = await fetch(`${HOST}/api/algorand?${params}`);
      const body = (await res.json()) as Record<string, unknown>;
      console.log(res.ok ? JSON.stringify(body, null, 2) : c.red(`  ${body.error}`));
      break;
    }
    case '/promote': {
      const id = args[0]?.startsWith('org/') ? args[0] : `org/${args[0] ?? ''}`;
      const res = await fetch(`${HOST}/api/memory/promote`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) });
      const item = (await res.json()) as any;
      console.log(res.ok ? c.green(`  promoted → ${item.id}`) : c.red(`  ${item.error}`));
      break;
    }
    case '/run':
      await showRun(args[0] ?? '');
      break;
    case '/metrics': {
      const m = (await (await fetch(`${HOST}/api/stats`)).json()) as any;
      console.log(`  Runs ${m.runs_today} today / ${m.runs_total} total · success ${m.success_rate ?? '—'}% · p50 ${(m.p50_ms / 1000).toFixed(1)}s · p95 ${(m.p95_ms / 1000).toFixed(1)}s`);
      console.log(`  Tokens today ${m.tokens_today} · cost today ${usd(m.cost_today_usd)} · all-time ${usd(m.cost_total_usd)}${m.budget_usd ? ` · budget ${usd(m.budget_usd)}` : ''}`);
      for (const [name, t] of Object.entries(m.tools as Record<string, any>)) {
        console.log(c.dim(`  ${name.padEnd(12)} ${t.calls} calls · ${t.success_rate}% ok · ${t.avg_ms}ms avg${t.denied ? ` · ${t.denied} denied` : ''}`));
      }
      break;
    }
    case '/open':
      console.log(`Dashboard: ${c.cyan(HOST)}`);
      break;
    case '/stop':
      client.send({ type: 'stop' });
      break;
    case '/select':
      await interactiveModelSelect(client);
      break;
    case '/skills': {
      const registry = new MCPRegistry(process.env.GITHUB_TOKEN);
      console.log(c.dim('Fetching MCP skill registry...'));
      const servers = await registry.discoverServers();
      console.log(c.bold(`\n  🔌 AVAILABLE MCP SKILLS (${servers.length} total)\n`));

      const byCategory = registry.groupByCategory(servers);
      for (const [cat, items] of Object.entries(byCategory).sort()) {
        console.log(c.bold(`  ${cat}`));
        for (const s of items) {
          console.log(`    ${c.cyan(s.name)} — ${s.description}`);
          if (s.tags.length) {
            console.log(c.dim(`      Tags: ${s.tags.join(', ')}`));
          }
        }
      }
      console.log(c.dim(`\n  Use: /skill SEARCH  or  /skill  for interactive selection`));
      break;
    }
    case '/skill': {
      const registry = new MCPRegistry(process.env.GITHUB_TOKEN);
      const skillName = args[0];

      if (!skillName) {
        // Interactive selection
        const servers = await registry.discoverServers();
        if (servers.length === 0) {
          console.log(c.red('  No skills found'));
          break;
        }

        const byCategory = registry.groupByCategory(servers);
        console.log(c.bold('\n  🔌 AVAILABLE MCP SKILLS\n'));
        const allServers: Array<{ index: number; server: any; category: string }> = [];
        let index = 1;

        for (const [cat, items] of Object.entries(byCategory).sort()) {
          console.log(c.bold(`  ${cat}`));
          for (const s of items) {
            console.log(`    ${index}. ${c.cyan(s.name)} — ${s.description}`);
            allServers.push({ index, server: s, category: cat });
            index++;
          }
        }

        const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
        rl.question(c.cyan('\n  Pick (number or search): '), async (input) => {
          rl.close();
          const num = parseInt(input, 10);
          if (!isNaN(num) && num >= 1 && num < index) {
            const selected = allServers.find((x) => x.index === num)?.server;
            if (selected) {
              console.log(c.green(`\n  ✓ Selected: ${selected.name}`));
              console.log(`  ${selected.description}`);
              if (selected.capabilities.length) {
                console.log(c.dim(`  Capabilities: ${selected.capabilities.join(', ')}`));
              }
            }
          } else {
            const matches = registry.filter(servers, input);
            if (matches.length === 0) {
              console.log(c.red('  No matches found'));
            } else if (matches.length === 1) {
              const s = matches[0];
              console.log(c.green(`\n  ✓ Selected: ${s.name}`));
              console.log(`  ${s.description}`);
              if (s.capabilities.length) {
                console.log(c.dim(`  Capabilities: ${s.capabilities.join(', ')}`));
              }
            } else {
              console.log(c.dim(`\n  Found ${matches.length} matches:`));
              matches.forEach((m, i) => {
                console.log(`    ${i + 1}. ${c.cyan(m.name)} — ${m.description}`);
              });
            }
          }
        });
      } else {
        // Direct search
        const servers = await registry.discoverServers();
        const matches = registry.filter(servers, skillName);

        if (matches.length === 0) {
          console.log(c.red(`  No skills matching "${skillName}"`));
        } else if (matches.length === 1) {
          const s = matches[0];
          console.log(`\n${c.bold(s.name)}`);
          console.log(c.dim(`  ${s.description}`));
          if (s.tags.length) {
            console.log(c.dim(`  Tags: ${s.tags.join(', ')}`));
          }
          if (s.capabilities.length) {
            console.log(c.dim(`  Capabilities: ${s.capabilities.join(', ')}`));
          }
        } else {
          console.log(c.dim(`\n  Found ${matches.length} matches:`));
          for (const m of matches) {
            console.log(`  ${c.cyan(m.name)} — ${m.description}`);
          }
        }
      }
      break;
    }
    case '/quit':
    case '/exit':
      return false;
    default:
      console.log(c.red(`Unknown command ${cmd}. Type /help`));
  }
  return true;
}

/** True at most once per 24 h: a marker file in ~/.kudbee records the last warning, so repeated `kudbee run` calls stay quiet. */
function shouldWarnLocalModelToday(): boolean {
  const marker = path.join(os.homedir(), '.kudbee', 'local-model-warned');
  try {
    if (Date.now() - fs.statSync(marker).mtimeMs < 24 * 3_600_000) return false;
  } catch { /* never warned */ }
  try {
    fs.mkdirSync(path.dirname(marker), { recursive: true });
    fs.writeFileSync(marker, new Date().toISOString());
  } catch { /* read-only home: warn every time rather than never */ }
  return true;
}

// Routing heuristics: Simple → cheap local Ollama model (THINKBOX_LOCAL_MODEL), Complex → Mercury-2.
// If the configured local model isn't installed in Ollama,
// fall back to Mercury-2 and report the fallback honestly (no fake savings).
function selectModelForGoal(goal: string, client: Client): RouteTelemtry {
  const agentModels = client.models.filter((m) => m.agent);
  const mercury = agentModels.find((m) => m.name === COMPLEX_MODEL) ?? agentModels[0];
  const local = client.models.find((m) => !m.agent && sameLocalModel(LOCAL_MODEL, m.name));

  // No enterprise agent model configured at all: nothing to route between.
  if (!mercury) {
    return {
      modelSelected: client.model,
      routeReason: 'manual',
      complexity: 'simple',
      estimatedTokensIfFullModel: 2500,
      estimatedTokensActual: 2500,
      tokensSavedEst: 0,
    };
  }

  const isComplex = isComplexGoal(goal);
  const complexity: 'simple' | 'complex' = isComplex ? 'complex' : 'simple';
  const estimatedTokensIfFullModel = isComplex ? 2500 : 1500;

  let telemetry: RouteTelemtry;

  if (isComplex) {
    telemetry = {
      modelSelected: mercury.name,
      routeReason: 'auto',
      complexity,
      estimatedTokensIfFullModel,
      estimatedTokensActual: 2500,
      tokensSavedEst: 0,
    };
  } else if (local) {
    telemetry = {
      modelSelected: local.name,
      routeReason: 'auto',
      complexity,
      estimatedTokensIfFullModel,
      estimatedTokensActual: 800,
      tokensSavedEst: estimatedTokensIfFullModel - 800,
    };
  } else {
    // Simple goal, but the configured local model isn't installed — never claim
    // savings we didn't get.
    telemetry = {
      modelSelected: mercury.name,
      routeReason: 'auto_fallback_no_local',
      complexity,
      estimatedTokensIfFullModel,
      estimatedTokensActual: estimatedTokensIfFullModel,
      tokensSavedEst: 0,
    };
    // No Ollama at all (nothing installed): nothing to warn about, every run would just repeat it. Ollama present but the configured model missing:
    // say so at most once a day, and name the models that ARE installed.
    const installed = client.models.filter((m) => !m.agent).map((m) => m.name);
    if (installed.length && shouldWarnLocalModelToday()) {
      console.log(c.dim(`  ⚠ ${localModelHint(LOCAL_MODEL)} Installed: ${installed.slice(0, 5).join(', ')}.`));
    }
  }

  if (telemetry.modelSelected !== client.model || telemetry.routeReason === 'auto_fallback_no_local') {
    if (telemetry.routeReason === 'auto_fallback_no_local') {
      if (process.env.KUDBEE_VERBOSE === '1') console.log(c.dim(`  💡 [${complexity}] → ${telemetry.modelSelected} (local model '${LOCAL_MODEL}' not installed)`));
    } else {
      const saved = telemetry.tokensSavedEst > 0 ? ` (est. saved ~${telemetry.tokensSavedEst} tokens)` : '';
      console.log(c.dim(`  💡 [${complexity}] → ${telemetry.modelSelected}${saved}`));
    }
  }

  return telemetry;
}


/** `kudbee tokens list|show`: reads the same think-tokens.db the dashboard reads, through the one shared reader. */
function tokensCommand(args: string[]): number {
  const flag = (name: string): string | undefined => {
    const i = args.indexOf(name);
    if (i < 0) return undefined;
    const [, value] = args.splice(i, 2);
    return value;
  };
  const json = args.includes('--json');
  if (json) args.splice(args.indexOf('--json'), 1);
  const status = flag('--status');
  const runId = flag('--run');
  const [sub, ...rest] = args;
  if (status !== undefined && !(TOKEN_STATUSES as readonly string[]).includes(status)) {
    console.log(c.red(`status must be one of: ${TOKEN_STATUSES.join(', ')}`));
    return 2;
  }
  let store;
  try {
    store = openTokenReader();
  } catch (err) {
    console.log(c.red(`No Think Token database to read at ${thinkTokenDbPath()} (${err instanceof Error ? err.message : err}).`));
    console.log(c.dim('Complete a goal with the Agent OS running, then try again.'));
    return 1;
  }
  try {
    if (sub === 'show') {
      const id = rest[0];
      if (!id) { console.log(c.red('usage: kudbee tokens show <TT-id> [--json]')); return 2; }
      const token = readToken(store, id);
      if (!token) { console.log(c.red(`No Think Token ${id}`)); return 1; }
      console.log(json ? JSON.stringify(token, null, 2) : formatTokenDetail(token));
      return 0;
    }
    if (sub === 'cube') {
      const id = rest[0];
      if (!id) { console.log(c.red('usage: kudbee token cube <TT-id> [--events] [--json]')); return 2; }
      const cube = readTokenCube(store, id);
      if (!cube) { console.log(c.red(`No Think Token ${id}`)); return 1; }
      if (json) { console.log(JSON.stringify(cube, null, 2)); return 0; }
      console.log(formatCubeGrid(cube));
      if (args.includes('--events')) {
        console.log(c.bold('  recent cell changes (newest first)'));
        for (const e of cube.events.slice(0, 30)) console.log(`  ${new Date(e.ts).toISOString().slice(0, 19)}  ${e.cause.padEnd(22)} ${e.key.padEnd(20)} ${String(e.before ?? '(none)').padEnd(14)} -> ${e.after}${e.ledger_seq ? c.dim(`  receipt #${e.ledger_seq}`) : ''}`);
      }
      return 0;
    }
    if (sub === 'links') {
      const id = rest[0];
      if (!id) { console.log(c.red('usage: kudbee tokens links <TT-id> [--json]')); return 2; }
      const token = readToken(store, id);
      if (!token) { console.log(c.red(`No Think Token ${id}`)); return 1; }
      const links = readTokenLinks(store, id);
      if (json) console.log(JSON.stringify({ id: token.id, links }, null, 2));
      else if (!links.length) console.log(c.dim(`No links for ${token.id}`));
      else {
        console.log(c.bold(`${token.id} links (${links.length})`));
        for (const L of links) {
          const other = L.from_id === token.id ? L.to_id : L.from_id;
          const dir = L.from_id === token.id ? '→' : '←';
          console.log(`  ${L.kind.padEnd(16)} ${dir} ${other}  w=${L.weight.toFixed(2)}  ${L.evidence}`);
        }
      }
      return 0;
    }
    if (sub === undefined || sub === 'list') {
      const query = rest.join(' ').trim() || undefined;
      const tokens = readTokens(store, { status: status as TokenStatus | undefined, run_id: runId, query, limit: 100 });
      if (json) console.log(JSON.stringify({ tokens, ledger: store.verifyLedger() }, null, 2));
      else if (!tokens.length) console.log(c.dim('No Think Tokens match.'));
      else {
        for (const t of tokens) console.log(formatTokenLine(t));
        const ledger = store.verifyLedger();
        console.log(c.dim(`${tokens.length} shown · ledger ${ledger.ok ? 'verified' : 'BROKEN'} (${ledger.entries} entries) · ${thinkTokenDbPath()}`));
      }
      return 0;
    }
    console.log(c.red('usage: kudbee tokens list|show <TT-id>|links <TT-id> [--json]'));
    return 2;
  } finally {
    store.close();
  }
}

async function main(): Promise<void> {
  if (!isLoopbackUrl(HOST)) {
    console.error(c.red(`kudbee: KUDBEE_URL must point to this machine (127.0.0.1 or localhost); refusing ${HOST}`));
    process.exit(2);
  }
  // Reading tokens needs no server and no WebSocket.
  if (process.argv[2] === 'tokens' || process.argv[2] === 'token') process.exit(tokensCommand(process.argv.slice(3)));

  await ensureServer();
  const client = new Client();
  await client.connect();

  // CLI uses its own session for persistent memory
  const cliSessionId = client.sessionId;

  const argv = process.argv.slice(2);
  if (argv[0] === 'run') argv.shift(); // `kudbee run "<goal>"` is the same as `kudbee "<goal>"`
  const autoYes = argv[0] === '--yes' || argv[0] === '-y';
  if (autoYes) argv.shift();
  if (argv[0] === '--agent') {
    argv.shift();
    client.agent = argv.shift()?.toLowerCase();
  }
  const goal = argv.join(' ').trim();
  client.onApproval = (req) => {
    printApproval(req);
    if (autoYes) return client.answer(req.id, true);
    if (!process.stdin.isTTY) {
      console.log(c.dim('    (no terminal to ask — denying; pass --yes to auto-approve)'));
      return client.answer(req.id, false);
    }
    const ask = readline.createInterface({ input: process.stdin, output: process.stdout });
    ask.question(c.yellow('    Approve? [y/N] '), (reply) => {
      ask.close();
      client.answer(req.id, /^y(es)?$/i.test(reply.trim()));
    });
  };
  if (goal.startsWith('/')) {
    await handleCommand(client, goal, cliSessionId);
    client.ws.close();
    process.exit(0);
  }

  // Enterprise: auto-route to optimal model for token savings
  if (goal) {
    const telemetry = selectModelForGoal(goal, client);
    client.routeTelemetry = telemetry;
    if (telemetry.modelSelected !== client.model) {
      client.model = telemetry.modelSelected;
    }
  }
  if (goal) {
    const ok = await client.run(goal);
    client.ws.close();
    process.exit(ok ? 0 : 1);
  }

  console.log(`${c.yellow('🐝 kudbEE Agent OS')} ${c.dim(`— session ${client.sessionId.slice(0, 8)} · model ${client.model} · ${HOST}`)}`);
  console.log(c.dim('Type a goal, or /help. Ctrl+C to exit.'));
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout, prompt: c.yellow('kudbee› ') });
  rl.prompt();
  let inFlight = 0;
  const pending: ApprovalRequest[] = [];
  client.onApproval = (req) => {
    printApproval(req);
    pending.push(req);
    process.stdout.write(c.yellow('    Approve? [y/N] '));
  };
  rl.on('line', async (raw) => {
    const line = raw.trim();
    const approval = pending.shift();
    if (approval) return client.answer(approval.id, /^y(es)?$/i.test(line));
    if (!line) return rl.prompt();
    if (line.startsWith('/')) {
      try {
        if (!(await handleCommand(client, line, cliSessionId))) return rl.close();
      } catch (err) {
        console.log(c.red(String(err)));
      }
      return rl.prompt();
    }
    // Goals never block the prompt: the server queues them per session and results arrive in order.
    if (inFlight) console.log(c.dim(`  ⏳ queued behind ${inFlight} goal(s)`));
    inFlight += 1;
    client
      .run(line)
      .catch((err) => console.log(c.red(String(err))))
      .finally(() => {
        inFlight -= 1;
        rl.prompt();
      });
    rl.prompt();
  });
  rl.on('close', () => {
    client.ws.close();
    process.exit(0);
  });
  client.ws.on('close', () => {
    console.log(c.red('\nDisconnected from Agent OS.'));
    process.exit(1);
  });
}

main().catch((err) => {
  console.error(c.red(`kudbee: ${err instanceof Error ? err.message : err}`));
  process.exit(1);
});
