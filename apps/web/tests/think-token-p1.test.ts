// ADR 029 P1: permanent TT- ids, lifecycle, migration, real extractor + challenge, model fallback, call caps, key hygiene.
// Hermetic: model callers are fakes; no network. The live Mercury run is recorded in docs/evidence/adr-029-p1.md, not here.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import Database from 'better-sqlite3';
import { SqliteTokenStore, formatTokenId, normalizeTokenId, scoreBreakdown, computeScore, type TokenDraft } from '../think-token-store.ts';
import { buildRunView, challengeLesson, checkGrounding, checkSpecificity, processFinishedRun, type PipelineDeps } from '../think-token-pipeline.ts';
import { createMercuryCaller, createLocalCaller, sanitizeForModel, scrubSecrets, type ModelCaller, type ModelMessage, type TokenModels } from '../think-token-model.ts';
import { formatTokenDetail, formatTokenLine, readToken, readTokens, toApiToken } from '../think-token-reader.ts';
import { resolveLocalModel } from '../local-model.ts';
import type { FinishedRun } from '../think-token-extract.ts';
import type { AgentEvent } from '../agent.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
const tmpDb = () => path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-p1-')), 'think-tokens.db');
const draft = (n: number, over: Partial<TokenDraft> = {}): TokenDraft => ({
  source_run_id: 'run-1', kind: 'lesson', title: `Lesson number ${n}`, content: `A distinct reusable lesson body number ${n} about write_file.`, tags: ['x'], evidence_ref: 'run:run-1', ...over,
});
const okW = <T extends { ok: boolean }>(r: T): Extract<T, { ok: true }> => { assert.equal(r.ok, true, JSON.stringify(r)); return r as Extract<T, { ok: true }>; };

// ─── ids ────────────────────────────────────────────────────────

test('ids: TT-000001 format, strictly increasing, unique', () => {
  const store = new SqliteTokenStore();
  const ids = [1, 2, 3, 4, 5].map((n) => okW(store.write(draft(n), 't')).id);
  assert.deepEqual(ids, ['TT-000001', 'TT-000002', 'TT-000003', 'TT-000004', 'TT-000005']);
  assert.equal(new Set(ids).size, 5);
  assert.deepEqual(store.list().map((t) => t.seq), [5, 4, 3, 2, 1]);
  store.close();
});

test('ids: normalizeTokenId accepts TT-42, tt-000042, 42 and legacy ids; rejects garbage', () => {
  for (const ok of ['TT-42', 'tt-000042', '42', 'TT-000042', ' tt42 ']) assert.equal(normalizeTokenId(ok), 'TT-000042', ok);
  assert.equal(normalizeTokenId('tt_0123456789ABCDEF'), 'tt_0123456789abcdef');
  for (const bad of ['', 'TT-', 'TT-0', '0', 'TT-12x', "TT-1'; DROP", 'tt_xyz', null, 7, {}, ['TT-1']]) assert.equal(normalizeTokenId(bad as unknown), null, String(bad));
  assert.equal(formatTokenId(1_234_567), 'TT-1234567');
});

test('ids: never reused after the token is deleted, retired or rejected', () => {
  const store = new SqliteTokenStore();
  const a = okW(store.write(draft(1), 't')).id;
  const b = okW(store.write(draft(2), 't')).id;
  const c = okW(store.write(draft(3), 't')).id;
  store.setStatus(a, 'retired', 'founder');
  store.handle.prepare('DELETE FROM think_tokens WHERE id = ?').run(c); // even a hard delete cannot hand the number out again
  store.handle.prepare("UPDATE think_tokens SET status = 'rejected' WHERE id = ?").run(b);
  const next = okW(store.write(draft(4), 't')).id;
  assert.equal(next, 'TT-000004');
  assert.ok(![a, b, c].includes(next));
  store.close();
});

test('ids: a duplicate lesson returns the existing id and counts a sighting instead of minting a new one', () => {
  const store = new SqliteTokenStore();
  const first = okW(store.write(draft(1), 't'));
  const dup = okW(store.write(draft(1, { title: 'Different title', content: `  ${draft(1).content.toUpperCase()}  ` }), 't'));
  assert.equal(dup.duplicate, true);
  assert.equal(dup.id, first.id);
  assert.equal(store.get(first.id)!.seen_count, 2);
  assert.equal(store.list().length, 1);
  assert.equal(okW(store.write(draft(2), 't')).id, 'TT-000002', 'the duplicate did not consume a number');
  store.close();
});

test('ids: survive a restart and keep counting', () => {
  const file = tmpDb();
  const one = new SqliteTokenStore(file);
  assert.equal(okW(one.write(draft(1), 't')).id, 'TT-000001');
  assert.equal(okW(one.write(draft(2), 't')).id, 'TT-000002');
  one.close();
  const two = new SqliteTokenStore(file);
  assert.equal(two.get('TT-000002')!.title, 'Lesson number 2');
  assert.equal(okW(two.write(draft(3), 't')).id, 'TT-000003');
  assert.deepEqual(two.verifyLedger(), { ok: true, entries: 6 });
  two.close();
});

