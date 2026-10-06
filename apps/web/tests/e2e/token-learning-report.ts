// Analysis for P3.33, computed ONLY from docs/evidence/p3.33-token-learning/raw-*.jsonl and tokens.json, applying the decision rules pre-registered in PLAN.md.
// Writes results.json and RESULTS.md. Run: npm run test:live-token-learning-report
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { pairedBootstrap, wilson } from '../../ab-stats.ts';

const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../../docs/evidence/p3.33-token-learning');
const read = (f: string): any[] => (fs.existsSync(path.join(dir, f)) ? fs.readFileSync(path.join(dir, f), 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l)) : []);
const pct = (x: number): string => `${(x * 100).toFixed(1)}%`;

/** Exact two-sided McNemar test: under no effect each discordant pair is a coin flip. */
export function mcnemarExact(b: number, c: number): number {
  const n = b + c;
  if (n === 0) return 1;
  const k = Math.min(b, c);
  let tail = 0;
  let term = 0.5 ** n;
  for (let i = 0; i <= k; i += 1) { tail += term; term = (term * (n - i)) / (i + 1); }
  return Math.min(1, 2 * tail);
}

const teacher = read('raw-teacher.jsonl');
const ab = read('raw-ab.jsonl');
const tokens = fs.existsSync(path.join(dir, 'tokens.json')) ? JSON.parse(fs.readFileSync(path.join(dir, 'tokens.json'), 'utf8')) : null;
const tRows = teacher.filter((r) => r.row); const summary = teacher.find((r) => r.summary);
const md: string[] = ['# P3.33 Think Token learning test: results', '', 'Computed only from `raw-*.jsonl` and `tokens.json` by `apps/web/tests/e2e/token-learning-report.ts`, applying the rules pre-registered in `PLAN.md`.', ''];
const out: Record<string, any> = {};

md.push('## Stage 1: Mercury teacher and the real pipeline', '',
  `- Teacher runs: ${tRows.length}; passed (grounded, on disk, machine check) ${tRows.filter((r) => r.pass).length}; fed to the pipeline ${tRows.filter((r) => r.fed_to_pipeline).length}`,
  `- Accepted tokens: ${summary?.accepted ?? 'n/a'} (written by mercury-2: ${summary?.accepted_by_mercury ?? 'n/a'}); Mercury lane spend $${(summary?.lane_spend_usd ?? 0).toFixed(4)}, pipeline spend estimate $${(summary?.pipeline_spend_usd_estimate ?? 0).toFixed(4)}`, '');
if (tokens) {
  const byStatus: Record<string, number> = {};
  for (const t of tokens.tokens) byStatus[t.status] = (byStatus[t.status] ?? 0) + 1;
  md.push(`- Tokens by status: ${JSON.stringify(byStatus)}`, '', '### The accepted tokens, verbatim', '');
  for (const t of tokens.tokens.filter((x: any) => x.status === 'accepted')) md.push(`- **${t.id}** (${t.kind}, ${t.extract_model}) ${t.title}: ${t.content}`);
  md.push('');
}
const spend = (summary?.lane_spend_usd ?? 0) + (summary?.pipeline_spend_usd_estimate ?? 0);
out.stage1 = { runs: tRows.length, passed: tRows.filter((r) => r.pass).length, accepted: summary?.accepted ?? 0, accepted_by_mercury: summary?.accepted_by_mercury ?? 0, spend_usd: Number(spend.toFixed(6)) };

