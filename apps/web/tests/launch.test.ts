// launch.mjs runs a pre-stripped JS mirror of the TypeScript sources for a faster start. The risks are serving STALE code and breaking when
// the build cannot run, so these tests cover: correct output, stack traces that still point at the .ts line, rebuild on edit / missing
// output, files that must not be built, the fallback, and a real server started both ways.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync, spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { ensureBuilt, listSources, toJs } from '../launch.mjs';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let tmp: string;
const procs: ChildProcess[] = [];
before(() => { tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-launch-')); });
after(() => { for (const p of procs) p.kill('SIGKILL'); fs.rmSync(tmp, { recursive: true, force: true }); });

function project(files: Record<string, string>): string {
  const root = fs.mkdtempSync(path.join(tmp, 'p-'));
  for (const [rel, text] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(root, rel)), { recursive: true });
    fs.writeFileSync(path.join(root, rel), text);
  }
  return root;
}
const run = (file: string) => execFileSync(process.execPath, ['--no-warnings', file], { encoding: 'utf8' }).trim();
const bump = (file: string) => { const t = new Date(Date.now() + 5000); fs.utimesSync(file, t, t); };

test('toJs: types are erased, relative .ts specifiers become .js (static, side-effect, dynamic), other strings are untouched', () => {
  const js = toJs([
    "import type { T } from './types.ts';",
    "import { a } from './a.ts';",
    "import './side.ts';",
    "import express from 'express';",
    "export const x: number = a as number;",
    "const lazy = await import('./lazy.ts');",
    "const name = 'server.ts';",
  ].join('\n'));
  assert.doesNotMatch(js, /: number|as number|import type|\{ T \}/);
  assert.match(js, /from '\.\/a\.js'/);
  assert.match(js, /import '\.\/side\.js'/);
  assert.match(js, /import\('\.\/lazy\.js'\)/);
  assert.match(js, /from 'express'/);
  assert.match(js, /const name = 'server\.ts'/, 'a plain string that happens to end in .ts is not rewritten');
  assert.equal(js.split('\n').length, 7, 'line count unchanged');
});

test('a built project runs and its stack traces still point at the TypeScript line', () => {
  const root = project({
    'b.ts': 'export function boom(n: number): never {\n  const message: string = `bad ${n}`;\n\n  throw new Error(message);\n}\n',
    'main.ts': "import { boom } from './b.ts';\ntry { boom(1); } catch (e) { console.log((e as Error).stack!.split('\\n')[1]); }\n",
  });
  assert.equal(ensureBuilt(root), true);
  assert.match(run(path.join(root, 'main.js')), /b\.js:4:/, 'the throw is on line 4 of b.ts and still reports line 4');
});

test('rebuilds when a source is edited or an output is missing, and otherwise leaves the build alone', () => {
  const root = project({ 'a.ts': "import { v } from './b.ts';\nconsole.log(v);\n", 'b.ts': 'export const v: string = "one";\n' });
  assert.equal(ensureBuilt(root), true);
  assert.equal(run(path.join(root, 'a.js')), 'one');

  const before = fs.statSync(path.join(root, 'b.js')).mtimeMs;
  assert.equal(ensureBuilt(root), true);
  assert.equal(fs.statSync(path.join(root, 'b.js')).mtimeMs, before, 'an unchanged tree is not rebuilt');

  fs.writeFileSync(path.join(root, 'b.ts'), 'export const v: string = "two";\n');
  bump(path.join(root, 'b.ts'));
  assert.equal(ensureBuilt(root), true);
  assert.equal(run(path.join(root, 'a.js')), 'two', 'an edit is picked up on the next start (no stale code)');

  fs.rmSync(path.join(root, 'a.js'));
  assert.equal(ensureBuilt(root), true);
  assert.ok(fs.existsSync(path.join(root, 'a.js')), 'a missing output is rebuilt');
});

