import { test } from 'node:test';
import assert from 'node:assert/strict';
import { alertKey, alertVerdict, coverageVerdict, newAlerts, overallVerdict, parseGateArgs, parseSarif, renderReport, selectedSteps, type GateReport, type StepResult } from '../gates.ts';

const sarif = (results: unknown[]): string => JSON.stringify({ runs: [{ results }] });
const res = (rule: string, uri: string, line: number, hash: string | undefined, text = 'm'): unknown => ({
  ruleId: rule, message: { text }, locations: [{ physicalLocation: { artifactLocation: { uri }, region: { startLine: line } } }],
  ...(hash ? { partialFingerprints: { primaryLocationLineHash: hash } } : {}),
});

test('steps: default is all six in fixed order; --only picks, --skip removes, "codeql" is both languages', () => {
  assert.deepEqual(selectedSteps(parseGateArgs([])), ['lint', 'typecheck', 'tsc', 'tests', 'codeql-js', 'codeql-py']);
  assert.deepEqual(selectedSteps(parseGateArgs(['--only', 'tests,lint'])), ['lint', 'tests']);
  assert.deepEqual(selectedSteps(parseGateArgs(['--skip', 'codeql'])), ['lint', 'typecheck', 'tsc', 'tests']);
  assert.deepEqual(selectedSteps(parseGateArgs(['--only', 'codeql', '--skip', 'codeql-py'])), ['codeql-js']);
});

test('args: flags, defaults and refusals', () => {
  const o = parseGateArgs(['--min-coverage', '85.5', '--base', 'origin/main', '--allow-dirty', '--record']);
  assert.equal(o.minCoverage, 85.5); assert.equal(o.base, 'origin/main'); assert.equal(o.allowDirty, true); assert.equal(o.record, true);
  const d = parseGateArgs([]);
  assert.equal(d.minCoverage, 90); assert.equal(d.base, 'main'); assert.equal(d.allowDirty, false); assert.equal(d.record, false);
  assert.throws(() => parseGateArgs(['--only', 'lnt']), /unknown step "lnt"/);
  assert.throws(() => parseGateArgs(['--bogus']), /unknown option --bogus/);
  assert.throws(() => parseGateArgs(['--base']), /needs a value/);
  assert.throws(() => parseGateArgs(['--only', '--record']), /needs a value/);
  assert.throws(() => parseGateArgs(['--min-coverage', '101']), /0 to 100/);
  assert.throws(() => parseGateArgs(['--min-coverage', 'abc']), /0 to 100/);
});

test('coverage: at the floor passes, below fails, and anything unreadable fails', () => {
  const sum = (pct: unknown): string => JSON.stringify({ total: { lines: { pct } } });
  assert.deepEqual(coverageVerdict(sum(90), 90), { ok: true, pct: 90, detail: 'lines 90% (floor 90%)' });
  assert.equal(coverageVerdict(sum(89.99), 90).ok, false);
  assert.equal(coverageVerdict(sum(91.13), 90).ok, true);
  assert.equal(coverageVerdict(null, 90).ok, false);
  assert.match(coverageVerdict(null, 90).detail, /no coverage summary/);
  assert.match(coverageVerdict('{nope', 90).detail, /not valid JSON/);
  assert.match(coverageVerdict('{"total":{}}', 90).detail, /no total line percentage/);
  assert.match(coverageVerdict(sum('91'), 90).detail, /no total line percentage/);
  assert.equal(coverageVerdict(sum(null), 90).ok, false);
});

test('sarif: reads rule, file, line, message; hash when present, message otherwise; several runs', () => {
  const text = JSON.stringify({ runs: [
    { results: [res('js/a', 'x.ts', 4, 'h1:1'), res('js/b', 'y.ts', 9, undefined, 'flow text')] },
    { results: [{ message: {} }] },
    {},
  ] });
  const a = parseSarif(text);
  assert.equal(a.length, 3);
  assert.deepEqual(a[0], { rule: 'js/a', file: 'x.ts', line: 4, message: 'm', key: 'js/a|x.ts|h1:1' });
  assert.equal(a[1].key, 'js/b|y.ts|flow text');
  assert.deepEqual([a[2].rule, a[2].file, a[2].line, a[2].message], ['unknown', 'unknown', 0, '']);
  assert.equal(alertKey('r', 'f', undefined, 'msg'), 'r|f|msg');
  assert.throws(() => parseSarif('{oops'), /not valid JSON/);
  assert.throws(() => parseSarif('{}'), /no runs/);
});

