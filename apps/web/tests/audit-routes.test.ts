// Choosing the agent's repository and undoing its changes are recorded in the audit log, by the human channel, and a refused request records nothing.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import type { Server } from 'node:http';
import { after, test } from 'node:test';
import express from 'express';
import { registerActiveRepoRoutes } from '../routes/active-repo.ts';

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-audit-routes-'));
const git = (...a: string[]): void => { execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', ...a], { cwd: root }); };
git('init', '-q', '-b', 'main'); fs.writeFileSync(path.join(root, 'a.txt'), 'one\n'); git('add', '-A'); git('commit', '-qm', 'base');

const seen: Array<{ kind: string; actor: string; summary: string; detail?: Record<string, unknown> }> = [];
let human = true;
const manager = { active: () => ({ name: 'demo', root, repo: null }), set: () => ({}), clear: () => undefined, list: () => ['demo'] };
const app = express(); app.use(express.json());
registerActiveRepoRoutes(app, { manager: manager as never, profileId: () => 'p1', isHuman: () => human, audit: (kind, actor, summary, detail) => { seen.push({ kind, actor, summary, detail }); } });
const server: Server = app.listen(0, '127.0.0.1');
await new Promise((r) => server.once('listening', r));
const base = `http://127.0.0.1:${(server.address() as { port: number }).port}`;
after(() => { server.close(); fs.rmSync(root, { recursive: true, force: true }); });
const send = (method: string, url: string, body?: unknown) => fetch(base + url, { method, headers: { 'Content-Type': 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}) });

test('choosing, clearing and undoing are recorded; a refused request is not', async () => {
  assert.equal((await send('POST', '/api/repo/active', { name: 'demo' })).status, 200);
  assert.equal((await send('DELETE', '/api/repo/active')).status, 200);
  fs.writeFileSync(path.join(root, 'a.txt'), 'ONE\n');
  assert.equal((await send('POST', '/api/repo/changes/undo', { path: 'a.txt' })).status, 200);
  fs.writeFileSync(path.join(root, 'a.txt'), 'ONE\n'); human = false;
  assert.equal((await send('POST', '/api/repo/active', { name: 'demo' })).status, 403);
  assert.equal((await send('POST', '/api/repo/changes/undo', {})).status, 403);
  human = true;
  assert.deepEqual(seen.map((e) => [e.kind, e.actor, e.summary]), [
    ['agent_repo_changed', 'human', 'agent repository set to demo'], ['agent_repo_changed', 'human', 'agent repository cleared'], ['changes_undone', 'human', 'undid a.txt'],
  ]);
  assert.deepEqual(seen[2]!.detail, { repo: 'demo', restored: 1 }); assert.deepEqual(seen[0]!.detail, { profile: 'p1' });
});
