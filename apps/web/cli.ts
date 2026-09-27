// kudbEE CLI — terminal client for kudbEE Agent OS (same WebSocket runtime as the dashboard).
//   kudbee                 interactive shell
//   kudbee "<goal>"        run one goal with the worker agent and exit
//   kudbee --yes "<goal>"  same, auto-approving gated tool calls (overwrites, new domains)
import { spawn } from 'node:child_process';
import readline from 'node:readline';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';

const HOST = process.env.KUDBEE_URL || 'http://localhost:3000';
const WS_URL = HOST.replace(/^http/, 'ws') + '/ws';
const __dirname = path.dirname(fileURLToPath(import.meta.url));

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
  if (await serverUp()) return;
  const logDir = path.join(os.homedir(), '.kudbee');
  fs.mkdirSync(logDir, { recursive: true });
  const log = fs.openSync(path.join(logDir, 'server.log'), 'a');
  process.stdout.write(c.dim(`Starting kudbEE Agent OS (${HOST})… `));
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
  private waiters: Array<{ type: string; resolve: (m: Msg) => void }> = [];

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(WS_URL);
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
    console.log(c.dim(`▶ ${this.model} working…`));
    const done = this.wait('result');
    this.send({ type: 'run_goal', goal, model: this.model });
    const { data: r } = await done;
    console.log();
    if (r.success) console.log(`${c.green('✓')} ${r.result}`);
    else console.log(c.red(`✗ ${r.error}`));
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

const HELP = `${c.bold('kudbEE CLI')} — type a goal for the worker agent, or a command:
  /models            list models        /model NAME   switch model
  /plugins           list plugins       /files        list workspace files
  /runs              run history        /run ID       step-by-step timeline
  /metrics           agent metrics      /cat PATH     print a file
  /memory [QUERY]    memory / search    /remember TITLE - TEXT   save org note
  /promote org/ID    promote a note to verified knowledge
  /algo status|account ADDR|asset ID|app ID|tx TXID|txs ADDR [mainnet]   read-only Algorand
  /status            server health
  /open              dashboard URL      /stop         stop the running goal
  /help              this help          /quit         exit
Example: ${c.cyan('Read https://hnrss.org/frontpage and write top5.md with the 5 top stories')}`;

async function handleCommand(client: Client, line: string): Promise<boolean> {
  const [cmd, ...args] = line.split(/\s+/);
  switch (cmd) {
    case '/help':
      console.log(HELP);
      break;
    case '/models':
      for (const m of client.models) {
        const mark = m.name === client.model ? c.green('●') : ' ';
        console.log(`  ${mark} ${m.name} ${c.dim(`[${m.provider ?? 'ollama'}]${m.agent ? ' tool-using worker agent' : ''}`)}`);
      }
      break;
    case '/model':
      if (!client.models.some((m) => m.name === args[0])) console.log(c.red(`Unknown model. Try /models`));
      else {
        client.model = args[0];
        console.log(`Model → ${c.bold(client.model)}`);
      }
      break;
    case '/plugins':
      for (const p of client.plugins) console.log(`  ${p.icon ?? '🔌'} ${p.name} ${c.dim(`[${p.permission}] ${p.description}`)}`);
      break;
    case '/files':
      await client.files();
      break;
    case '/cat':
      await client.cat(args.join(' '));
      break;
    case '/status':
      console.log(await (await fetch(`${HOST}/api/health`)).json());
      break;
    case '/runs':
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
    case '/remember': {
      const text = args.join(' ').trim();
      if (!text) {
        console.log(c.red('Usage: /remember TITLE - TEXT'));
        break;
      }
      const [title, ...rest] = text.split(/\s+[-—:]\s+/);
      const res = await fetch(`${HOST}/api/memory`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ layer: 'org', title, content: rest.join(' - ') || text }),
      });
      const item = (await res.json()) as any;
      console.log(res.ok ? c.green(`  saved ${item.id} (${item.path})`) : c.red(`  ${item.error}`));
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
    case '/quit':
    case '/exit':
      return false;
    default:
      console.log(c.red(`Unknown command ${cmd}. Type /help`));
  }
  return true;
}

async function main(): Promise<void> {
  await ensureServer();
  const client = new Client();
  await client.connect();

  const argv = process.argv.slice(2);
  const autoYes = argv[0] === '--yes' || argv[0] === '-y';
  if (autoYes) argv.shift();
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
    await handleCommand(client, goal);
    client.ws.close();
    process.exit(0);
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
  let busy = false;
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
    if (!line || busy) return rl.prompt();
    busy = true;
    try {
      if (line.startsWith('/')) {
        if (!(await handleCommand(client, line))) return rl.close();
      } else {
        await client.run(line);
      }
    } catch (err) {
      console.log(c.red(String(err)));
    }
    busy = false;
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
