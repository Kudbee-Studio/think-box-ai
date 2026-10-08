import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { test } from 'node:test';

const mod = { exports: {} as { render(r: unknown, doc: unknown): unknown } };
vm.runInNewContext(fs.readFileSync(new URL('../public/js/doctor-panel.js', import.meta.url), 'utf8'), { module: mod });
const panel = mod.exports;

type El = { tag: string; className: string; textContent: string; children: El[]; appendChild(c: El): El };
const doc = { createElement: (tag: string): El => ({ tag, className: '', textContent: '', children: [], appendChild(c) { this.children.push(c); return c; } }) };
const flat = (e: El): string[] => [e.textContent, ...e.children.flatMap(flat)];

test('the panel shows one row per check with its status word and detail, and a summary', () => {
  const el = panel.render({ ok: false, checks: [{ id: 'data-permissions', status: 'fail', detail: '3 entries are loose' }, { id: 'bind-address', status: 'ok', detail: 'local only' }] }, doc) as unknown as El;
  const text = flat(el).join('|');
  for (const part of ['Fix', 'data permissions', '3 entries are loose', 'OK', 'bind address', 'Failures found']) assert.ok(text.includes(part), part);
  assert.equal(el.children[0].className, 'doctor-row doctor-fail');
});

test('the page has the button, the panel and loads the script', () => {
  const html = fs.readFileSync(new URL('../public/index.html', import.meta.url), 'utf8');
  for (const id of ['doctor-button', 'doctor-panel', 'close-doctor', 'doctor-container']) assert.ok(html.includes(`id="${id}"`), id);
  assert.ok(html.includes('/js/doctor-panel.js'));
});
