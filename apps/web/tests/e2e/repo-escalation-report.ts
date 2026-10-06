// Analysis for P3.32, computed ONLY from docs/evidence/p3.32-escalation/raw-*.jsonl and applying the decision rules pre-registered in PLAN.md.
// Writes results.json and RESULTS.md. Run: npm run test:live-repo-escalation-report
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { pairedBootstrap, wilson } from '../../ab-stats.ts';

const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../../docs/evidence/p3.32-escalation');
interface Attempt { outcome: string; why: string; accepted: boolean; pass: boolean; false_accept: boolean; latency_ms: number; tokens: number; tool_calls: number; failure: string | null; cost_usd?: number }
interface Row { goal_id: string; local: Attempt; trigger: string | null; skipped_for_cap: boolean; escalation: Attempt | null; final: { pass: boolean; false_accept: boolean } }
const pct = (x: number): string => `${(x * 100).toFixed(1)}%`;
const kindOf = (id: string): 'untested' | 'constant' | 'missing' => (id.includes('untested') ? 'untested' : id.includes('constant') ? 'constant' : 'missing');

function load(set: string): { meta: Record<string, any>; rows: Row[] } | null {
  const f = path.join(dir, `raw-${set}.jsonl`);
  if (!fs.existsSync(f)) return null;
  const lines = fs.readFileSync(f, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
  return { meta: lines.find((l) => l.meta)?.meta ?? {}, rows: lines.filter((l) => l.row) };
}

function analyse(rows: Row[]) {
  const n = rows.length;
  const L: number[] = rows.map((r) => (r.local.pass ? 1 : 0)); const E: number[] = rows.map((r) => (r.final.pass ? 1 : 0));
  const triggered = rows.filter((r) => r.trigger); const escalated = rows.filter((r) => r.escalation);
  const rescued = rows.filter((r) => !r.local.pass && r.final.pass).length; const lost = rows.filter((r) => r.local.pass && !r.final.pass).length;
  const boot = pairedBootstrap(L, E, { seed: 20261006 });
  const lp = L.reduce((a, b) => a + b, 0); const ep = E.reduce((a, b) => a + b, 0);
  const spend = escalated.reduce((t, r) => t + (r.escalation!.cost_usd ?? 0), 0);
  const kinds = Object.fromEntries((['untested', 'constant', 'missing'] as const).map((k) => { const g = rows.filter((r) => kindOf(r.goal_id) === k); return [k, { n: g.length, local_pass: g.filter((r) => r.local.pass).length, final_pass: g.filter((r) => r.final.pass).length, triggered: g.filter((r) => r.trigger).length }]; }));
  return {
    n, local_pass: lp, local_ci: wilson(lp, n), final_pass: ep, final_ci: wilson(ep, n), diff: boot.diff, ci_lo: boot.lo, ci_hi: boot.hi, triggered: triggered.length, escalated: escalated.length, skipped_for_cap: rows.filter((r) => r.skipped_for_cap).length,
    rescued, lost, false_accepts_local: rows.filter((r) => r.local.false_accept).length, false_accepts_final: rows.filter((r) => r.final.false_accept).length, spend_usd: Number(spend.toFixed(6)),
    mercury_pass_when_escalated: escalated.filter((r) => r.escalation!.pass).length, kinds,
    triggers: Object.fromEntries([...new Set(triggered.map((r) => r.trigger!.replace(/\(.*$/, '').trim().slice(0, 60)))].map((t) => [t, triggered.filter((r) => r.trigger!.startsWith(t.slice(0, 20))).length])),
    local_latency_mean_ms: Math.round(rows.reduce((t, r) => t + r.local.latency_ms, 0) / Math.max(1, n)), mercury_latency_mean_ms: escalated.length ? Math.round(escalated.reduce((t, r) => t + r.escalation!.latency_ms, 0) / escalated.length) : null,
  };
}

const out: Record<string, any> = {};
const md: string[] = ['# P3.32 escalation lane: results', '', 'Computed only from `raw-*.jsonl` by `apps/web/tests/e2e/repo-escalation-report.ts`, applying the rules pre-registered in `PLAN.md`.', ''];
for (const set of ['primary', 'secondary']) {
  const d = load(set);
  if (!d) { md.push(`## ${set}: NOT RUN`, ''); continue; }
  const a = analyse(d.rows);
  const complete = d.rows.length === d.meta.goals;
  out[set] = { complete, meta: d.meta, ...a };
  md.push(`## ${set} (n=${a.n}${complete ? '' : `, INCOMPLETE: ${d.meta.goals} goals planned`})`, '',
    `Local \`${d.meta.local_model}\`, escalation \`${d.meta.escalation_model}\`, commit \`${d.meta.commit}\`, goals hash \`${String(d.meta.goals_hash).slice(0, 12)}\`.`, '',
    '| Arm | Pass (95% Wilson CI) | False accepts |', '|---|---|---|',
    `| L local only | ${a.local_pass}/${a.n} (${pct(a.local_pass / a.n)}, ${pct(a.local_ci.lo)}-${pct(a.local_ci.hi)}) | ${a.false_accepts_local} |`,
    `| E local + escalation | ${a.final_pass}/${a.n} (${pct(a.final_pass / a.n)}, ${pct(a.final_ci.lo)}-${pct(a.final_ci.hi)}) | ${a.false_accepts_final} |`, '',
    `- E minus L: ${a.diff >= 0 ? '+' : ''}${(a.diff * 100).toFixed(1)} pts, paired-bootstrap 95% CI [${(a.ci_lo * 100).toFixed(1)}, ${(a.ci_hi * 100).toFixed(1)}]; rescued ${a.rescued}, lost ${a.lost}`,
    `- Trigger fired on ${a.triggered}/${a.n}; escalated ${a.escalated}; skipped for the cap ${a.skipped_for_cap}; Mercury passed ${a.mercury_pass_when_escalated}/${a.escalated} of what it was given`,
    `- By kind (local pass / final pass / triggered): ${Object.entries(a.kinds).map(([k, v]: [string, any]) => `${k} ${v.local_pass}/${v.final_pass}/${v.triggered} of ${v.n}`).join('; ')}`,
    `- Mercury spend (from reported tokens at the price table): $${a.spend_usd.toFixed(4)}; mean latency local ${(a.local_latency_mean_ms / 1000).toFixed(1)}s${a.mercury_latency_mean_ms ? `, Mercury ${(a.mercury_latency_mean_ms / 1000).toFixed(1)}s` : ''}`, '');
}

const P = out.primary; const S = out.secondary;
const totalSpend = (P?.spend_usd ?? 0) + (S?.spend_usd ?? 0);
let verdict = 'NOT RUN';
if (P) {
  const testable = P.triggered >= 5;
  const better = testable && P.complete && P.diff >= 0.3 && P.ci_lo > 0 && P.false_accepts_final <= P.false_accepts_local && totalSpend < 0.5;
  const secondaryOk = !!S && S.complete && S.rescued >= 1 && S.lost === 0;
  verdict = !testable ? 'UNPROVEN (trigger fired on fewer than 5 primary goals)' : better ? (secondaryOk ? 'PROVEN' : 'MIXED (primary met, secondary not)') : P.diff < 0 || P.false_accepts_final > P.false_accepts_local ? 'NEGATIVE' : 'UNPROVEN';
  out.decision = { testable, primary_better: better, secondary_ok: secondaryOk, total_spend_usd: Number(totalSpend.toFixed(6)), spend_under_cap: totalSpend < 0.5, verdict };
}
md.push('## Decision (pre-registered rules)', '', `Total Mercury spend $${totalSpend.toFixed(4)} (cap $0.50). **Verdict: ${verdict}.**`, '');
fs.writeFileSync(path.join(dir, 'results.json'), `${JSON.stringify(out, null, 2)}\n`);
fs.writeFileSync(path.join(dir, 'RESULTS.md'), `${md.join('\n')}\n`);
console.log(md.join('\n'));