test('ids: four processes writing to one database at once get 100 distinct, gap-free numbers', async () => {
  const file = tmpDb();
  new SqliteTokenStore(file).close(); // create the schema once so the children only write
  const run = (tag: string) => new Promise<string[]>((resolve, reject) => {
    const child = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', path.join(here, 'helpers/write-tokens.ts'), file, '25', tag], { stdio: ['ignore', 'pipe', 'pipe'] });
    let out = '';
    let err = '';
    child.stdout.on('data', (d) => (out += d));
    child.stderr.on('data', (d) => (err += d));
    child.on('close', (code) => (code === 0 ? resolve(JSON.parse(out)) : reject(new Error(`child ${tag} failed: ${err.slice(0, 300)}`))));
  });
  const all = (await Promise.all(['a', 'b', 'c', 'd'].map(run))).flat();
  assert.equal(all.length, 100);
  assert.equal(new Set(all).size, 100, 'no id was handed out twice');
  assert.deepEqual([...all].sort(), Array.from({ length: 100 }, (_, i) => formatTokenId(i + 1)));
  const store = new SqliteTokenStore(file);
  assert.equal(store.list({ limit: 100 }).length, 100);
  assert.equal(store.verifyLedger().ok, true);
  store.close();
});

// ─── lifecycle ──────────────────────────────────────────────────

const pass = { verdict: 'pass' as const, reason: 'true, specific and supported', model: 'mercury-2' };
const model = (over: Partial<TokenDraft> = {}) => draft(1, { extractor: 'mercury', extract_model: 'mercury-2', ...over });

test('lifecycle: candidate -> extracted -> scored -> challenged -> accepted, every step a ledger entry', () => {
  const store = new SqliteTokenStore();
  const { id } = okW(store.write(model(), 'agent'));
  assert.equal(store.get(id)!.status, 'candidate');
  okW(store.advance(id, 'extracted', 'agent'));
  okW(store.advance(id, 'scored', 'agent'));
  okW(store.advance(id, 'challenged', 'agent', { challenge: pass }));
  okW(store.advance(id, 'accepted', 'agent'));
  const row = store.get(id)!;
  assert.equal(row.status, 'accepted');
  assert.deepEqual(row.challenge, { verdict: 'pass', reason: pass.reason, model: 'mercury-2', meta: {} });
  const steps = row.receipts!.map((r) => r.action);
  assert.deepEqual(steps, ['write', 'transition', 'transition', 'transition', 'transition']);
  assert.deepEqual(store.verifyLedger(), { ok: true, entries: 10 });
  store.close();
});

test('lifecycle: a failed challenge ends in rejected, and rejected tokens are never retrieved', () => {
  const store = new SqliteTokenStore();
  const { id } = okW(store.write(model(), 'agent'));
  for (const to of ['extracted', 'scored'] as const) okW(store.advance(id, to, 'agent'));
  okW(store.advance(id, 'challenged', 'agent', { challenge: { verdict: 'fail', reason: 'generic', model: 'mercury-2' } }));
  assert.equal(store.advance(id, 'accepted', 'agent').ok, false, 'a failed challenge cannot be accepted by the pipeline');
  okW(store.advance(id, 'rejected', 'agent'));
  assert.equal(store.get(id)!.status, 'rejected');
  assert.deepEqual(store.retrieve('write_file lesson reusable distinct', 3), []);
  store.close();
});

test('lifecycle: illegal transitions are refused and receipted as rejected', () => {
  const store = new SqliteTokenStore();
  const { id } = okW(store.write(model(), 'agent'));
  const before = store.verifyLedger().entries;
  const illegal: Array<() => ReturnType<typeof store.advance>> = [
    () => store.advance(id, 'scored', 'agent'), // skips extracted
    () => store.advance(id, 'accepted', 'agent'), // skips everything
    () => store.advance(id, 'challenged', 'agent', { challenge: pass }), // skips two steps
    () => store.advance(id, 'candidate', 'agent'),
    () => store.advance(id, 'retired', 'agent'), // the pipeline never retires
    () => store.advance(id, 'nonsense' as 'scored', 'agent'),
  ];
  for (const attempt of illegal) {
    const r = attempt();
    assert.equal(r.ok, false);
    if (!r.ok) assert.equal(r.receipt.decision, 'rejected');
  }
  assert.equal(store.get(id)!.status, 'candidate');
  assert.equal(store.verifyLedger().entries, before + illegal.length);
  okW(store.advance(id, 'extracted', 'agent'));
  assert.equal(store.advance(id, 'extracted', 'agent').ok, false, 'no repeating a step');
  assert.equal(store.advance(id, 'challenged', 'agent').ok, false, 'a challenge needs a verdict');
  assert.equal(store.advance('TT-999999', 'extracted', 'agent').ok, false);
  store.close();
});

test('lifecycle: operators can only accept or retire, retired is final, and template tokens never advance on their own', () => {
  const store = new SqliteTokenStore();
  const template = okW(store.write(draft(1), 'agent')).id;
  assert.equal(store.get(template)!.extractor, 'template');
  const r = store.advance(template, 'extracted', 'agent');
  assert.equal(r.ok, false);
  if (!r.ok) assert.match(r.reason, /template/);
  assert.equal(store.setStatus(template, 'scored', 'founder').ok, false);
  assert.equal(store.setStatus(template, 'rejected', 'founder').ok, false);
  okW(store.setStatus(template, 'accepted', 'founder'));
  assert.equal(store.setStatus(template, 'accepted', 'founder').ok, false, 'already accepted');
  okW(store.setStatus(template, 'retired', 'founder'));
  assert.equal(store.setStatus(template, 'accepted', 'founder').ok, false, 'retired is final');
  assert.equal(store.setStatus(template, 'retired', 'founder').ok, false);
  store.close();
});

// ─── score breakdown ────────────────────────────────────────────

