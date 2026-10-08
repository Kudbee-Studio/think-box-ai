// `npm run gates`: the local replacement for CI. Runs lint, tsgo, tsc, the full suite with the c8 line floor, and CodeQL (JS/TS and Python) compared with the base branch.
// The rules (floor, "new alert", verdict) are in ../../gates.ts and are tested; this file only spawns the tools and reads their output.
// Usage: npm run gates -- [--only lint,tests,codeql] [--skip codeql] [--min-coverage 90] [--base main] [--allow-dirty] [--record]
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { auditVerdict, parseAudit } from '../../dep-audit.ts';
import { loadBaseline, scanHistory, scanTracked, withoutBaseline } from '../../secret-scan.ts';
import { alertVerdict, coverageVerdict, overallVerdict, parseGateArgs, parseSarif, renderReport, selectedSteps, type GateOptions, type GateReport, type GateStep, type StepResult } from '../../gates.ts';

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const cache = process.env.GATES_CACHE || path.join(os.homedir(), '.cache', 'kudbee-gates');
fs.mkdirSync(cache, { recursive: true });

function run(cmd: string, args: string[], cwd: string, log?: string): { code: number; out: string } {
  const r = spawnSync(cmd, args, { cwd, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, env: process.env });
  const out = `${r.stdout ?? ''}${r.stderr ?? ''}`;
  if (log) fs.writeFileSync(log, out);
  return { code: r.status ?? 1, out };
}
const git = (args: string[]): string => {
  const r = run('git', args, webDir);
  if (r.code !== 0) throw new Error(`git ${args[0]} failed: ${r.out.trim().split('\n').pop()}`);
  return r.out.trim();
};
const tail = (text: string, n = 3): string => text.trim().split('\n').slice(-n).join(' | ').slice(0, 300);

let opts: GateOptions;
try { opts = parseGateArgs(process.argv.slice(2)); } catch (e) { console.error((e as Error).message); process.exit(2); }
if (opts.base.startsWith('-')) { console.error('--base must be a git ref'); process.exit(2); }

const root = git(['rev-parse', '--show-toplevel']);
const head = git(['rev-parse', '--short=8', 'HEAD']);
const branch = git(['rev-parse', '--abbrev-ref', 'HEAD']);
let baseSha: string;
try { baseSha = git(['rev-parse', '--verify', '--short=8', `${opts.base}^{commit}`]); } catch { console.error(`cannot resolve --base ${opts.base}`); process.exit(2); }
const dirty = git(['status', '--porcelain']).length > 0;
if (dirty && !opts.allowDirty) {
  console.error('The working tree has uncommitted changes, so a result would not describe any commit. Commit first, or pass --allow-dirty (the report will say so).');
  process.exit(2);
}

const logDir = path.join(cache, 'logs');
fs.mkdirSync(logDir, { recursive: true });
const results: StepResult[] = [];
const record = (step: GateStep, status: StepResult['status'], detail: string, started: number): void => {
  const r = { step, status, detail, ms: Date.now() - started };
  results.push(r);
  console.log(`${status.toUpperCase().padEnd(7)} ${step}  ${detail}`);
};

function npmStep(step: GateStep, script: string): void {
  const t = Date.now();
  const log = path.join(logDir, `${step}.log`);
  const r = run('npm', ['run', script], webDir, log);
  record(step, r.code === 0 ? 'pass' : 'fail', r.code === 0 ? `npm run ${script}` : `exit ${r.code}: ${tail(r.out)} (full log ${log})`, t);
}

function secretsStep(): void {
  const t = Date.now();
  const baseline = loadBaseline(root);
  const tracked = withoutBaseline(scanTracked(root), baseline);
  const hist = withoutBaseline(scanHistory(root), baseline);
  const where = [...tracked, ...hist].slice(0, 5).map((f) => `${f.file}${f.line ? `:${f.line}` : ''} ${f.rule}${f.commit ? ` @${f.commit}` : ''}`).join('; ');
  record('secrets', tracked.length + hist.length ? 'fail' : 'pass', tracked.length + hist.length ? `${tracked.length} new in files, ${hist.length} new in history: ${where}` : `0 new (baseline holds ${baseline.size})`, t);
}

function auditStep(): void {
  const t = Date.now();
  const r = run('npm', ['audit', '--json'], webDir);
  const v = auditVerdict(parseAudit(r.out));
  record('audit', v.status === 'pass' ? 'pass' : v.status === 'fail' ? 'fail' : 'not_run', v.detail, t);
}

function testsStep(): void {
  const t = Date.now();
  const summary = path.join(webDir, '.coverage', 'coverage-summary.json');
  fs.rmSync(summary, { force: true });
  const log = path.join(logDir, 'tests.log');
  const r = run('npm', ['run', 'test:coverage'], webDir, log);
  let text: string | null = null;
  try { text = fs.readFileSync(summary, 'utf8'); } catch { text = null; }
  const cov = coverageVerdict(text, opts.minCoverage);
  const counts = /ℹ pass (\d+)[\s\S]*?ℹ fail (\d+)/.exec(r.out);
  const tally = counts ? `${counts[1]} passed, ${counts[2]} failed; ` : '';
  record('tests', r.code === 0 && cov.ok ? 'pass' : 'fail', `${tally}${cov.detail}${r.code === 0 ? '' : ` (exit ${r.code}, full log ${log})`}`, t);
}

