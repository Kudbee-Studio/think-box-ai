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
import { routeLabel } from './route-decision.ts';
import { modeLabel, type ConvoyState } from './convoy.ts';
import { matchRecipe } from './local-recipes.ts';
import { localModelHint, resolveLocalModel, sameLocalModel } from './local-model.ts';
import { loadMeasurements, pickMeasured } from './measured-routing.ts';
import { formatCubeGrid, formatTokenDetail, formatTokenLine, openTokenReader, readHealth, readToken, readTokenCube, readTokenLinks, readTokens, thinkTokenDbPath } from './think-token-reader.ts';
import { formatTokenHealth } from './think-token-health.ts';
import { AuditLog } from './audit-log.ts';
import { budgetConfig, formatUsd } from './budget-guard.ts';
import { formatSpendReport, spendReport, type SpendRun } from './spend-report.ts';
import { TOKEN_STATUSES, type TokenStatus } from './think-token-store.ts';
import { TOKEN_HEADER, isLoopbackUrl, readLocalToken } from './local-token.ts';
import { httpError } from './http-error.ts';
import { installCoverageFlush } from './coverage-flush.ts';
import type { Thought, WsMessage } from './types.ts';
import { MODELS_PRIVACY_NOTE, cloudModelNote, localModelNote, quickHelp, welcome } from './cli-help.ts';

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
interface PluginInfo { name: string; icon?: string; permission: string; description: string }
type RouteReason = 'auto' | 'manual' | 'auto_fallback_no_local' | 'measured_lookup';
interface RouteTelemtry { modelSelected: string; routeReason: RouteReason; complexity: 'simple' | 'complex'; estimatedTokensIfFullModel: number; estimatedTokensActual: number; tokensSavedEst: number }

const usd = (v: number): string => (v >= 0.01 ? `$${v.toFixed(2)}` : `$${(v || 0).toFixed(4)}`);

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
  spawn(process.execPath, [path.join(__dirname, 'launch.mjs'), 'server'], {
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

function printThought(t: Thought): void {
  const text = String((t.content ?? t.plugin) as string ?? '').replace(/\s+/g, ' ');
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
      const tokenId = (t.tokenId as string | undefined);
      const tokenStatus = (t.tokenStatus as string | undefined) ?? 'saved';
      console.log(tokenId ? c.green(`  🧩 ${tokenId} [${tokenStatus}] ${text}`) : c.dim(`  🧩 ${text}`));
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
  plugins: PluginInfo[] = [];
  onApproval: (req: ApprovalRequest) => void = (req) => this.answer(req.id, false);
  routeTelemetry?: RouteTelemtry;
  /** Tool-scoped agent lane (e.g. 'hermes'). Undefined = full worker agent. */
  agent?: string;
  private waiters: Array<{ type: string; resolve: (m: WsMessage) => void }> = [];

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      // The server only accepts WebSocket upgrades from its own loopback origin. The local token (file, mode 0600; never printed) identifies this
      // client as the CLI, so the run is labeled and mirrored live in the dashboard terminal.
      const token = readLocalToken(DATA_DIR);
      this.ws = new WebSocket(WS_URL, { origin: new URL(HOST).origin, ...(token ? { headers: { [TOKEN_HEADER]: token } } : {}) });

      let resolved = false;
      const onError = (err: Error) => {
        if (!resolved) {
          resolved = true;
          reject(err);
        } else {
          console.log(c.red(`WebSocket error: ${err.message}`));
        }
      };

      this.ws.on('error', onError);
      this.ws.on('message', (raw) => {
        try {
          const msg = JSON.parse(raw.toString()) as WsMessage;
          if (msg.type === 'init') {
            const init = (msg.data ?? {}) as { sessionId?: string; models?: Model[]; plugins?: PluginInfo[]; config?: { model?: string } };
            this.sessionId = init.sessionId ?? '';
            this.models = init.models ?? [];
            this.plugins = init.plugins ?? [];
            this.model = init.config?.model ?? this.models[0]?.name ?? '';
            if (!resolved) {
              resolved = true;
              this.ws.removeListener('error', onError);
              resolve();
            }
          } else if (msg.type === 'thought') {
            printThought(msg.data as Thought);
          } else if (msg.type === 'approval_request') {
            this.onApproval(msg.data as ApprovalRequest);
          } else if (msg.type === 'stream') {
            process.stdout.write(String(msg.data));
          }
          const i = this.waiters.findIndex((w) => w.type === msg.type);
          if (i >= 0) this.waiters.splice(i, 1)[0].resolve(msg);
        } catch (parseErr) {
          console.log(c.red(`Error parsing WebSocket message: ${parseErr instanceof Error ? parseErr.message : String(parseErr)}`));
        }
      });
    });
  }

  wait(type: string): Promise<WsMessage> {
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
    let { data: r } = await Promise.race([
      done,
      new Promise<WsMessage>((_, reject) =>
        setTimeout(() => reject(new Error('Run timeout: server did not respond within 60 minutes')), 60 * 60 * 1000)
      )
    ]);
    console.log();
    // The final answer is always printed, including after an evidence-check retry or a FLAGGED replacement.
    const result = r as Record<string, unknown>;
    if (Array.isArray(result.evidence_conflicts) && result.evidence_conflicts.length) {
      console.log(c.yellow(`  ⚖ evidence check: the first answer conflicted with this run's tool results (${String((result.evidence_conflicts as unknown[])[0]).slice(0, 200)}); final answer below.`));
    }
    // A streamed (local chat) answer is already on screen token by token; do not print it again.
    if (result.success) console.log(`${c.green('✓')} ${(result.streamed as boolean) ? 'done' : String(result.result ?? '').trim() || '(the agent returned no answer text)'}`);
    else console.log(c.red(`✗ ${result.error ?? 'the run failed without an error message'}`));
    if (result.steps !== undefined) {
      console.log(c.dim(`  ${result.steps} step(s) · ${result.tool_calls} tool call(s) · ${result.tokens} tokens · ${usd(result.cost_usd as number)} · ${(((result.duration_ms as number) ?? 0) / 1000).toFixed(1)}s · run ${String(result.run_id).slice(0, 8)}`));
    }
    const routed = routeLabel(result.route);
    if (routed) console.log(c.dim(`  ${routed}`));
    await this.files(true);
    return Boolean(result.success);
  }

  async files(quiet = false): Promise<void> {
    try {
      const res = await fetch(`${HOST}/api/sessions/${this.sessionId}/files`);
      if (!res.ok) throw await httpError(res);
      const { files } = (await res.json()) as { files: Array<{ path: string; size: number }> };
      if (!files?.length) {
        if (!quiet) console.log(c.dim('  (workspace empty)'));
        return;
      }
      console.log(c.bold('  Workspace files:'));
      for (const f of files) console.log(`    ${f.path} ${c.dim(`${f.size} B`)}`);
      console.log(c.dim(`    ${path.join(__dirname, 'workspaces', this.sessionId)}`));
    } catch (err) {
      console.log(c.red(`Error listing files: ${err instanceof Error ? err.message : String(err)}`));
    }
  }

  async cat(file: string): Promise<void> {
    try {
      const res = await fetch(`${HOST}/api/sessions/${this.sessionId}/files/content?path=${encodeURIComponent(file)}`);
      if (!res.ok) throw await httpError(res);
      const body = (await res.json()) as { content?: string; error?: string };
      console.log(body.content ?? c.red(body.error ?? 'error'));
    } catch (err) {
      console.log(c.red(`Error reading file: ${err instanceof Error ? err.message : String(err)}`));
    }
  }
}

