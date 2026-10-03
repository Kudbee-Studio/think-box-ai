// CodeQL js/tainted-format-string + js/log-injection: a repository path or error text must be an argument, not part of the format string.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const src = fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), '../git-repo-manager.ts'), 'utf8');

test('git-repo-manager never interpolates a value into the format string of console.warn/error/log', () => {
  const bad = src.split('\n').filter((l) => /console\.(warn|error|log)\(`[^`]*\$\{/.test(l));
  assert.deepEqual(bad, []);
});
