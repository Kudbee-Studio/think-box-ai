// Profile import hardening: strict schema, bounded sizes, and writes that cannot leave the profile folder.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { IMPORT_LIMITS, parseProfileBundle, slugFor, writeProfileMemory, writeProfileRuns } from '../profile-import.ts';

const item = (over: Record<string, unknown> = {}) => ({ id: 'org/fact', title: 'A fact', tags: ['x'], source: 'human', created: '2026-01-01', updated: '2026-01-02', content: 'body', ...over });
const bundle = (over: Record<string, unknown> = {}) => ({ format: 'kudbee-profile', profile: { name: 'P' }, memory: { org: [item()] }, runs: [{ id: 'r1' }], ...over });
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'prof-import-'));

test('a well-formed bundle parses into fresh, bounded values', () => {
  const b = parseProfileBundle(bundle());
  assert.equal(b.memory.length, 1);
  assert.equal(b.memory[0].id, 'org/fact');
  assert.equal(b.runs.length, 1);
});

test('malformed bundles are refused', () => {
  for (const bad of [null, 'x', [], {}, { format: 'other' }, bundle({ memory: [] }), bundle({ memory: { nope: [] } }), bundle({ memory: { org: 'x' } }), bundle({ memory: { org: [5] } }), bundle({ memory: { org: [item({ id: 7 })] } }), bundle({ memory: { org: [item({ id: 'task/x' })] } }), bundle({ memory: { org: [item({ tags: 'a' })] } }), bundle({ runs: {} }), bundle({ runs: [1] })]) {
    assert.throws(() => parseProfileBundle(bad), /Import|kudbee profile/, JSON.stringify(bad)?.slice(0, 60));
  }
});

test('oversized bundles are refused', () => {
  assert.throws(() => parseProfileBundle(bundle({ memory: { org: [item({ content: 'x'.repeat(IMPORT_LIMITS.contentChars + 1) })] } })), /content is longer/);
  assert.throws(() => parseProfileBundle(bundle({ memory: { org: [item({ title: 'x'.repeat(IMPORT_LIMITS.titleChars + 1) })] } })), /title is longer/);
  assert.throws(() => parseProfileBundle(bundle({ memory: { org: Array.from({ length: IMPORT_LIMITS.itemsPerLayer + 1 }, (_, i) => item({ id: `org/a${i}` })) } })), /more than/);
  assert.throws(() => parseProfileBundle(bundle({ runs: Array.from({ length: IMPORT_LIMITS.runs + 1 }, () => ({})) })), /more than/);
  assert.throws(() => parseProfileBundle(bundle({ runs: [{ blob: 'x'.repeat(IMPORT_LIMITS.runBytes) }] })), /larger than/);
});

test('path-traversal ids are neutralised to a plain file name', () => {
  for (const id of ['org/../../etc/passwd', 'org/..', 'org/a/b/c', 'org/.hidden', 'org/%2e%2e%2fx', 'org/\u0000x']) {
    const slug = slugFor('org', id);
    assert.match(slug, /^[a-zA-Z0-9_-][a-zA-Z0-9._-]*$|^memory$/, id);
    assert.ok(!slug.includes('/') && !slug.startsWith('.'), id);
  }
});

test('writes stay inside the profile folder and never overwrite an existing memory', async () => {
  const root = tmp();
  const memoryRoot = path.join(root, 'memory');
  const parsed = parseProfileBundle(bundle({ memory: { org: [item({ id: 'org/../../escape' }), item({ id: 'org/fact' })] } }));
  await writeProfileMemory(memoryRoot, parsed.memory);
  assert.ok(fs.existsSync(path.join(memoryRoot, 'org', 'fact.md')));
  assert.deepEqual(fs.readdirSync(root), ['memory'], 'nothing written next to the profile');
  fs.writeFileSync(path.join(memoryRoot, 'org', 'fact.md'), 'EDITED');
  await writeProfileMemory(memoryRoot, parsed.memory);
  assert.equal(fs.readFileSync(path.join(memoryRoot, 'org', 'fact.md'), 'utf8'), 'EDITED');
});

test('a symlinked layer folder pointing outside is refused, nothing is written there', async () => {
  const root = tmp();
  const outside = tmp();
  const memoryRoot = path.join(root, 'memory');
  fs.mkdirSync(memoryRoot);
  fs.symlinkSync(outside, path.join(memoryRoot, 'org'));
  await assert.rejects(writeProfileMemory(memoryRoot, parseProfileBundle(bundle()).memory));
  assert.deepEqual(fs.readdirSync(outside), []);
});

test('runs are written as JSON inside the profile folder', async () => {
  const root = tmp();
  await writeProfileRuns(root, [{ id: 'r1' }]);
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(root, 'runs.json'), 'utf8')), [{ id: 'r1' }]);
});
