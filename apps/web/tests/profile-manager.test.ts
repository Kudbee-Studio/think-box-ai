// ProfileManager: named profiles each with isolated data, plus export/import with a fresh UUID.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { ProfileManager, ProfileError } from '../profile-manager.ts';

const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-profile-test-'));

test('a fresh manager creates exactly one active Default profile and persists it', () => {
  const root = tmp();
  const manager = new ProfileManager(root, root);
  const list = manager.list();
  assert.equal(list.length, 1);
  assert.equal(list[0].name, 'Default');
  assert.equal(list[0].is_active, true);
  assert.equal(manager.getActiveId(), list[0].id);
  manager.close();

  // A new manager on the same DB sees the same profile and pointer.
  const reopened = new ProfileManager(root, root);
  assert.equal(reopened.list().length, 1);
  assert.equal(reopened.getActiveId(), list[0].id);
  reopened.close();
});

test('create/get/list/update carry the profile fields and settings', () => {
  const root = tmp();
  const manager = new ProfileManager(root, root);
  const alpha = manager.create({ name: 'Alpha', description: 'first', settings: { model: 'mercury-2', theme: 'dark' } });
  assert.match(alpha.id, /^[0-9a-f-]{36}$/);
  assert.equal(alpha.name, 'Alpha');
  assert.equal(alpha.description, 'first');
  assert.deepEqual(alpha.settings, { model: 'mercury-2', theme: 'dark' });
  assert.equal(alpha.is_active, false, 'a new profile is not active until setActive');

  const updated = manager.update(alpha.id, { name: 'Alpha 2', settings: { theme: 'light' } });
  assert.equal(updated.name, 'Alpha 2');
  assert.deepEqual(updated.settings, { model: 'mercury-2', theme: 'light' }, 'settings merge, not replace');
  assert.equal(manager.get(alpha.id)?.name, 'Alpha 2');
  assert.equal(manager.list().length, 2);
  manager.close();
});

test('setActive switches the pointer; unknown ids are refused', () => {
  const root = tmp();
  const manager = new ProfileManager(root, root);
  const alpha = manager.create({ name: 'Alpha' });
  const beta = manager.create({ name: 'Beta' });
  assert.equal(manager.setActive(beta.id).id, beta.id);
  assert.equal(manager.active().id, beta.id);
  assert.equal(manager.get(alpha.id)?.is_active, false);
  assert.equal(manager.get(beta.id)?.is_active, true);
  assert.throws(() => manager.setActive('nope'), ProfileError);
  manager.close();
});

test('delete removes the profile and its data directory; the last profile cannot be deleted', () => {
  const root = tmp();
  const manager = new ProfileManager(root, root);
  const extra = manager.create({ name: 'Extra' });
  assert.ok(fs.existsSync(manager.dataDirFor(extra.id)));
  assert.equal(manager.delete(extra.id), true);
  assert.equal(manager.get(extra.id), undefined);
  assert.equal(fs.existsSync(manager.dataDirFor(extra.id)), false, 'data dir is gone');
  assert.throws(() => manager.delete(manager.getActiveId()), /last profile/);
  manager.close();
});

test('deleting the active profile switches to another and persists the new pointer', () => {
  const root = tmp();
  const manager = new ProfileManager(root, root);
  const first = manager.getActiveId();
  const second = manager.create({ name: 'Second' });
  manager.setActive(second.id);
  manager.delete(second.id);
  assert.equal(manager.getActiveId(), first);
  manager.close();

  const reopened = new ProfileManager(root, root);
  assert.equal(reopened.getActiveId(), first);
  reopened.close();
});

test('export/import gives the copy a fresh UUID and a suffixed name', () => {
  const root = tmp();
  const manager = new ProfileManager(root, root);
  const alpha = manager.create({ name: 'Alpha', description: 'x', settings: { model: 'mercury-2' } });
  const bundle = manager.export(alpha.id, { verified: [], org: [{ id: 'org/n', layer: 'org', title: 'N', tags: [], source: 'human', created: '', updated: '', content: 'c' }], task: [] }, [{ id: 'r1' }]);
  assert.equal(bundle.format, 'kudbee-profile');
  assert.equal(bundle.profile.name, 'Alpha');
  assert.equal(bundle.memory.org.length, 1);

  const copy = manager.import(bundle, bundle.memory, bundle.runs);
  assert.notEqual(copy.id, alpha.id, 'import gets a fresh UUID');
  assert.equal(copy.name, 'Alpha (imported)');
  assert.deepEqual(copy.settings, { model: 'mercury-2' });
  assert.equal(manager.list().length, 3, 'Default + source + copy; source is untouched');
  manager.close();
});

test('bad input is refused: no name, over-long name, bad export bundle', () => {
  const root = tmp();
  const manager = new ProfileManager(root, root);
  assert.throws(() => manager.create({ name: '   ' }), /needs a name/);
  assert.throws(() => manager.create({ name: 'x'.repeat(81) }), /too long/);
  assert.throws(() => manager.import({ format: 'nope' } as never, {}, []), /Not a kudbee profile export/);
  manager.close();
});
