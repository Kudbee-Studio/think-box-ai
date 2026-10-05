import { test } from 'node:test';
import assert from 'node:assert/strict';
import { goalShape, runRepoAssist } from '../investigation-assist.ts';
import type { RepoEvidence } from '../repo-tools.ts';

test('the goal shapes the engine knows, and only those', () => {
  assert.deepEqual(goalShape('Find an exported function in src/billing.ts that has no test.'), { shape: 'untested-function', file: 'src/billing.ts' });
  assert.deepEqual(goalShape('Which exported function in src/ledger.ts is never covered by a test?'), { shape: 'untested-function', file: 'src/ledger.ts' });
  assert.deepEqual(goalShape('Which file defines MAX_RETRIES and what is its value?'), { shape: 'defines-constant', name: 'MAX_RETRIES' });
  assert.deepEqual(goalShape('Find a function named chargeBitcoin.'), { shape: 'named-function', name: 'chargeBitcoin' });
  assert.equal(goalShape('Find something with no test.'), null, 'no file named in the goal, so the engine will not guess one');
  assert.equal(goalShape('Tell me about this codebase'), null);
});

const read = (lines: string[]): RepoEvidence => ({ tool: 'repo_read', path: 'src/x.ts', start: 1, end: lines.length, total_lines: lines.length, lines: lines.map((text, i) => ({ n: i + 1, text })), fetched_at: '', tool_calls: 1, latency_ms: 0 });
const search = (query: string, path: string): RepoEvidence => ({ tool: 'repo_search', query, path, matches: [], truncated: false, files_scanned: 1, fetched_at: '', tool_calls: 1, latency_ms: 0 });

test('untested-function: reads the file the goal names, then searches the tests folder for each exported function (capped)', async () => {
  const calls: Array<[string, Record<string, unknown>]> = [];
  const n = await runRepoAssist('Find an exported function in src/x.ts that has no test.', async (tool, args) => {
    calls.push([tool, args]);
    return tool === 'repo_read' ? read(['export const LIMIT = 1;', ...Array.from({ length: 9 }, (_, i) => `export function f${i}() {`)]) : search(String(args.query), String(args.path));
  });
  assert.equal(calls[0]![0], 'repo_read'); assert.equal(calls[0]![1].path, 'src/x.ts');
  assert.equal(calls.filter((c) => c[0] === 'repo_search').length, 6, 'capped at 6 symbols; the constant is not a function');
  assert.ok(calls.filter((c) => c[0] === 'repo_search').every((c) => c[1].path === 'tests'));
  assert.equal(n, 7);
});
test('no tests folder: the engine falls back to a whole-repo search for that symbol; a failed read yields nothing more', async () => {
  const seen: string[] = [];
  await runRepoAssist('Find an exported function in src/x.ts that has no test.', async (tool, args) => {
    if (tool === 'repo_read') return read(['export function only() {']);
    seen.push(String(args.path)); return args.path === 'tests' ? null : search(String(args.query), '');
  });
  assert.deepEqual(seen, ['tests', '']);
  assert.equal(await runRepoAssist('Find an exported function in src/missing.ts that has no test.', async () => null), 1, 'the read failed: one call, nothing invented afterwards');
});
test('constant and named-function goals get one whole-repo search; unknown goals get nothing', async () => {
  const calls: Array<Record<string, unknown>> = [];
  assert.equal(await runRepoAssist('Which file defines TTL_SECONDS and what is its value?', async (_t, a) => { calls.push(a); return search('TTL_SECONDS', ''); }), 1);
  assert.deepEqual(calls, [{ query: 'TTL_SECONDS', path: '' }]);
  assert.equal(await runRepoAssist('hello', async () => { throw new Error('must not be called'); }), 0);
});
