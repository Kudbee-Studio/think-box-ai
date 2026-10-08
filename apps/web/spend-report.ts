// What was spent, from the saved run records (Layer 1, read-only): totals, per day, per model and per profile. Costs are what the run records hold: billed cost where the
// provider reports it, otherwise tokens at the model's price; an estimated price is an estimate. Nothing here talks to a provider.
export interface SpendRun { cost_usd: number; started_at: number; model?: string; provider?: string; profile_id?: string; status?: string }
export interface SpendLine { runs: number; cost_usd: number; avg_cost_usd: number }
export interface SpendReport {
  runs: number;
  today_usd: number; last_7d_usd: number; all_time_usd: number;
  by_day: Array<{ day: string } & SpendLine>;
  by_model: Array<{ model: string } & SpendLine>;
  by_profile: Array<{ profile: string; name?: string } & SpendLine>;
}

const line = (runs: number, cost: number): SpendLine => ({ runs, cost_usd: cost, avg_cost_usd: runs ? cost / runs : 0 });
const dayOf = (ts: number): string => { const d = new Date(ts); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };

function group<T extends string>(runs: SpendRun[], key: (r: SpendRun) => T): Array<[T, SpendLine]> {
  const m = new Map<T, { n: number; cost: number }>();
  for (const r of runs) { const k = key(r); const v = m.get(k) ?? { n: 0, cost: 0 }; v.n += 1; v.cost += r.cost_usd || 0; m.set(k, v); }
  return [...m.entries()].map(([k, v]) => [k, line(v.n, v.cost)]);
}

export function spendReport(runs: SpendRun[], opts: { now?: number; days?: number; names?: Record<string, string> } = {}): SpendReport {
  const now = opts.now ?? Date.now(); const days = opts.days ?? 14;
  const startToday = new Date(now); startToday.setHours(0, 0, 0, 0);
  const sum = (since: number): number => runs.filter((r) => r.started_at >= since).reduce((s, r) => s + (r.cost_usd || 0), 0);
  const recent = runs.filter((r) => r.started_at >= startToday.getTime() - (days - 1) * 86_400_000);
  return {
    runs: runs.length,
    today_usd: sum(startToday.getTime()), last_7d_usd: sum(startToday.getTime() - 6 * 86_400_000), all_time_usd: sum(0),
    by_day: group(recent, (r) => dayOf(r.started_at)).sort((a, b) => b[0].localeCompare(a[0])).map(([day, l]) => ({ day, ...l })),
    by_model: group(runs, (r) => r.model || 'unknown').sort((a, b) => b[1].cost_usd - a[1].cost_usd).map(([model, l]) => ({ model, ...l })),
    by_profile: group(runs, (r) => r.profile_id || 'unknown').sort((a, b) => b[1].cost_usd - a[1].cost_usd).map(([profile, l]) => ({ profile, ...(opts.names?.[profile] ? { name: opts.names[profile] } : {}), ...l })),
  };
}

const usd = (n: number): string => `$${n < 0.01 ? n.toFixed(4) : n.toFixed(2)}`;
export function formatSpendReport(r: SpendReport): string {
  const out = [`Spend: today ${usd(r.today_usd)} · last 7 days ${usd(r.last_7d_usd)} · all time ${usd(r.all_time_usd)} (${r.runs} runs)`, '', 'By model (all time):'];
  for (const m of r.by_model) out.push(`  ${m.model.padEnd(18)} ${String(m.runs).padStart(4)} runs  ${usd(m.cost_usd).padStart(9)}  avg ${usd(m.avg_cost_usd)}/run`);
  out.push('', 'By profile (all time):');
  for (const p of r.by_profile) out.push(`  ${(p.name ?? p.profile.slice(0, 8)).padEnd(18)} ${String(p.runs).padStart(4)} runs  ${usd(p.cost_usd).padStart(9)}`);
  out.push('', 'By day (newest first):');
  for (const d of r.by_day) out.push(`  ${d.day}  ${String(d.runs).padStart(4)} runs  ${usd(d.cost_usd).padStart(9)}`);
  return out.join('\n');
}