const LANG: Record<'codeql-js' | 'codeql-py', { id: string; suite: string }> = {
  'codeql-js': { id: 'javascript-typescript', suite: 'codeql/javascript-queries:codeql-suites/javascript-security-extended.qls' },
  'codeql-py': { id: 'python', suite: 'codeql/python-queries:codeql-suites/python-security-extended.qls' },
};

function findCodeql(): string | null {
  for (const c of [process.env.CODEQL_BIN, path.join(os.homedir(), 'tools', 'codeql', 'codeql')]) if (c && fs.existsSync(c)) return c;
  return run('codeql', ['version'], webDir).code === 0 ? 'codeql' : null;
}

/** One CodeQL scan of `source` into `sarif`. The database is scratch and removed. */
function scan(bin: string, step: 'codeql-js' | 'codeql-py', source: string, sarif: string, tag: string): string | null {
  const db = path.join(cache, `db-${tag}-${LANG[step].id}`);
  const log = path.join(logDir, `${tag}-${LANG[step].id}`);
  try {
    const c = run(bin, ['database', 'create', db, `--language=${LANG[step].id}`, `--source-root=${source}`, '--overwrite', '-q'], webDir, `${log}.create.log`);
    if (c.code !== 0) return `database create failed: ${tail(c.out)}`;
    const a = run(bin, ['database', 'analyze', db, LANG[step].suite, '--format=sarif-latest', `--output=${sarif}`, '--threads=2', '--ram=2500'], webDir, `${log}.analyze.log`);
    return a.code === 0 ? null : `analyze failed: ${tail(a.out)}`;
  } finally { fs.rmSync(db, { recursive: true, force: true }); }
}

/** Scans the commit `sha` from a clean checkout, so local-only files (other worktrees, scratch directories) never count as alerts. Returns an error text or null. */
function scanCommit(bin: string, step: 'codeql-js' | 'codeql-py', sha: string, sarif: string, tag: string): string | null {
  const wt = path.join(cache, `wt-${sha}`);
  fs.rmSync(wt, { recursive: true, force: true });
  const add = run('git', ['worktree', 'add', '--detach', wt, sha], root);
  if (add.code !== 0) return `cannot check out ${sha}: ${tail(add.out)}`;
  try { return scan(bin, step, wt, sarif, tag); } finally { run('git', ['worktree', 'remove', '--force', wt], root); }
}

function codeqlStep(step: 'codeql-js' | 'codeql-py'): void {
  const t = Date.now();
  const bin = findCodeql();
  if (!bin) return record(step, 'not_run', 'codeql not found (set CODEQL_BIN or install it under ~/tools/codeql)', t);
  const baseSarif = path.join(cache, `base-${baseSha}-${LANG[step].id}.sarif`);
  if (!fs.existsSync(baseSarif)) {
    const err = scanCommit(bin, step, baseSha, baseSarif, `base-${baseSha}`);
    if (err) { fs.rmSync(baseSarif, { force: true }); return record(step, 'not_run', `base scan: ${err}`, t); }
  }
  const headSarif = path.join(cache, `head-${head}-${LANG[step].id}.sarif`);
  const err = scanCommit(bin, step, head, headSarif, `head-${head}`);
  if (err) return record(step, 'not_run', `head scan: ${err}`, t);
  const v = alertVerdict(parseSarif(fs.readFileSync(baseSarif, 'utf8')), parseSarif(fs.readFileSync(headSarif, 'utf8')));
  record(step, v.ok ? 'pass' : 'fail', `${v.detail}${dirty ? ' (scanned the committed HEAD, not the uncommitted changes)' : ''}`, t);
}

const wanted = selectedSteps(opts);
for (const step of ['lint', 'typecheck', 'tsc', 'secrets', 'audit', 'tests', 'codeql-js', 'codeql-py'] as const) {
  if (!wanted.includes(step)) { results.push({ step, status: 'skipped', detail: 'not requested', ms: 0 }); continue; }
  if (step === 'lint') npmStep(step, 'lint');
  else if (step === 'typecheck') npmStep(step, 'typecheck');
  else if (step === 'tsc') npmStep(step, 'typecheck:tsc');
  else if (step === 'secrets') secretsStep();
  else if (step === 'audit') auditStep();
  else if (step === 'tests') testsStep();
  else codeqlStep(step);
}

const report: GateReport = { generated_at: new Date().toISOString(), head, base: opts.base, base_sha: baseSha, branch, dirty, min_coverage: opts.minCoverage, steps: results, verdict: overallVerdict(results) };
console.log(`\n${renderReport(report)}`);
if (opts.record) {
  const dir = path.join(root, 'docs', 'evidence', 'gates');
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `${branch.replace(/[^A-Za-z0-9._-]/g, '_')}-${head}.json`);
  fs.writeFileSync(file, `${JSON.stringify(report, null, 2)}\n`);
  console.log(`recorded ${path.relative(root, file)}`);
}
process.exit(report.verdict === 'PASS' ? 0 : 1);
