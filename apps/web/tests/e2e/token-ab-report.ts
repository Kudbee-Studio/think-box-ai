// Analysis for the P3.24 A/B, computed ONLY from docs/evidence/p3.24-ab/raw-*.jsonl, applying the decision rules pre-registered in PLAN.md.
// Writes docs/evidence/p3.24-ab/results.json and RESULTS.md. Run: npm run test:live-token-ab3-report
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { fisherExact, pairedBootstrap, percentile, wilson } from '../../ab-stats.ts';

const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../../docs/evidence/p3.24-ab');
interface Row { arm: 'A' | 'B' | 'C'; goal_id: string; class: 'lookup' | 'repo'; outcome: string; pass: boolean; grounded: boolean; latency_ms: number; tokens_retrieved: string[]; absence?: { path: string } }
const pct = (x: number): string => `${(x * 100).toFixed(1)}%`;
const files = fs.readdirSync(dir).filter((f) => /^raw-.*\.jsonl$/.test(f)).sort();
const out: Record<string, unknown> = { generated_from: files, models: {} };
const md: string[] = ['# P3.24 A/B results', '', 'Computed only from `raw-*.jsonl` by `apps/web/tests/e2e/token-ab-report.ts`, applying the rules pre-registered in `PLAN.md`.', ''];
const verdicts: Array<{ model: string; testable: boolean; bBetterThanA: boolean; bNegative: boolean }> = [];

