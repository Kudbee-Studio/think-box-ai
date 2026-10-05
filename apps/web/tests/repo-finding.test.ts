// Findings from the repository: a file, a line and an exact quote must trace to what the worker's own tool calls returned; absence needs a zero-hit search.
import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { newRunContext, runGovernedTool, TOOLS } from '../agent.ts';
import { parseFinding, validateFinding, type RepoFinding } from '../grounding.ts';
import { repoRead, repoSearch, type RepoEvidence } from '../repo-tools.ts';
import { lookupHooks } from './helpers/lookup-hooks.ts';

let root = '';
before(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), 'repo-finding-'));
  const w = (rel: string, t: string) => { fs.mkdirSync(path.dirname(path.join(root, rel)), { recursive: true }); fs.writeFileSync(path.join(root, rel), t); };
  w('src/alpha.ts', 'export function alpha(x: number): number {\n  return x + 1;\n}\nexport function orphan() {\n  return 7;\n}\n');
  w('tests/alpha.test.ts', 'import { alpha } from "../src/alpha.ts";\ntest("alpha", () => alpha(1));\n');
  process.env.KUDBEE_REPO_ROOT = root;
});
after(() => { delete process.env.KUDBEE_REPO_ROOT; fs.rmSync(root, { recursive: true, force: true }); });

const found = (o: Partial<RepoFinding> = {}): RepoFinding => ({ found: true, file: 'src/alpha.ts', line: 4, quote: 'export function orphan()', claim: 'The function `orphan` exists.', ...o });
const claims = (f: RepoFinding, ev: RepoEvidence[]) => validateFinding(f, ev).unsupported.map((u) => `${u.kind}:${u.claim}`);

describe('parseFinding', () => {
  it('accepts a complete finding and a no-finding with a reason', () => {
    assert.deepEqual(parseFinding({ found: true, file: 'a.ts', line: 3, quote: 'q', claim: 'c' }), { ok: true, finding: { found: true, file: 'a.ts', line: 3, quote: 'q', claim: 'c' } });
    assert.deepEqual(parseFinding({ found: false, reason: 'nothing stood out' }), { ok: true, finding: { found: false, reason: 'nothing stood out' } });
    assert.equal(parseFinding({ found: true, file: 'a.ts', line: 3, quote: 'q', claim: 'c', absence_search: { query: 'x', path: 'tests' } }).ok, true);
  });
  it('rejects malformed findings with a reason', () => {
    const bad: unknown[] = [null, [], 'x', {}, { found: 'yes' }, { found: false }, { found: false, reason: ' ' }, { found: true, line: 1, quote: 'q', claim: 'c' }, { found: true, file: 'a.ts', line: 0, quote: 'q', claim: 'c' }, { found: true, file: 'a.ts', line: 1.5, quote: 'q', claim: 'c' }, { found: true, file: 'a.ts', line: 1, claim: 'c' }, { found: true, file: 'a.ts', line: 1, quote: 'q' }, { found: true, file: 'a.ts', line: 1, quote: 'x'.repeat(241), claim: 'c' }, { found: true, file: 'a.ts', line: 1, quote: 'q', claim: 'c', extra: 1 }, { found: true, file: 'a.ts', line: 1, quote: 'q', claim: 'c', absence_search: 'x' }];
    for (const b of bad) assert.equal(parseFinding(b).ok, false, JSON.stringify(b));
  });
});

