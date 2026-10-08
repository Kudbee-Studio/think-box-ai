import assert from 'node:assert/strict';
import { test } from 'node:test';
import { TOOLS } from '../agent.ts';
import { JOB_TEMPLATES, fillGoal } from '../job-templates.ts';

const toolNames = new Set(TOOLS.map((t) => t.function.name));
const GENERAL = new Set(['list_files', 'read_file', 'write_file', 'fetch_url']);

test('every template has a unique id, a name, a description and a goal that fits one prompt', () => {
  assert.ok(JOB_TEMPLATES.length >= 6);
  assert.equal(new Set(JOB_TEMPLATES.map((t) => t.id)).size, JOB_TEMPLATES.length);
  for (const t of JOB_TEMPLATES) {
    assert.ok(t.name && t.description, t.id);
    const r = fillGoal(t.id, t.param ? 'src/app.ts' : undefined);
    assert.ok(r.ok, t.id); if (r.ok) assert.ok(r.goal.length > 80 && r.goal.length < 1200, `${t.id}: ${r.goal.length}`);
  }
});

test('a template only names tools a normal run really has (no invented tools, no tools that need a special profile)', () => {
  for (const t of JOB_TEMPLATES) {
    const r = fillGoal(t.id, t.param ? 'x' : undefined); assert.ok(r.ok);
    const named = (r.ok ? r.goal : '').match(/\b[a-z]+(?:_[a-z]+)+\b/g) ?? [];
    for (const n of named) { assert.ok(toolNames.has(n), `${t.id} names "${n}", which is not a tool`); assert.ok(GENERAL.has(n), `${t.id} names "${n}", which a normal run is not offered`); }
  }
});

test('every goal tells the agent it cannot run code and must say what it could not verify', () => {
  for (const t of JOB_TEMPLATES) { const r = fillGoal(t.id, t.param ? 'x' : undefined); assert.ok(r.ok && /cannot run/i.test(r.goal) && /could not verify|not verified/i.test(r.goal), t.id); }
});

test('a template with a required input refuses to fill without it, and the input is cleaned and capped', () => {
  const needs = JOB_TEMPLATES.find((t) => t.param?.required)!;
  assert.deepEqual(fillGoal(needs.id, ''), { ok: false, error: `${needs.param!.label} is required` });
  assert.deepEqual(fillGoal(needs.id, undefined), { ok: false, error: `${needs.param!.label} is required` });
  const r = fillGoal(needs.id, `a\u0000b\nc ${'z'.repeat(2000)}`);
  assert.ok(r.ok); if (r.ok) { assert.ok(!r.goal.includes('\u0000')); assert.ok(r.goal.length < 1200); assert.ok(!/a\nb/.test(r.goal)); }
});

test('an unknown template id is refused', () => assert.deepEqual(fillGoal('nope'), { ok: false, error: 'Unknown template' }));

test('an optional input may be left out', () => {
  const opt = JOB_TEMPLATES.find((t) => t.param && !t.param.required);
  if (opt) assert.ok(fillGoal(opt.id, '').ok);
});
