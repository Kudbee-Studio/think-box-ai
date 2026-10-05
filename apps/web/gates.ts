// Local gates: the pass/fail rules behind `npm run gates`. GitHub Actions is billing-locked, so these checks are the only ones that run before a merge.
// Everything here is pure (no process, no file, no network) so the rules are tested; the runner that spawns lint/tsc/tests/CodeQL is tests/e2e/gates.ts.

export const GATE_STEPS = ['lint', 'typecheck', 'tsc', 'tests', 'codeql-js', 'codeql-py'] as const;
export type GateStep = (typeof GATE_STEPS)[number];
export const DEFAULT_MIN_COVERAGE = 90;

export type StepStatus = 'pass' | 'fail' | 'skipped' | 'not_run';
export interface StepResult { step: GateStep; status: StepStatus; detail: string; ms: number }

export interface GateOptions { only: GateStep[]; skip: GateStep[]; minCoverage: number; allowDirty: boolean; record: boolean; base: string }

/** The steps this run is asked for, in the fixed order. `--only` picks, `--skip` removes; a step in neither list is included. */
export function selectedSteps(o: Pick<GateOptions, 'only' | 'skip'>): GateStep[] {
  return GATE_STEPS.filter((s) => (o.only.length === 0 || o.only.includes(s)) && !o.skip.includes(s));
}

const STEP_GROUPS: Record<string, GateStep[]> = { codeql: ['codeql-js', 'codeql-py'] };

function stepList(raw: string): GateStep[] {
  const out: GateStep[] = [];
  for (const name of raw.split(',').map((s) => s.trim()).filter(Boolean)) {
    const group = STEP_GROUPS[name];
    if (group) { out.push(...group); continue; }
    if (!(GATE_STEPS as readonly string[]).includes(name)) throw new Error(`unknown step "${name}" (known: ${[...GATE_STEPS, ...Object.keys(STEP_GROUPS)].join(', ')})`);
    out.push(name as GateStep);
  }
  return out;
}

export function parseGateArgs(argv: string[]): GateOptions {
  const o: GateOptions = { only: [], skip: [], minCoverage: DEFAULT_MIN_COVERAGE, allowDirty: false, record: false, base: 'main' };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const value = (): string => {
      const v = argv[++i];
      if (v === undefined || v.startsWith('--')) throw new Error(`${a} needs a value`);
      return v;
    };
    if (a === '--only') o.only.push(...stepList(value()));
    else if (a === '--skip') o.skip.push(...stepList(value()));
    else if (a === '--min-coverage') {
      const n = Number(value());
      if (!Number.isFinite(n) || n < 0 || n > 100) throw new Error('--min-coverage must be a number from 0 to 100');
      o.minCoverage = n;
    } else if (a === '--base') o.base = value();
    else if (a === '--allow-dirty') o.allowDirty = true;
    else if (a === '--record') o.record = true;
    else throw new Error(`unknown option ${a}`);
  }
  return o;
}

// ---- coverage ----

export interface CoverageVerdict { ok: boolean; pct: number | null; detail: string }

/** Reads c8's json-summary text. A missing or unreadable summary is a failure: "no number" never passes the floor. */
export function coverageVerdict(summaryText: string | null, min: number): CoverageVerdict {
  if (summaryText === null) return { ok: false, pct: null, detail: 'no coverage summary was written' };
  let pct: unknown;
  try { pct = (JSON.parse(summaryText) as { total?: { lines?: { pct?: unknown } } }).total?.lines?.pct; } catch { return { ok: false, pct: null, detail: 'coverage summary is not valid JSON' }; }
  if (typeof pct !== 'number' || !Number.isFinite(pct)) return { ok: false, pct: null, detail: 'coverage summary has no total line percentage' };
  return { ok: pct >= min, pct, detail: `lines ${pct}% (floor ${min}%)` };
}

// ---- CodeQL alerts ----

export interface Alert { rule: string; file: string; line: number; message: string; key: string }