test('score: the breakdown is stored next to the score and reproduces 0.525 for a fresh token', () => {
  const store = new SqliteTokenStore();
  const { id } = okW(store.write(draft(1), 't'));
  const row = store.get(id)!;
  assert.equal(row.score, 0.525);
  assert.equal(row.score_breakdown.score, 0.525);
  assert.deepEqual(row.score_breakdown.components, { usefulness: 0.5, recency: 1, reuse: 0, feedback: 0.5 });
  assert.deepEqual(row.score_breakdown.weighted, { usefulness: 0.225, recency: 0.2, reuse: 0, feedback: 0.1 });
  assert.equal(row.score_breakdown.weights.usefulness + row.score_breakdown.weights.recency + row.score_breakdown.weights.reuse + row.score_breakdown.weights.feedback, 1);
  const stored = JSON.parse((store.handle.prepare('SELECT score_breakdown FROM think_tokens WHERE id = ?').get(id) as { score_breakdown: string }).score_breakdown);
  assert.equal(stored.score, 0.525, 'persisted in the database, not only computed on read');
  store.recordUse([id], 'run-9', 'agent');
  const used = store.get(id)!;
  assert.equal(used.score_breakdown.inputs.uses, 1);
  assert.ok(used.score_breakdown.components.reuse > 0);
  assert.equal(used.score_breakdown.score, computeScore(used));
  assert.equal(scoreBreakdown(used).score, used.score);
  store.close();
});

// ─── migration ──────────────────────────────────────────────────

const sha = (t: string) => createHash('sha256').update(t).digest('hex');

test('migration: v1 database (hash ids) -> TT ids; legacy ids kept; old ledger untouched and still verifies', () => {
  const file = tmpDb();
  const db = new Database(file);
  db.exec(`
    CREATE TABLE think_tokens (id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL DEFAULT 'local', created_at INTEGER NOT NULL, source_run_id TEXT NOT NULL,
      kind TEXT NOT NULL CHECK (kind IN ('lesson','fix','tool_pattern')), title TEXT NOT NULL, content TEXT NOT NULL, tags TEXT NOT NULL DEFAULT '[]',
      score REAL NOT NULL DEFAULT 0.5, uses INTEGER NOT NULL DEFAULT 0, last_used_at INTEGER,
      status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate','accepted','retired')), evidence_ref TEXT NOT NULL, content_hash TEXT NOT NULL,
      success_runs INTEGER NOT NULL DEFAULT 0, failed_runs INTEGER NOT NULL DEFAULT 0, thumbs_up INTEGER NOT NULL DEFAULT 0, thumbs_down INTEGER NOT NULL DEFAULT 0,
      UNIQUE (tenant_id, content_hash));
    CREATE TABLE think_token_uses (token_id TEXT NOT NULL, run_id TEXT NOT NULL, used_at INTEGER NOT NULL, success INTEGER, PRIMARY KEY (token_id, run_id));
    CREATE TABLE think_token_ledger (seq INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, decision TEXT NOT NULL,
      token_id TEXT, run_id TEXT, detail TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
  `);
  db.pragma('user_version = 1');
  const ins = db.prepare("INSERT INTO think_tokens (id, created_at, source_run_id, kind, title, content, tags, score, status, evidence_ref, content_hash, uses) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)");
  ins.run('tt_aaaaaaaaaaaaaaaa', 2000, 'run-new', 'lesson', 'Newer', 'newer lesson body text here', '["a"]', 0.525, 'candidate', 'run:run-new', 'h-new', 0);
  ins.run('tt_bbbbbbbbbbbbbbbb', 1000, 'run-old', 'tool_pattern', 'Older', 'older lesson body text here', '["b"]', 0.6, 'accepted', 'run:run-old', 'h-old', 1);
  db.prepare("INSERT INTO think_token_uses (token_id, run_id, used_at, success) VALUES ('tt_bbbbbbbbbbbbbbbb', 'run-use', 3000, 1)").run();
  let prev = '0'.repeat(64);
  for (const [i, tokenId] of ['tt_bbbbbbbbbbbbbbbb', 'tt_aaaaaaaaaaaaaaaa'].entries()) {
    const body = JSON.stringify({ ts: 100 + i, actor: 'agent', action: 'write', decision: 'admitted', tokenId, runId: 'r', detail: { n: i } });
    const hash = sha(prev + body);
    db.prepare('INSERT INTO think_token_ledger (ts, actor, action, decision, token_id, run_id, detail, prev_hash, hash) VALUES (?,?,?,?,?,?,?,?,?)').run(100 + i, 'agent', 'write', 'admitted', tokenId, 'r', JSON.stringify({ n: i }), prev, hash);
    prev = hash;
  }
  db.close();

  const store = new SqliteTokenStore(file); // opening runs migrateUp
  const rows = store.list({ limit: 10 });
  assert.deepEqual(rows.map((r) => [r.id, r.legacy_id]).sort(), [['TT-000001', 'tt_bbbbbbbbbbbbbbbb'], ['TT-000002', 'tt_aaaaaaaaaaaaaaaa']]);
  assert.equal(store.get('TT-000001')!.title, 'Older', 'numbered in created_at order');
  assert.equal(store.get('tt_aaaaaaaaaaaaaaaa')!.id, 'TT-000002', 'a legacy id still resolves');
  assert.equal(store.get('TT-000001')!.status, 'accepted');
  assert.equal(store.get('TT-000001')!.extractor, 'template');
  assert.deepEqual(store.get('TT-000001')!.used_by!.map((u) => u.run_id), ['run-use'], 'uses were re-pointed');
  const ledger = store.handle.prepare('SELECT action, token_id FROM think_token_ledger ORDER BY seq').all() as Array<{ action: string; token_id: string | null }>;
  assert.deepEqual(ledger.slice(0, 2).map((l) => l.token_id), ['tt_bbbbbbbbbbbbbbbb', 'tt_aaaaaaaaaaaaaaaa'], 'old entries are never rewritten');
  assert.equal(ledger[2].action, 'migrate_ids');
  assert.equal(store.verifyLedger().ok, true);
  assert.equal(store.get('TT-000001')!.receipts!.length, 1, 'the old ledger entry is found through the legacy id');
  assert.equal(store.get('TT-000001')!.receipts![0].action, 'write');
  assert.equal(okW(store.write(draft(9), 't')).id, 'TT-000003', 'numbering continues after the migration');
  store.close();
  const again = new SqliteTokenStore(file);
  assert.equal(again.list().length, 3, 'migrating twice changes nothing');
  assert.equal((again.handle.prepare("SELECT COUNT(*) n FROM think_token_ledger WHERE action = 'migrate_ids'").get() as { n: number }).n, 1);
  again.close();
});

