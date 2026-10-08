import assert from 'node:assert/strict';
import fs from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const mod = { exports: {} as { summaryText(s: unknown): string; renderSteps(s: unknown, doc: unknown): unknown } };
vm.runInNewContext(fs.readFileSync(new URL('../public/js/setup-panel.js', import.meta.url), 'utf8'), { module: mod });
const p = mod.exports;
type El = { className: string; textContent: string; children: El[]; appendChild(c: El): El };
const doc = { createElement: (_t: string): El => ({ className: '', textContent: '', children: [], appendChild(c) { this.children.push(c); return c; } }) };
const flat = (e: El): string[] => [e.textContent, ...e.children.flatMap(flat)];

test('the run summary text has the headline, indented facts and arrowed next steps', () => {
  const t = p.summaryText({ headline: 'Done in 3.0s', lines: ['Changed 1 file: a.ts'], next: ['Review the changes'] });
  assert.equal(t, '— Done in 3.0s\n  Changed 1 file: a.ts\n  → Review the changes');
  assert.equal(p.summaryText(null), '');
});

test('the checklist says what is missing, and which steps are optional', () => {
  const tree = p.renderSteps({ ready: false, steps: [{ id: 'model', title: 'Connect a model', done: false, required: true, hint: 'Run kudbee init' }, { id: 'spend-limit', title: 'Set a daily spend limit', done: false, required: false, hint: 'Set it' }] }, doc) as El;
  const text = flat(tree).join('|');
  for (const part of ['connect a model', 'To do', 'Optional', 'Run kudbee init']) assert.ok(text.toLowerCase().includes(part.toLowerCase()), part);
  assert.ok(flat(p.renderSteps({ ready: true, steps: [] }, doc) as El).join('|').includes('ready to run goals'));
});

test('the page has the Get started button, panel and script; app.js shows the summary after a result', () => {
  const html = fs.readFileSync(new URL('../public/index.html', import.meta.url), 'utf8');
  for (const id of ['setup-button', 'setup-panel', 'close-setup', 'setup-container']) assert.ok(html.includes(`id="${id}"`), id);
  assert.ok(html.includes('/js/setup-panel.js'));
  const app = fs.readFileSync(new URL('../public/js/app.js', import.meta.url), 'utf8');
  assert.ok(app.includes('showRunSummary(r.run_id)') && app.includes('/summary'));
});
