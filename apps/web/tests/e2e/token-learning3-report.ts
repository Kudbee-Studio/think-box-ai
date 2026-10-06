// Analysis for P3.34, computed ONLY from docs/evidence/p3.35-confirmation/raw-*.jsonl and tokens.json, applying the rules pre-registered in PLAN.md.
// Writes results.json and RESULTS.md. Run: npm run test:live-token-learning3-report
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { pairedBootstrap, wilson } from '../../ab-stats.ts';

const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../../docs/evidence/p3.35-confirmation');
const read = (f: string): any[] => (fs.existsSync(path.join(dir, f)) ? fs.readFileSync(path.join(dir, f), 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l)) : []);
const pct = (x: number): string => `${(x * 100).toFixed(1)}%`;

/** Exact two-sided McNemar test: under no effect each discordant pair is a coin flip. */
function mcnemarExact(b: number, c: number): number {
  const n = b + c;
  if (n === 0) return 1;
  const k = Math.min(b, c);
  let tail = 0; let term = 0.5 ** n;
  for (let i = 0; i <= k; i += 1) { tail += term; term = (term * (n - i)) / (i + 1); }
  return Math.min(1, 2 * tail);
}

function describeArms(rows: any[], meta: any) {
  const goals = [...new Set(rows.map((r) => r.goal_id))].sort();
  const get = (arm: string, g: string) => rows.find((r) => r.arm === arm && r.goal_id === g);
  const complete = goals.length === meta.goals && goals.every((g) => get('A', g) && get('B', g));
  const A: number[] = goals.map((g) => (get('A', g)?.pass ? 1 : 0)); const B: number[] = goals.map((g) => (get('B', g)?.pass ? 1 : 0));
  const n = goals.length; const ap = A.reduce((a, b) => a + b, 0); const bp = B.reduce((a, b) => a + b, 0);
  const boot = pairedBootstrap(A, B, { seed: 20261009 });
  const bOnly = goals.filter((_, i) => B[i] === 1 && A[i] === 0).length; const aOnly = goals.filter((_, i) => A[i] === 1 && B[i] === 0).length;
  const count = (arm: string, f: (r: any) => boolean): number => goals.filter((g) => { const r = get(arm, g); return r && f(r); }).length;
  const mean = (arm: string): number => Math.round(goals.reduce((t, g) => t + (get(arm, g)?.latency_ms ?? 0), 0) / Math.max(1, n));
  const per = (arm: string) => ({ pass: count(arm, (r) => r.pass), false_accepts: count(arm, (r) => r.false_accept), would_escalate: count(arm, (r) => r.would_escalate), tool_failed: count(arm, (r) => r.failure === 'tool_failed'), malformed: count(arm, (r) => r.failure === 'malformed_tool_request'), used_retry: count(arm, (r) => r.tool_retries > 0), ungrounded: count(arm, (r) => r.outcome === 'ungrounded'), mean_latency_ms: mean(arm) });
  return { complete, n, ap, bp, boot, bOnly, aOnly, p: mcnemarExact(bOnly, aOnly), A: per('A'), B: per('B'), coverage: meta.retrieval_coverage as number };
}
const table = (d: ReturnType<typeof describeArms>): string[] => {
  const row = (label: string, k: number, a: ReturnType<typeof describeArms>['A']) => `| ${label} | ${k}/${d.n} (${pct(k / d.n)}, ${pct(wilson(k, d.n).lo)}-${pct(wilson(k, d.n).hi)}) | ${a.false_accepts} | ${a.tool_failed} | ${a.malformed} | ${a.used_retry} | ${a.would_escalate} | ${(a.mean_latency_ms / 1000).toFixed(1)}s |`;
  return ['| Arm | Pass (95% Wilson CI) | False accepts | tool_failed | malformed | used a retry | Would escalate | Mean latency |', '|---|---|---|---|---|---|---|---|', row('A no tokens', d.ap, d.A), row('B tokens', d.bp, d.B), '',
    `- B minus A: ${d.boot.diff >= 0 ? '+' : ''}${(d.boot.diff * 100).toFixed(1)} pts, paired-bootstrap 95% CI [${(d.boot.lo * 100).toFixed(1)}, ${(d.boot.hi * 100).toFixed(1)}]; goals only B passed ${d.bOnly}, only A passed ${d.aOnly}; exact McNemar p=${d.p.toFixed(4)}`];
};

const teacher = read('raw-teacher.jsonl');
const tokens = fs.existsSync(path.join(dir, 'tokens.json')) ? JSON.parse(fs.readFileSync(path.join(dir, 'tokens.json'), 'utf8')) : null;
const tRows = teacher.filter((r) => r.row); const summary = teacher.find((r) => r.summary);
const usable = tRows.filter((r) => r.pipeline && r.pipeline.tokens.some((t: any) => !t.duplicate)).length;
const unusable = tRows.filter((r) => r.pipeline?.dropped?.some((d: any) => d.title === '(unusable reply)')).length;
const out: Record<string, any> = {};
const md: string[] = ['# P3.35 confirmation of the Think Token effect: results', '', 'Computed only from `raw-*.jsonl` and `tokens.json` by `apps/web/tests/e2e/token-learning3-report.ts`, applying the rules pre-registered in `PLAN.md`.', '',
  '## Stage 1: Mercury teacher and the real pipeline', '',
  `- Teacher runs ${tRows.length}; verified ${tRows.filter((r) => r.pass).length}; fed to the pipeline ${tRows.filter((r) => r.fed_to_pipeline).length}; runs that yielded at least one new token **${usable}** (P3.34: 6 of 10); runs whose extract reply was unusable **${unusable}** (P3.34: 0 of 10)`,
  `- Accepted tokens ${summary?.accepted ?? 'n/a'} (written by mercury-2: ${summary?.accepted_by_mercury ?? 'n/a'}); Mercury lane spend $${(summary?.lane_spend_usd ?? 0).toFixed(4)}, pipeline spend estimate $${(summary?.pipeline_spend_usd_estimate ?? 0).toFixed(4)}`, ''];
