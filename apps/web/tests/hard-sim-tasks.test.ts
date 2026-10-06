// The frozen P3.50 task set is only usable if every task fails as written and passes with its reference fix (the experiment's V0, checked here with no model and no network).
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { TASKS as HARD } from './helpers/hard-sim-tasks.ts';
import { PACKAGE_JSON, TASKS as EASY } from './helpers/local-sim-tasks.ts';

const run = (dir: string): number => spawnSync('sh', ['-c', 'node --test tests/*.test.js'], { cwd: path.join(dir, 'apps/web'), encoding: 'utf8', env: { PATH: process.env.PATH ?? '', HOME: dir } }).status ?? 1;

function materialize(files: Record<string, string>): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-task-'));
  fs.mkdirSync(path.join(dir, 'apps/web'), { recursive: true }); fs.writeFileSync(path.join(dir, 'apps/web/package.json'), PACKAGE_JSON);
  for (const [f, c] of Object.entries(files)) { fs.mkdirSync(path.dirname(path.join(dir, f)), { recursive: true }); fs.writeFileSync(path.join(dir, f), c); }
  return dir;
}

test('the hard task set has unique ids, none shared with the easy set', () => {
  const ids = HARD.map((t) => t.id);
  assert.equal(new Set(ids).size, ids.length);
  assert.equal(HARD.length, 12);
  for (const id of ids) assert.ok(!EASY.some((t) => t.id === id));
});

for (const task of HARD) {
  test(`${task.id} (${task.kind}) fails as written and passes with its reference fix`, () => {
    const before = materialize(task.files); const after = materialize(task.files);
    try {
      assert.notEqual(run(before), 0, 'must fail as written');
      for (const e of task.ref) {
        const p = path.join(after, e.path); const s = fs.readFileSync(p, 'utf8');
        assert.equal(s.split(e.find!).length, 2, 'reference find text must be unique');
        fs.writeFileSync(p, s.replace(e.find!, () => e.replace!));
      }
      assert.equal(run(after), 0, 'must pass with the reference fix');
    } finally { fs.rmSync(before, { recursive: true, force: true }); fs.rmSync(after, { recursive: true, force: true }); }
  });
}
