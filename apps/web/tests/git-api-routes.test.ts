// Unit tests for git-api-routes.ts: the /api/git router mounts, validates input, confines file access and serves a registered repo.
// Uses the real Express Router and no network (a pre-created local directory stands in for a cloned repository).
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import express from 'express';
import { createGitRouter } from '../git-api-routes.ts';

let server: http.Server;
let base: string;
let baseDir: string;

before(async () => {
  baseDir = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-gitapi-'));
  const app = express();
  app.use(express.json());
  app.use('/api/git', createGitRouter(baseDir));
  await new Promise<void>((r) => { server = app.listen(0, '127.0.0.1', () => r()); });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}/api/git`;
});
after(() => new Promise<void>((r) => { server.close(() => { fs.rmSync(baseDir, { recursive: true, force: true }); r(); }); }));

const j = async (r: Response) => ({ status: r.status, body: await r.json() as Record<string, unknown> });
const get = async (p: string) => j(await fetch(base + p));
const post = async (p: string, body: unknown) => j(await fetch(base + p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }));

test('clone validates the url and rejects a non-github url', async () => {
  assert.equal((await post('/clone', {})).status, 400);
  const bad = await post('/clone', { url: 'https://evil.example/x' });
  assert.equal(bad.status, 400);
  assert.match(String(bad.body.error), /github/i);
});

test('a pre-existing local directory registers a repository through the clone route, then tree/status/file/save/delete work', async () => {
  const repoDir = path.join(baseDir, 'repo');
  fs.mkdirSync(repoDir, { recursive: true });
  fs.mkdirSync(path.join(repoDir, 'src'));
  fs.writeFileSync(path.join(repoDir, 'src', 'a.ts'), 'export const x = 1;');
  fs.writeFileSync(path.join(repoDir, 'LICENCE'), 'text without an extension');

  const cloned = await post('/clone', { url: 'https://github.com/owner/repo' });
  assert.equal(cloned.status, 200);
  assert.equal(cloned.body.name, 'repo');

  const repos = await get('/repos');
  assert.equal(repos.status, 200);
  assert.equal((repos.body as unknown as unknown[]).length, 1);

  const tree = await get('/tree?repo=repo');
  assert.equal(tree.status, 200);
  assert.equal((tree.body as { name: string }).name, 'repo');

  const status = await get('/status?repo=repo');
  assert.equal(status.status, 200);

  const file = await get('/file?path=repo/src/a.ts');
  assert.equal(file.status, 200);
  assert.equal(file.body.language, 'typescript');
  assert.match(String(file.body.content), /export const x/);

  const unknownExt = await get('/file?path=repo/LICENCE');
  assert.equal(unknownExt.body.language, 'plaintext');

  const saved = await post('/save', { path: 'repo/new.txt', content: 'hello' });
  assert.equal(saved.status, 200);
  assert.equal(saved.body.success, true);
  assert.equal(fs.readFileSync(path.join(repoDir, 'new.txt'), 'utf8'), 'hello');

  const deleted = await fetch(`${base}/repos/repo`, { method: 'DELETE' });
  assert.equal(deleted.status, 200);
  await deleted.json();
});

test('missing and unknown repositories are client errors', async () => {
  assert.equal((await get('/tree')).status, 400);
  assert.equal((await get('/tree?repo=missing')).status, 404);
  assert.equal((await get('/status')).status, 400);
  assert.equal((await get('/status?repo=missing')).status, 404);
  assert.equal((await fetch(`${base}/repos/missing`, { method: 'DELETE' })).status, 404);
});

test('file and save require input and refuse path traversal', async () => {
  assert.equal((await get('/file')).status, 400);
  assert.equal((await get('/file?path=..%2F..%2Fetc%2Fpasswd')).status, 403);
  assert.equal((await post('/save', {})).status, 400);
  assert.equal((await post('/save', { path: '../../escape.txt', content: 'x' })).status, 403);
});
