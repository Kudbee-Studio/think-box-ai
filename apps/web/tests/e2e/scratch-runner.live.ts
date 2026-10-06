// Opt-in live check for the scratch runner (npm run test:live-scratch): the REAL repository at HEAD, the REAL node_modules, the REAL bubblewrap sandbox.
// 1. all four named checks on a clean HEAD must verify; 2. a patch that adds a type error must fail typecheck and tsc; 3. a patch that changes a constant must fail the
// test file that pins it; 4. the real working tree must be exactly as it was. Output: docs/evidence/p3.38-scratch-runner/live.json (output tails are short).
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { probeSandbox, runScratch, type ScratchReport } from '../../scratch-runner.ts';
import { writeEvidence } from '../helpers/evidence-file.ts';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');
const OUT = path.join(repoRoot, 'docs/evidence/p3.38-scratch-runner');
const git = (...a: string[]): string => execFileSync('git', a, { cwd: repoRoot, encoding: 'utf8' });
const treeState = (): string => createHash('sha256').update(git('status', '--porcelain', '--ignored') + git('rev-parse', 'HEAD')).digest('hex');

/** A one-line change to a tracked file as a unified git diff with three lines of context (read from the commit, not the working tree). */
function lineChange(file: string, from: string, to: string): string {
  const lines = git('show', `HEAD:${file}`).split('\n');
  const i = lines.findIndex((l) => l === from);
  if (i < 0) throw new Error(`${file} has no line ${JSON.stringify(from)}`);
  const lo = Math.max(0, i - 3); const hi = Math.min(lines.length, i + 4);
  const body = lines.slice(lo, hi).map((l, k) => (lo + k === i ? `-${l}\n+${to}` : ` ${l}`)).join('\n');
  return `diff --git a/${file} b/${file}\n--- a/${file}\n+++ b/${file}\n@@ -${lo + 1},${hi - lo} +${lo + 1},${hi - lo + 0} @@\n${body}\n`;
}
const addFile = (file: string, text: string): string => `diff --git a/${file} b/${file}\nnew file mode 100644\n--- /dev/null\n+++ b/${file}\n@@ -0,0 +1 @@\n+${text}\n`;
const brief = (r: ScratchReport) => ({ sha: r.sha, verified: r.verified, patch_sha256: r.patch_sha256, files_touched: r.files_touched, flags: r.flags, sandbox: r.sandbox, duration_ms: r.duration_ms,
  checks: r.checks.map((c) => ({ check: c.check, file: c.file ?? null, exit_code: c.exit_code, passed: c.passed, timed_out: c.timed_out, duration_ms: c.duration_ms, tests: c.tests ?? null, output_tail: c.passed ? '' : c.output_tail.slice(-500) })) });

const before = treeState();
const probe = await probeSandbox();
if (!probe.ok) { console.error(`no proven sandbox: ${probe.reason}`); process.exit(2); }
const results: Record<string, unknown> = { generated_at: new Date().toISOString(), head: git('rev-parse', 'HEAD').trim(), sandbox: probe.attestation };

const clean = await runScratch({ repoRoot, ref: 'HEAD', checks: [{ check: 'lint' }, { check: 'typecheck' }, { check: 'tsc' }, { check: 'test' }] });
results.clean = brief(clean);
console.log(`clean HEAD: verified=${clean.verified} ${clean.checks.map((c) => `${c.check}:${c.exit_code}${c.tests ? ` (${c.tests.pass} pass, ${c.tests.fail} fail)` : ''} ${(c.duration_ms / 1000).toFixed(1)}s`).join('  ')}`);

const typeErr = await runScratch({ repoRoot, ref: 'HEAD', patch: addFile('apps/web/zz-scratch-type-error.ts', "export const broken: number = 'not a number';"), checks: [{ check: 'typecheck' }, { check: 'tsc' }] });
results.type_error_patch = brief(typeErr);
console.log(`type-error patch: verified=${typeErr.verified} ${typeErr.checks.map((c) => `${c.check}:${c.exit_code}`).join('  ')} touched=${typeErr.files_touched}`);

const constPatch = lineChange('apps/web/gates.ts', 'export const DEFAULT_MIN_COVERAGE = 90;', 'export const DEFAULT_MIN_COVERAGE = 91;');
const broken = await runScratch({ repoRoot, ref: 'HEAD', patch: constPatch, checks: [{ check: 'test_file', file: 'tests/gates.test.ts' }] });
results.constant_patch = brief(broken);
console.log(`constant patch: verified=${broken.verified} ${broken.checks.map((c) => `${c.check}:${c.exit_code} ${c.tests ? `(${c.tests.pass} pass, ${c.tests.fail} fail)` : ''}`).join('  ')} flags=${JSON.stringify(broken.flags)}`);

const after = treeState();
results.working_tree_unchanged = before === after;
results.criteria = {
  c1_clean_head_verifies_all_four: clean.verified && clean.checks.length === 4,
  c2_type_error_caught: !typeErr.verified && typeErr.checks.every((c) => !c.passed),
  c3_broken_constant_caught: !broken.verified && (broken.checks[0]?.tests?.fail ?? 0) >= 1,
  c4_real_tree_untouched: before === after,
};
const ok = Object.values(results.criteria as Record<string, boolean>).every(Boolean);
results.verdict = ok ? 'PASS' : 'FAIL';
await writeEvidence(OUT, path.join(OUT, 'live.json'), results);
console.log(JSON.stringify(results.criteria), results.verdict);
process.exit(ok ? 0 : 1);
