// The A/B goal set is frozen: 30 goals, unique ids, none of the earlier eval wordings, and the engine-checked ones are answerable in the fixture.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EVAL_TASKS } from '../local-eval.ts';
import fs from 'node:fs';
import path from 'node:path';
import { AB_GOALS, HELD2_GOALS, HELD2_MODULES, HELD3_GOALS, HELD3_MODULES, HELD_GOALS, HELD_MODULES, TRAIN_GOALS, goalsHash, held2GoalsHash, held3GoalsHash, heldGoalsHash, startAbWorld, startHeld2World, startHeld3World, startHeldWorld, startTrainWorld, trainGoalsHash } from './helpers/ab-fixture.ts';
import { runAbsenceCheck } from '../absence.ts';

test('30 frozen goals, 15 lookup + 15 repo, unique, none reused from the earlier eval', () => {
  assert.equal(AB_GOALS.length, 30);
  assert.equal(AB_GOALS.filter((g) => g.class === 'lookup').length, 15);
  assert.equal(new Set(AB_GOALS.map((g) => g.id)).size, 30);
  const old = new Set(EVAL_TASKS.map((t) => t.goal.toLowerCase()));
  assert.deepEqual(AB_GOALS.filter((g) => old.has(g.goal.toLowerCase())), []);
  assert.match(goalsHash(), /^[0-9a-f]{64}$/);
});
test('in the fixture each untested function really has no test and each tested one does (engine check agrees)', async () => {
  const world = await startAbWorld();
  try {
    const f = (file: string, fn: string, line: number) => ({ found: true, file: `src/${file}.ts`, line, quote: `export function ${fn}(x: number): number {`, claim: `\`${fn}\` has no tests` });
    assert.equal((await runAbsenceCheck(f('billing', 'refundCard', 5), world.root)).contradicted.length, 0);
    assert.ok((await runAbsenceCheck(f('billing', 'chargeCard', 2), world.root)).contradicted.length >= 1);
  } finally { await world.close(); }
});

test('the P3.25 training world shares no goal wording and no identifier with the held-out world', async () => {
  assert.equal(TRAIN_GOALS.length, 20);
  assert.match(trainGoalsHash(), /^[0-9a-f]{64}$/);
  const held = new Set(AB_GOALS.map((g) => g.goal.toLowerCase()));
  assert.deepEqual(TRAIN_GOALS.filter((g) => held.has(g.goal.toLowerCase())), []);
  const heldWorld = await startAbWorld(); const trainWorld = await startTrainWorld();
  try {
    const { default: fs } = await import('node:fs');
    const names = (root: string) => new Set(fs.readdirSync(`${root}/src`).flatMap((f) => [...fs.readFileSync(`${root}/src/${f}`, 'utf8').matchAll(/export (?:function|const) (\w+)/g)].map((m) => m[1]!)));
    const a = names(heldWorld.root); const b = names(trainWorld.root);
    const base = new Set(['alpha', 'orphan', 'BETA_LIMIT']); // the eval world's own files, present in both but used by neither goal set
    assert.deepEqual([...b].filter((n) => a.has(n) && !base.has(n)), []);
  } finally { await heldWorld.close(); await trainWorld.close(); }
});

test('P3.33 held-out world: 20 goals, both phrasings, no name shared with the A/B or training worlds, and the engine agrees on every module', async () => {
  assert.equal(HELD_GOALS.length, 20);
  assert.equal(new Set(HELD_GOALS.map((g) => g.id)).size, 20);
  assert.equal(HELD_GOALS.filter((g) => g.goal.startsWith('Find an exported function')).length, 10);
  assert.equal(HELD_GOALS.filter((g) => g.goal.startsWith('Which exported function')).length, 10);
  assert.match(heldGoalsHash(), /^[0-9a-f]{64}$/);
  const others = new Set<string>();
  const ab = await startAbWorld(); const tr = await startTrainWorld(); const held = await startHeldWorld();
  try {
    for (const w of [ab, tr]) for (const f of fs.readdirSync(path.join(w.root, 'src'))) { others.add(f); for (const id of fs.readFileSync(path.join(w.root, 'src', f), 'utf8').match(/[A-Za-z_]{4,}/g) ?? []) others.add(id); }
    for (const m of HELD_MODULES) {
      assert.ok(!others.has(`${m.file}.ts`), m.file);
      assert.ok(!others.has(m.tested) && !others.has(m.untested), `${m.tested}/${m.untested}`);
      const line = (fn: string): number => fs.readFileSync(path.join(held.root, 'src', `${m.file}.ts`), 'utf8').split('\n').findIndex((l) => l.includes(`function ${fn}(`)) + 1;
      const f = (fn: string) => ({ found: true, file: `src/${m.file}.ts`, line: line(fn), quote: `export function ${fn}(x: number): number {`, claim: `\`${fn}\` has no tests` });
      assert.equal((await runAbsenceCheck(f(m.untested), held.root)).contradicted.length, 0, `${m.untested} is untested`);
      assert.ok((await runAbsenceCheck(f(m.tested), held.root)).contradicted.length >= 1, `${m.tested} is tested`);
    }
    const g = HELD_GOALS[0]!; const m = HELD_MODULES[0]!;
    assert.equal(g.check({ finding: { found: true, file: `src/${m.file}.ts`, quote: `export function ${m.untested}(x: number): number {` } } as any).ok, true);
    assert.equal(g.check({ finding: { found: true, file: `src/${m.file}.ts`, quote: `export function ${m.tested}(x: number): number {` } } as any).ok, false);
    assert.equal(g.check({ finding: { found: false, reason: 'x' } } as any).ok, false);
    assert.equal(g.check({ finding: { found: true, file: 'src/other.ts', quote: m.untested } } as any).ok, false);
  } finally { await ab.close(); await tr.close(); await held.close(); }
});