for (const f of files) {
  const lines = fs.readFileSync(path.join(dir, f), 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
  const meta = lines.find((l) => l.meta)?.meta; const rows: Row[] = lines.filter((l) => l.row);
  const model = meta?.model ?? f;
  const goals = [...new Set(rows.map((r) => r.goal_id))].sort();
  const complete = (['A', 'B', 'C'] as const).every((a) => rows.filter((r) => r.arm === a).length === goals.length) && goals.length === (meta?.goals ?? 30);
  const get = (arm: string, goal: string): Row => rows.find((r) => r.arm === arm && r.goal_id === goal)!;
  const sub = (pred: (g: string) => boolean) => goals.filter(pred);
  const arm = (a: 'A' | 'B' | 'C', gs: string[] = goals) => {
    const r = gs.map((g) => get(a, g)); const k = r.filter((x) => x.pass).length; const gr = r.filter((x) => x.grounded).length;
    const lat = r.map((x) => x.latency_ms);
    return { n: r.length, pass: k, pass_rate: k / r.length, pass_ci: wilson(k, r.length), grounded: gr, grounded_rate: gr / r.length, latency_ms: { mean: Math.round(lat.reduce((p, q) => p + q, 0) / lat.length), p50: percentile(lat, 0.5), p95: percentile(lat, 0.95) }, outcomes: Object.fromEntries(['pass', 'wrong', 'ungrounded', 'failed'].map((o) => [o, r.filter((x) => x.outcome === o).length])) };
  };
  const cmp = (x: 'A' | 'B' | 'C', y: 'A' | 'B' | 'C', gs: string[] = goals) => {
    if (!gs.length) return null;
    const xs = gs.map((g) => (get(x, g).pass ? 1 : 0)); const ys = gs.map((g) => (get(y, g).pass ? 1 : 0));
    const a = ys.filter((v) => v).length; const c = xs.filter((v) => v).length;
    return { n: gs.length, ...pairedBootstrap(xs, ys), fisher_p: fisherExact(a, gs.length - a, c, gs.length - c), pass_x: c, pass_y: a };
  };
  const untested = sub((g) => g.startsWith('untested-'));
  const A = arm('A'), B = arm('B'), C = arm('C');
  const BA = cmp('A', 'B'), CB = cmp('B', 'C'), CA = cmp('A', 'C');
  const coverage = goals.filter((g) => get('B', g).tokens_retrieved.length > 0).length;
  const testable = coverage / goals.length >= 0.5;
  const bBetter = !!BA && testable && BA.diff >= 0.10 && BA.lo > 0 && BA.fisher_p < 0.025 && B.grounded_rate >= A.grounded_rate - 0.05 && B.latency_ms.p95 <= 1.5 * A.latency_ms.p95;
  const bNeg = !!BA && BA.hi < 0;
  const cBetter = (() => { const x = cmp('B', 'C', untested); return !!x && x.diff >= 0.20 && x.lo > 0 && x.fisher_p < 0.025; })();
  verdicts.push({ model, testable, bBetterThanA: bBetter, bNegative: bNeg });
  const lookupDet = sub((g) => get('B', g).class === 'lookup'); const agree = lookupDet.filter((g) => get('B', g).outcome === get('C', g).outcome).length;
  const engineRuns = rows.filter((r) => r.arm === 'C' && r.absence); const esc = engineRuns.filter((r) => r.absence!.path === 'escalate').length;
  (out.models as Record<string, unknown>)[model] = { complete, goals: goals.length, retrieval_coverage: coverage, store: meta?.store, goals_hash: meta?.goals_hash, commit: meta?.commit, arms: { A, B, C }, B_minus_A: BA, C_minus_B: CB, C_minus_A: CA, subgroups: { lookup: { A: arm('A', sub((g) => get('A', g).class === 'lookup')), B: arm('B', sub((g) => get('A', g).class === 'lookup')), C: arm('C', sub((g) => get('A', g).class === 'lookup')) }, repo: { A: arm('A', sub((g) => get('A', g).class === 'repo')), B: arm('B', sub((g) => get('A', g).class === 'repo')), C: arm('C', sub((g) => get('A', g).class === 'repo')) }, untested_function: { A: arm('A', untested), B: arm('B', untested), C: arm('C', untested), C_minus_B: cmp('B', 'C', untested), B_minus_A: cmp('A', 'B', untested) } }, decisions: { testable, B_better_than_A: bBetter, B_significantly_worse_than_A: bNeg, engine_C_better_than_B_on_untested: cBetter }, lookup_B_vs_C_same_outcome: `${agree}/${lookupDet.length}`, engine_absence_runs: { runs: engineRuns.length, escalated: esc } };
  const row = (n: string, s: ReturnType<typeof arm>) => `| ${n} | ${s.pass}/${s.n} (${pct(s.pass_rate)}, CI ${pct(s.pass_ci.lo)}-${pct(s.pass_ci.hi)}) | ${pct(s.grounded_rate)} | ${(s.latency_ms.mean / 1000).toFixed(1)}s / ${(s.latency_ms.p50 / 1000).toFixed(1)}s / ${(s.latency_ms.p95 / 1000).toFixed(1)}s | ${s.outcomes.wrong} / ${s.outcomes.ungrounded} / ${s.outcomes.failed} |`;
  const c = (x: ReturnType<typeof cmp>) => (x ? `${x.diff >= 0 ? '+' : ''}${(x.diff * 100).toFixed(1)} pts, 95% CI [${(x.lo * 100).toFixed(1)}, ${(x.hi * 100).toFixed(1)}], Fisher p=${x.fisher_p.toFixed(4)}` : 'n/a');
  md.push(`## ${model}${complete ? '' : ' (INCOMPLETE: not all 90 trials present)'}`, '', `Tokens retrieved for ${coverage}/${goals.length} goals (store: ${meta?.store?.accepted} accepted). Goals hash \`${meta?.goals_hash?.slice(0, 12)}\`, commit \`${meta?.commit}\`.`, '', '| Arm | Pass (95% Wilson CI) | Grounded | Latency mean / p50 / p95 | wrong / ungrounded / failed |', '|---|---|---|---|---|', row('A no token, engine off', A), row('B tokens, engine off', B), row('C tokens + engine', C), '', `- B - A: ${c(BA)}`, `- C - B: ${c(CB)}`, `- C - A: ${c(CA)}`, `- Untested-function goals only (n=${untested.length}): A ${arm('A', untested).pass}/${untested.length}, B ${arm('B', untested).pass}/${untested.length}, C ${arm('C', untested).pass}/${untested.length}; C - B: ${c(cmp('B', 'C', untested))}`, `- Lookup goals B vs C (same config, determinism check): same outcome on ${agree}/${lookupDet.length}`, `- Engine absence path on C: ${engineRuns.length} repository findings claimed an absence, ${esc} escalated`, '', `Decision rules: testable=${testable}, **B better than A: ${bBetter ? 'YES' : 'NO'}**, engine C better than B on untested-function: ${cBetter ? 'YES' : 'NO'}.`, '');
}
const proven = verdicts.some((v) => v.bBetterThanA) && verdicts.every((v) => !v.bNegative);
out.learning_benefit = proven ? 'PROVEN (pre-registered rule met)' : 'UNPROVEN';
md.push('## Learning benefit (pre-registered rule, PLAN.md decision 1)', '', `**${proven ? 'PROVEN' : 'UNPROVEN'}** ${proven ? '' : '(B was not shown better than A under the pre-registered rule.)'}`, '');
fs.writeFileSync(path.join(dir, 'results.json'), JSON.stringify(out, null, 2) + '\n');
fs.writeFileSync(path.join(dir, 'RESULTS.md'), md.join('\n') + '\n');
console.log(md.join('\n'));
