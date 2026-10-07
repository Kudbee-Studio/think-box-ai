// A repository the agent is pointed at (a clone) is not always shaped like ours: a plain `README`, a LICENSE, a Makefile, Go or Rust sources. The repository tools
// must read those, and must still refuse secrets, keys, databases and binary-looking files.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { checkRepoPath, isTextFile, repoRead, repoSearch } from '../repo-tools.ts';

let root = '';
const write = (rel: string, text: string) => { fs.mkdirSync(path.dirname(path.join(root, rel)), { recursive: true }); fs.writeFileSync(path.join(root, rel), text); };
before(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), 'repo-types-'));
  write('README', 'Hello World!\n'); write('LICENSE', 'MIT License needle\n'); write('Makefile', 'build:\n\techo needle\n'); write('Dockerfile', 'FROM node needle\n');
  write('cmd/main.go', 'package main // needle\n'); write('src/lib.rs', 'fn needle() {}\n'); write('web/App.tsx', 'export const App = () => "needle";\n');
  write('id_rsa', 'needle private\n'); write('server.key', 'needle\n'); write('db.sqlite', 'needle\n'); write('image.png', 'needle\n'); write('notes.bin', 'needle\n'); write('.env', 'needle=1\n'); write('config/secrets.go', 'needle\n'); write('data.csv', 'needle\n');
});
after(() => fs.rmSync(root, { recursive: true, force: true }));

test('isTextFile: source and documentation extensions and the well-known extensionless names, case-insensitive; nothing else', () => {
  for (const ok of ['a.ts', 'a.tsx', 'a.go', 'a.rs', 'a.java', 'a.rb', 'a.php', 'a.c', 'a.h', 'a.cpp', 'a.cs', 'a.sql', 'a.xml', 'a.rst', 'README', 'readme', 'LICENSE', 'Makefile', 'Dockerfile', 'CHANGELOG', 'CODEOWNERS', 'dir/sub/README', 'x/Makefile']) assert.ok(isTextFile(ok), ok);
  for (const no of ['a.png', 'a.bin', 'a.exe', 'a.zip', 'a.sqlite', 'a', 'README.exe', 'noext', '', 'dir/']) assert.ok(!isTextFile(no), no);
});

test('the search finds text in an extensionless README, a LICENSE, a Makefile, a Dockerfile, Go, Rust and TSX files', async () => {
  const e = await repoSearch({ query: 'needle', path: '' }, root) as { matches: Array<{ path: string }> };
  const paths = e.matches.map((m) => m.path).sort();
  assert.deepEqual(paths, ['Dockerfile', 'LICENSE', 'Makefile', 'cmd/main.go', 'src/lib.rs', 'web/App.tsx']);
  const hello = await repoSearch({ query: 'Hello World', path: '' }, root) as { matches: Array<{ path: string }> };
  assert.deepEqual(hello.matches.map((m) => m.path), ['README'], 'the README of a plain-README repository is no longer invisible');
});

test('the read tool opens those files, and still refuses secrets, keys, databases, binaries and hidden files', async () => {
  assert.match(JSON.stringify(await repoRead({ path: 'README', start: 1, end: 5 }, root)), /Hello World!/);
  assert.equal(checkRepoPath('Makefile').ok, true);
  for (const bad of ['id_rsa', 'server.key', 'db.sqlite', 'image.png', 'notes.bin', '.env', 'config/secrets.go', 'data.csv']) assert.equal(checkRepoPath(bad).ok, false, bad);
  const all = JSON.stringify(await repoSearch({ query: 'needle', path: '' }, root));
  for (const hidden of ['id_rsa', 'server.key', 'db.sqlite', 'image.png', 'notes.bin', '.env', 'secrets.go', 'data.csv']) assert.ok(!all.includes(hidden), `${hidden} never appears in results`);
});