// ─── extractor accuracy and challenge ───────────────────────────

const tool = (name: string, ok: boolean, args: Record<string, unknown> = {}, extra: Partial<Extract<AgentEvent, { kind: 'tool' }>> = {}): AgentEvent =>
  ({ kind: 'tool', step: 1, name, args, ok, latency_ms: 3, output: '', ...extra });

// Mirrors run ab5e5299: list_files, recall, fetch_url x2, write_file.
const RUN: FinishedRun = {
  id: 'run-ab5e5299', goal: 'train a think token', success: true, files: ['think-token-notes.md'], result: 'Wrote the notes.',
  steps: [tool('list_files', true), tool('recall', true, { query: 'think token' }, { output: '2 memories' }), tool('fetch_url', true, { url: 'https://example.test/docs' }, { output: 'Think tokens are reusable learning units' }),
    tool('fetch_url', true, { url: 'https://example.test/more' }), tool('write_file', true, { path: 'think-token-notes.md', content: '# notes' }, { output: 'ok' })],
};
const GOOD = {
  kind: 'lesson', title: 'Recall, fetch twice, then write notes',
  lesson: 'For a research-and-notes goal, call recall first, then fetch_url on two distinct pages and write_file a notes file; the second fetch_url added the detail the first lacked. Skip the second fetch_url when recall already returns relevant notes.',
  tools_cited: ['recall', 'fetch_url', 'write_file'], files_cited: ['think-token-notes.md'], tags: ['research', 'notes'],
};
// The checkers read `content`; the model reply uses `lesson`.
const GOOD_C = { ...GOOD, content: GOOD.lesson };
const PASS = JSON.stringify({ true: true, specific: true, supported: true, reason: 'Matches the run tool sequence and output.' });
const lessons = (...l: object[]) => JSON.stringify({ lessons: l });

function fake(provider: 'mercury' | 'local', name: string, replies: Array<string | Error>): ModelCaller & { calls: ModelMessage[][] } {
  const calls: ModelMessage[][] = [];
  const caller = (async (messages: ModelMessage[]) => {
    calls.push(messages);
    const next = replies.shift();
    if (next === undefined) throw new Error(`${provider} fake exhausted`);
    if (next instanceof Error) throw next;
    return { text: next, provider, model: name, latency_ms: 7, tokens_in: 120, tokens_out: 60 };
  }) as ModelCaller & { calls: ModelMessage[][] };
  caller.calls = calls;
  return caller;
}
const deps = (models: Partial<TokenModels>, store = new SqliteTokenStore(), env: Record<string, string | undefined> = {}): PipelineDeps => ({ store, models: { mercury: null, local: null, ...models }, env });

test('extractor: a lesson that cites a tool the run never called fails (cited and mentioned)', () => {
  const view = buildRunView(RUN);
  assert.deepEqual(view.tool_names, ['list_files', 'recall', 'fetch_url', 'write_file']);
  assert.equal(checkGrounding(GOOD_C, view).ok, true);
  assert.ok(GOOD_C.content.includes('fetch_url'), 'the lesson text under test is real');
  const cited = checkGrounding({ ...GOOD_C, tools_cited: ['recall', 'shell_exec'] }, view);
  assert.equal(cited.ok, false);
  assert.match(cited.reasons.join(), /shell_exec/);
  const mentioned = checkGrounding({ title: 't', content: 'Use read_file to confirm the notes before write_file.', tools_cited: [], files_cited: [] }, view);
  assert.equal(mentioned.ok, false);
  assert.match(mentioned.reasons.join(), /read_file/);
  const file = checkGrounding({ ...GOOD_C, files_cited: ['secrets.env'] }, view);
  assert.equal(file.ok, false);
  const text = checkGrounding({ title: 't', content: 'Then edit summary.json by hand with write_file.', tools_cited: [], files_cited: [] }, view);
  assert.equal(text.ok, false, 'a file named only in the prose must also be in the run');
});

