// Defence in depth for the file-system sinks CodeQL flags as js/path-injection. The routes already pass only validated values;
// these tests call the methods DIRECTLY with hostile input to prove each sink enforces its own boundary.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { GitRepoManager, GitInputError } from '../git-repo-manager.ts';
import { MemoryStore } from '../memory.ts';

let tmp: string;
let base: string;
let outside: string;
before(() => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-confine-'));
  base = path.join(tmp, 'ws');
  outside = path.join(tmp, 'ws-evil'); // shares the base's name as a prefix: a naive startsWith(base) would accept it
  fs.mkdirSync(path.join(base, 'repo'), { recursive: true });
  fs.mkdirSync(outside, { recursive: true });
  fs.writeFileSync(path.join(base, 'repo', 'a.txt'), 'a');
  fs.writeFileSync(path.join(outside, 'secret.txt'), 'secret');
});
after(() => fs.rmSync(tmp, { recursive: true, force: true }));

const seed = (m: GitRepoManager, name: string, localPath: string) => (m as unknown as { repos: Map<string, unknown> }).repos.set(name, { url: 'https://github.com/o/r', name, localPath, branch: 'main', lastSync: 0, fileCount: 0, isDirty: false, status: 'idle' });

test('git manager: listing and status refuse anything outside the base, including a sibling that shares its prefix', () => {
  const m = new GitRepoManager(base);
  for (const bad of ['..', '../ws-evil', outside, '/etc', path.join(base, '..', 'ws-evil'), 'repo/../../ws-evil']) {
    assert.throws(() => m.getFileTree(bad), GitInputError, `getFileTree(${bad})`);
    assert.throws(() => m.getRepositoryStatus(bad), GitInputError, `getRepositoryStatus(${bad})`);
  }
  assert.equal(m.getFileTree(path.join(base, 'repo')).children?.length, 1, 'a repository inside the base still lists');
  assert.equal(m.getFileTree(base).type, 'directory', 'the base itself may be listed');
  assert.equal(m.getFileTree('repo').children?.length, 1, 'a relative path resolves against the base');
});

test('git manager: deleteRepository never removes anything outside the base, nor the base itself', () => {
  const m = new GitRepoManager(base);
  seed(m, 'evil', outside);
  assert.throws(() => m.deleteRepository('evil'), GitInputError);
  assert.ok(fs.existsSync(path.join(outside, 'secret.txt')), 'the outside directory is untouched');
  seed(m, 'root', base);
  assert.throws(() => m.deleteRepository('root'), GitInputError);
  assert.ok(fs.existsSync(path.join(base, 'repo', 'a.txt')), 'the base is untouched');
  seed(m, 'up', path.join(base, '..'));
  assert.throws(() => m.deleteRepository('up'), GitInputError);
  assert.ok(fs.existsSync(outside));
  fs.mkdirSync(path.join(base, 'gone'));
  seed(m, 'gone', path.join(base, 'gone'));
  assert.equal(m.deleteRepository('gone'), true, 'a repository inside the base is deleted');
  assert.ok(!fs.existsSync(path.join(base, 'gone')));
  assert.equal(m.deleteRepository('unknown'), false);
});

test('git manager: a clone target outside the base is refused before git runs', async () => {
  const m = new GitRepoManager(base);
  for (const localPath of ['../escape', outside, '/tmp/escape', path.join(base, '..', 'ws-evil', 'x')]) {
    await assert.rejects(m.cloneRepository({ url: 'https://github.com/octocat/Hello-World.git', localPath }), GitInputError, localPath);
  }
  assert.ok(!fs.existsSync(path.join(tmp, 'escape')) && !fs.existsSync(path.join(outside, 'x')));
});

test('git manager: readFile/writeFile keep refusing escapes (existing confinement still holds)', () => {
  const m = new GitRepoManager(base);
  assert.throws(() => m.readFile('../ws-evil/secret.txt'), GitInputError);
  assert.throws(() => m.writeFile('../ws-evil/new.txt', 'x'), GitInputError);
  assert.ok(!fs.existsSync(path.join(outside, 'new.txt')));
  assert.equal(m.readFile('repo/a.txt'), 'a');
});

test('memory: the layer becomes a directory name, so an unknown layer is refused at runtime and writes nothing', async () => {
  const root = path.join(tmp, 'mem');
  const store = new MemoryStore(root, {});
  for (const layer of ['../../escape', '../ws-evil', 'secret', '']) {
    await assert.rejects(store.write(layer as never, { title: 't', content: 'c' }), /Unknown memory layer/, layer);
  }
  assert.ok(!fs.existsSync(path.join(tmp, 'escape.md')));
  assert.deepEqual(fs.readdirSync(outside), ['secret.txt'], 'nothing was written next to the base');
  const ok = await store.write('org', { title: 'A fine title', content: 'body' });
  assert.equal(ok.layer, 'org');
  assert.ok(fs.existsSync(path.join(root, 'org', `${ok.id.split('/')[1]}.md`)));
});

test('memory: a hostile slug or title cannot leave its layer directory', async () => {
  const root = path.join(tmp, 'mem2');
  const store = new MemoryStore(root, {});
  const item = await store.write('task', { title: '../../../etc/passwd', content: 'c', slug: '../../../../evil' });
  assert.match(item.id, /^task\/[a-z0-9-]+$/);
  const written = path.join(root, item.path);
  assert.ok(written.startsWith(path.join(root, 'task') + path.sep));
  assert.ok(fs.existsSync(written));
});

test('memory: an enormous title is slugged in bounded time', async () => {
  const store = new MemoryStore(path.join(tmp, 'mem3'), {});
  const started = Date.now();
  const item = await store.write('task', { title: '-'.repeat(200_000) + 'x' + '-'.repeat(200_000), content: 'c' });
  assert.ok(Date.now() - started < 2000, 'no quadratic regex blow-up');
  assert.match(item.id, /^task\//);
});
