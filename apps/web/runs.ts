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
  /** Profile this run belongs to; runs are listed per active profile. */
  profile_id?: string;
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
  /** Memory ids injected into the prompt at run start. */
  recalled?: string[];
  /** Think Token ids (ADR 028) injected into the planner context for this run. */
  think_tokens?: string[];
  result?: string;
  /** What this run's tools said when the final-answer check found the answer contradicting them (see evidence.ts). */
  evidence_conflicts?: string[];
  error?: string;
  failure_kind?: string;
  /** Who answered and why (route-decision.ts): the same record for every path. */
  route?: Record<string, any>;
  /** Feature 5: model routing decision + estimated token savings for this run. */
  routeTelemetry?: Record<string, any>;
  /** HERMES etc: which named tool-scoped agent profile ran this goal, if any. */
  agentProfile?: string;
  /** Specialist job provenance; each box has its own RunRecord. */
  jobId?: string;
  specialistId?: string;
  thinkBoxId?: string;
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
  /**
   * Runs belong to a profile. When set, list/stats/cost see only that profile's runs; create stamps new runs
   * with it. Switching profiles updates this pointer (see setProfile) so a shared file keeps every run.
   */
  private profileId: string | undefined;

  constructor(file: string, profileId?: string) {
    this.file = file;
    this.profileId = profileId;
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
    } catch (err) {
      this.runs = [];
      // A missing file is a fresh install. Anything else (truncated or hand-edited JSON, a permission error) must not be lost:
      // the next save() would overwrite the file, so keep a copy and say so.
      if ((err as NodeJS.ErrnoException).code !== 'ENOENT') {
        const kept = `${file}.corrupt-${new Date().toISOString().replace(/[:.]/g, '-')}`;
        try { fs.copyFileSync(file, kept); } catch { /* unreadable: nothing to keep */ }
        console.warn(`[runs] could not read ${file} (${err instanceof Error ? err.message : String(err)}); starting empty, original kept at ${kept}`);
      }
    }
  }

  /** Point the store at a profile (no argument = all profiles). Called when the active profile changes. */
  setProfile(profileId?: string): void {
    this.flush();
    this.profileId = profileId;
  }

  get activeProfile(): string | undefined {
    return this.profileId;
  }

  private visible(): RunRecord[] {
    return this.profileId ? this.runs.filter((run) => run.profile_id === this.profileId) : this.runs;
  }

  create(run: RunRecord): RunRecord {
    if (this.profileId && run.profile_id === undefined) run.profile_id = this.profileId;
    this.runs.push(run);
    if (this.runs.length > MAX_RUNS) this.runs.splice(0, this.runs.length - MAX_RUNS);
    this.save();
    return run;
  }

  get(id: string): RunRecord | undefined {
    return this.visible().find((run) => run.id === id);
  }

  list(limit = 50): RunRecord[] {
    return this.visible().slice(-limit).reverse();
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
    return this.visible().filter((run) => run.started_at >= since).reduce((sum, run) => sum + run.cost_usd, 0);
  }

  costToday(): number {
    return this.costSince(startOfToday());
  }

  stats(): Record<string, unknown> {
    const visible = this.visible();
    const finished = visible.filter((run) => run.status !== 'running');
    const today = visible.filter((run) => run.started_at >= startOfToday());
    const durations = finished.map((run) => run.duration_ms ?? 0).sort((a, b) => a - b);
    const succeeded = finished.filter((run) => run.status === 'completed').length;
    const failures: Record<string, number> = {};
    for (const run of finished) if (run.failure_kind) failures[run.failure_kind] = (failures[run.failure_kind] ?? 0) + 1;

    const tools: Record<string, { calls: number; ok: number; total_ms: number; denied: number }> = {};
    const models: Record<string, { calls: number; total_ms: number }> = {};
    for (const run of visible) {
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
    for (const run of visible) {
      const age = Math.floor((now - run.started_at) / hourMs);
      if (age < 0 || age >= 24) continue;
      const bucket = hourly[23 - age];
      bucket.runs += 1;
      bucket.cost_usd += run.cost_usd;
      if (run.status === 'failed') bucket.failed += 1;
    }

    return {
      runs_total: visible.length,
      runs_today: today.length,
      running: visible.filter((run) => run.status === 'running').length,
      success_rate: finished.length ? Math.round((succeeded / finished.length) * 1000) / 10 : null,
      failed: finished.length - succeeded,
      failures,
      p50_ms: percentile(durations, 50),
      p95_ms: percentile(durations, 95),
      avg_steps: finished.length ? Math.round((finished.reduce((s, r) => s + r.current_step, 0) / finished.length) * 10) / 10 : 0,
      tokens_today: today.reduce((sum, run) => sum + run.prompt_tokens + run.completion_tokens, 0),
      cost_today_usd: this.costToday(),
      cost_total_usd: visible.reduce((sum, run) => sum + run.cost_usd, 0),
      tools: Object.fromEntries(
        Object.entries(tools).map(([name, t]) => [name, { calls: t.calls, success_rate: Math.round((t.ok / t.calls) * 100), avg_ms: Math.round(t.total_ms / t.calls), denied: t.denied }]),
      ),
      models: Object.fromEntries(Object.entries(models).map(([name, m]) => [name, { calls: m.calls, avg_ms: Math.round(m.total_ms / m.calls) }])),
      hourly,
    };
  }

  /** Write any pending save immediately. Called before a profile switch so nothing is lost on restart. */
  flush(): void {
    if (!this.saveTimer) return;
    clearTimeout(this.saveTimer);
    this.saveTimer = null;
    this.writeNow();
  }

  private save(): void {
    if (this.saveTimer) return;
    this.saveTimer = setTimeout(() => {
      this.saveTimer = null;
      this.writeNow();
    }, 250);
  }

  private writeNow(): void {
    const tmp = `${this.file}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(this.runs));
    fs.renameSync(tmp, this.file);
  }
}