test('P3.34 held-out world: 30 goals, both phrasings, every name new (also versus the P3.33 world), and the engine agrees on every module', async () => {
  assert.equal(HELD2_GOALS.length, 30);
  assert.equal(new Set(HELD2_GOALS.map((g) => g.id)).size, 30);
  assert.equal(HELD2_GOALS.filter((g) => g.goal.startsWith('Find an exported function')).length, 15);
  assert.match(held2GoalsHash(), /^[0-9a-f]{64}$/);
  assert.notEqual(held2GoalsHash(), heldGoalsHash());
  const seen = new Set<string>();
  const worlds = [await startAbWorld(), await startTrainWorld(), await startHeldWorld()];
  const held2 = await startHeld2World();
  try {
    for (const w of worlds) for (const f of fs.readdirSync(path.join(w.root, 'src'))) { seen.add(f); for (const id of fs.readFileSync(path.join(w.root, 'src', f), 'utf8').match(/[A-Za-z_]{4,}/g) ?? []) seen.add(id); }
    for (const m of HELD2_MODULES) {
      assert.ok(!seen.has(`${m.file}.ts`), m.file);
      assert.ok(!seen.has(m.tested) && !seen.has(m.untested), `${m.tested}/${m.untested}`);
      const line = (fn: string): number => fs.readFileSync(path.join(held2.root, 'src', `${m.file}.ts`), 'utf8').split('\n').findIndex((l) => l.includes(`function ${fn}(`)) + 1;
      const f = (fn: string) => ({ found: true, file: `src/${m.file}.ts`, line: line(fn), quote: `export function ${fn}(x: number): number {`, claim: `\`${fn}\` has no tests` });
      assert.equal((await runAbsenceCheck(f(m.untested), held2.root)).contradicted.length, 0, `${m.untested} is untested`);
      assert.ok((await runAbsenceCheck(f(m.tested), held2.root)).contradicted.length >= 1, `${m.tested} is tested`);
    }
    const g = HELD2_GOALS[0]!; const m = HELD2_MODULES[0]!;
    assert.equal(g.check({ finding: { found: true, file: `src/${m.file}.ts`, quote: `export function ${m.untested}(x: number): number {` } } as any).ok, true);
    assert.equal(g.check({ finding: { found: true, file: `src/${m.file}.ts`, quote: `export function ${m.tested}(x: number): number {` } } as any).ok, false);
    assert.equal(g.check({ finding: { found: false, reason: 'x' } } as any).ok, false);
  } finally { for (const w of worlds) await w.close(); await held2.close(); }
});

test('P3.35 confirmation world: 60 goals, both phrasings, every name new versus all four earlier worlds, no name the repo tools hide, and the engine agrees on every module', async () => {
  assert.equal(HELD3_GOALS.length, 60);
  assert.equal(new Set(HELD3_GOALS.map((g) => g.id)).size, 60);
  assert.equal(new Set(HELD3_MODULES.flatMap((m) => [m.tested, m.untested])).size, 120, 'every function name is distinct');
  assert.equal(HELD3_GOALS.filter((g) => g.goal.startsWith('Find an exported function')).length, 30);
  assert.ok(new Set([held3GoalsHash(), held2GoalsHash(), heldGoalsHash(), goalsHash(), trainGoalsHash()]).size === 5);
  const seen = new Set<string>();
  const worlds = [await startAbWorld(), await startTrainWorld(), await startHeldWorld(), await startHeld2World()];
  const held3 = await startHeld3World();
  try {
    for (const w of worlds) for (const f of fs.readdirSync(path.join(w.root, 'src'))) { seen.add(f); for (const id of fs.readFileSync(path.join(w.root, 'src', f), 'utf8').match(/[A-Za-z_]{4,}/g) ?? []) seen.add(id); }
    for (const m of HELD3_MODULES) {
      assert.ok(!seen.has(`${m.file}.ts`), m.file);
      assert.ok(!seen.has(m.tested) && !seen.has(m.untested), `${m.tested}/${m.untested}`);
      assert.doesNotMatch(`${m.file} ${m.tested} ${m.untested}`, /secret|credential|token|password/i, 'the repo tools hide files with such names');
      const line = (fn: string): number => fs.readFileSync(path.join(held3.root, 'src', `${m.file}.ts`), 'utf8').split('\n').findIndex((l) => l.includes(`function ${fn}(`)) + 1;
      const f = (fn: string) => ({ found: true, file: `src/${m.file}.ts`, line: line(fn), quote: `export function ${fn}(x: number): number {`, claim: `\`${fn}\` has no tests` });
      assert.equal((await runAbsenceCheck(f(m.untested), held3.root)).contradicted.length, 0, `${m.untested} is untested`);
      assert.ok((await runAbsenceCheck(f(m.tested), held3.root)).contradicted.length >= 1, `${m.tested} is tested`);
    }
    const g = HELD3_GOALS[0]!; const m = HELD3_MODULES[0]!;
    assert.equal(g.check({ finding: { found: true, file: `src/${m.file}.ts`, quote: `export function ${m.untested}(x: number): number {` } } as any).ok, true);
    assert.equal(g.check({ finding: { found: true, file: `src/${m.file}.ts`, quote: `export function ${m.tested}(x: number): number {` } } as any).ok, false);
  } finally { for (const w of worlds) await w.close(); await held3.close(); }
});

