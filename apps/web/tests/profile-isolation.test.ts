// Profile isolation: MemoryStore reads/writes only the active profile's folder, and RunStore lists only
// the active profile's runs. This is the core of "switchable profiles with persistent memory".
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { MemoryStore, profileMemoryRoot } from '../memory.ts';
import { RunStore, type RunRecord } from '../runs.ts';
import { ProfileManager } from '../profile-manager.ts';

const ENV = { KUDBEE_VECTOR_NAMESPACE: 'test' } as NodeJS.ProcessEnv;
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-profile-iso-'));

function newRun(store: RunStore, id: string, goal: string): RunRecord {
  return store.create({
    id,
    session_id: 's',
    goal,
    model: 'mercury-2',
    provider: 'inception',
    status: 'completed',
    started_at: Date.now(),
    steps: [],
    current_step: 0,
    tool_calls: 0,
    prompt_tokens: 0,
    completion_tokens: 0,
    cost_usd: 0,
    approvals: { approved: 0, denied: 0 },
    files: [],
  });
}

test('memory written under one profile is invisible under another, and comes back on switch', async () => {
  const root = tmp();
  const profilesDir = path.join(root, 'profiles');
  const manager = new ProfileManager(profilesDir, root);
  const alpha = manager.create({ name: 'Alpha' });
  const beta = manager.create({ name: 'Beta' });

  const store = new MemoryStore(profileMemoryRoot(profilesDir, alpha.id), ENV, alpha.id);

  // Beta has nothing.
  store.switchTo(profileMemoryRoot(profilesDir, beta.id), beta.id);
  assert.deepEqual(store.counts(), { task: 0, org: 0, verified: 0 });
  assert.equal((await store.search('anything')).hits.length, 0);

  // Alpha writes; Beta must not see it.
  store.switchTo(profileMemoryRoot(profilesDir, alpha.id), alpha.id);
  await store.write('org', { title: 'Alpha secret', content: 'Only Alpha knows the answer' });
  await store.write('verified', { title: 'Alpha fact', content: 'Promoted truth' });
  assert.deepEqual(store.counts(), { task: 0, org: 1, verified: 1 });

  store.switchTo(profileMemoryRoot(profilesDir, beta.id), beta.id);
  assert.deepEqual(store.counts(), { task: 0, org: 0, verified: 0 }, 'Beta sees none of Alpha memory');
  assert.equal(store.list().length, 0);

  // Back to Alpha: everything is still there.
  store.switchTo(profileMemoryRoot(profilesDir, alpha.id), alpha.id);
  assert.deepEqual(store.counts(), { task: 0, org: 1, verified: 1 });
  const hits = await store.search('Alpha secret');
  assert.equal(hits.hits[0]?.item.title, 'Alpha secret');

  // Each profile has its own folder on disk, not a shared one.
  assert.ok(fs.existsSync(path.join(profileMemoryRoot(profilesDir, alpha.id), 'org/alpha-secret.md')));
  assert.ok(!fs.existsSync(path.join(profileMemoryRoot(profilesDir, beta.id), 'org/alpha-secret.md')));
  manager.close();
});

test('run history is filtered to the active profile and survives switching back', () => {
  const root = tmp();
  const profilesDir = path.join(root, 'profiles');
  const manager = new ProfileManager(profilesDir, root);
  const alpha = manager.create({ name: 'Alpha' });
  const beta = manager.create({ name: 'Beta' });
  const runFile = path.join(root, 'runs.json');

  // One shared file, pointed at Alpha first.
  const store = new RunStore(runFile, alpha.id);
  newRun(store, 'a1', 'alpha goal');
  newRun(store, 'a2', 'another alpha goal');
  assert.equal(store.list().length, 2);
  assert.deepEqual(store.list().map((r) => r.id), ['a2', 'a1']);

  // Switch to Beta: it sees nothing, and new runs land in Beta.
  store.setProfile(beta.id);
  assert.equal(store.list().length, 0, 'Beta sees no Alpha runs');
  newRun(store, 'b1', 'beta goal');
  assert.equal(store.list().length, 1);
  assert.equal(store.get('a1'), undefined, 'Alpha run detail is not reachable from Beta');

  // Back to Alpha: both Alpha runs are there, Beta's is not.
  store.setProfile(alpha.id);
  assert.deepEqual(store.list().map((r) => r.id).sort(), ['a1', 'a2']);
  assert.equal(store.get('b1'), undefined);
  assert.equal((store.stats().runs_total as number), 2, 'stats are profile-scoped');

  // A store reopened with no profile (library use) sees everything.
  const all = new RunStore(runFile);
  assert.equal(all.list().length, 3);
  manager.close();
});

test('profileMemoryRoot refuses a non-UUID id', () => {
  assert.throws(() => profileMemoryRoot('/tmp/x', '../../etc'), /Invalid profile id/);
});