test('challenge: generic and template lessons are rejected deterministically, before any model is asked', async () => {
  const view = buildRunView(RUN);
  const store = new SqliteTokenStore();
  const d = deps({ mercury: fake('mercury', 'mercury-2', [PASS]) }, store);
  const generic = [
    'Goals like "train a think token" were answered successfully using observed evidence from fetch_url.', // the real stored template lesson
    'Ground "train a think token" in evidence',
    'Always verify your work and cite sources carefully before reporting results to the user.', // no tool, file or argument from the run
    'train a think token think token train',
    'It worked.',
  ];
  for (const content of generic) {
    const verdict = await challengeLesson(d, view, { title: 'x', content, tags: [] }, 'agent');
    assert.equal(verdict?.verdict, 'fail', content);
    assert.equal(verdict?.model, 'deterministic-check');
  }
  assert.equal((d.models.mercury as ReturnType<typeof fake>).calls.length, 0, 'the model was never called for a lesson that fails the cheap checks');
  assert.equal(checkSpecificity({ title: 't', content: GOOD.lesson }, view).ok, true);
  store.close();
});

test('pipeline: Mercury extracts a specific lesson, it is scored, challenged by a second call and accepted; models are recorded', async () => {
  const store = new SqliteTokenStore();
  const mercury = fake('mercury', 'mercury-2', [lessons(GOOD), PASS]);
  const result = await processFinishedRun(deps({ mercury }, store), RUN, 'agent:ab5e5299');
  assert.equal(result.tokens.length, 1);
  const t = result.tokens[0];
  assert.equal(t.id, 'TT-000001');
  assert.equal(t.status, 'accepted');
  assert.equal(t.extractor, 'mercury');
  assert.equal(t.model, 'mercury-2');
  const row = store.get(t.id)!;
  assert.equal(row.source_run_id, 'run-ab5e5299');
  assert.equal(row.evidence_ref, 'run:run-ab5e5299');
  assert.equal(row.content, GOOD.lesson);
  assert.deepEqual(row.challenge, { verdict: 'pass', reason: 'Matches the run tool sequence and output.', model: 'mercury-2', meta: { latency_ms: 7, tokens_in: 120, tokens_out: 60 } });
  assert.deepEqual(row.extract_meta, { latency_ms: 7, tokens_in: 120, tokens_out: 60 });
  assert.deepEqual(row.receipts!.map((r) => r.action), ['write', 'transition', 'transition', 'transition', 'transition']);
  assert.deepEqual(store.modelUsage('run-ab5e5299').map((u) => [u.step, u.provider, u.model, u.ok]), [['extract', 'mercury', 'mercury-2', true], ['challenge', 'mercury', 'mercury-2', true]]);
  assert.equal(store.retrieve('research notes goal fetch_url', 3).length, 1, 'an accepted token is retrievable for planner context');
  assert.equal(mercury.calls.length, 2);
  store.close();
});

test('pipeline: the extractor prompt carries the real run (tools, args, files) and not the paths or secrets in it', async () => {
  const store = new SqliteTokenStore();
  const run: FinishedRun = { ...RUN, goal: 'summarise /home/domin/secret-project/plan.md with key sk-abcdefghijklmnop1234', steps: [...RUN.steps, tool('read_file', true, { path: '/home/domin/projects/x/notes.md' })] };
  const mercury = fake('mercury', 'mercury-2', [lessons(GOOD), PASS]);
  await processFinishedRun(deps({ mercury }, store), run, 'agent');
  const sent = JSON.stringify(mercury.calls[0]);
  assert.match(sent, /write_file/);
  assert.match(sent, /think-token-notes\.md/);
  assert.doesNotMatch(sent, /\/home\/domin/);
  assert.doesNotMatch(sent, /sk-abcdefghijklmnop1234/);
  assert.match(sent, /<path>/);
  assert.ok(sanitizeForModel('x'.repeat(50_000)).length <= 8000, 'inputs are size-capped');
  store.close();
});

test('pipeline: lessons citing a missing tool, or phrased as the old template, are dropped before they become tokens (and receipted)', async () => {
  const store = new SqliteTokenStore();
  const bad = { ...GOOD, title: 'Use a shell', lesson: 'Run shell_exec to list the notes folder, then write_file the notes to disk and keep going.', tools_cited: ['shell_exec', 'write_file'] };
  const template = { ...GOOD, title: 'Ground "train a think token" in evidence', lesson: 'Goals like "train a think token" were answered successfully using observed evidence from fetch_url.', tools_cited: ['fetch_url'] };
  const result = await processFinishedRun(deps({ mercury: fake('mercury', 'mercury-2', [lessons(bad, template, GOOD), PASS]) }, store), RUN, 'agent');
  assert.equal(result.tokens.length, 1);
  assert.equal(result.tokens[0].content, GOOD.lesson);
  assert.equal(result.dropped.length, 2);
  assert.match(result.dropped[0].reasons.join(), /shell_exec/);
  assert.match(result.dropped[1].reasons.join(), /template phrasing/);
  const rejections = store.handle.prepare("SELECT action, decision FROM think_token_ledger WHERE action = 'extract_rejected'").all() as Array<{ decision: string }>;
  assert.equal(rejections.length, 2);
  assert.ok(rejections.every((r) => r.decision === 'rejected'));
  store.close();
});

