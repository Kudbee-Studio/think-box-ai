import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { renderDoctor, runDoctor } from '../doctor.ts';

const fakeKey = ['sk', 'live', 'abcdefghij1234567890wxyz'].join('-');

function setup(): { repo: string; data: string } {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'doc-'));
  const git = (...a: string[]) => execFileSync('git', a, { cwd: repo, stdio: 'pipe' });
  git('init', '-q'); git('config', 'user.email', 't@t'); git('config', 'user.name', 't');
  fs.writeFileSync(path.join(repo, 'a.ts'), 'export const n = 1;\n');
  git('add', '-A'); git('commit', '-qm', 'one');
  const data = path.join(repo, 'data');
  fs.mkdirSync(data, { mode: 0o755 });
  fs.chmodSync(data, 0o755);
  return { repo, data };
}
const byId = (r: Awaited<ReturnType<typeof runDoctor>>, id: string) => r.checks.find((c) => c.id === id);

test('a clean setup passes every offline check', async () => {
  const { repo, data } = setup();
  fs.chmodSync(data, 0o700);
  const r = await runDoctor({ repoRoot: repo, dataDir: data, env: {}, online: false });
  assert.equal(byId(r, 'data-permissions')?.status, 'ok');
  assert.equal(byId(r, 'tracked-secrets')?.status, 'ok');
  assert.equal(byId(r, 'history-secrets')?.status, 'ok');
  assert.equal(byId(r, 'bind-address')?.status, 'ok');
  assert.equal(r.ok, true);
});

test('it flags a loose data folder, a secret in a tracked file, a secret in history, a public bind, and a world-readable .env', async () => {
  const { repo, data } = setup();
  fs.writeFileSync(path.join(repo, 'a.ts'), `export const k = "${fakeKey}";\n`);
  execFileSync('git', ['commit', '-qam', 'leak'], { cwd: repo });
  fs.writeFileSync(path.join(repo, '.env'), 'X=1\n', { mode: 0o644 });
  const r = await runDoctor({ repoRoot: repo, dataDir: data, env: { LISTEN_ADDR: '0.0.0.0' }, online: false });
  for (const id of ['data-permissions', 'tracked-secrets', 'history-secrets', 'bind-address', 'env-file']) assert.notEqual(byId(r, id)?.status, 'ok', id);
  assert.equal(r.ok, false);
  const text = renderDoctor(r);
  assert.ok(!text.includes('abcdefghij1234567890wxyz'), 'the report never prints the secret');
  assert.match(text, /tracked-secrets/);
});

test('offline mode says the network checks were not run, it does not pretend they passed', async () => {
  const { repo, data } = setup();
  const r = await runDoctor({ repoRoot: repo, dataDir: data, env: {}, online: false });
  assert.equal(byId(r, 'dependency-audit')?.status, 'skipped');
  assert.equal(byId(r, 'outdated-packages')?.status, 'skipped');
});
