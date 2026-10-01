// CI must not be able to hang for hours. A single hung update_config test once stalled `npm test`
// indefinitely because the runner had no per-test timeout.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const pkg = JSON.parse(fs.readFileSync(path.resolve(here, '..', 'package.json'), 'utf8')) as { scripts: Record<string, string> };

test('npm test runs every test file with a per-test timeout (1-120 s)', () => {
  const match = pkg.scripts.test.match(/--test-timeout=(\d+)/);
  assert.ok(match, 'npm test needs --test-timeout so one hung test fails instead of stalling the whole run');
  const ms = Number(match[1]);
  assert.ok(ms >= 1000 && ms <= 120000, `--test-timeout=${ms} should be between 1000 and 120000`);
  assert.match(pkg.scripts.test, /tests\/\*\.test\.ts/, 'the glob must still cover every test file');
});