test('pipeline: a failed model challenge rejects the token; an unreachable challenge model leaves it scored, never accepted', async () => {
  const failing = new SqliteTokenStore();
  const rejected = await processFinishedRun(deps({ mercury: fake('mercury', 'mercury-2', [lessons(GOOD), JSON.stringify({ true: true, specific: false, supported: true, reason: 'could apply to any goal' })]) }, failing), RUN, 'agent');
  assert.equal(rejected.tokens[0].status, 'rejected');
  assert.match(failing.get('TT-000001')!.challenge.reason!, /not specific/);
  assert.deepEqual(failing.retrieve('research notes fetch_url', 3), []);
  failing.close();

  const unreachable = new SqliteTokenStore();
  const scored = await processFinishedRun(deps({ mercury: fake('mercury', 'mercury-2', [lessons(GOOD), new Error('mercury HTTP 503')]) }, unreachable), RUN, 'agent');
  assert.equal(scored.tokens[0].status, 'scored');
  assert.equal(unreachable.get('TT-000001')!.challenge.verdict, null);
  assert.deepEqual(unreachable.retrieve('research notes fetch_url', 3), []);
  assert.deepEqual(unreachable.modelUsage('run-ab5e5299').map((u) => u.ok), [true, false, false], 'the challenge was retried once, then gave up');
  unreachable.close();
});

test('retry: one transient Mercury failure (an empty reply, seen in a live run) is retried and the token is still challenged and accepted', async () => {
  const store = new SqliteTokenStore();
  const mercury = fake('mercury', 'mercury-2', [lessons(GOOD), new Error('mercury returned no text'), PASS]);
  const r = await processFinishedRun(deps({ mercury }, store), RUN, 'agent');
  assert.equal(r.tokens[0].status, 'accepted');
  assert.deepEqual(store.modelUsage('run-ab5e5299').map((u) => [u.step, u.ok]), [['extract', true], ['challenge', false], ['challenge', true]]);
  assert.ok(store.handle.prepare("SELECT 1 FROM think_token_ledger WHERE action = 'model_call' AND decision = 'rejected' AND detail LIKE '%no text%'").get(), 'the failed attempt is receipted');
  store.close();
});

test('fallback: Mercury missing or erroring uses the local model; both missing keeps the labeled template as a candidate', async () => {
  const noKey = new SqliteTokenStore();
  const local = fake('local', 'llama3:8b', [lessons(GOOD), PASS]);
  const a = await processFinishedRun(deps({ mercury: null, local }, noKey), RUN, 'agent');
  assert.equal(a.tokens[0].extractor, 'local');
  assert.equal(a.tokens[0].model, 'llama3:8b');
  assert.equal(a.tokens[0].status, 'accepted');
  noKey.close();

  const erroring = new SqliteTokenStore();
  const mercury = fake('mercury', 'mercury-2', [new Error('mercury HTTP 500'), new Error('mercury HTTP 500')]);
  const local2 = fake('local', 'llama3:8b', [lessons(GOOD), PASS]);
  const b = await processFinishedRun(deps({ mercury, local: local2 }, erroring), RUN, 'agent');
  assert.equal(b.tokens[0].extractor, 'local');
  assert.deepEqual(erroring.modelUsage('run-ab5e5299').map((u) => [u.provider, u.ok]), [['mercury', false], ['mercury', false], ['local', true], ['mercury', false], ['mercury', false], ['local', true]]);
  erroring.close();

  const none = new SqliteTokenStore();
  const c = await processFinishedRun(deps({}, none), RUN, 'agent');
  assert.ok(c.tokens.length > 0);
  assert.ok(c.tokens.every((t) => t.extractor === 'template' && t.status === 'candidate' && t.model === null));
  assert.equal(none.advance(c.tokens[0].id, 'extracted', 'agent').ok, false);
  assert.equal(none.modelCallCount({}), 0);
  none.close();
});

const GOOD2 = {
  kind: 'lesson', title: 'Recall first, one fetch is enough',
  lesson: 'Run recall before any fetch_url call and write_file the notes afterwards; one fetch_url is enough when recall already returned matching notes, so skip the second page.',
  tools_cited: ['recall', 'fetch_url', 'write_file'], files_cited: [] as string[], tags: ['research'],
};
const RUN2: FinishedRun = { ...RUN, id: 'run-second' };

test('novelty: accepted lessons reach both the extraction and the challenge prompts so repeats can be skipped', async () => {
  const store = new SqliteTokenStore();
  await processFinishedRun(deps({ mercury: fake('mercury', 'mercury-2', [lessons(GOOD), PASS]) }, store), RUN, 'agent');
  const mercury = fake('mercury', 'mercury-2', [lessons({ ...GOOD2 }), JSON.stringify({ true: true, specific: true, supported: true, novel: true, reason: 'adds the one-fetch rule' })]);
  const r = await processFinishedRun(deps({ mercury }, store), RUN2, 'agent');
  const extraction = mercury.calls[0];
  assert.match(extraction[0].content, /do NOT repeat or paraphrase/);
  const payload = JSON.parse(extraction[1].content);
  assert.deepEqual(payload.known_lessons.map((k: { id: string }) => k.id), ['TT-000001']);
  assert.match(payload.known_lessons[0].lesson, /write_file/);
  assert.match(mercury.calls[1][0].content, /"novel"/);
  assert.equal(JSON.parse(mercury.calls[1][1].content).known_lessons[0].id, 'TT-000001');
  assert.equal(r.tokens[0].status, 'accepted');
  store.close();
});