test('only server sources are built: tests, declarations, config, node_modules, public and data are skipped', () => {
  const root = project({
    'server.ts': 'export const a: number = 1;\n', 'sdk/x.ts': 'export const b: number = 2;\n',
    'types.d.ts': 'export type T = number;\n', 'thing.test.ts': 'export {};\n', 'vitest.config.ts': 'export default {};\n',
    'tests/t.ts': 'export {};\n', 'node_modules/m/i.ts': 'export {};\n', 'public/p.ts': 'export {};\n', 'data/d.ts': 'export {};\n',
  });
  assert.deepEqual(listSources(root).map((f) => path.relative(root, f)), ['sdk/x.ts', 'server.ts']);
  assert.equal(ensureBuilt(root), true);
  for (const rel of ['server.js', 'sdk/x.js']) assert.ok(fs.existsSync(path.join(root, rel)), rel);
  for (const rel of ['types.d.js', 'thing.test.js', 'vitest.config.js', 'tests/t.js', 'node_modules/m/i.js', 'public/p.js', 'data/d.js']) assert.ok(!fs.existsSync(path.join(root, rel)), `${rel} must not be built`);
});

test('syntax that needs a real transform (enum) makes the build report failure so the caller falls back, leaving no stamp', () => {
  const root = project({ 'server.ts': 'export enum Color { Red, Green }\n' });
  assert.equal(ensureBuilt(root), false);
  assert.ok(!fs.existsSync(path.join(root, '.js-build.json')));
});

async function waitHealthy(url: string): Promise<void> {
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 100))) {
    try { if ((await fetch(`${url}/api/health`)).ok) return; } catch { /* starting */ }
  }
  throw new Error('server did not start');
}

function launch(extraEnv: Record<string, string>): { url: string; proc: ChildProcess } {
  const port = 20000 + Math.floor(Math.random() * 20000);
  const dead = 'http://127.0.0.1:9';
  const proc = spawn(process.execPath, ['--no-warnings', 'launch.mjs', 'server'], {
    cwd: appDir,
    env: {
      ...process.env, PORT: String(port), INCEPTION_API_KEY: 'test', INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: dead, JANUS_BASE_URL: dead,
      UPSTASH_VECTOR_REST_URL: dead, UPSTASH_VECTOR_REST_TOKEN: 'none', KUDBEE_DAILY_BUDGET_USD: '0', THINKBOX_BACKEND_URL: dead,
      KUDBEE_DATA_DIR: path.join(tmp, `d-${port}`), KUDBEE_WORKSPACE_DIR: path.join(tmp, `w-${port}`), ...extraEnv,
    },
    stdio: 'ignore',
  });
  procs.push(proc);
  return { url: `http://127.0.0.1:${port}`, proc };
}

test('real server through launch.mjs: starts from the built JS, serves the dashboard, and the data/workspace paths are the configured ones', async () => {
  const { url } = launch({});
  await waitHealthy(url);
  const page = await fetch(url);
  assert.equal(page.status, 200);
  assert.match(await page.text(), /kudbEE/);
  assert.ok(fs.existsSync(path.join(appDir, 'server.js')) && fs.existsSync(path.join(appDir, '.js-build.json')), 'the build is in place next to the sources');
  assert.ok(fs.existsSync(path.join(appDir, 'server.ts')), 'sources untouched');
});

test('real server through launch.mjs with KUDBEE_NO_BUILD=1 falls back to --experimental-strip-types and still works', async () => {
  const { url } = launch({ KUDBEE_NO_BUILD: '1' });
  await waitHealthy(url);
  assert.equal((await fetch(`${url}/api/health`)).status, 200);
});

test('the generated files are git-ignored, and npm start and the CLI server auto-start use the launcher', () => {
  const root = path.resolve(appDir, '..', '..');
  for (const p of ['apps/web/server.js', 'apps/web/sdk/index.js', 'apps/web/services/analytics.js', 'apps/web/.js-build.json']) {
    assert.doesNotThrow(() => execFileSync('git', ['check-ignore', '-q', p], { cwd: root }), `${p} should be ignored`);
  }
  assert.throws(() => execFileSync('git', ['check-ignore', '-q', 'apps/web/public/js/app.js'], { cwd: root }), 'front-end sources must NOT be ignored');
  const pkg = JSON.parse(fs.readFileSync(path.join(appDir, 'package.json'), 'utf8')) as { scripts: Record<string, string> };
  assert.equal(pkg.scripts.start, 'node launch.mjs server');
  assert.match(fs.readFileSync(path.join(appDir, 'cli.ts'), 'utf8'), /launch\.mjs'\), 'server'/);
});
