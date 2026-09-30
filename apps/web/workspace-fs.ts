// Workspace file access that cannot be led outside the workspace by a symlink.
//
// Callers pass the workspace root and a destination that is already lexically inside it (no `..`,
// no absolute path; see safeWorkspacePath in server.ts). A lexical check alone is not enough: any path
// component can be a symlink that points out (for example one inside a cloned repository), and a
// component can be swapped for a symlink between a check and the open (TOCTOU). So:
// - the real path of the target (or its nearest existing ancestor) must be inside the real root;
// - reads and writes open the RESOLVED path with O_NOFOLLOW, never the caller's path;
// - after opening, the descriptor itself is checked (/proc/self/fd, or an inode match where /proc is
//   unavailable), so a directory swapped in after the check is still caught before any data moves.
import fs from 'node:fs';
import path from 'node:path';

export class WorkspacePathError extends Error {
  constructor(message = 'Path escapes workspace') {
    super(message);
    this.name = 'WorkspacePathError';
  }
}

const O_NOFOLLOW = fs.constants.O_NOFOLLOW ?? 0;

/** open() with O_NOFOLLOW; a symlink at the final component (ELOOP) is refused as a confinement error. */
async function openNoFollow(file: string, flags: number, mode?: number): Promise<fs.promises.FileHandle> {
  try {
    return await fs.promises.open(file, flags | O_NOFOLLOW, mode);
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === 'ELOOP') throw new WorkspacePathError('Refusing to follow a symlink');
    throw err;
  }
}

export function isInside(candidate: string, root: string): boolean {
  return candidate === root || candidate.startsWith(`${root}${path.sep}`);
}

/** Throws unless the nearest existing ancestor of `destination` resolves inside the real root. */
export async function assertRealInside(root: string, destination: string): Promise<string> {
  const realRoot = await fs.promises.realpath(root);
  for (let probe = destination; ; probe = path.dirname(probe)) {
    try {
      if (!isInside(await fs.promises.realpath(probe), realRoot)) throw new WorkspacePathError();
      return realRoot;
    } catch (err) {
      if ((err as NodeJS.ErrnoException).code !== 'ENOENT' || probe === path.dirname(probe)) throw err;
    }
  }
}

/** Synchronous form for the agent's resolvePath hook. */
export function assertRealInsideSync(root: string, destination: string): void {
  const realRoot = fs.realpathSync(root);
  for (let probe = destination; ; probe = path.dirname(probe)) {
    try {
      if (!isInside(fs.realpathSync(probe), realRoot)) throw new WorkspacePathError();
      return;
    } catch (err) {
      if ((err as NodeJS.ErrnoException).code !== 'ENOENT' || probe === path.dirname(probe)) throw err;
    }
  }
}

/** Verify the file actually opened is inside the root, whatever happened to the path after the check. */
async function assertHandleInside(handle: fs.promises.FileHandle, openedPath: string, realRoot: string): Promise<void> {
  let actual: string | null = null;
  try {
    actual = await fs.promises.readlink(`/proc/self/fd/${handle.fd}`);
  } catch {
    // No /proc (macOS, Windows): the opened inode must be the one the resolved path names now.
  }
  if (actual !== null) {
    if (!isInside(actual, realRoot)) throw new WorkspacePathError();
    return;
  }
  const [opened, named] = await Promise.all([handle.stat(), fs.promises.stat(openedPath)]);
  const realNow = await fs.promises.realpath(openedPath);
  if (opened.ino !== named.ino || opened.dev !== named.dev || !isInside(realNow, realRoot)) throw new WorkspacePathError();
}

export class FileTooLargeError extends Error {}

/** Read a regular file inside the workspace. */
export async function readConfined(root: string, destination: string, maxBytes = Infinity): Promise<Buffer> {
  const realRoot = await assertRealInside(root, destination);
  const real = await fs.promises.realpath(destination);
  if (!isInside(real, realRoot)) throw new WorkspacePathError();
  const handle = await openNoFollow(real, fs.constants.O_RDONLY);
  try {
    await assertHandleInside(handle, real, realRoot);
    const stat = await handle.stat();
    if (!stat.isFile()) throw new WorkspacePathError('Not a regular file');
    if (stat.size > maxBytes) throw new FileTooLargeError('File is too large to preview');
    return await handle.readFile();
  } finally {
    await handle.close();
  }
}

/** Create or replace a regular file inside the workspace. */
export async function writeConfined(root: string, destination: string, data: string | Buffer, { mkdirs = false } = {}): Promise<void> {
  await assertRealInside(root, destination);
  if (mkdirs) await fs.promises.mkdir(path.dirname(destination), { recursive: true });
  const realRoot = await fs.promises.realpath(root);
  const parent = await fs.promises.realpath(path.dirname(destination));
  if (!isInside(parent, realRoot)) throw new WorkspacePathError();
  const target = path.join(parent, path.basename(destination));
  const existing = await fs.promises.lstat(target).catch(() => null);
  if (existing?.isSymbolicLink()) throw new WorkspacePathError('Refusing to write through a symlink');
  // No O_TRUNC at open: truncate only after the descriptor is proven to be inside the workspace.
  const handle = await openNoFollow(target, fs.constants.O_WRONLY | fs.constants.O_CREAT, 0o644);
  try {
    await assertHandleInside(handle, target, realRoot);
    if (!(await handle.stat()).isFile()) throw new WorkspacePathError('Not a regular file');
    await handle.truncate(0);
    await handle.writeFile(data);
  } finally {
    await handle.close();
  }
}

/** Remove a directory entry inside the workspace. A symlink is removed itself; its target is never touched. */
export async function unlinkConfined(root: string, destination: string): Promise<void> {
  await assertRealInside(root, path.dirname(destination));
  const realRoot = await fs.promises.realpath(root);
  const parent = await fs.promises.realpath(path.dirname(destination));
  if (!isInside(parent, realRoot)) throw new WorkspacePathError();
  const target = path.join(parent, path.basename(destination));
  if ((await fs.promises.lstat(target)).isDirectory()) throw new WorkspacePathError('Not a file');
  await fs.promises.unlink(target);
}