/**
 * Identity of an alert across two checkouts. CodeQL's primaryLocationLineHash survives an edit that only moves the line, so it is used when present;
 * without it the message text stands in (it names the flow, not the line number).
 */
export function alertKey(rule: string, file: string, lineHash: string | undefined, message: string): string {
  return `${rule}|${file}|${lineHash ?? message}`;
}

interface SarifResult {
  ruleId?: string;
  message?: { text?: string };
  locations?: { physicalLocation?: { artifactLocation?: { uri?: string }; region?: { startLine?: number } } }[];
  partialFingerprints?: { primaryLocationLineHash?: string };
}

export function parseSarif(text: string): Alert[] {
  let doc: { runs?: { results?: SarifResult[] }[] };
  try { doc = JSON.parse(text); } catch { throw new Error('SARIF file is not valid JSON'); }
  if (!Array.isArray(doc.runs)) throw new Error('SARIF file has no runs');
  const alerts: Alert[] = [];
  for (const run of doc.runs) {
    for (const r of run.results ?? []) {
      const loc = r.locations?.[0]?.physicalLocation;
      const rule = r.ruleId ?? 'unknown';
      const file = loc?.artifactLocation?.uri ?? 'unknown';
      const message = r.message?.text ?? '';
      alerts.push({ rule, file, line: loc?.region?.startLine ?? 0, message, key: alertKey(rule, file, r.partialFingerprints?.primaryLocationLineHash, message) });
    }
  }
  return alerts;
}

/** Alerts in `head` that `base` does not have. Counted, not just listed: a second copy of an existing alert is new. */
export function newAlerts(base: Alert[], head: Alert[]): Alert[] {
  const budget = new Map<string, number>();
  for (const a of base) budget.set(a.key, (budget.get(a.key) ?? 0) + 1);
  const fresh: Alert[] = [];
  for (const a of head) {
    const left = budget.get(a.key) ?? 0;
    if (left > 0) budget.set(a.key, left - 1);
    else fresh.push(a);
  }
  return fresh;
}

export function alertVerdict(base: Alert[], head: Alert[]): { ok: boolean; fresh: Alert[]; detail: string } {
  const fresh = newAlerts(base, head);
  const shown = fresh.slice(0, 5).map((a) => `${a.rule} ${a.file}:${a.line}`).join('; ');
  return { ok: fresh.length === 0, fresh, detail: `${head.length} alerts here, ${base.length} on base, ${fresh.length} new${shown ? `: ${shown}${fresh.length > 5 ? '; ...' : ''}` : ''}` };
}

// ---- the report ----

export interface GateReport { generated_at: string; head: string; base: string; base_sha: string; branch: string; dirty: boolean; min_coverage: number; steps: StepResult[]; verdict: 'PASS' | 'FAIL' }

/** One bad step fails the run. A step that was asked for but never ran counts as bad; one the caller explicitly skipped does not, but a run where nothing passed is not a pass. */
export function overallVerdict(steps: StepResult[]): 'PASS' | 'FAIL' {
  return steps.some((s) => s.status === 'pass') && steps.every((s) => s.status === 'pass' || s.status === 'skipped') ? 'PASS' : 'FAIL';
}

export function renderReport(r: GateReport): string {
  const mark: Record<StepStatus, string> = { pass: 'PASS   ', fail: 'FAIL   ', skipped: 'skipped', not_run: 'NOT RUN' };
  const lines = r.steps.map((s) => `${mark[s.status]}  ${s.step.padEnd(10)} ${(s.ms / 1000).toFixed(1).padStart(7)}s  ${s.detail}`);
  const skipped = r.steps.filter((s) => s.status === 'skipped').map((s) => s.step);
  const note = skipped.length ? `\nSkipped on request, so NOT checked: ${skipped.join(', ')}` : '';
  return [`head ${r.head}${r.dirty ? ' (uncommitted changes)' : ''}  base ${r.base} @ ${r.base_sha}`, ...lines, `VERDICT: ${r.verdict}${note}`].join('\n');
}