if (tokens) { md.push('### The accepted tokens, verbatim', ''); for (const t of tokens.tokens.filter((x: any) => x.status === 'accepted')) md.push(`- **${t.id}** (${t.kind}, ${t.extract_model}) ${t.title}: ${t.content}`); md.push(''); }
const spend = (summary?.lane_spend_usd ?? 0) + (summary?.pipeline_spend_usd_estimate ?? 0);
out.stage1 = { runs: tRows.length, usable_runs: usable, unusable_replies: unusable, accepted: summary?.accepted ?? 0, accepted_by_mercury: summary?.accepted_by_mercury ?? 0, spend_usd: Number(spend.toFixed(6)) };

let verdict = 'NOT RUN';
const prim = read('raw-ab.jsonl'); const pm = prim.find((r) => r.meta)?.meta;
if (!pm) md.push('## Primary A/B: NOT RUN', '');
else if (pm.skipped) { verdict = 'UNPROVEN (no tokens produced: teacher guard)'; md.push(`## Primary A/B: not run (${pm.skipped})`, ''); }
else {
  const d = describeArms(prim.filter((r) => r.row), pm);
  const testable = d.coverage / d.n >= 0.5;
  const better = d.complete && testable && d.boot.diff >= 0.2 && d.boot.lo > 0 && d.p < 0.05 && d.B.false_accepts <= d.A.false_accepts && spend < 0.5;
  verdict = !testable ? 'UNPROVEN (tokens rarely applied)' : better ? 'PROVEN' : d.boot.hi < 0 ? 'NEGATIVE' : 'UNPROVEN';
  out.primary = { b_only: d.bOnly, a_only: d.aOnly, complete: d.complete, n: d.n, A: d.A, B: d.B, A_pass: d.ap, B_pass: d.bp, diff: d.boot.diff, ci_lo: d.boot.lo, ci_hi: d.boot.hi, mcnemar_p: d.p, retrieval_coverage: d.coverage, commit: pm.commit, goals_hash: pm.goals_hash, tokens_sha256: pm.tokens_sha256 };
  md.push(`## Primary A/B on 60 fresh held-out goals (n=${d.n}${d.complete ? '' : `, INCOMPLETE: ${pm.goals} planned`})`, '', `Local \`${pm.local_model}\`, commit \`${pm.commit}\`, goals hash \`${String(pm.goals_hash).slice(0, 12)}\`, tokens retrieved for ${d.coverage}/${d.n} goals.`, '', ...table(d), '');
}
const p34 = path.resolve(dir, '..', 'p3.34-recoverable-errors', 'raw-ab.jsonl');
if (out.primary && fs.existsSync(p34)) {
  const rows34 = fs.readFileSync(p34, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l)).filter((x) => x.row);
  const goals34 = [...new Set(rows34.map((x) => x.goal_id))];
  const a34 = goals34.filter((g) => rows34.find((x) => x.arm === 'A' && x.goal_id === g)?.pass).length; const b34 = goals34.filter((g) => rows34.find((x) => x.arm === 'B' && x.goal_id === g)?.pass).length;
  const bOnly34 = goals34.filter((g) => rows34.find((x) => x.arm === 'B' && x.goal_id === g)?.pass && !rows34.find((x) => x.arm === 'A' && x.goal_id === g)?.pass).length;
  const aOnly34 = goals34.filter((g) => !rows34.find((x) => x.arm === 'B' && x.goal_id === g)?.pass && rows34.find((x) => x.arm === 'A' && x.goal_id === g)?.pass).length;
  const P = out.primary;
  const pooledN = goals34.length + P.n; const pooledA = a34 + P.A_pass; const pooledB = b34 + P.B_pass;
  out.pooled_descriptive = { n: pooledN, A_pass: pooledA, B_pass: pooledB, discordant_b_only: bOnly34 + P.b_only, discordant_a_only: aOnly34 + P.a_only, mcnemar_p: mcnemarExact(bOnly34 + P.b_only, aOnly34 + P.a_only), note: 'two independent token sets; not a pre-registered test' };
  md.push('## Pooled with P3.34 (descriptive only; two independent token sets; not a pre-registered test)', '', `- Pass A ${pooledA}/${pooledN} (${pct(pooledA / pooledN)}), B ${pooledB}/${pooledN} (${pct(pooledB / pooledN)}); only B passed ${bOnly34 + P.b_only}, only A passed ${aOnly34 + P.a_only}; exact McNemar p=${out.pooled_descriptive.mcnemar_p.toFixed(4)}`, '');
}
md.push('## Decision (pre-registered rules, primary set only)', '', `Total Mercury spend $${spend.toFixed(4)} (cap $0.50). **Learning benefit: ${verdict}.**`, '');
out.verdict = verdict;
fs.writeFileSync(path.join(dir, 'results.json'), `${JSON.stringify(out, null, 2)}\n`);
fs.writeFileSync(path.join(dir, 'RESULTS.md'), `${md.join('\n')}\n`);
console.log(md.join('\n'));
