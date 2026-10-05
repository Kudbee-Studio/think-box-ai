// The engine-run absence check: true absence is grounded, a false absence is rejected with the reference that disproves it, aliases and re-exports count.
import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { aliasesIn, claimKinds, extractSymbol, isTestPath, runAbsenceCheck } from '../absence.ts';
import { validateFinding, type RepoFinding } from '../grounding.ts';

let root = '';
before(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), 'absence-'));
  const w = (rel: string, t: string) => { fs.mkdirSync(path.dirname(path.join(root, rel)), { recursive: true }); fs.writeFileSync(path.join(root, rel), t); };
  w('src/lib.ts', 'export function orphan() {\n  return 1;\n}\nexport function covered() {\n  return 2;\n}\nexport function viaAlias() {\n  return 3;\n}\nexport function onlyUsed() {\n  return 4;\n}\n');
  w('src/index.ts', 'export { viaAlias as publicName } from "./lib.ts";\nimport { onlyUsed } from "./lib.ts";\nonlyUsed();\n');
  w('tests/lib.test.ts', 'import { covered } from "../src/lib.ts";\nimport { publicName } from "../src/index.ts";\ncovered();\npublicName();\n');
});
after(() => fs.rmSync(root, { recursive: true, force: true }));

const f = (symbol: string, line: number, claim: string, file = 'src/lib.ts'): RepoFinding => ({ found: true, file, line, quote: `export function ${symbol}() {`, claim });

describe('claim kinds and symbols (pure)', () => {
  it('reads what is being claimed', () => {
    assert.deepEqual(claimKinds('orphan has no tests'), ['test']);
    assert.deepEqual(claimKinds('this is unused'), ['usage']);
    assert.deepEqual(claimKinds('never called and never tested').sort(), ['test', 'usage']);
    assert.deepEqual(claimKinds('this function returns 7'), []);
  });
  it('finds the symbol in backticks, as name(), or from the quoted declaration', () => {
    assert.equal(extractSymbol({ claim: 'The function `foo` has no test', quote: 'x' }), 'foo');
    assert.equal(extractSymbol({ claim: 'bar() is unused', quote: 'x' }), 'bar');
    assert.equal(extractSymbol({ claim: 'this is unused', quote: 'export const BETA_LIMIT = 42;' }), 'BETA_LIMIT');
    assert.equal(extractSymbol({ claim: 'nothing is tested', quote: 'return 1' }), null);
  });
  it('recognises test files and aliases', () => {
    assert.equal(isTestPath('tests/a.ts'), true);
    assert.equal(isTestPath('src/a.test.ts'), true);
    assert.equal(isTestPath('src/a.ts'), false);
    assert.deepEqual(aliasesIn('xx', [{ path: 'a', line: 1, text: 'export { xx as yy } from "./m"' }, { path: 'a', line: 2, text: 'const zz = xx;' }]).sort(), ['yy', 'zz']);
  });
});

