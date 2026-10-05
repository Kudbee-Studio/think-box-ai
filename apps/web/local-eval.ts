// Per-model measurement of the local tool loops (list item 5/10: route from measurements, keep a standing regression set).
// Pure: task definitions with machine-checked expectations, trial scoring and per-model summaries. No I/O, no model calls; the opt-in runner
// (tests/e2e/local-eval.live.ts) feeds it real results against the fixtures in tests/helpers/local-eval-fixture.ts.
import type { LocalToolResult } from './local-tools.ts';

export type TaskClass = 'lookup' | 'repo';
/** pass: right and grounded. wrong: completed and grounded but not what was asked (grounded is not on-topic). ungrounded: a claim the evidence does not support. failed: the loop did not finish. */
export type Outcome = 'pass' | 'wrong' | 'ungrounded' | 'failed';

export interface EvalTask {
  id: string;
  class: TaskClass;
  goal: string;
  /** Machine check of a completed, GROUNDED result against the fixture's known facts. */
  check: (r: LocalToolResult<any>) => { ok: boolean; why: string };
}

const has = (text: string | undefined, re: RegExp): boolean => re.test(text ?? '');

/** The facts these tasks rely on are the fixture's: PRs #363 (open, newest), #362, #361 (open), #360; CI run 812 failed; branches main + feat/pr363; no open issues. */
export const EVAL_TASKS: EvalTask[] = [
  { id: 'last-pr', class: 'lookup', goal: 'What is the last PR?', check: (r) => has(r.answer, /363/) && has(r.answer, /open/i) ? { ok: true, why: 'names #363 and that it is open' } : { ok: false, why: 'did not name #363 as open' } },
  { id: 'open-prs', class: 'lookup', goal: 'Which pull requests are open?', check: (r) => has(r.answer, /363/) && has(r.answer, /361/) ? { ok: true, why: 'names #363 and #361' } : { ok: false, why: 'missing #363 or #361' } },
  { id: 'ci', class: 'lookup', goal: 'Did the last CI run pass?', check: (r) => has(r.answer, /fail/i) && !has(r.answer, /\b(passed|succeeded|succeeded successfully|was successful)\b/i) ? { ok: true, why: 'says it failed' } : { ok: false, why: 'did not say the run failed' } },
  { id: 'branches', class: 'lookup', goal: 'What branches exist?', check: (r) => has(r.answer, /\bmain\b/) && has(r.answer, /feat\/pr363/) ? { ok: true, why: 'names main and feat/pr363' } : { ok: false, why: 'missing a branch' } },
  { id: 'no-issues', class: 'lookup', goal: 'Are there any open issues?', check: (r) => has(r.answer, /\b(no|none|zero|0)\b/i) && !has(r.answer, /\b(issue #\d+|there are [1-9])/i) ? { ok: true, why: 'says there are none' } : { ok: false, why: 'did not say there are no open issues' } },
  { id: 'find-constant', class: 'repo', goal: 'Find which file defines BETA_LIMIT and what its value is', check: (r) => r.finding?.found && r.finding.file === 'src/beta.ts' ? { ok: true, why: 'src/beta.ts' } : { ok: false, why: `reported ${r.finding?.found ? r.finding.file : 'nothing'}` } },
  { id: 'untested-function', class: 'repo', goal: 'Find one exported function in src that has no test', check: (r) => r.finding?.found && r.finding.file === 'src/alpha.ts' && /orphan/.test(r.finding.quote ?? '') ? { ok: true, why: 'orphan() in src/alpha.ts' } : { ok: false, why: `reported ${r.finding?.found ? `${r.finding.file}` : 'nothing'}` } },
  { id: 'honest-absence', class: 'repo', goal: 'Find a function named teleport', check: (r) => r.finding && r.finding.found === false ? { ok: true, why: 'reported that it does not exist' } : { ok: false, why: 'invented a finding for a function that is not there' } },
];

export interface Trial { model: string; task: string; class: TaskClass; outcome: Outcome; why: string; latency_ms: number; tool_calls: number; tokens: number; mode: string; failure?: string }

export function scoreTrial(task: EvalTask, result: LocalToolResult<any>): Trial {
  const base = { model: result.model, task: task.id, class: task.class, latency_ms: result.latency_ms, tool_calls: result.tool_calls, tokens: result.prompt_tokens + result.completion_tokens, mode: result.mode };
  if (!result.success) return { ...base, outcome: 'failed', why: `${result.failure?.kind}: ${result.failure?.message}`, failure: result.failure?.kind };
  if (result.grounding?.status !== 'GROUNDED') return { ...base, outcome: 'ungrounded', why: (result.grounding?.unsupported ?? []).map((u) => `${u.kind} ${u.claim}`).join('; ') || 'not grounded' };
  const verdict = task.check(result);
  return { ...base, outcome: verdict.ok ? 'pass' : 'wrong', why: verdict.why };
}

const percentile = (xs: number[], p: number): number => { if (!xs.length) return 0; const s = [...xs].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.ceil((p / 100) * s.length) - 1)]!; };

export interface ModelSummary { model: string; class: TaskClass; trials: number; pass: number; pass_rate: number; wrong: number; ungrounded: number; failed: number; p50_ms: number; p95_ms: number; avg_tokens: number }

export function summarize(trials: Trial[]): ModelSummary[] {
  const groups = new Map<string, Trial[]>();
  for (const t of trials) { const k = `${t.model}\u0000${t.class}`; groups.set(k, [...(groups.get(k) ?? []), t]); }
  return [...groups.values()].map((g) => {
    const n = g.length; const count = (o: Outcome) => g.filter((t) => t.outcome === o).length;
    return { model: g[0]!.model, class: g[0]!.class, trials: n, pass: count('pass'), pass_rate: Math.round((count('pass') / n) * 1000) / 1000, wrong: count('wrong'), ungrounded: count('ungrounded'), failed: count('failed'),
      p50_ms: percentile(g.map((t) => t.latency_ms), 50), p95_ms: percentile(g.map((t) => t.latency_ms), 95), avg_tokens: Math.round(g.reduce((s, t) => s + t.tokens, 0) / n) };
  }).sort((a, b) => a.class.localeCompare(b.class) || b.pass_rate - a.pass_rate || a.model.localeCompare(b.model));
}

/** The routing question the table answers: is this model measured good enough for this class? Needs enough trials, a high pass rate and no ungrounded answers. */
export function sufficient(s: ModelSummary, opts: { minTrials?: number; minPassRate?: number } = {}): boolean {
  return s.trials >= (opts.minTrials ?? 6) && s.pass_rate >= (opts.minPassRate ?? 0.8) && s.ungrounded === 0;
}

export function renderTable(rows: ModelSummary[]): string {
  const head = '| Model | Class | Trials | Pass | Wrong | Ungrounded | Failed | p50 | p95 | Avg tokens | Sufficient |\n|---|---|---|---|---|---|---|---|---|---|---|';
  return [head, ...rows.map((r) => `| ${r.model} | ${r.class} | ${r.trials} | ${Math.round(r.pass_rate * 100)}% | ${r.wrong} | ${r.ungrounded} | ${r.failed} | ${(r.p50_ms / 1000).toFixed(1)}s | ${(r.p95_ms / 1000).toFixed(1)}s | ${r.avg_tokens} | ${sufficient(r) ? 'yes' : 'no'} |`)].join('\n');
}
