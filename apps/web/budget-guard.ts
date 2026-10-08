// Spend limits (Layer 1): a daily budget (KUDBEE_DAILY_BUDGET_USD) and an optional cap on any single run (KUDBEE_RUN_BUDGET_USD), both off at 0 or unset.
// `check` is the agent loop's `checkBudget` hook: it returns the message that stops the run, or null. Crossing 80% of the daily budget raises a one-time warning per day.
// Both limits are decided between steps, so a run can finish the step it is in before it stops: the overshoot is at most one step's cost.
export interface BudgetConfig { daily: number; run: number }

const amount = (value: string | undefined): number => { const n = Number(value); return Number.isFinite(n) && n > 0 ? n : 0; };
export function budgetConfig(env: Record<string, string | undefined> = process.env): BudgetConfig {
  return { daily: amount(env.KUDBEE_DAILY_BUDGET_USD), run: amount(env.KUDBEE_RUN_BUDGET_USD) };
}

export const formatUsd = (n: number): string => `$${n < 0.01 ? n.toFixed(4) : n.toFixed(2)}`;

export interface BudgetDeps {
  costToday: () => number;
  /** Called once per day when the daily spend first reaches 80% of the daily budget. */
  onWarn?: (message: string) => void;
  /** Called when a run is stopped by a limit (once per run and limit). */
  onStop?: (message: string, runId: string | undefined) => void;
  now?: () => number;
}

export class BudgetGuard {
  private warnedDay = '';
  private readonly stopped = new Set<string>();
  readonly config: BudgetConfig;
  private readonly deps: BudgetDeps;
  constructor(config: BudgetConfig, deps: BudgetDeps) { this.config = config; this.deps = deps; }

  /** The message that stops this run, or null. `runCost` is what the run has spent so far. */
  check(runCost: number, runId?: string): string | null {
    const { daily, run } = this.config;
    const today = daily > 0 ? this.deps.costToday() : 0;
    if (daily > 0 && today >= daily) return this.stop(`Daily budget of ${formatUsd(daily)} reached (KUDBEE_DAILY_BUDGET_USD)`, runId);
    if (run > 0 && runCost >= run) return this.stop(`Run budget of ${formatUsd(run)} reached (KUDBEE_RUN_BUDGET_USD)`, runId);
    if (daily > 0 && today >= 0.8 * daily) {
      const day = new Date((this.deps.now ?? Date.now)()).toDateString();
      if (this.warnedDay !== day) { this.warnedDay = day; this.deps.onWarn?.(`80% of the daily budget is used: ${formatUsd(today)} of ${formatUsd(daily)}`); }
    }
    return null;
  }

  private stop(message: string, runId: string | undefined): string {
    const key = `${runId ?? ''}|${message}`;
    if (!this.stopped.has(key)) { this.stopped.add(key); this.deps.onStop?.(message, runId); }
    return message;
  }
}
