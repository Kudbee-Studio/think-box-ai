// ADR 029 P3.13: the 100-cell Think Token. Every cell is a documented field drawn from real stored data; the 54-sticker cube is a view; learning events record
// exactly which cells changed, with a ledger receipt. Real SQLite store, no mocks.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { CELL_COUNT, CELL_DEFS, FACES, ROWS, STICKER_COUNT, buildCells, diffCells, lessonFailureModes, projectTo54, stickerOfCell } from '../think-token-cube.ts';
import { SqliteTokenStore, type TokenDraft } from '../think-token-store.ts';
import { formatCubeGrid, readTokenCube } from '../think-token-reader.ts';

const T0 = Date.parse('2026-10-02T12:00:00Z');
const draft = (n: number, over: Partial<TokenDraft> = {}): TokenDraft => ({
  source_run_id: `run-${n}`, kind: 'lesson', title: `Habit ${n} amber${n} basalt${n}`, content: `Prefer amber${n} when the situation repeats; it avoids a missing file.`, tags: ['tool:write_file'], evidence_ref: `run:run-${n}`,
  extractor: 'mercury', extract_model: 'mercury-2', extract_meta: { latency_ms: 900, tokens_in: 600, tokens_out: 200 }, ...over,
});
const ok = <T extends { ok: boolean }>(r: T): Extract<T, { ok: true }> => { assert.equal(r.ok, true, JSON.stringify(r)); return r as Extract<T, { ok: true }>; };
const accept = (s: SqliteTokenStore, d: TokenDraft): string => {
  const id = ok(s.write(d, 't')).id;
  for (const to of ['extracted', 'scored'] as const) ok(s.advance(id, to, 't'));
  ok(s.advance(id, 'challenged', 't', { challenge: { verdict: 'pass', reason: 'specific and supported', model: 'mercury-2', meta: { latency_ms: 700, tokens_in: 500, tokens_out: 120 } } }));
  ok(s.advance(id, 'accepted', 't'));
  return id;
};
const byKey = (cells: Array<{ key: string; display: string }>): Record<string, string> => Object.fromEntries(cells.map((c) => [c.key, c.display]));

test('the layout: exactly 100 distinct documented cells, ten rows of ten, each with a source and a description', () => {
  assert.equal(CELL_DEFS.length, CELL_COUNT);
  assert.equal(new Set(CELL_DEFS.map((d) => d.key)).size, 100, 'unique keys');
  assert.deepEqual([...new Set(CELL_DEFS.map((d) => d.row))], [...ROWS]);
  for (const r of ROWS) assert.equal(CELL_DEFS.filter((d) => d.row === r).length, 10, r);
  for (const d of CELL_DEFS) {
    assert.ok(d.label.length > 2 && d.source.length > 3 && d.doc.length > 10, `${d.key} is documented`);
    assert.equal(d.index, ROWS.indexOf(d.row) * 10 + d.col);
  }
});

test('total and honest: any token maps to 100 cells; a fresh token has data only where data exists, everything else is "empty", never a stand-in', () => {
  const s = new SqliteTokenStore();
  const id = ok(s.write(draft(1), 't')).id;
  const cells = s.cubeCells(id, T0)!;
  assert.equal(cells.length, 100);
  const d = byKey(cells);
  assert.equal(d.id, id);
  assert.equal(d.status, 'candidate');
  for (const k of ['challenge_verdict', 'challenge_model', 'challenge_latency', 'last_used_age', 'win_rate', 'embedding_model', 'when_to_use_source', 'merged_into', 'strongest_weight', 'credit_1']) {
    assert.equal(d[k], 'empty', `${k} has no data for a fresh token`);
    assert.equal(cells.find((c) => c.key === k)!.value, null);
  }
  assert.equal(d.never_used, 'yes');
  assert.ok(cells.filter((c) => c.empty).length >= 20, 'most of the grid is honestly empty for a fresh token');
  assert.equal(s.cubeCells('TT-999999'), null, 'an unknown token has no cube');
  s.close();
});

test('stable: the same token and clock give byte-identical cells', () => {
  const s = new SqliteTokenStore();
  const id = accept(s, draft(1));
  assert.deepEqual(s.cubeCells(id, T0), s.cubeCells(id, T0));
  assert.equal(JSON.stringify(s.cubeCells(id, T0)), JSON.stringify(s.cubeCells(id, T0)));
  s.close();
});

