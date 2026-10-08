// The audit log: what is recorded, that secrets and file contents are not, that an edited, removed or reordered row is detected, and that the chain survives a restart.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test } from 'node:test';
import Database from 'better-sqlite3';
import { AuditLog, summarizeArgs } from '../audit-log.ts';

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-audit-'));
after(() => fs.rmSync(tmp, { recursive: true, force: true }));
let n = 0; const file = (): string => path.join(tmp, `a${n++}.db`);
const tamper = (f: string, sql: string): void => { const db = new Database(f); db.exec(sql); db.close(); };

test('records events in order with a chain, lists newest first, filters by kind and run', () => {
  const log = new AuditLog(); log.record('approval_requested', 'agent', 'write_file: save the report', { tool: 'write_file' }, 'run-1', 1000);
  log.record('approval_resolved', 'dashboard', 'approved', { approved: true }, 'run-1', 2000); log.record('run_finished', 'system', 'completed: x', { cost_usd: 0.01 }, 'run-2', 3000);
  const all = log.list(); assert.deepEqual(all.map((e) => e.kind), ['run_finished', 'approval_resolved', 'approval_requested']);
  assert.equal(all[2]!.prev_hash, '0'.repeat(64)); assert.equal(all[1]!.prev_hash, all[2]!.hash);
  assert.deepEqual(log.list({ kind: 'approval_resolved' }).map((e) => e.actor), ['dashboard']);
  assert.deepEqual(log.list({ run_id: 'run-1' }).length, 2); assert.equal(log.list({ since: 2500 }).length, 1); assert.equal(log.list({ limit: 1 }).length, 1);
  const v = log.verify(); assert.deepEqual([v.ok, v.entries, v.head], [true, 3, all[0]!.hash]); log.close();
});

test('secrets in the summary, the detail and the actor are redacted before they are stored', () => {
  const log = new AuditLog(); const key = 'sk-abcdefghijklmnopqrstuvwxyz0123456789';
  const e = log.record('approval_requested', `agent ${key}`, `send ${key} to the server`, { header: `Bearer ${key}`, note: 'password=hunter2hunter2' })!;
  const stored = JSON.stringify(log.list()); assert.ok(!stored.includes(key)); assert.ok(!stored.includes('hunter2'));
  assert.match(e.summary, /REDACTED/); log.close();
});

test('tool arguments are summarised: names, sizes and a short start, never whole file contents', () => {
  const big = 'x'.repeat(5000);
  const s = summarizeArgs({ path: 'report.md', content: big, items: [1, 2, 3], nested: { a: 1 }, flag: true, key: 'sk-abcdefghijklmnopqrstuvwxyz0123456789' });
  assert.equal(s.path, 'report.md'); assert.match(String(s.content), /\(5000 chars\)$/); assert.ok(String(s.content).length < 120);
  assert.equal(s.items, '[3 items]'); assert.equal(s.nested, '{…}'); assert.equal(s.flag, true); assert.match(String(s.key), /REDACTED/);
  assert.deepEqual(summarizeArgs(null), {}); assert.deepEqual(summarizeArgs('text'), {});
});

test('an edited row is detected, with the row it happened at', () => {
  const f = file(); const log = new AuditLog(f); for (let i = 0; i < 4; i++) log.record('run_finished', 'system', `run ${i}`, { cost_usd: 0.01 }, `r${i}`); log.close();
  tamper(f, "UPDATE audit_events SET summary = 'completed: nothing happened' WHERE seq = 3");
  const v = new AuditLog(f).verify(); assert.equal(v.ok, false); assert.equal(v.broken_at, 3); assert.match(v.reason ?? '', /changed after it was written/);
});

test('a removed row, an inserted row and a reordered pair are detected', () => {
  const mk = (): string => { const f = file(); const log = new AuditLog(f); for (let i = 0; i < 4; i++) log.record('run_finished', 'system', `run ${i}`); log.close(); return f; };
  const removed = mk(); tamper(removed, 'DELETE FROM audit_events WHERE seq = 2'); const r = new AuditLog(removed).verify(); assert.equal(r.ok, false); assert.equal(r.broken_at, 3); assert.match(r.reason ?? '', /removed, inserted or reordered/);
  const reordered = mk(); tamper(reordered, 'UPDATE audit_events SET seq = 99 WHERE seq = 2; UPDATE audit_events SET seq = 2 WHERE seq = 3; UPDATE audit_events SET seq = 3 WHERE seq = 99'); assert.equal(new AuditLog(reordered).verify().ok, false);
  const last = mk(); tamper(last, 'DELETE FROM audit_events WHERE seq = 4'); const cut = new AuditLog(last).verify(); assert.deepEqual([cut.ok, cut.entries], [true, 3]); // the tail can be cut off undetected: the chain proves order and edits, not completeness
});

test('the chain continues across a restart', () => {
  const f = file(); const a = new AuditLog(f); a.record('run_finished', 'system', 'one'); a.close();
  const b = new AuditLog(f); b.record('run_finished', 'system', 'two'); const v = b.verify(); assert.deepEqual([v.ok, v.entries], [true, 2]); b.close();
});

test('a failing write is reported once and never throws into the caller', () => {
  const log = new AuditLog(); log.close(); const real = console.error; const seen: string[] = []; console.error = (m: string) => { seen.push(String(m)); };
  try { assert.equal(log.record('run_finished', 'system', 'after close'), null); } finally { console.error = real; }
  assert.match(seen[0] ?? '', /audit log write failed/);
});
