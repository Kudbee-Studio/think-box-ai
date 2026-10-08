// The data folder holds run history, audit log, memory and tokens. Nobody but the owner should read it: 700 for folders, 600 for files.
import fs from 'node:fs';
import path from 'node:path';

function walk(dir: string, visit: (p: string, isDir: boolean) => void): void {
  let names: string[];
  try { names = fs.readdirSync(dir); } catch { return; }
  for (const name of names) {
    const p = path.join(dir, name);
    const st = fs.lstatSync(p); // lstat: a symlink is left alone and never followed out of the folder
    if (st.isSymbolicLink()) continue;
    if (st.isDirectory()) { visit(p, true); walk(p, visit); } else if (st.isFile()) visit(p, false);
  }
}
const want = (isDir: boolean): number => (isDir ? 0o700 : 0o600);

/** Entries (folder included) that group or others can read. */
export function looseEntries(dir: string): string[] {
  const out: string[] = [];
  const check = (p: string, isDir: boolean): void => { if ((fs.statSync(p).mode & 0o777) !== want(isDir)) out.push(p); };
  try { check(dir, true); } catch { return []; }
  walk(dir, check);
  return out;
}

/** Makes the folder and everything in it private to the owner. Returns how many entries were changed. */
export function lockDataDir(dir: string): number {
  let changed = 0;
  const fix = (p: string, isDir: boolean): void => {
    if ((fs.statSync(p).mode & 0o777) === want(isDir)) return;
    fs.chmodSync(p, want(isDir));
    changed++;
  };
  try { fix(dir, true); } catch { return 0; }
  walk(dir, fix);
  return changed;
}

/** For the server at start: locks what exists and makes everything created from now on private too (databases and their -wal files are made later). */
export function secureDataDir(dir: string): number {
  process.umask(0o077);
  fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
  return lockDataDir(dir);
}