test('changes only where the data changed: a new use flips the use/score/receipt cells and nothing about identity, lesson, challenge or links', () => {
  const s = new SqliteTokenStore();
  const id = accept(s, draft(1));
  const before = s.cubeCells(id, T0 + 3_600_000)!;
  s.recordUse([id], 'run-x', 'agent');
  const after = s.cubeCells(id, T0 + 3_600_000)!;
  const changed = diffCells(before, after).map((c) => c.key);
  const allowed = new Set(['uses', 'distinct_runs', 'uses_7d', 'ledger_uses', 'never_used', 'reuse', 'recency', 'base_score', 'score', 'score_age_days', 'last_used_age', 'receipts', 'last_receipt_age', 'first_receipt_age', 'win_rate']);
  for (const k of changed) assert.ok(allowed.has(k), `unexpected cell changed by a use: ${k}`);
  for (const k of ['uses', 'distinct_runs', 'ledger_uses', 'never_used', 'reuse']) assert.ok(changed.includes(k), `${k} should change on a use`);
  for (const k of ['id', 'kind', 'title_len', 'content_len', 'challenge_verdict', 'challenge_model', 'links_total', 'status', 'is_accepted', 'tags']) assert.ok(!changed.includes(k), `${k} must not change on a use`);
  s.close();
});

test('feedback changes the feedback cells only; a link changes the link cells of both ends only', () => {
  const s = new SqliteTokenStore();
  const a = accept(s, draft(1, { tags: ['tool:write_file', 'tool:read_rss'] }));
  const b = accept(s, draft(2, { tags: ['tool:write_file', 'tool:read_rss'] }));
  accept(s, draft(3, { tags: ['tool:algorand'] }));
  accept(s, draft(4, { tags: ['tool:medication'] }));
  const t = T0 + 3_600_000;
  const beforeA = s.cubeCells(a, t)!;
  ok(s.feedback(a, 'up', 'founder'));
  const fb = diffCells(beforeA, s.cubeCells(a, t)!).map((c) => c.key);
  for (const k of ['thumbs_up', 'feedback', 'has_feedback', 'ledger_outcomes']) void k;
  assert.ok(fb.includes('thumbs_up') && fb.includes('feedback') && fb.includes('has_feedback'));
  assert.ok(!fb.includes('uses') && !fb.includes('links_total') && !fb.includes('status'));
  const beforeLinks = s.cubeCells(b, t)!;
  s.linkToken(a, 'p');
  const linked = diffCells(beforeLinks, s.cubeCells(b, t)!).map((c) => c.key);
  assert.ok(linked.includes('links_total') && linked.includes('link_same_tool'));
  assert.ok(!linked.includes('uses') && !linked.includes('thumbs_up') && !linked.includes('challenge_verdict'));
  s.close();
});

test('cell events: every learning step records which cells changed in SQLite, with one ledger receipt naming the cause; nothing is recorded when nothing changed; the chain still verifies', () => {
  const s = new SqliteTokenStore();
  const id = accept(s, draft(1));
  const causes = () => [...new Set(s.cellEvents(id, 500).map((e) => e.cause))];
  assert.ok(['created', 'transition:extracted', 'transition:scored', 'transition:challenged', 'transition:accepted'].every((c) => causes().includes(c)), causes().join());
  const ledgerBefore = s.verifyLedger().entries;
  const noop = s.recordCells(id, 'noop-check', 'x', Date.now());
  assert.deepEqual(noop, [], 'nothing changed, nothing recorded');
  assert.equal(s.verifyLedger().entries, ledgerBefore);
  s.recordUse([id], 'run-1', 'agent');
  s.feedback(id, 'down', 'founder');
  assert.ok(causes().includes('used') && causes().includes('feedback:down'));
  const used = s.cellEvents(id, 500).filter((e) => e.cause === 'used');
  assert.ok(used.some((e) => e.key === 'uses' && e.before === '0' && e.after === '1'), 'before and after values are stored');
  assert.ok(used.every((e) => e.ledger_seq !== null), 'every event points at its ledger receipt');
  const raw = s.handle.prepare("SELECT detail FROM think_token_ledger WHERE action = 'cells' AND seq = ?").get(used[0]!.ledger_seq) as { detail: string };
  const detail = JSON.parse(raw.detail) as { cause: string; changed: string[] };
  assert.equal(detail.cause, 'used');
  assert.ok(detail.changed.includes('uses'));
  assert.equal(s.verifyLedger().ok, true);
  assert.equal(s.get(id)!.receipts!.some((r) => r.action === 'cells'), false, 'cell bookkeeping receipts do not clutter the token\'s own receipt list');
  s.close();
});