test('novelty: a lesson the reviewer calls a repeat is rejected, and a missing answer leaves it unchallenged', async () => {
  const repeat = new SqliteTokenStore();
  await processFinishedRun(deps({ mercury: fake('mercury', 'mercury-2', [lessons(GOOD), PASS]) }, repeat), RUN, 'agent');
  const dup = await processFinishedRun(deps({ mercury: fake('mercury', 'mercury-2', [lessons({ ...GOOD2 }), JSON.stringify({ true: true, specific: true, supported: true, novel: false, reason: 'same as TT-000001' })]) }, repeat), RUN2, 'agent');
  assert.equal(dup.tokens[0].status, 'rejected');
  assert.match(repeat.get(dup.tokens[0].id)!.challenge.reason!, /repeats a known lesson/);
  assert.equal(repeat.get(dup.tokens[0].id)!.challenge.verdict, 'fail');
  repeat.close();

  const silent = new SqliteTokenStore();
  await processFinishedRun(deps({ mercury: fake('mercury', 'mercury-2', [lessons(GOOD), PASS]) }, silent), RUN, 'agent');
  const unanswered = await processFinishedRun(deps({ mercury: fake('mercury', 'mercury-2', [lessons({ ...GOOD2 }), PASS, PASS]) }, silent), RUN2, 'agent');
  assert.equal(unanswered.tokens[0].status, 'scored', 'no novel verdict -> not verified -> never accepted');
  assert.ok(silent.handle.prepare("SELECT 1 FROM think_token_ledger WHERE action = 'challenge_rejected' AND detail LIKE '%whether the lesson is new%'").get());
  silent.close();

  const first = new SqliteTokenStore();
  const noKnown = await processFinishedRun(deps({ mercury: fake('mercury', 'mercury-2', [lessons(GOOD), PASS]) }, first), RUN, 'agent');
  assert.equal(noKnown.tokens[0].status, 'accepted', 'with nothing known yet, no novel field is needed');
  first.close();
});

test('no-new-lessons: an empty answer, or a model that answered with something unusable, saves nothing and never falls back to the template', async () => {
  for (const reply of [lessons(), '[]', '```json\n{"lessons": []}\n```']) {
    const store = new SqliteTokenStore();
    const r = await processFinishedRun(deps({ mercury: fake('mercury', 'mercury-2', [reply]) }, store), RUN, 'agent');
    assert.deepEqual(r.tokens, [], reply);
    assert.equal(store.list().length, 0, 'no token, and no template fallback, because a model answered');
    store.close();
  }
  const store = new SqliteTokenStore();
  const secret = 'sk-abcdefghijklmnop1234';
  const r = await processFinishedRun(deps({ mercury: fake('mercury', 'mercury-2', [`I found nothing new to add (key ${secret}). Sorry!`]) }, store), RUN, 'agent');
  assert.deepEqual(r.tokens, [], 'an unusable reply saves nothing');
  assert.equal(store.list().length, 0, 'and does not fall back to a template lesson the model declined to write');
  const row = store.handle.prepare("SELECT decision, detail FROM think_token_ledger WHERE action = 'extract_rejected'").get() as { decision: string; detail: string };
  assert.equal(row.decision, 'rejected');
  assert.match(row.detail, /not the expected JSON/);
  assert.match(row.detail, /nothing new to add/, 'a short excerpt of what the model said is kept for debugging');
  assert.ok(!row.detail.includes(secret), 'and it is sanitized');
  assert.equal(store.modelUsage('run-ab5e5299').length, 1, 'no further model calls were spent');
  store.close();
});

test('caps: the per-run and per-day model call caps stop further calls and are receipted', async () => {
  const perRun = new SqliteTokenStore();
  const mercury = fake('mercury', 'mercury-2', [lessons(GOOD), PASS]);
  const r = await processFinishedRun(deps({ mercury }, perRun, { THINKBOX_TOKEN_MODEL_CALLS_PER_RUN: '1' }), RUN, 'agent');
  assert.equal(mercury.calls.length, 1, 'only the extraction call was made');
  assert.equal(r.tokens[0].status, 'scored');
  assert.ok(perRun.handle.prepare("SELECT 1 FROM think_token_ledger WHERE action = 'model_call' AND decision = 'rejected' AND detail LIKE '%per-run%'").get());
  perRun.close();

  const perDay = new SqliteTokenStore();
  const m2 = fake('mercury', 'mercury-2', [lessons(GOOD), PASS]);
  const d = await processFinishedRun(deps({ mercury: m2 }, perDay, { THINKBOX_TOKEN_MODEL_CALLS_PER_DAY: '0' }), RUN, 'agent');
  assert.equal(m2.calls.length, 0);
  assert.ok(d.tokens.every((t) => t.extractor === 'template'), 'with no model allowed the template fallback is used');
  perDay.close();
});

// ─── key hygiene ────────────────────────────────────────────────

const KEY = 'ZZSENTINEL-key2-0123456789abcdef';