let verdict = 'NOT RUN';
const meta = ab.find((r) => r.meta)?.meta;
const rows = ab.filter((r) => r.row);
if (!meta) md.push('## Stage 2: NOT RUN', '');
else if (meta.skipped) { verdict = 'UNPROVEN (no tokens produced: teacher guard)'; md.push(`## Stage 2: not run (${meta.skipped})`, ''); }
else {
  const goals = [...new Set(rows.map((r) => r.goal_id))].sort();
  const get = (arm: string, g: string) => rows.find((r) => r.arm === arm && r.goal_id === g);
  const complete = goals.length === meta.goals && goals.every((g) => get('A', g) && get('B', g));
  const A: number[] = goals.map((g) => (get('A', g)?.pass ? 1 : 0)); const B: number[] = goals.map((g) => (get('B', g)?.pass ? 1 : 0));
  const n = goals.length; const ap = A.reduce((a, b) => a + b, 0); const bp = B.reduce((a, b) => a + b, 0);
  const boot = pairedBootstrap(A, B, { seed: 20261007 });
  const bOnly = goals.filter((_, i) => B[i] === 1 && A[i] === 0).length; const aOnly = goals.filter((_, i) => A[i] === 1 && B[i] === 0).length;
  const p = mcnemarExact(bOnly, aOnly);
  const fa = (arm: string): number => goals.filter((g) => get(arm, g)?.false_accept).length;
  const esc = (arm: string): number => goals.filter((g) => get(arm, g)?.would_escalate).length;
  const coverage = meta.retrieval_coverage as number;
  const testable = coverage / n >= 0.5;
  const better = complete && testable && boot.diff >= 0.2 && boot.lo > 0 && p < 0.05 && fa('B') <= fa('A') && spend < 0.5;
  const negative = boot.hi < 0;
  verdict = !testable ? 'UNPROVEN (tokens rarely applied)' : better ? 'PROVEN' : negative ? 'NEGATIVE' : 'UNPROVEN';
  const mean = (arm: string): number => Math.round(goals.reduce((t, g) => t + (get(arm, g)?.latency_ms ?? 0), 0) / Math.max(1, n));
  out.stage2 = { complete, n, A_pass: ap, B_pass: bp, diff: boot.diff, ci_lo: boot.lo, ci_hi: boot.hi, mcnemar_p: p, b_only: bOnly, a_only: aOnly, false_accepts: { A: fa('A'), B: fa('B') }, would_escalate: { A: esc('A'), B: esc('B') }, retrieval_coverage: coverage, spend_usd: Number(spend.toFixed(6)), commit: meta.commit, goals_hash: meta.goals_hash, tokens_sha256: meta.tokens_sha256 };
  md.push(`## Stage 2: held-out A/B (n=${n}${complete ? '' : `, INCOMPLETE: ${meta.goals} planned`})`, '',
    `Local \`${meta.local_model}\`, commit \`${meta.commit}\`, held-out goals hash \`${String(meta.goals_hash).slice(0, 12)}\`, tokens retrieved for ${coverage}/${n} goals.`, '',
    '| Arm | Pass (95% Wilson CI) | False accepts | Would escalate | Mean latency |', '|---|---|---|---|---|',
    `| A no tokens | ${ap}/${n} (${pct(ap / n)}, ${pct(wilson(ap, n).lo)}-${pct(wilson(ap, n).hi)}) | ${fa('A')} | ${esc('A')} | ${(mean('A') / 1000).toFixed(1)}s |`,
    `| B tokens | ${bp}/${n} (${pct(bp / n)}, ${pct(wilson(bp, n).lo)}-${pct(wilson(bp, n).hi)}) | ${fa('B')} | ${esc('B')} | ${(mean('B') / 1000).toFixed(1)}s |`, '',
    `- B minus A: ${boot.diff >= 0 ? '+' : ''}${(boot.diff * 100).toFixed(1)} pts, paired-bootstrap 95% CI [${(boot.lo * 100).toFixed(1)}, ${(boot.hi * 100).toFixed(1)}]; goals only B passed ${bOnly}, only A passed ${aOnly}; exact McNemar p=${p.toFixed(4)}`,
    `- Mercury spend (teacher + pipeline): $${spend.toFixed(4)} of the $0.50 cap`, '');
}
md.push('## Decision (pre-registered rules)', '', `**Learning benefit: ${verdict}.**`, '');
out.verdict = verdict;
fs.writeFileSync(path.join(dir, 'results.json'), `${JSON.stringify(out, null, 2)}\n`);
fs.writeFileSync(path.join(dir, 'RESULTS.md'), `${md.join('\n')}\n`);
console.log(md.join('\n'));

