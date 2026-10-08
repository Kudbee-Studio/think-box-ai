import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { initEnv } from '../init-env.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
const installer = path.resolve(here, '..', '..', '..', 'install.sh');

function root(example = 'INCEPTION_API_KEY=\nKUDBEE_DAILY_BUDGET_USD=\n'): string {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'init-'));
  fs.writeFileSync(path.join(d, '.env.example'), example);
  return d;
}

test('init creates a private .env from the example and says which line to fill in', () => {
  const d = root();
  const r = initEnv(d);
  assert.equal(r.created, true);
  assert.equal(fs.readFileSync(path.join(d, '.env'), 'utf8'), 'INCEPTION_API_KEY=\nKUDBEE_DAILY_BUDGET_USD=\n');
  assert.equal(fs.statSync(path.join(d, '.env')).mode & 0o777, 0o600);
  assert.match(r.message, /INCEPTION_API_KEY|DEEPSEEK_API_KEY|XAI_API_KEY|Ollama/);
});

test('init never overwrites an existing .env, and tightens its permissions', () => {
  const d = root();
  fs.writeFileSync(path.join(d, '.env'), 'MINE=1\n', { mode: 0o644 });
  const r = initEnv(d);
  assert.equal(r.created, false);
  assert.equal(fs.readFileSync(path.join(d, '.env'), 'utf8'), 'MINE=1\n');
  assert.equal(fs.statSync(path.join(d, '.env')).mode & 0o777, 0o600);
});

test('init without an example file fails clearly instead of writing an empty .env', () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'init-'));
  assert.throws(() => initEnv(d), /\.env\.example/);
  assert.equal(fs.existsSync(path.join(d, '.env')), false);
});

test('install.sh is valid bash and its --check mode reports node and git without installing anything', () => {
  execFileSync('bash', ['-n', installer]);
  const r = spawnSync('bash', [installer, '--check'], { encoding: 'utf8' });
  assert.match(r.stdout, /node/i); assert.match(r.stdout, /git/i);
  assert.equal(r.status, 0, r.stdout + r.stderr);
});

test('install.sh --check fails with a clear message when node is too old', () => {
  const fake = fs.mkdtempSync(path.join(os.tmpdir(), 'fakenode-'));
  fs.writeFileSync(path.join(fake, 'node'), '#!/bin/sh\necho v18.0.0\n', { mode: 0o755 });
  const r = spawnSync('bash', [installer, '--check'], { encoding: 'utf8', env: { ...process.env, PATH: `${fake}:/usr/bin:/bin` } });
  assert.notEqual(r.status, 0);
  assert.match(r.stdout + r.stderr, /22\.6/);
});