test('key: never appears in logs, database rows, events, formatted output or errors', async () => {
  const logged: string[] = [];
  const spies = (['log', 'error', 'warn', 'info', 'debug'] as const).map((m) => {
    const original = console[m];
    console[m] = (...args: unknown[]) => { logged.push(args.map(String).join(' ')); };
    return () => { console[m] = original; };
  });
  const requests: Array<{ url: string; auth: string | undefined; body: string }> = [];
  let call = 0;
  const fetchFake = (async (url: string, init: any) => {
    requests.push({ url, auth: init.headers.Authorization, body: String(init.body) });
    call += 1;
    // the first call fails with an error text that echoes the request (a hostile or sloppy upstream)
    if (call === 1) throw Object.assign(new Error(`connect failed to ${url} with Authorization: Bearer ${KEY}`), { name: `Error:${KEY}` });
    const content = call === 2 ? lessons(GOOD) : PASS;
    return new Response(JSON.stringify({ choices: [{ message: { content } }], usage: { prompt_tokens: 10, completion_tokens: 5 } }), { status: 200 });
  }) as unknown as typeof fetch;
  const env = { INCEPTION_API_KEY_2: KEY, INCEPTION_BASE_URL: 'http://mock.invalid/v1' };
  const store = new SqliteTokenStore();
  let result;
  try {
    // an extraction that fails once (leaking the key into the error) then succeeds
    result = await processFinishedRun({ store, models: { mercury: createMercuryCaller(env, fetchFake), local: null }, env }, RUN, 'agent');
    const direct = await createMercuryCaller(env, (async () => { throw new Error(`boom ${KEY}`); }) as unknown as typeof fetch)!([{ role: 'user', content: 'hi' }]).catch((e: Error) => e.message);
    logged.push(String(direct));
  } finally {
    for (const restore of spies) restore();
  }
  assert.equal(result!.tokens[0]?.extractor, 'mercury', 'the first extraction call failed (echoing the key); the retry succeeded');
  assert.ok(store.handle.prepare("SELECT 1 FROM think_token_ledger WHERE action = 'model_call' AND decision = 'rejected'").get(), 'the leaking failure was receipted (scrubbed)');
  // every table, as the database stores it
  const dump = (['think_tokens', 'think_token_ledger', 'think_token_uses', 'think_token_model_calls', 'think_token_seq'] as const)
    .map((t) => JSON.stringify(store.handle.prepare(`SELECT * FROM ${t}`).all())).join('\n');
  assert.ok(!dump.includes(KEY), 'database rows');
  assert.ok(!dump.includes('ZZSENTINEL'), 'database rows (partial)');
  assert.ok(!logged.join('\n').includes(KEY), 'console output');
  assert.ok(!JSON.stringify(result).includes(KEY), 'pipeline result');
  const api = readTokens(store, {});
  assert.ok(!JSON.stringify(api).includes(KEY) && !api.map(formatTokenDetail).join().includes(KEY) && !api.map(formatTokenLine).join().includes(KEY), 'reader output');
  assert.ok(requests.every((r) => r.auth === `Bearer ${KEY}`), 'the key is only ever sent as the bearer header');
  assert.ok(requests.every((r) => !r.body.includes(KEY) && !r.url.includes(KEY)), 'never in the url or body');
  assert.equal(scrubSecrets(`oops ${KEY} oops`, [KEY]).includes(KEY), false);
  store.close();
});

test('key: missing means no Mercury caller (the local model is used); the local caller never pulls a model', async () => {
  assert.equal(createMercuryCaller({}), null);
  assert.equal(createMercuryCaller({ INCEPTION_API_KEY_2: '   ' }), null);
  assert.equal(createMercuryCaller({ INCEPTION_API_KEY: 'only-the-worker-key' }), null, 'the worker key is not the extraction key');
  const calls: string[] = [];
  const fetchFake = (async (url: string) => { calls.push(String(url)); return new Response(JSON.stringify({ models: [{ name: 'llama3:8b' }] }), { status: 200 }); }) as unknown as typeof fetch;
  const caller = createLocalCaller({ THINKBOX_LOCAL_MODEL: 'qwen2.5:1.5b' }, fetchFake);
  await assert.rejects(() => caller([{ role: 'user', content: 'x' }]), /THINKBOX_LOCAL_MODEL/);
  assert.ok(calls.every((u) => u.endsWith('/api/tags')), 'only listed installed models; never called /api/pull');
  assert.equal(resolveLocalModel({ THINKBOX_LOCAL_MODEL: 'llama3:8b', KUDBEE_LOCAL_MODEL: 'other' }), 'llama3:8b');
  assert.equal(resolveLocalModel({ KUDBEE_LOCAL_MODEL: 'other' }), 'other');
  assert.equal(resolveLocalModel({}), 'qwen2.5:1.5b');
  assert.equal(resolveLocalModel({ THINKBOX_LOCAL_MODEL: 'smollm2' }), 'qwen2.5:1.5b');
});

// ─── reader (the one shared formatter) ──────────────────────────

test('reader: one projection shows id, title, lesson, status, score breakdown, run id and receipt', async () => {
  const store = new SqliteTokenStore();
  await processFinishedRun(deps({ mercury: fake('mercury', 'mercury-2', [lessons(GOOD), PASS]) }, store), RUN, 'agent');
  const api = readToken(store, 'tt-1')!;
  assert.equal(api.id, 'TT-000001');
  assert.deepEqual(api, toApiToken(store.get('TT-000001')!));
  assert.equal(api.receipt!.action, 'transition');
  const text = formatTokenDetail(api);
  for (const needle of ['TT-000001', 'accepted', GOOD.title, GOOD.lesson, 'run-ab5e5299', 'mercury-2', '0.45*usefulness', api.receipt!.receipt_id, 'challenge:  pass']) assert.ok(text.includes(needle), needle);
  assert.match(formatTokenLine(api), /^TT-000001 +accepted +0\.\d{3} +lesson +Recall, fetch twice/);
  assert.equal(readTokens(store, { run_id: 'run-ab5e5299' }).length, 1);
  assert.equal(readTokens(store, { run_id: 'run-other' }).length, 0);
  assert.equal(readTokens(store, { query: 'TT-1' }).length, 1, 'search by id');
  assert.equal(readTokens(store, { query: '000001' }).length, 1);
  store.close();
  assert.throws(() => SqliteTokenStore.openReadOnly(path.join(os.tmpdir(), 'does-not-exist-kudbee.db')));
});