function printApproval(req: ApprovalRequest): void {
  console.log(c.yellow(`\n  ⚖ APPROVAL: ${req.tool} — ${req.reason}`));
  console.log(c.dim(`    ${JSON.stringify(req.args).slice(0, 300)}`));
}

const CONVOY_TERMINAL = new Set(['COMPLETED', 'PARTIAL', 'FAILED', 'REJECTED', 'EXPIRED', 'CANCELLED']);
const usdOrUnmeasured = (n: unknown): string => (typeof n === 'number' ? usd(n) : 'unmeasured');

function printConvoy(cv: any): void {
  const live = !['PLANNED', 'PENDING', 'REJECTED', 'EXPIRED', 'CANCELLED'].includes(cv.state);
  console.log(`${(live ? c.red : c.cyan)(`[${modeLabel(cv.state as ConvoyState)}]`)} ${c.bold(cv.goal)} ${c.dim(`${String(cv.id).slice(0, 8)} · ${cv.state}${cv.outcome ? ` · ${cv.outcome}` : ''}`)}`);
  const plan = cv.plan;
  if (plan) {
    for (const w of plan.workers) console.log(`    ${c.dim(`wave ${w.wave}`)} ${w.name} ${c.dim(`on ${w.model ?? 'no model'} · tools ${w.tools.join(', ') || 'none'} · ${w.permission} · est ${usdOrUnmeasured(w.estimated_cost_usd)}`)}`);
    const u = plan.budget_use;
    console.log(c.dim(`    budget: ${u.worst_case_workers}/${plan.budget.max_workers} workers possible · est ${usdOrUnmeasured(u.estimated_cost_usd)} (worst ${usdOrUnmeasured(u.worst_case_cost_usd)}) of $${plan.budget.max_cost_usd} · up to ${u.estimated_tool_calls}/${plan.budget.max_tool_calls} tool calls`));
    for (const a of plan.added_by_mayor ?? []) console.log(c.dim(`    added by the Mayor: ${a.id} (${a.reason})`));
    if (plan.escalation) console.log(c.dim(`    fallback: ${plan.escalation.model} if ${plan.escalation.when}`));
    for (const w of plan.warnings ?? []) console.log(c.yellow(`    note: ${w}`));
    for (const r of plan.blocked_reasons) console.log(c.red(`    blocked: ${r}`));
  }
  if (cv.policy) console.log(c.dim(`    policy: ${cv.policy.decision} · risk ${cv.policy.risk} · mode ${String(plan?.think_mode ?? 'observe').toUpperCase()}`));
  for (const t of cv.learned_tokens ?? []) console.log(c.dim(`    learned ${t.id} ${t.kind} ${String(t.status).toUpperCase()}: ${t.title}`));
  if (cv.review && cv.review.state !== 'not_required') console.log(c.dim(`    outcome review: ${cv.review.state}${cv.review.decided_by ? ` by ${cv.review.decided_by}` : ' (waiting for a human)'}`));
  if (cv.approval) console.log(c.dim(`    approval: ${cv.approval.state}${cv.approval.decided_by ? ` by ${cv.approval.decided_by}` : ` until ${new Date(cv.approval.expires_at).toISOString()}`}`));
  if (cv.grounding) console.log((cv.grounding.status === 'GROUNDED' ? c.green : c.red)(`    ${cv.grounding.status}${(cv.grounding.unsupported ?? []).map((x: any) => `\n      ${x.kind}: ${x.claim}`).join('')}`));
  if (cv.final_answer) console.log(`    ${c.green('answer:')} ${String(cv.final_answer).slice(0, 400)}`);
  if (cv.error) console.log(c.red(`    ${cv.error}`));
  if (live && typeof cv.cost_usd === 'number') console.log(c.dim(`    ${usd(cv.cost_usd)} · ${cv.tool_calls} tool call(s) · ${cv.tokens} tokens`));
}

