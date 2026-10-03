#!/usr/bin/env node
// Fast launcher: `node launch.mjs server` (npm start, and the CLI's auto-start of the server). `cli` is supported but measured no faster
// than running cli.ts directly (it loads far fewer files), so bin/kudbee does not use it.
//
// Node strips TypeScript types on every start (WASM, no cache): about 120 ms of a ~450 ms server start. This launcher strips every
// source file once with Node's own `strip` mode (types become whitespace, so line and column numbers in stack traces do not move),
// writes `x.js` NEXT TO `x.ts` (so __dirname, data/, workspaces/ and public/ are exactly where they always were), and runs that.
// A signature of every source's path, size and modification time (plus the Node version) decides when to rebuild, so an edited file
// is picked up on the next start.
//
// It only ever speeds things up. If the build cannot run (old Node without stripTypeScriptTypes, a read-only checkout, syntax that
// needs a real transform) or KUDBEE_NO_BUILD=1 is set, it runs the .ts entry the old way with --experimental-strip-types.
// Tests and `tsgo` keep using the .ts sources; the generated .js files are git-ignored.
import { stripTypeScriptTypes } from 'node:module';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const SKIP_DIRS = new Set(['node_modules', 'tests', 'public', 'data', 'workspaces', 'plugins', 'bin', 'scripts', '.git']);
const STAMP = '.js-build.json';

export function listSources(root = here) {
  const out = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.isDirectory()) { if (!SKIP_DIRS.has(entry.name)) walk(path.join(dir, entry.name)); continue; }
      if (entry.name.endsWith('.ts') && !entry.name.endsWith('.d.ts') && !/\.(test|config)\.ts$/.test(entry.name)) out.push(path.join(dir, entry.name));
    }
  };
  walk(root);
  return out.sort();
}

export function toJs(source) {
  const js = stripTypeScriptTypes(source, { mode: 'strip' });
  // Static, side-effect and dynamic relative imports keep their explicit extension: .ts becomes .js.
  return js.replace(/(\bfrom\s+|\bimport\s*\(\s*|\bimport\s+)(['"])(\.{1,2}\/[^'"]+?)\.ts\2/g, '$1$2$3.js$2');
}

/** Rebuild the .js mirror when the sources changed. Returns true when a build is in place, false when the caller should fall back. */
export function ensureBuilt(root = here) {
  if (typeof stripTypeScriptTypes !== 'function') return false;
  try {
    const files = listSources(root);
    // Path, size and modification time are enough to notice an edit (any save changes the mtime) and cost ~1 ms for ~65 files;
    // reading and hashing every file cost ~10 ms. A checkout or touch only causes one harmless rebuild.
    const hash = createHash('sha1').update(process.version);
    for (const f of files) {
      const st = fs.statSync(f);
      hash.update('\0').update(path.relative(root, f)).update(':').update(String(st.size)).update(':').update(String(st.mtimeMs));
    }
    const signature = hash.digest('hex');
    const stampFile = path.join(root, STAMP);
    let current = false;
    try {
      current = JSON.parse(fs.readFileSync(stampFile, 'utf8')).signature === signature && files.every((f) => fs.existsSync(f.replace(/\.ts$/, '.js')));
    } catch { /* no stamp yet */ }
    if (current) return true;
    for (const f of files) {
      const out = f.replace(/\.ts$/, '.js');
      const tmp = `${out}.${process.pid}.tmp`;
      fs.writeFileSync(tmp, toJs(fs.readFileSync(f, 'utf8')));
      fs.renameSync(tmp, out);
    }
    fs.writeFileSync(`${stampFile}.${process.pid}.tmp`, JSON.stringify({ signature, files: files.length }));
    fs.renameSync(`${stampFile}.${process.pid}.tmp`, stampFile);
    return true;
  } catch (err) {
    if (process.env.KUDBEE_DEBUG) console.error('launch: build skipped:', err instanceof Error ? err.message : err);
    return false;
  }
}

const ENTRIES = { server: 'server', cli: 'cli' };

async function main() {
  const [name, ...args] = process.argv.slice(2);
  const entry = ENTRIES[name ?? ''];
  if (!entry) {
    console.error('usage: node launch.mjs <server|cli> [args...]');
    process.exit(2);
  }
  if (process.env.KUDBEE_NO_BUILD !== '1' && ensureBuilt()) {
    const built = path.join(here, `${entry}.js`);
    process.argv = [process.argv[0], built, ...args];
    await import(pathToFileURL(built).href);
    return;
  }
  const result = spawnSync(process.execPath, ['--experimental-strip-types', '--no-warnings', path.join(here, `${entry}.ts`), ...args], { stdio: 'inherit' });
  process.exit(result.status ?? 1);
}

if (process.argv[1] && pathToFileURL(fs.realpathSync(process.argv[1])).href === import.meta.url) await main();
