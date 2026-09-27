// Durable run history for kudbEE Agent OS: every goal becomes a RunRecord with a step-level trace.
// Stored as one JSON file (atomic rename) so history survives browser reloads and server restarts.
import fs from 'fs';
import path from 'path';
import type { AgentEvent } from './agent.ts';

export type RunStatus = 'running' | 'completed' | 'failed' | 'stopped';

export interface RunRecord {
  id: string;
  session_id: string;
  goal: string;
  model: string;
  provider: string;
  status: RunStatus;
  started_at: number;
  ended_at?: number;
  duration_ms?: number;
  steps: AgentEvent[];
  current_step: number;
  current_action?: string;
  tool_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
  approvals: { approved: number; denied: number };
  files: string[];
  result?: string;
  error?: string;
  failure_kind?: string;
}

const MAX_RUNS = 500;

export function classifyFailure(error: string | undefined, stopped: boolean): string | undefined {
  if (stopped) return 'stopped';
  if (!error) return undefined;
  if (/budget/i.test(error)) return 'budget';
  if (/step limit/i.test(error)) return 'step_limit';
  if (/Inception API HTTP|timeout|aborted/i.test(error)) return 'api_error';
  if (/fetch failed|ENOTFOUND|ECONNREFUSED|network/i.test(error)) return 'network';
  return 'error';
}

function percentile(sorted: number[], p: number): number {
  if (!sorted.length) return 0;
  return sorted[Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length))];
}

function startOfToday(): number {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
}

export class RunStore {
  private runs: RunRecord[] = [];
  private saveTimer: NodeJS.Timeout | null = null;
  private readonly file: string;

  constructor(file: string) {
    this.file = file;
    fs.mkdirSync(path.dirname(file), { recursive: true });
    try {
      this.runs = JSON.parse(fs.readFileSync(file, 'utf8')) as RunRecord[];
      // A run still marked running at boot was interrupted by a restart.
      for (const run of this.runs) {
        if (run.status === 'running') {
          run.status = 'failed';
          run.error = 'Interrupted by server restart';
          run.failure_kind = 'interrupted';
        }
      }
    } catch {
      this.runs = [];
    }
  }

  create(run: RunRecord): RunRecord {
    this.runs.push(run);
    if (this.runs.length > MAX_RUNS) this.runs.splice(0, this.runs.length - MAX_RUNS);
    this.save();
    return run;
  }

  get(id: string): RunRecord | undefined {
    return this.runs.find((run) => run.id === id);
  }

  list(limit = 50): RunRecord[] {
    return this.runs.slice(-limit).reverse();
  }

  addEvent(run: RunRecord, event: AgentEvent): void {
    run.steps.push(event);
    run.current_step = event.step;
    if (event.kind === 'model') {
      run.prompt_tokens += event.prompt_tokens;
      run.completion_tokens += event.completion_tokens;
      run.cost_usd += event.cost_usd;
      run.current_action = event.tool_calls.length ? event.tool_calls.join(', ') : 'answering';
    } else {
      run.tool_calls += 1;
      run.current_action = event.name;
      if (event.approval) run.approvals[event.approval] += 1;
      if (event.name === 'write_file' && event.ok && typeof event.args.path === 'string' && !run.files.includes(event.args.path)) {
        run.files.push(event.args.path);
      }
    }
    this.save();
  }

  finish(run: RunRecord, updates: Partial<RunRecord>): void {
    Object.assign(run, updates);
    run.ended_at = Date.now();
    run.duration_ms = run.ended_at - run.started_at;
    run.current_action = undefined;
    this.save();
  }

  costSince(since: number): number {
    return this.runs.filter((run) => run.started_at >= since).reduce((sum, run) => sum + run.cost_usd, 0);
  }

  costToday(): number {
    return this.costSince(startOfToday());
  }

  stats(): Record<string, unknown> {
    const finished = this.runs.filter((run) => run.status !== 'running');
    const today = this.runs.filter((run) => run.started_at >= startOfToday());
    const durations = finished.map((run) => run.duration_ms ?? 0).sort((a, b) => a - b);
    const succeeded = finished.filter((run) => run.status === 'completed').length;
    const failures: Record<string, number> = {};
    for (const run of finished) if (run.failure_kind) failures[run.failure_kind] = (failures[run.failure_kind] ?? 0) + 1;

    const tools: Record<string, { calls: number; ok: number; total_ms: number; denied: number }> = {};
    const models: Record<string, { calls: number; total_ms: number }> = {};
    for (const run of this.runs) {
      for (const step of run.steps) {
        if (step.kind === 'tool') {
          const t = (tools[step.name] ??= { calls: 0, ok: 0, total_ms: 0, denied: 0 });
          t.calls += 1;
          t.total_ms += step.latency_ms;
          if (step.ok) t.ok += 1;
          if (step.approval === 'denied') t.denied += 1;
        } else {
          const m = (models[run.model] ??= { calls: 0, total_ms: 0 });
          m.calls += 1;
          m.total_ms += step.latency_ms;
        }
      }
    }

    // Hourly buckets for the last 24h (oldest first) — drives the activity sparkline.
    const hourMs = 3_600_000;
    const now = Date.now();
    const hourly = Array.from({ length: 24 }, () => ({ runs: 0, failed: 0, cost_usd: 0 }));
    for (const run of this.runs) {
      const age = Math.floor((now - run.started_at) / hourMs);
      if (age < 0 || age >= 24) continue;
      const bucket = hourly[23 - age];
      bucket.runs += 1;
      bucket.cost_usd += run.cost_usd;
      if (run.status === 'failed') bucket.failed += 1;
    }

    return {
      runs_total: this.runs.length,
      runs_today: today.length,
      running: this.runs.filter((run) => run.status === 'running').length,
      success_rate: finished.length ? Math.round((succeeded / finished.length) * 1000) / 10 : null,
      failed: finished.length - succeeded,
      failures,
      p50_ms: percentile(durations, 50),
      p95_ms: percentile(durations, 95),
      avg_steps: finished.length ? Math.round((finished.reduce((s, r) => s + r.current_step, 0) / finished.length) * 10) / 10 : 0,
      tokens_today: today.reduce((sum, run) => sum + run.prompt_tokens + run.completion_tokens, 0),
      cost_today_usd: this.costToday(),
      cost_total_usd: this.runs.reduce((sum, run) => sum + run.cost_usd, 0),
      tools: Object.fromEntries(
        Object.entries(tools).map(([name, t]) => [name, { calls: t.calls, success_rate: Math.round((t.ok / t.calls) * 100), avg_ms: Math.round(t.total_ms / t.calls), denied: t.denied }]),
      ),
      models: Object.fromEntries(Object.entries(models).map(([name, m]) => [name, { calls: m.calls, avg_ms: Math.round(m.total_ms / m.calls) }])),
      hourly,
    };
  }

  private save(): void {
    if (this.saveTimer) return;
    this.saveTimer = setTimeout(() => {
      this.saveTimer = null;
      const tmp = `${this.file}.tmp`;
      fs.writeFileSync(tmp, JSON.stringify(this.runs));
      fs.renameSync(tmp, this.file);
    }, 250);
  }
}
