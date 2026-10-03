import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { MemoryStore } from '../memory.ts';

test('MemoryStore writes README.md once and never overwrites an edited one', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'mem-readme-'));
  try {
    new MemoryStore(root, {});
    const readme = path.join(root, 'README.md');
    assert.ok(fs.existsSync(readme), 'README.md is created on first start');
    fs.writeFileSync(readme, 'my own notes');
    new MemoryStore(root, {});
    assert.equal(fs.readFileSync(readme, 'utf8'), 'my own notes');
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
