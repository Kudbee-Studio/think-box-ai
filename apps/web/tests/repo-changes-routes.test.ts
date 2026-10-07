// The review-changes routes: reading is open, undo needs a human, and nothing works without a chosen repository.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import type { Server } from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test } from 'node:test';
import express from 'express';
import { registerRepoChangesRoutes } from '../routes/repo-changes.ts';

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-changes-routes-'));
const git = (...a: string[]): void => { execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', ...a], { cwd: root }); };
git('init', '-q', '-b', 'main'); fs.writeFileSync(path.join(root, 'a.txt'), 'one\n'); git('add', '-A'); git('commit', '-qm', 'base');

let chosen: { name: string; root: string } | null = { name: 'demo', root };
let human = true;
const app = express(); app.use(express.json());
registerRepoChangesRoutes(app, { manager: { active: () => chosen } as never, profileId: () => 'p', isHuman: () => human });
const server: Server = app.listen(0, '127.0.0.1');
await new Promise((r) => server.once('listening', r));
const base = `http://127.0.0.1:${(server.address() as { port: number }).port}`;
after(() => { server.close(); fs.rmSync(root, { recursive: true, force: true }); });
const call = async (url: string, init?: RequestInit): Promise<{ status: number; body: any }> => { const r = await fetch(base + url, init); return { status: r.status, body: await r.json() }; };
const post = (body: unknown) => call('/api/repo/changes/undo', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

test('lists changes, shows a diff, and undoes one file', async () => {
  fs.writeFileSync(path.join(root, 'a.txt'), 'ONE\n');
  const list = await call('/api/repo/changes');
  assert.deepEqual(list.body, { repo: 'demo', files: [{ path: 'a.txt', status: 'modified' }], truncated: false });
  assert.match((await call('/api/repo/changes/diff?path=a.txt')).body.diff, /\+ONE/);
  assert.equal((await call('/api/repo/changes/diff?path=nope.txt')).status, 400);
  assert.equal((await post({ path: 'a.txt' })).body.restored, 1);
  assert.equal(fs.readFileSync(path.join(root, 'a.txt'), 'utf8'), 'one\n');
});

test('undo is refused for a request that is not from the dashboard, and changes nothing', async () => {
  fs.writeFileSync(path.join(root, 'a.txt'), 'ONE\n'); human = false;
  assert.equal((await post({})).status, 403);
  human = true;
  assert.equal(fs.readFileSync(path.join(root, 'a.txt'), 'utf8'), 'ONE\n');
  assert.equal((await post({})).body.restored, 1);
});

test('with no repository chosen the list is empty and diff and undo say so', async () => {
  chosen = null;
  assert.deepEqual((await call('/api/repo/changes')).body, { repo: null, files: [], truncated: false });
  assert.equal((await call('/api/repo/changes/diff?path=a.txt')).status, 400);
  assert.equal((await post({})).status, 400);
});