describe('validateFinding against real tool evidence', () => {
  it('grounds a finding whose file, line and quote the worker really read', async () => {
    const ev = [await repoRead({ path: 'src/alpha.ts', start: 1, end: 6 })];
    const r = validateFinding(found(), ev);
    assert.equal(r.status, 'GROUNDED');
    assert.equal(r.checked.quotes, 1);
    assert.equal(r.checked.identifiers, 1);
  });
  it('accepts a quote copied from a search match, and a quote running over the next lines', async () => {
    const viaSearch = [await repoSearch({ query: 'orphan', path: '' })];
    assert.equal(validateFinding(found(), viaSearch).status, 'GROUNDED');
    const ev = [await repoRead({ path: 'src/alpha.ts', start: 1, end: 6 })];
    assert.equal(validateFinding(found({ quote: 'export function orphan() { return 7;' }), ev).status, 'GROUNDED');
  });
  it('fails a file the worker never read, a line no tool returned, and a quote that is not there', async () => {
    const ev = [await repoRead({ path: 'src/alpha.ts', start: 1, end: 3 })];
    assert.ok(claims(found({ file: 'src/other.ts' }), ev).includes('file:src/other.ts'));
    assert.ok(claims(found({ line: 4 }), ev).some((c) => c.startsWith('line:src/alpha.ts:4')), 'line 4 was outside the 1-3 window');
    assert.ok(claims(found({ line: 1, quote: 'export function gamma' }), ev).some((c) => c.startsWith('quote:')));
    assert.equal(validateFinding(found(), []).classification, 'no_evidence');
  });
  it('fails an identifier in backticks that no tool output contains', async () => {
    const ev = [await repoRead({ path: 'src/alpha.ts', start: 1, end: 6 })];
    assert.ok(claims(found({ claim: 'The function `invented` is never called.', absence_search: undefined }), ev).includes('identifier:invented'));
  });
  it('a claim of absence is grounded only by a search that ran, found nothing and was not cut off', async () => {
    const read = await repoRead({ path: 'src/alpha.ts', start: 1, end: 6 });
    const claim = 'The function `orphan` has no tests.';
    assert.ok(claims(found({ claim }), [read]).some((c) => c.startsWith('absence:')), 'no absence_search given');
    const noSearchRun = found({ claim, absence_search: { query: 'orphan', path: 'tests' } });
    assert.ok(claims(noSearchRun, [read]).some((c) => c.startsWith('absence:orphan in tests')), 'the search was never run');
    const zero = await repoSearch({ query: 'orphan', path: 'tests' });
    assert.equal(validateFinding(noSearchRun, [read, zero]).status, 'GROUNDED');
    const hit = await repoSearch({ query: 'alpha', path: 'tests' });
    assert.ok(claims(found({ claim: 'The function `alpha` has no tests.', quote: 'export function alpha(x: number)', line: 1, absence_search: { query: 'alpha', path: 'tests' } }), [read, hit]).some((c) => /not absent|match/.test(c) || c.startsWith('absence:alpha')));
    const cut: RepoEvidence = { ...(zero as any), truncated: true };
    assert.ok(claims(noSearchRun, [read, cut]).some((c) => c.startsWith('absence:orphan')), 'a cut-off search proves nothing');
    const wrongPath = await repoSearch({ query: 'orphan', path: '' });
    assert.ok(claims(noSearchRun, [read, wrongPath]).some((c) => c.startsWith('absence:')), 'a search of a different scope does not prove absence in tests/');
  });
  it('recognizes the many ways a claim of absence is worded (found in a real run: "without any tests" slipped through)', async () => {
    const read = await repoRead({ path: 'src/alpha.ts', start: 1, end: 6 });
    for (const claim of ['The function `orphan` is found without any tests.', 'The function `orphan` lacks tests.', 'Function `orphan` is not covered by tests.', '`orphan` has zero coverage.', '`orphan` is untested.', '`orphan` is never called.', 'No test exercises `orphan`.', '`orphan` isn\'t tested', '`orphan` is unused.']) {
      assert.ok(claims(found({ claim }), [read]).some((c) => c.startsWith('absence:')), claim);
    }
    for (const claim of ['The function `orphan` returns the number 7.', 'The function `orphan` is exported from this module.']) assert.equal(validateFinding(found({ claim }), [read]).status, 'GROUNDED', claim);
  });
  it('"nothing found" is an honest outcome, not a grounding failure', () => {
    assert.equal(validateFinding({ found: false, reason: 'nothing stood out' }, []).status, 'GROUNDED');
  });
});

describe('repo tools through the governed path', () => {
  it('are not in a default run: not offered, and refused if called without an allowlist naming them', async () => {
    const { hooks } = lookupHooks();
    const g = await runGovernedTool('repo_read', { path: 'src/alpha.ts' }, hooks, newRunContext(), 1);
    assert.equal(g.output.ok, false);
    assert.match(String(g.output.error), /repository tools are opt-in/);
    const g2 = await runGovernedTool('repo_search', { query: 'alpha' }, lookupHooks({ allowedTools: ['live_lookup'] }).hooks, newRunContext(), 1);
    assert.equal(g2.output.ok, false);
    assert.ok(TOOLS.some((t) => t.function.name === 'repo_read'), 'registered in the one registry');
  });
  it('work when the allowlist names them: evidence, no approval prompt (read-only), and bad requests are explicit errors', async () => {
    const { hooks, approvals } = lookupHooks({ allowedTools: ['repo_search', 'repo_read'] });
    const ctx = newRunContext();
    const s = await runGovernedTool('repo_search', { query: 'orphan', path: 'src' }, hooks, ctx, 1);
    assert.equal(s.output.ok, true);
    assert.equal((s.output as any).evidence.matches[0].line, 4);
    const r = await runGovernedTool('repo_read', { path: 'src/alpha.ts', start: 1, end: 3 }, hooks, ctx, 2);
    assert.equal((r.output as any).evidence.lines.length, 3);
    assert.equal(approvals.length, 0);
    for (const args of [{ path: '../../etc/passwd.ts' }, { path: '.env' }, { path: 'src/alpha.ts', extra: 1 }, { path: 'src/missing.ts' }]) {
      const bad = await runGovernedTool('repo_read', args as any, hooks, ctx, 3);
      assert.equal(bad.output.ok, false, JSON.stringify(args));
      assert.equal((bad.output as any).evidence, undefined);
    }
  });
});