test('new alerts: a moved line is not new, a changed finding is, and a second copy counts', () => {
  const base = parseSarif(sarif([res('js/a', 'x.ts', 10, 'h1:1'), res('js/b', 'y.ts', 3, 'h2:1')]));
  const moved = parseSarif(sarif([res('js/a', 'x.ts', 14, 'h1:1'), res('js/b', 'y.ts', 3, 'h2:1')]));
  assert.deepEqual(newAlerts(base, moved), []);
  const changed = parseSarif(sarif([res('js/a', 'x.ts', 10, 'h9:1'), res('js/b', 'y.ts', 3, 'h2:1')]));
  assert.deepEqual(newAlerts(base, changed).map((a) => a.key), ['js/a|x.ts|h9:1']);
  const twice = parseSarif(sarif([res('js/a', 'x.ts', 10, 'h1:1'), res('js/a', 'x.ts', 40, 'h1:1'), res('js/b', 'y.ts', 3, 'h2:1')]));
  assert.equal(newAlerts(base, twice).length, 1);
  assert.deepEqual(newAlerts(base, []), []);
});

test('alert verdict: zero new passes with counts; new ones fail and name the first five', () => {
  const base = parseSarif(sarif([res('js/a', 'x.ts', 1, 'h1:1')]));
  assert.deepEqual(alertVerdict(base, base), { ok: true, fresh: [], detail: '1 alerts here, 1 on base, 0 new' });
  const many = parseSarif(sarif(Array.from({ length: 7 }, (_, i) => res('js/n', `f${i}.ts`, i + 1, `n${i}:1`))));
  const v = alertVerdict(base, many);
  assert.equal(v.ok, false); assert.equal(v.fresh.length, 7);
  assert.match(v.detail, /7 new: js\/n f0\.ts:1; .*f4\.ts:5; \.\.\.$/);
  assert.match(alertVerdict(base, parseSarif(sarif([res('js/z', 'z.ts', 2, 'z:1')]))).detail, /1 new: js\/z z\.ts:2$/);
});

const step = (status: StepResult['status'], name: StepResult['step'] = 'lint'): StepResult => ({ step: name, status, detail: 'd', ms: 1500 });

test('verdict: all pass is PASS; one fail or not-run is FAIL; skipped alone is not a pass', () => {
  assert.equal(overallVerdict([step('pass'), step('pass', 'tsc')]), 'PASS');
  assert.equal(overallVerdict([step('pass'), step('skipped', 'tests')]), 'PASS');
  assert.equal(overallVerdict([step('pass'), step('fail', 'tests')]), 'FAIL');
  assert.equal(overallVerdict([step('pass'), step('not_run', 'codeql-js')]), 'FAIL');
  assert.equal(overallVerdict([step('skipped')]), 'FAIL');
  assert.equal(overallVerdict([]), 'FAIL');
});

test('report: lists every step, says what was skipped, and flags uncommitted changes', () => {
  const base: GateReport = { generated_at: 'x', head: 'abc1234', base: 'main', base_sha: 'def5678', branch: 'b', dirty: false, min_coverage: 90, steps: [step('pass'), step('skipped', 'codeql-py'), step('not_run', 'codeql-js')], verdict: 'FAIL' };
  const text = renderReport(base);
  assert.match(text, /^head abc1234  base main @ def5678\nPASS     lint/);
  assert.match(text, /skipped {2}codeql-py/);
  assert.match(text, /NOT RUN {2}codeql-js/);
  assert.match(text, /VERDICT: FAIL\nSkipped on request, so NOT checked: codeql-py$/);
  assert.match(renderReport({ ...base, dirty: true, steps: [step('pass')], verdict: 'PASS' }), /head abc1234 \(uncommitted changes\)/);
  assert.doesNotMatch(renderReport({ ...base, steps: [step('pass')], verdict: 'PASS' }), /Skipped on request/);
});