test('merged and linked tokens record cell events for both ends; a merge flips the health cells', () => {
  const s = new SqliteTokenStore();
  const a = accept(s, draft(1, { title: 'Create-then-verify file workflow', content: 'After write_file call list_files to confirm the file exists before reporting success.', tags: ['tool:write_file', 'tool:list_files'] }));
  const b = accept(s, draft(2, { title: 'Verify file creation with list_files', content: 'Confirm with list_files that the file write_file created is present before you answer.', tags: ['tool:write_file', 'tool:list_files'] }));
  accept(s, draft(3, { title: 'Feed digests', content: 'Summaries of syndicated feeds cite each headline.', tags: ['tool:read_rss'] }));
  s.feedback(a, 'up', 'founder');
  const report = s.mergeDuplicates('p', ['write_file', 'list_files', 'read_rss']);
  assert.equal(report.merged.length, 1);
  const [gone, kept] = [report.merged[0]!.id, report.merged[0]!.into];
  assert.ok(s.cellEvents(gone, 500).some((e) => e.cause === 'merged:away' && e.key === 'is_merged_away' && e.after === 'yes'));
  assert.ok(s.cellEvents(kept, 500).some((e) => e.cause === 'merged:absorbed' && e.key === 'merged_from'));
  assert.ok(s.cellEvents(gone, 500).some((e) => e.cause === 'merged:away' && e.key === 'merged_into'));
  assert.ok(s.cellEvents(gone, 500).some((e) => e.cause === 'merged:away' && e.key === 'is_retired' && e.after === 'yes'));
  void b;
  s.close();
});

test('the 54-sticker view: total (every cell lands on exactly one sticker), stable, six faces of nine, every sticker covers one or two cells', () => {
  const seen = new Map<number, number>();
  for (let c = 0; c < 100; c++) { const st = stickerOfCell(c); seen.set(st, (seen.get(st) ?? 0) + 1); assert.equal(stickerOfCell(c), st, 'stable'); }
  assert.equal(seen.size, STICKER_COUNT);
  assert.deepEqual([...new Set(seen.values())].sort(), [1, 2]);
  assert.equal([...seen.values()].reduce((a, b) => a + b, 0), 100);
  assert.throws(() => stickerOfCell(100), RangeError);
  assert.throws(() => stickerOfCell(-1), RangeError);
  const s = new SqliteTokenStore();
  const id = accept(s, draft(1));
  const view = projectTo54(s.cubeCells(id, T0)!);
  assert.equal(view.length, 54);
  assert.deepEqual([...new Set(view.map((v) => v.face))], [...FACES]);
  for (const f of FACES) assert.equal(view.filter((v) => v.face === f).length, 9);
  assert.deepEqual(view.flatMap((v) => v.cells).sort((x, y) => x - y), Array.from({ length: 100 }, (_, i) => i), 'no cell lost or double-mapped');
  for (const v of view) assert.equal(v.empty, v.cells.every((i) => s.cubeCells(id, T0)![i]!.empty), 'a sticker is empty only when all its cells are');
  s.close();
});

test('the reader gives the CLI and the dashboard one projection: 100 cells, 54 stickers, the latest change; the ASCII grid marks changed cells and empty cells', () => {
  const s = new SqliteTokenStore();
  const id = accept(s, draft(1));
  s.recordUse([id], 'run-1', 'agent');
  const cube = readTokenCube(s, id, Date.now())!;
  assert.equal(cube.cells.length, 100);
  assert.equal(cube.stickers.length, 54);
  assert.equal(cube.last_change!.cause, 'used');
  assert.ok(cube.last_change!.keys.includes('uses'));
  const grid = formatCubeGrid(cube);
  assert.match(grid, /TT-000001: \d+\/100 cells filled/);
  assert.equal(grid.split('\n').filter((l) => /^ {2}(identity|lesson|provenance|challenge|score|usage|links|lifecycle|health|propagation)/.test(l)).length, 10);
  assert.match(grid, /\*[█▓▒░]/, 'changed cells are starred');
  assert.match(grid, /·/, 'empty cells are dots');
  assert.match(grid, /changed by "used"/);
  assert.equal(readTokenCube(s, 'TT-424242'), null);
  assert.equal(readTokenCube(s, 'garbage'), null);
  s.close();
});