async function convoyCommand(args: string[], client: Client): Promise<void> {
  const sub = (args[0] ?? 'list').toLowerCase();
  const api = async (path: string, method = 'GET', body?: unknown): Promise<any> => {
    const token = readLocalToken(DATA_DIR);
    const res = await fetch(`${HOST}/api/convoys${path}`, { method, headers: { 'content-type': 'application/json', ...(token ? { [TOKEN_HEADER]: token } : {}) }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
    const data = (await res.json()) as any;
    if (!res.ok) throw new Error(data?.error ?? `HTTP ${res.status}`);
    return data;
  };
  const resolveId = async (prefix: string | undefined): Promise<string> => {
    const { convoys } = await api('');
    const hit = prefix && convoys.find((x: any) => x.id.startsWith(prefix));
    if (!hit) throw new Error('Usage: /convoy <show|submit|approve|reject> ID (first characters from /convoy list)');
    return hit.id;
  };
  try {
    if (sub === 'plan') {
      const rest = args.slice(1);
      let mode: string | undefined;
      const flag = rest.indexOf('--mode');
      if (flag >= 0) { mode = rest[flag + 1]; rest.splice(flag, 2); }
      const goal = rest.join(' ').trim();
      if (!goal) return console.log(c.red('Usage: /convoy plan [--mode observe|learn] GOAL'));
      const { convoy } = await api('/plan', 'POST', { goal, model: client.model, ...(mode ? { mode } : {}) });
      printConvoy(convoy);
      console.log(c.dim(convoy.plan.executable ? `  Next: /convoy submit ${convoy.id.slice(0, 8)} (queues it for your approval; still runs nothing)` : '  This plan cannot run as it is (see blocked above).'));
    } else if (sub === 'list') {
      const { convoys } = await api('');
      if (!convoys.length) return console.log(c.dim('  (no convoys yet; /convoy plan GOAL)'));
      for (const x of convoys) console.log(`  ${x.id.slice(0, 8)} ${(['PLANNED', 'PENDING', 'REJECTED', 'EXPIRED', 'CANCELLED'].includes(x.state) ? c.cyan : c.red)(modeLabel(x.state).padEnd(40))} ${x.state.padEnd(9)} ${usd(x.cost_usd).padStart(8)}  ${String(x.goal).slice(0, 60)}`);
    } else if (sub === 'board') {
      const board = await api('/board');
      for (const lane of ['ready', 'open', 'review', 'finished'] as const) {
        const cards = board.lanes[lane] as any[];
        console.log(`${({ ready: c.cyan, open: c.yellow, review: c.magenta, finished: c.green } as const)[lane](c.bold(lane.toUpperCase()))} ${c.dim(`(${board.counts[lane]})`)}`);
        for (const card of cards.slice(0, 8)) console.log(`    ${String(card.convoy_id).slice(0, 8)} ${card.name} ${c.dim(`on ${card.model ?? 'no model'} · ${card.detail} · ${String(card.goal).slice(0, 50)}`)}`);
      }
      if (board.not_ready) console.log(c.dim(`  ${board.not_ready} worker(s) not on the board yet (plan waiting for approval, or waiting for a worker they depend on)`));
    } else if (sub === 'review') {
      const id = await resolveId(args[1]);
      const decision = args[2];
      if (decision !== 'accept' && decision !== 'reject') return console.log(c.red('Usage: /convoy review ID accept|reject [NOTE]'));
      client.send({ type: 'convoy_review', id, decision, note: args.slice(3).join(' ') });
      await new Promise((r) => setTimeout(r, 800));
      const { convoy } = await api(`/${id}`);
      console.log(convoy.review?.state === (decision === 'accept' ? 'accepted' : 'rejected') ? c.green(`  outcome ${convoy.review.state} by ${convoy.review.decided_by}`) : c.red(`  not recorded (review is ${convoy.review?.state ?? 'absent'}; a finished convoy with a result can be reviewed once)`));
    } else if (sub === 'show') {
      const { convoy } = await api(`/${await resolveId(args[1])}`);
      printConvoy(convoy);
      for (const r of convoy.runs ?? []) console.log(c.dim(`    run ${String(r.id).slice(0, 8)} ${r.model} ${r.status} ${usd(r.cost_usd)} · ${r.steps.filter((s: any) => s.kind === 'tool').map((s: any) => `${s.name}${s.ok ? '' : ' FAILED'}`).join(', ') || 'no tools'}`));
      for (const e of convoy.events) console.log(c.dim(`    ${e.seq}. ${e.state} by ${e.by} #${String(e.hash).slice(0, 8)} ${e.note}`));
    } else if (sub === 'submit') {
      const { convoy } = await api(`/${await resolveId(args[1])}/submit`, 'POST');
      printConvoy(convoy);
      console.log(c.dim(`  Waiting for your decision: /convoy approve ${convoy.id.slice(0, 8)} or /convoy reject ${convoy.id.slice(0, 8)}`));
    } else if (sub === 'reject') {
      const { convoy } = await api(`/${await resolveId(args[1])}/reject`, 'POST', {});
      printConvoy(convoy);
    } else if (sub === 'approve') {
      const id = await resolveId(args[1]);
      client.send({ type: 'convoy_approve', id });
      console.log(c.red('  LIVE EXECUTION: approved; real workers are starting (tool approvals will still ask).'));
      let last = '';
      for (let i = 0; i < 1800; i += 1) {
        await new Promise((r) => setTimeout(r, 1000));
        const { convoy } = await api(`/${id}`);
        if (convoy.state !== last) { last = convoy.state; console.log(c.dim(`  ${convoy.state}`)); }
        if (CONVOY_TERMINAL.has(convoy.state)) { printConvoy(convoy); return; }
      }
      console.log(c.yellow('  Still running after 30 minutes; check /convoy show.'));
    } else console.log(c.red('Usage: /convoy plan [--mode learn] GOAL | list | board | show ID | submit ID | approve ID | reject ID | review ID accept|reject'));
  } catch (err) {
    console.log(c.red(`  ${err instanceof Error ? err.message : String(err)}`));
  }
}

async function showRuns(): Promise<void> {
  try {
    const res = await fetch(`${HOST}/api/runs?limit=15`);
    if (!res.ok) throw await httpError(res);
    const { runs } = (await res.json()) as { runs: any[] };
    if (!runs?.length) return console.log(c.dim('  (no runs yet)'));
    for (const r of runs) {
      const color = r.status === 'completed' ? c.green : r.status === 'running' ? c.cyan : r.status === 'stopped' ? c.yellow : c.red;
      console.log(`  ${r.id.slice(0, 8)} ${color(r.status.padEnd(9))} ${usd(r.cost_usd).padStart(8)} ${c.dim(`${((r.duration_ms ?? 0) / 1000).toFixed(1)}s`.padStart(6))}  ${r.goal.slice(0, 70)}`);
    }
  } catch (err) {
    console.log(c.red(`Error fetching runs: ${err instanceof Error ? err.message : String(err)}`));
  }
}

async function showRun(prefix: string): Promise<void> {
  try {
    const res = await fetch(`${HOST}/api/runs?limit=500`);
    if (!res.ok) throw await httpError(res);
    const { runs } = (await res.json()) as { runs: any[] };
    const match = prefix && runs?.find((r) => r.id.startsWith(prefix));
    if (!match) return console.log(c.red('Usage: /run ID (first characters from /runs)'));
    const runRes = await fetch(`${HOST}/api/runs/${match.id}`);
    if (!runRes.ok) throw await httpError(runRes);
    const run = (await runRes.json()) as any;
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
  } catch (err) {
    console.log(c.red(`Error: ${err instanceof Error ? err.message : String(err)}`));
  }
}

async function interactiveModelSelect(client: Client): Promise<boolean> {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    const cleanup = () => {
      rl.removeAllListeners();
      rl.close();
    };

    rl.on('error', (err) => {
      cleanup();
      console.log(c.red(`Error: ${err instanceof Error ? err.message : String(err)}`));
      resolve(false);
    });

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
      cleanup();
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
  ${c.dim('kudbee spend [--json]')}  what was spent per day, model and profile, and the spend limits
  ${c.dim('kudbee audit [--verify] [--kind K] [--run ID] [--limit N] [--json]')}  who approved what, and what runs cost; --verify checks the log was not altered
  ${c.dim('kudbee tokens health [--json]')}  how many tokens are used, waiting or stale
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

${c.bold('CONVOYS (Mayor plans, human approves)')}
  /convoy plan [--mode observe|learn] GOAL   PLAN ONLY: the Mayor plans workers, budget and policy; nothing runs
  /convoy [list]      one line per convoy, marked PLAN ONLY or LIVE EXECUTION
  /convoy show ID     plan, policy, approval, runs, evidence chain
  /convoy submit ID   queue the plan for approval (still runs nothing)
  /convoy board       READY / OPEN / REVIEW / FINISHED for every agent
  /convoy review ID accept|reject [NOTE]   accept or reject what a finished convoy produced (you are the human)
  /convoy approve ID  approve AND run it LIVE (you are the human; tool approvals still ask)
  /convoy reject ID   reject a pending plan

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
  /capacity           server load: running agents, pending approvals, CPU, memory
  /config             this session's model, provider, agent, session id, connection
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
      console.log(args[0]?.toLowerCase() === 'all' ? HELP : quickHelp(c));
      break;
    case '/models': {
      // Enterprise: show model categories with metadata
      const mercury = client.models.filter((m) => m.agent);
      const local = client.models.filter((m) => !m.agent);

      if (mercury.length) {
        console.log(c.bold('\n  🤖 Cloud agents (they can use tools)'));
        for (const m of mercury) {
          const mark = m.name === client.model ? c.green('●') : ' ';
          console.log(`    ${mark} ${m.name} ${c.dim(cloudModelNote(m.name, m.provider))}`);
        }
      }
      if (local.length) {
        console.log(c.bold('\n  💻 Local models (on this machine)'));
        for (const m of local) {
          const mark = m.name === client.model ? c.green('●') : ' ';
          const cheapRoute = sameLocalModel(LOCAL_MODEL, m.name) ? c.dim(' (cheap route)') : '';
          console.log(`    ${mark} ${m.name} ${c.dim(localModelNote(m.provider))}${cheapRoute}`);
        }
      }
      const localRouteReady = local.some((m) => sameLocalModel(LOCAL_MODEL, m.name));
      if (!localRouteReady) {
        console.log(c.bold('\n  💻 Local models (on this machine)'));
        console.log(c.red(`    ✗ ${LOCAL_MODEL} is not installed — auto-routing falls back to Mercury-2 for simple goals`));
        console.log(c.dim('      Set THINKBOX_LOCAL_MODEL to a model from `ollama list` (nothing is pulled for you).'));
      }
      console.log(c.dim(`\n  ${MODELS_PRIVACY_NOTE}`));
      console.log(c.dim(`  Use: /model NAME, for example /model ${client.models.find((m) => m.agent)?.name ?? LOCAL_MODEL}`));
      break;
    }
    case '/model':
      if (!args[0]) {
        console.log(`Current model: ${c.bold(client.model || '(none)')}`);
        console.log('Available:');
        for (const m of client.models) console.log(`    ${m.name === client.model ? c.green('●') : ' '} ${m.name}`);
        console.log(c.dim('Usage: /model NAME'));
      } else if (!client.models.some((m) => m.name === args[0])) {
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
      try {
        const res = await fetch(`${HOST}/api/agents`);
        if (!res.ok) throw await httpError(res);
        const { agents } = (await res.json()) as { agents: Array<{ id: string; name: string; description: string; allowedTools: string[] }> };
        console.log(c.bold('\n  Worker agent (default)') + c.dim(' — full tool access'));
        for (const a of agents) {
          const mark = client.agent === a.id ? c.green('●') : ' ';
          console.log(`  ${mark} ${c.bold(a.name)} ${c.dim(`(/agent ${a.id})`)}`);
          console.log(c.dim(`      ${a.description}`));
          console.log(c.dim(`      tools: ${a.allowedTools.join(', ')}`));
        }
        console.log(c.dim('\n  Use: /agent NAME  or  /agent  (clears — back to default worker)'));
      } catch (err) {
        console.log(c.red(`Error listing agents: ${err instanceof Error ? err.message : String(err)}`));
      }
      break;
    }
    case '/agent':
      if (!args[0]) {
        client.agent = undefined;
        console.log(c.green('🤖 Agent → default worker (full tools)'));
      } else {
        try {
          const res = await fetch(`${HOST}/api/agents`);
          if (!res.ok) throw await httpError(res);
          const { agents } = (await res.json()) as { agents: Array<{ id: string; name: string }> };
          const match = agents?.find((a) => a.id === args[0].toLowerCase());
          if (!match) {
            console.log(c.red(`Unknown agent "${args[0]}". See /agents.`));
          } else {
            client.agent = match.id;
            console.log(c.green(`🤖 Agent → ${match.name} (read-only tool lane)`));
          }
        } catch (err) {
          console.log(c.red(`Error selecting agent: ${err instanceof Error ? err.message : String(err)}`));
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
        let result: unknown;
        try {
          const response = await Promise.race<WsMessage>([
            done,
            new Promise<WsMessage>((_, reject) =>
              setTimeout(() => reject(new Error('Plugin execution timeout')), 30000)
            ),
          ]);
          result = response?.data;
          if (!result) throw new Error('No response data from plugin');
        } catch (timeoutErr) {
          console.log(c.red(`Error: ${timeoutErr instanceof Error ? timeoutErr.message : 'Plugin execution timeout (30s)'}`));
          break;
        }
        const pluginResult = result as Record<string, unknown>;
        if (pluginResult?.success) {
          console.log(c.green(`✓ ${pluginName} executed successfully`));
          if (pluginResult.output) {
            const formatted = typeof pluginResult.output === 'string'
              ? pluginResult.output
              : JSON.stringify(pluginResult.output, null, 2);
            console.log(c.dim('Output:'));
            console.log(`  ${formatted.split('\n').join('\n  ')}`);
          }
        } else {
          console.log(c.red(`✗ Plugin execution failed: ${pluginName}`));
          if (pluginResult?.error) console.log(c.dim(`  Error: ${pluginResult.error}`));
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
    case '/status': {
      try {
        const res = await fetch(`${HOST}/api/health`);
        if (!res.ok) throw await httpError(res);
        console.log(await res.json());
      } catch (err) {
        console.log(c.red(`Error checking status: ${err instanceof Error ? err.message : String(err)}`));
      }
      break;
    }
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
    case '/convoy':
      await convoyCommand(args, client);
      break;
    case '/memory': {
      try {
        const query = args.join(' ').trim();
        const params = new URLSearchParams({ limit: '10', ...(query ? { q: query } : {}) });
        const res = await fetch(`${HOST}/api/memory?${params}`);
        if (!res.ok) throw await httpError(res);
        const { items, backend } = (await res.json()) as { items: any[]; backend: string };
        if (!items?.length) console.log(c.dim(`  (no memories${query ? ` match "${query}"` : ''})`));
        if (query && items?.length) console.log(c.dim(`  search backend: ${backend}`));
        const color: Record<string, (s: string) => string> = { verified: c.green, org: c.yellow, task: c.cyan };
        for (const item of items) {
          console.log(`  ${(color[item.layer] ?? c.dim)(item.layer.padEnd(8))} ${item.title}${item.score !== undefined ? c.dim(` · ${Number(item.score).toFixed(2)}`) : ''}`);
          console.log(c.dim(`           ${item.id} — ${item.content.slice(0, 110)}`));
        }
      } catch (err) {
        console.log(c.red(`Error fetching memories: ${err instanceof Error ? err.message : String(err)}`));
      }
      break;
    }
    case '/notes': {
      try {
        const layer = args[0] || '';
        const params = new URLSearchParams({ limit: '20', sessionId });
        if (layer && ['session', 'task', 'org', 'verified'].includes(layer)) {
          params.set('layer', layer);
        }
        const res = await fetch(`${HOST}/api/memory/notes?${params}`);
        if (!res.ok) throw await httpError(res);
        const data = (await res.json()) as any;
        if (!data.notes?.length) {
          console.log(c.dim(`  (no notes${layer ? ` in ${layer}` : ''})`));
          break;
        }
        for (const note of data.notes as any[]) {
          const layerColor = { session: c.cyan, task: c.magenta, org: c.yellow, verified: c.green }[note.layer as string] || c.dim;
          console.log(`  ${layerColor(note.layer.padEnd(8))} ${note.title}`);
          console.log(c.dim(`    ${note.id} — ${note.content.slice(0, 80)}`));
        }
      } catch (err) {
        console.log(c.red(`Error fetching notes: ${err instanceof Error ? err.message : String(err)}`));
      }
      break;
    }

    case '/remember': {
      try {
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
        if (!res.ok) throw await httpError(res);
        const item = (await res.json()) as any;
        console.log(c.green(`  ✓ saved ${layer} note: ${item.id}`));
      } catch (err) {
        console.log(c.red(`Error saving note: ${err instanceof Error ? err.message : String(err)}`));
      }
      break;
    }

    case '/forget': {
      try {
        const query = args.join(' ').trim();
        if (!query) {
          console.log(c.red('Usage: /forget ID|QUERY'));
          break;
        }
        const res = await fetch(`${HOST}/api/memory/notes/${encodeURIComponent(query)}?sessionId=${encodeURIComponent(sessionId)}`, { method: 'DELETE' });
        const result = (await res.json()) as any;
        console.log(res.ok ? c.green(`  ✓ deleted: ${result.deleted ?? 'note'}`) : c.red(`  ✗ ${result.error}`));
      } catch (err) {
        console.log(c.red(`Error deleting note: ${err instanceof Error ? err.message : String(err)}`));
      }
      break;
    }
    case '/algo': {
      try {
        const [action = 'status', target, maybeNetwork] = args;
        const network = [target, maybeNetwork].find((v) => v === 'mainnet' || v === 'testnet') ?? 'testnet';
        const aliases: Record<string, string> = { app: 'application', tx: 'transaction', txs: 'account_transactions', history: 'account_transactions' };
        const resolved = aliases[action] ?? action;
        const params = new URLSearchParams({ action: resolved, network });
        if (target && target !== network) {
          params.set(['account', 'account_transactions'].includes(resolved) ? 'address' : resolved === 'transaction' ? 'txid' : 'id', target);
        }
        const res = await fetch(`${HOST}/api/algorand?${params}`);
        if (!res.ok) throw await httpError(res);
        const body = (await res.json()) as Record<string, unknown>;
        console.log(JSON.stringify(body, null, 2));
      } catch (err) {
        console.log(c.red(`Error: ${err instanceof Error ? err.message : String(err)}`));
      }
      break;
    }
    case '/promote': {
      try {
        const id = args[0]?.startsWith('org/') ? args[0] : `org/${args[0] ?? ''}`;
        const res = await fetch(`${HOST}/api/memory/promote`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) });
        if (!res.ok) throw await httpError(res);
        const item = (await res.json()) as any;
        console.log(c.green(`  promoted → ${item.id}`));
      } catch (err) {
        console.log(c.red(`Error promoting note: ${err instanceof Error ? err.message : String(err)}`));
      }
      break;
    }
    case '/run':
      await showRun(args[0] ?? '');
      break;
    case '/metrics': {
      try {
        const res = await fetch(`${HOST}/api/stats`);
        if (!res.ok) throw await httpError(res);
        const m = (await res.json()) as any;
        console.log(`  Runs ${m.runs_today} today / ${m.runs_total} total · success ${m.success_rate ?? '—'}% · p50 ${(m.p50_ms / 1000).toFixed(1)}s · p95 ${(m.p95_ms / 1000).toFixed(1)}s`);
        console.log(`  Tokens today ${m.tokens_today} · cost today ${usd(m.cost_today_usd)} · all-time ${usd(m.cost_total_usd)}${m.budget_usd ? ` · budget ${usd(m.budget_usd)}` : ''}`);
        for (const [name, t] of Object.entries(m.tools as Record<string, any>)) {
          console.log(c.dim(`  ${name.padEnd(12)} ${t.calls} calls · ${t.success_rate}% ok · ${t.avg_ms}ms avg${t.denied ? ` · ${t.denied} denied` : ''}`));
        }
      } catch (err) {
        console.log(c.red(`Error fetching metrics: ${err instanceof Error ? err.message : String(err)}`));
      }
      break;
    }
    case '/config': {
      const provider = client.models.find((m) => m.name === client.model)?.provider;
      const config = {
        model: client.model,
        provider: provider ?? null,
        agent: client.agent ?? null,
        sessionId: client.sessionId,
        wsConnected: client.ws?.readyState === 1,
        url: HOST,
      };
      console.log(`${c.bold('Configuration:')}\n${JSON.stringify(config, null, 2)}`);
      break;
    }
    case '/capacity': {
      try {
        const res = await fetch(`${HOST}/api/stats`);
        if (!res.ok) throw await httpError(res);
        const cap = ((await res.json()) as any).capacity;
        if (!cap) throw new Error('the server reported no capacity data');
        console.log(c.bold('  Capacity (server)'));
        console.log(`  Agents running: ${cap.running_agents} of ${cap.connected_sessions} connected session(s)`);
        console.log(`  Pending approvals: ${cap.pending_approvals}`);
        console.log(`  Server CPU: ${cap.server_cpu_pct}% · RSS ${cap.server_rss_mb} MB`);
        console.log(`  System memory: ${cap.system_mem_used_pct}% of ${cap.system_mem_total_gb} GB · load ${(cap.load_avg ?? []).join(' / ')} · ${cap.cores} cores`);
      } catch (err) {
        console.log(c.red(`Error fetching capacity: ${err instanceof Error ? err.message : String(err)}`));
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
        let answered = false;
        rl.on('error', () => {
          if (!answered) {
            answered = true;
            rl.close();
            console.log(c.red('  Error reading input'));
          }
        });
        rl.question(c.cyan('\n  Pick (number or search): '), async (input) => {
          if (answered) return;
          answered = true;
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
  // A live-data lookup goes to the installed local model the measured table qualifies for lookups (gemma3:4b at the time of writing), when there is one;
  // otherwise the configured local model, as before.
  const lookupGoal = Boolean(matchRecipe(goal));
  const installedNames = client.models.filter((m) => !m.agent).map((m) => m.name);
  const measured = lookupGoal ? pickMeasured('lookup', installedNames, loadMeasurements()) : null;
  const measuredLocal = measured?.model ? client.models.find((m) => !m.agent && sameLocalModel(measured.model!, m.name)) : undefined;
  const local = measuredLocal ?? client.models.find((m) => !m.agent && sameLocalModel(LOCAL_MODEL, m.name));

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

  // A common live question (open PRs, workspace files, a named file) is a local recipe: the server makes the lookup and the local model words the answer.
  const isComplex = isComplexGoal(goal) && !(local && matchRecipe(goal));
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
      routeReason: measuredLocal ? 'measured_lookup' : 'auto',
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
      console.log(c.dim(`  💡 [${complexity}] → ${telemetry.modelSelected}${saved}${telemetry.routeReason === 'measured_lookup' && measured ? ` — ${measured.reason}` : ''}`));
    }
  }

  return telemetry;
}


/** `kudbee spend [--json]`: what was spent, from every profile's saved runs (per day, per model, per profile), read-only. Limits: KUDBEE_DAILY_BUDGET_USD and KUDBEE_RUN_BUDGET_USD. */
function spendCommand(args: string[]): number {
  const json = args.includes('--json');
  const dir = path.join(DATA_DIR, 'profiles');
  const runs: SpendRun[] = []; const names: Record<string, string> = {};
  let ids: string[] = [];
  try { ids = fs.readdirSync(dir); } catch { /* none yet */ }
  for (const id of ids) {
    try { const list = JSON.parse(fs.readFileSync(path.join(dir, id, 'runs.json'), 'utf8')) as SpendRun[]; for (const r of Array.isArray(list) ? list : []) runs.push({ ...r, profile_id: r.profile_id ?? id }); } catch { /* no runs for this profile */ }
  }
  if (!runs.length) { console.log(c.dim(`No saved runs under ${dir} yet.`)); return 1; }
  const report = spendReport(runs, { names });
  const cfg = budgetConfig();
  if (json) { console.log(JSON.stringify({ ...report, budget: cfg }, null, 2)); return 0; }
  console.log(formatSpendReport(report));
  console.log(c.dim(`limits: daily ${cfg.daily ? formatUsd(cfg.daily) : 'off'} (KUDBEE_DAILY_BUDGET_USD) · per run ${cfg.run ? formatUsd(cfg.run) : 'off'} (KUDBEE_RUN_BUDGET_USD)`));
  return 0;
}

/** `kudbee audit [--verify] [--kind K] [--run ID] [--limit N] [--json]`: reads the same audit.db the server writes (read-only on the chain; nothing is added or removed). */
function auditCommand(args: string[]): number {
  const flag = (name: string): string | undefined => { const i = args.indexOf(name); if (i < 0) return undefined; const [, value] = args.splice(i, 2); return value; };
  const json = args.includes('--json'); if (json) args.splice(args.indexOf('--json'), 1);
  const verify = args.includes('--verify'); if (verify) args.splice(args.indexOf('--verify'), 1);
  const kind = flag('--kind'); const run = flag('--run'); const limit = Number(flag('--limit')) || 50;
  const file = path.join(DATA_DIR, 'audit.db');
  if (!fs.existsSync(file)) { console.log(c.red(`No audit log at ${file}.`)); console.log(c.dim('Start the Agent OS and approve or run something, then try again.')); return 1; }
  const log = new AuditLog(file);
  try {
    const verdict = log.chainStatus();
    if (verify) { console.log(json ? JSON.stringify(verdict) : verdict.ok ? c.green(`audit log intact: ${verdict.entries} entries, newest row ${verdict.head?.slice(0, 16)} (note it down to detect a later cut)`) : c.red(`audit log BROKEN at entry ${verdict.broken_at}: ${verdict.reason}`)); return verdict.ok ? 0 : 1; }
    const events = log.list({ limit, kind, run_id: run });
    if (json) { console.log(JSON.stringify({ events, chain: verdict }, null, 2)); return 0; }
    for (const e of events.reverse()) console.log(`${new Date(e.ts).toISOString().slice(0, 19)}  ${e.kind.padEnd(18)} ${e.actor.padEnd(10)} ${e.run_id ? e.run_id.slice(0, 8) : '        '}  ${e.summary}`);
    console.log(c.dim(`${events.length} shown, newest last, chain ${verdict.ok ? 'intact' : 'BROKEN'} (${verdict.entries} entries), ${file}`));
    return 0;
  } finally { log.close(); }
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
    if (sub === 'health') { const h = readHealth(store); console.log(json ? JSON.stringify(h, null, 2) : formatTokenHealth(h)); return 0; }
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
    console.log(c.red('usage: kudbee tokens list|show <TT-id>|links <TT-id>|health [--json]'));
    return 2;
  } finally {
    store.close();
  }
}

async function main(): Promise<void> {
  // A spawned CLI is stopped by a signal in tests; make that a clean exit so NODE_V8_COVERAGE is written (coverage only).
  installCoverageFlush();
  if (!isLoopbackUrl(HOST)) {
    console.error(c.red(`kudbee: KUDBEE_URL must point to this machine (127.0.0.1 or localhost); refusing ${HOST}`));
    process.exit(2);
  }
  // Reading tokens needs no server and no WebSocket.
  if (process.argv[2] === 'tokens' || process.argv[2] === 'token') process.exit(tokensCommand(process.argv.slice(3)));
  if (process.argv[2] === 'audit') process.exit(auditCommand(process.argv.slice(3)));
  if (process.argv[2] === 'spend') process.exit(spendCommand(process.argv.slice(3)));

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
    let answered = false;

    const cleanup = (approved: boolean) => {
      if (!answered) {
        answered = true;
        ask.removeAllListeners();
        ask.close();
        client.answer(req.id, approved);
      }
    };

    ask.on('error', () => cleanup(false));
    ask.question(c.yellow('    Approve? [y/N] '), (reply) => {
      cleanup(/^y(es)?$/i.test(reply.trim()));
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

  console.log(welcome(c, { session: client.sessionId.slice(0, 8), model: client.model, host: HOST }));
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout, prompt: c.yellow('kudbee› ') });
  rl.on('error', (err) => {
    console.log(c.red(`Error: ${err instanceof Error ? err.message : String(err)}`));
    process.exit(1);
  });
  rl.on('close', () => {
    process.exit(0);
  });
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
