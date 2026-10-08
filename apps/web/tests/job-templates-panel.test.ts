import assert from 'node:assert/strict';
import fs from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const mod = { exports: {} as { render(d: unknown, hasRepo: boolean, onUse: (t: unknown, v: string) => void, doc: unknown): unknown; useTemplate(t: unknown, v: string, doc: unknown, f: unknown): Promise<{ ok: boolean; error?: string }> } };
vm.runInNewContext(fs.readFileSync(new URL('../public/js/job-templates-panel.js', import.meta.url), 'utf8'), { module: mod });
type El = { tag: string; className: string; textContent: string; placeholder: string; value: string; children: El[]; listeners: Record<string, () => void>; appendChild(c: El): El; addEventListener(t: string, f: () => void): void };
const mk = (tag: string): El => ({ tag, className: '', textContent: '', placeholder: '', value: '', children: [], listeners: {}, appendChild(c) { this.children.push(c); return c; }, addEventListener(t, f) { this.listeners[t] = f; } });
const doc = { createElement: mk };
const flat = (e: El): El[] => [e, ...e.children.flatMap(flat)];
const data = { templates: [{ id: 'explain-codebase', name: 'Explain this codebase', description: 'desc one' }, { id: 'fix-bug', name: 'Fix a bug', description: 'desc two', param: { key: 'bug', label: 'What is wrong', placeholder: 'e.g. off by one', required: true } }] };

test('one card per template, an input only where a template asks for one, and a warning when no repository is chosen', () => {
  const withRepo = flat(mod.exports.render(data, true, () => {}, doc) as El);
  assert.equal(withRepo.filter((e) => e.className === 'jobs-card').length, 2);
  assert.equal(withRepo.filter((e) => e.tag === 'input').length, 1);
  assert.equal(withRepo.filter((e) => e.className === 'jobs-warning').length, 0);
  assert.equal(withRepo.filter((e) => e.tag === 'button').length, 2);
  assert.equal(flat(mod.exports.render(data, false, () => {}, doc) as El).filter((e) => e.className === 'jobs-warning').length, 1);
});

test('the button passes the template and the typed input to the handler; text is not HTML', () => {
  let got: [string, string] | null = null;
  const tree = flat(mod.exports.render({ templates: [{ ...data.templates[1], name: '<b>x</b>' }] }, true, (t, v) => { got = [(t as { id: string }).id, v]; }, doc) as El);
  tree.find((e) => e.tag === 'input')!.value = 'it breaks on page 2';
  tree.find((e) => e.tag === 'button')!.listeners.click();
  assert.deepEqual(got, ['fix-bug', 'it breaks on page 2']);
  assert.ok(tree.some((e) => e.textContent === '<b>x</b>'));
});

test('useTemplate puts the finished goal in the goal box and reports a refusal without touching it', async () => {
  const goalBox = { value: 'keep me', focus() {}, dispatchEvent() { return true; } };
  const d = { getElementById: (id: string) => (id === 'goal-input' ? goalBox : null) };
  const ok = await mod.exports.useTemplate({ id: 'a' }, '', d, async () => ({ json: async () => ({ ok: true, goal: 'the goal text' }) }));
  assert.equal(ok.ok, true); assert.equal(goalBox.value, 'the goal text');
  const bad = await mod.exports.useTemplate({ id: 'b' }, '', d, async () => ({ json: async () => ({ ok: false, error: 'What is wrong is required' }) }));
  assert.equal(bad.ok, false); assert.equal(bad.error, 'What is wrong is required'); assert.equal(goalBox.value, 'the goal text');
});