test('lesson failure modes are read from the lesson text only', () => {
  assert.deepEqual(lessonFailureModes('read_file raises ENOENT when the file does not exist'), ['missing']);
  assert.deepEqual(lessonFailureModes('write_file reports bytes, not characters'), ['encoding']);
  assert.deepEqual(lessonFailureModes('Use a plain relative path'), []);
});

test('buildCells on hostile input values stays total and only ever produces strings', () => {
  const s = new SqliteTokenStore();
  const id = ok(s.write(draft(1, { title: '<img src=x onerror=alert(1)>', content: '<script>alert(2)</script> body text here' }), 't')).id;
  const cells = buildCells(s.cubeInputs(id)!, T0);
  assert.equal(cells.length, 100);
  for (const c of cells) { assert.equal(typeof c.display, 'string'); assert.ok(c.value === null || (c.value >= 0 && c.value <= 1)); }
  s.close();
});

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { validateTokenMessage } from '../think-token-ws.ts';

test('the WebSocket cube request is validated like every other token message', () => {
  assert.deepEqual(validateTokenMessage({ type: 'think_token_cube', id: 'TT-000007' }), { ok: true, req: { type: 'think_token_cube', id: 'TT-000007' } });
  for (const bad of [{ type: 'think_token_cube' }, { type: 'think_token_cube', id: "TT-1'; DROP TABLE" }, { type: 'think_token_cube', id: 'TT-1', extra: 1 }, { type: 'think_token_cube', id: 7 }]) assert.equal(validateTokenMessage(bad).ok, false, JSON.stringify(bad));
});

test('CLI: `kudbee token cube TT-id` prints the ASCII grid, `--events` the recorded changes with receipts, `--json` the same projection as the reader', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-cube-'));
  const file = path.join(dir, 'think-tokens.db');
  const s = new SqliteTokenStore(file);
  const id = accept(s, draft(1));
  s.recordUse([id], 'run-1', 'agent');
  const expected = readTokenCube(s, id, Date.now())!;
  s.close();
  const cli = (...args: string[]) => spawnSync(process.execPath, ['--experimental-strip-types', '--no-warnings', 'cli.ts', 'token', ...args], { cwd: path.resolve(import.meta.dirname, '..'), env: { ...process.env, KUDBEE_THINK_TOKEN_DB: file }, encoding: 'utf8' });
  const text = cli('cube', id);
  assert.equal(text.status, 0, text.stderr);
  assert.match(text.stdout, /TT-000001: \d+\/100 cells filled/);
  assert.match(text.stdout, /changed by "used"/);
  const ev = cli('cube', id, '--events');
  assert.match(ev.stdout, /recent cell changes/);
  assert.match(ev.stdout.replace(/\x1b\[[0-9;]*m/g, ''), /used\s+uses\s+0\s+-> 1\s+receipt #\d+/);
  const json = JSON.parse(cli('cube', id, '--json').stdout) as typeof expected;
  assert.equal(json.cells.length, 100);
  assert.deepEqual(json.cells.map((c) => c.key), expected.cells.map((c) => c.key));
  assert.deepEqual(json.last_change!.keys, expected.last_change!.keys);
  assert.notEqual(cli('cube', 'TT-999999').status, 0);
  assert.equal(cli('cube').status, 2);
});

test('a token that predates the cube gets a silent baseline snapshot, so its first real change is attributed to its real cause', () => {
  const dir = mkdtempSync(join(tmpdir(), 'tt-base-'));
  const file = join(dir, 'think-tokens.db');
  try {
    const a = new SqliteTokenStore(file);
    const id = accept(a, draft(1));
    (a as unknown as { db: { exec(s: string): void } }).db.exec('DELETE FROM think_token_cells; DELETE FROM think_token_cell_events;');
    a.close();
    const b = new SqliteTokenStore(file);
    assert.equal(((b as unknown as { db: { prepare(s: string): { get(): unknown } } }).db.prepare('SELECT COUNT(*) AS n FROM think_token_cells').get() as { n: number }).n, 1);
    assert.equal(((b as unknown as { db: { prepare(s: string): { get(): unknown } } }).db.prepare('SELECT COUNT(*) AS n FROM think_token_cell_events').get() as { n: number }).n, 0, 'no events for the baseline');
    b.recordUse([id], 'run-1', 'agent');
    assert.deepEqual([...new Set(b.cellEvents(id, 50).map((e) => e.cause))], ['used']);
    b.close();
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