describe('runAbsenceCheck against a real directory', () => {
  it('a true absence: no reference at all -> ran, nothing contradicts it, grounded by the engine search', async () => {
    const finding = f('orphan', 1, 'The function `orphan` has no tests.');
    const c = await runAbsenceCheck(finding, root);
    assert.equal(c.path, 'engine_search'); assert.equal(c.ran, true); assert.equal(c.contradicted.length, 0);
    assert.equal(c.searches.length >= 1, true);
    const g = validateFinding(finding, [{ tool: 'repo_read', path: 'src/lib.ts', start: 1, end: 3, total_lines: 12, lines: [{ n: 1, text: 'export function orphan() {' }], fetched_at: '', tool_calls: 1, latency_ms: 0 }, ...c.searches], c);
    assert.equal(g.status, 'GROUNDED', JSON.stringify(g.unsupported));
    assert.equal(g.checked.absence, 1);
  });
  it('a false absence: a test imports it -> rejected, naming the test file', async () => {
    const finding = f('covered', 4, 'The function `covered` has no tests.');
    const c = await runAbsenceCheck(finding, root);
    assert.equal(c.contradicted.some((h) => h.path === 'tests/lib.test.ts'), true);
    const g = validateFinding(finding, [{ tool: 'repo_read', path: 'src/lib.ts', start: 1, end: 6, total_lines: 12, lines: [{ n: 4, text: 'export function covered() {' }], fetched_at: '', tool_calls: 1, latency_ms: 0 }], c);
    assert.equal(g.status, 'GROUNDING FAILED');
    assert.match(g.unsupported[0]!.why, /claim is false/);
  });
  it('an alias / re-export: tested only through its public name -> still a false absence', async () => {
    const c = await runAbsenceCheck(f('viaAlias', 7, 'The function `viaAlias` has no tests.'), root);
    assert.deepEqual(c.aliases, ['publicName']);
    assert.equal(c.contradicted.some((h) => h.path === 'tests/lib.test.ts' && /publicName/.test(h.text)), true);
  });
  it('"has no test" is true for something used in src but not in tests, while "is unused" is false for it', async () => {
    const t = await runAbsenceCheck(f('onlyUsed', 10, 'The function `onlyUsed` has no tests.'), root);
    assert.equal(t.contradicted.length, 0);
    const u = await runAbsenceCheck(f('onlyUsed', 10, 'The function `onlyUsed` is unused.'), root);
    assert.equal(u.contradicted.some((h) => h.path === 'src/index.ts'), true);
  });
  it('the definition line itself never counts as a reference, and a longer name does not match a shorter one', async () => {
    const c = await runAbsenceCheck(f('orphan', 1, '`orphan` is unused'), root);
    assert.equal(c.contradicted.length, 0);
    fs.writeFileSync(path.join(root, 'src/other.ts'), 'export const orphanage = 1;\n');
    const d = await runAbsenceCheck(f('orphan', 1, '`orphan` is unused'), root);
    assert.equal(d.contradicted.length, 0, 'orphanage is a different word');
    fs.rmSync(path.join(root, 'src/other.ts'));
  });
  it('cannot-check cases escalate instead of guessing: no symbol, a universal claim, a cut-off search', async () => {
    const v = await runAbsenceCheck({ found: true, file: 'src/lib.ts', line: 2, quote: 'return 1;', claim: 'Nothing in this repository is tested.' }, root);
    assert.equal(v.path, 'escalate'); assert.match(v.reason!, /everything or nothing/);
    const n = await runAbsenceCheck({ found: true, file: 'src/lib.ts', line: 2, quote: 'return 1;', claim: 'this is unused' }, root);
    assert.equal(n.path, 'escalate'); assert.match(n.reason!, /no symbol/);
    const big = fs.mkdtempSync(path.join(os.tmpdir(), 'absence-big-'));
    try {
      fs.writeFileSync(path.join(big, 'a.ts'), 'export function zed() {}\n' + 'zed\n'.repeat(60));
      const t = await runAbsenceCheck({ found: true, file: 'a.ts', line: 1, quote: 'export function zed() {}', claim: '`zed` has no tests' }, big);
      assert.equal(t.path, 'escalate'); assert.match(t.reason!, /cut off/);
      const g = validateFinding({ found: true, file: 'a.ts', line: 1, quote: 'export function zed() {}', claim: '`zed` has no tests' }, [{ tool: 'repo_read', path: 'a.ts', start: 1, end: 1, total_lines: 61, lines: [{ n: 1, text: 'export function zed() {}' }], fetched_at: '', tool_calls: 1, latency_ms: 0 }], t);
      assert.equal(g.classification, 'needs_escalation');
    } finally { fs.rmSync(big, { recursive: true, force: true }); }
  });
  it('a search that throws is "could not check", never "absent"', async () => {
    const c = await runAbsenceCheck(f('orphan', 1, '`orphan` has no tests'), path.join(root, 'does-not-exist'));
    assert.equal(c.path, 'escalate'); assert.match(c.reason!, /failed/);
  });
  it('a finding that claims nothing is missing is not checked', async () => {
    const c = await runAbsenceCheck(f('orphan', 1, '`orphan` returns 1'), root);
    assert.equal(c.applies, false);
    assert.equal((await runAbsenceCheck({ found: false, reason: 'x' }, root)).applies, false);
  });
});
