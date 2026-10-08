import assert from 'node:assert/strict';
import fs from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const mod = { exports: {} as { renderSpend(s: unknown, doc: unknown): unknown; renderAudit(a: unknown, chain: unknown, doc: unknown): unknown; usedPercent(spent: number, limit: number): number } };
vm.runInNewContext(fs.readFileSync(new URL('../public/js/audit-panel.js', import.meta.url), 'utf8'), { module: mod });
const p = mod.exports;

type El = { className: string; textContent: string; style: Record<string, string>; children: El[]; appendChild(c: El): El };
const doc = { createElement: (_t: string): El => ({ className: '', textContent: '', style: {}, children: [], appendChild(c) { this.children.push(c); return c; } }) };
const flat = (e: El): string[] => [e.textContent, ...e.children.flatMap(flat)];

test('usedPercent: no limit means no bar, over the limit is capped at 100', () => {
  assert.equal(p.usedPercent(5, 0), 0);
  assert.equal(p.usedPercent(0.8, 1), 80);
  assert.equal(p.usedPercent(3, 1), 100);
});

test('spend shows today, 7 days, all time, the daily limit with a warning at 80%, and per-model cost', () => {
  const spend = { today_usd: 0.85, last_7d_usd: 2, all_time_usd: 9.5, budget: { daily: 1, run: 0.25 }, by_model: [{ model: 'mercury-2', runs: 5, cost_usd: 0.069 }] };
  const text = flat(p.renderSpend(spend, doc) as El).join('|');
  for (const part of ['$0.85', '$2.00', '$9.50', 'Daily limit $1.00', '85%', 'Near the daily limit', 'Per-run limit $0.25', 'mercury-2']) assert.ok(text.includes(part), part);
});

test('spend with no limits says so and shows no warning', () => {
  const text = flat(p.renderSpend({ today_usd: 0, last_7d_usd: 0, all_time_usd: 0, budget: { daily: 0, run: 0 }, by_model: [] }, doc) as El).join('|');
  assert.ok(text.includes('No spend limit set')); assert.ok(!text.includes('Near the daily limit'));
});

test('audit shows chain status and one row per event; an empty log says so; a broken chain is loud', () => {
  const ev = [{ ts: Date.UTC(2026, 9, 7, 12, 0, 0), kind: 'approval_resolved', actor: 'dashboard', run_id: 'abcdef123456', summary: 'approved' }];
  const ok = flat(p.renderAudit({ events: ev }, { ok: true, entries: 4 }, doc) as El).join('|');
  for (const part of ['Chain intact', '4 entries', 'approval resolved', 'dashboard', 'abcdef12', 'approved']) assert.ok(ok.includes(part), part);
  assert.ok(flat(p.renderAudit({ events: [] }, { ok: true, entries: 0 }, doc) as El).join('|').includes('Nothing recorded yet'));
  assert.ok(flat(p.renderAudit({ events: ev }, { ok: false, entries: 4, broken_at: 3, reason: 'row edited' }, doc) as El).join('|').includes('Chain BROKEN at entry 3'));
});

test('summaries are shown as text, never as HTML', () => {
  const ev = [{ ts: 0, kind: 'run_finished', actor: 'x', run_id: null, summary: '<img src=x onerror=alert(1)>' }];
  const tree = p.renderAudit({ events: ev }, { ok: true, entries: 1 }, doc) as El;
  assert.ok(flat(tree).includes('<img src=x onerror=alert(1)>'));
});

test('the page has the button, the panel and loads the script', () => {
  const html = fs.readFileSync(new URL('../public/index.html', import.meta.url), 'utf8');
  for (const id of ['audit-button', 'audit-panel', 'close-audit', 'audit-container']) assert.ok(html.includes(`id="${id}"`), id);
  assert.ok(html.includes('/js/audit-panel.js'));
});
