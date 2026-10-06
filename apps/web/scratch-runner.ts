// Scratch runner (Layer 4): verify a proposed change by running the repository's OWN checks (lint, typecheck, tsc, tests) in a throwaway copy of a commit, inside a
// bubblewrap sandbox. Design, threat model and the slices still to come: docs/scratch-runner-design.md.
//   - The copy is `git archive` of one commit (no uncommitted work, no credentials, no .env), re-initialised as a fresh local git repo with no remote.
//   - A patch is applied to the COPY only, after a path policy check (no escapes, secrets, symlinks, binary patches); what it touches is reported and flagged.
//   - Only NAMED checks run, each a fixed argv from the repo's own package.json scripts; there is no way to pass a command string.
//   - The sandbox has no network (loopback only), no home, no host files except a read-only system, a read-only node and the read-only installed node_modules, a cleared
//     environment, a private pid namespace that dies with its parent, a timeout, an output cap and a file-size limit. If the sandbox cannot be proven, nothing runs.
//   - Nothing here pushes, opens a pull request, merges or reads a key. The governed tool, approvals and the SIMULATE convoy mode are separate, later slices.
import { spawn, execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { checkRepoPath } from './repo-tools.ts';

// ─── the named checks ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export const CHECKS = {
  lint: { script: 'lint', timeoutMs: 180_000 },
  typecheck: { script: 'typecheck', timeoutMs: 180_000 },
  tsc: { script: 'typecheck:tsc', timeoutMs: 180_000 },
  test: { script: 'test', timeoutMs: 600_000 },
} as const;
export type CheckName = keyof typeof CHECKS | 'test_file';
export const CHECK_NAMES: readonly CheckName[] = [...(Object.keys(CHECKS) as Array<keyof typeof CHECKS>), 'test_file'];
const TEST_FILE = /^tests\/[\w.-]+\.test\.ts$/;
export const OUTPUT_TAIL_BYTES = 60_000;
export const MAX_PATCH_CHARS = 200_000;
export const MAX_PATCH_FILES = 50;
const FILE_SIZE_LIMIT_BYTES = 256 * 1024 * 1024;

/** The argv for a named check, or the reason it is refused. A script name comes from the table, never from the caller. */
export function checkCommand(name: string, file?: string): { ok: true; argv: string[]; timeoutMs: number } | { ok: false; error: string } {
  if (name === 'test_file') {
    if (typeof file !== 'string' || !TEST_FILE.test(file)) return { ok: false, error: 'test_file needs a path like tests/name.test.ts' };
    return { ok: true, argv: ['node', '--experimental-strip-types', '--no-warnings', '--test', '--test-timeout=30000', file], timeoutMs: 180_000 };
  }
  if (!Object.hasOwn(CHECKS, name)) return { ok: false, error: `unknown check "${name}" (the checks are ${CHECK_NAMES.join(', ')})` };
  if (file !== undefined) return { ok: false, error: `${name} takes no file` };
  const c = CHECKS[name as keyof typeof CHECKS];
  return { ok: true, argv: ['npm', 'run', c.script], timeoutMs: c.timeoutMs };
}

// ─── patch policy ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export type PatchReview = { ok: true; files: string[]; flags: string[]; sha256: string } | { ok: false; error: string };

const PATCH_PATH = /^(?:diff --git a\/(.+) b\/(.+)|rename (?:from|to) (.+)|copy (?:from|to) (.+)|--- a\/(.+)|\+\+\+ b\/(.+))$/;
/** Paths whose change deserves a flag: a patch that edits the tests or the gates that judge it can make a broken change look green. */
const SENSITIVE: Array<[string, RegExp]> = [
  ['touches_tests', /(^|\/)tests?\/|\.test\.[cm]?[jt]s$/],
  ['touches_ci_or_gates', /(^|\/)\.github\/|(^|\/)gates\.ts$|(^|\/)package(-lock)?\.json$|(^|\/)tsconfig[\w.-]*\.json$|(^|\/)\.c8rc|vitest\.config/],
];

/** Judges a unified diff before anything is applied. Pure. */
export function reviewPatch(diff: unknown): PatchReview {
  if (typeof diff !== 'string' || !diff.trim()) return { ok: false, error: 'the patch is empty' };
  if (diff.length > MAX_PATCH_CHARS) return { ok: false, error: `the patch is larger than ${MAX_PATCH_CHARS} characters` };
  if (diff.includes('\0')) return { ok: false, error: 'the patch contains a NUL byte' };
  if (!/^diff --git /m.test(diff)) return { ok: false, error: 'the patch must be a unified git diff (diff --git a/... b/...)' };
  if (/^GIT binary patch$|^Binary files /m.test(diff)) return { ok: false, error: 'binary patches are not accepted' };
  if (/^(?:new|old|deleted) (?:file )?mode 120000$|^index [0-9a-f.]+ 120000$/m.test(diff) || /^new file mode 120000/m.test(diff)) return { ok: false, error: 'symlinks are not accepted' };
  const files = new Set<string>();
  for (const line of diff.split('\n')) {
    const m = PATCH_PATH.exec(line.replace(/\r$/, ''));
    if (!m) continue;
    for (const raw of m.slice(1).filter((x): x is string => Boolean(x))) {
      const p = checkRepoPath(raw);
      if (!p.ok) return { ok: false, error: `${raw}: ${p.error}` };
      files.add(p.rel);
    }
  }
  if (!files.size) return { ok: false, error: 'the patch names no file' };
  if (files.size > MAX_PATCH_FILES) return { ok: false, error: `the patch touches more than ${MAX_PATCH_FILES} files` };
  const flags = SENSITIVE.filter(([, re]) => [...files].some((f) => re.test(f))).map(([name]) => name);
  if (/^deleted file mode /m.test(diff)) flags.push('deletes_files');
  return { ok: true, files: [...files].sort(), flags, sha256: createHash('sha256').update(diff).digest('hex') };
}

// ─── the sandbox ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export interface SandboxPaths { work: string; nodeRoot: string; nodeModules: string; cwdRel: string }

/** The environment inside the sandbox: a fixed list, nothing inherited. No key, token or path of the host's can appear here. */
export function sandboxEnv(nodeRoot: string): Record<string, string> {
  return {
    PATH: `${nodeRoot}/bin:/usr/bin:/bin`, HOME: '/tmp/home', TMPDIR: '/tmp', LANG: 'C.UTF-8', CI: '1', NODE_ENV: 'test', FORCE_COLOR: '0',
    npm_config_update_notifier: 'false', npm_config_audit: 'false', npm_config_fund: 'false', npm_config_cache: '/tmp/npm-cache', GIT_CONFIG_NOSYSTEM: '1',
  };
}

/** The bwrap argument list: every namespace unshared (so no network beyond a private loopback), a read-only system, the work copy writable, nothing else of the host. */
export function bwrapArgs(p: SandboxPaths, argv: string[]): string[] {
  const args = ['--unshare-all', '--die-with-parent', '--new-session',
    '--ro-bind', '/usr', '/usr', '--ro-bind', '/lib', '/lib', '--ro-bind', '/lib64', '/lib64', '--ro-bind', '/bin', '/bin', '--ro-bind', p.nodeRoot, p.nodeRoot,
    '--bind', p.work, '/work', '--ro-bind', p.nodeModules, `/work/${p.cwdRel}/node_modules`,
    '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--chdir', `/work/${p.cwdRel}`, '--clearenv'];
  for (const [k, v] of Object.entries(sandboxEnv(p.nodeRoot))) args.push('--setenv', k, v);
  return [...args, ...argv];
}

const run = (cmd: string, args: string[], opts: { cwd?: string; input?: string; env?: Record<string, string>; timeoutMs?: number } = {}): Promise<{ code: number | null; out: string }> =>
  new Promise((resolve) => {
    const child = execFile(cmd, args, { cwd: opts.cwd, env: opts.env ?? { PATH: '/usr/bin:/bin' }, timeout: opts.timeoutMs ?? 120_000, maxBuffer: 80 * 1024 * 1024, encoding: 'utf8' }, (err, stdout, stderr) => {
      resolve({ code: err ? (typeof (err as { code?: unknown }).code === 'number' ? (err as { code: number }).code : 1) : 0, out: `${stdout}${stderr}` });
    });
    if (opts.input !== undefined) child.stdin?.end(opts.input);
  });

export interface Attestation { tool: 'bwrap'; version: string; network: 'blocked'; home_hidden: true; system_read_only: true; env_cleared: true }
export type Probe = { ok: true; attestation: Attestation } | { ok: false; reason: string };

/** The node directory (…/node-vX) the sandbox must see, derived from the running binary. */
export const nodeRootOf = (execPath: string = process.execPath): string => path.dirname(path.dirname(execPath));

// What the sandbox must be true of, checked from INSIDE it: no outside network, none of the host's home contents (the node install, mounted read-only, may sit under it),
// no writable system, no inherited secret. argv: the host's home directory and the one entry of it the node install needs ('' when node is not under it).
const PROBE_SCRIPT = `
const fs = require('fs'); const out = {};
const [hostHome, allowed] = process.argv.slice(1);
out.home_leak = (() => { try { return fs.readdirSync(hostHome).filter((e) => e !== allowed); } catch { return []; } })();
out.system = (() => { try { fs.writeFileSync('/usr/probe', 'x'); return 'writable'; } catch { return 'read_only'; } })();
out.env_leak = Object.keys(process.env).filter((k) => /KEY|TOKEN|SECRET|PASS|CANARY/i.test(k));
fetch('https://api.github.com', { signal: AbortSignal.timeout(2500) }).then(() => { out.network = 'reachable'; }, () => { out.network = 'blocked'; }).then(() => console.log(JSON.stringify(out)));
`;

let probeCache: Promise<Probe> | null = null;
/** Runs a tiny script in the sandbox and checks the properties above. Cached. A failure means nothing may run: there is no unsandboxed fallback. */
export function probeSandbox(opts: { nodeRoot?: string; nodeModules?: string; force?: boolean } = {}): Promise<Probe> {
  if (probeCache && !opts.force) return probeCache;
  probeCache = (async (): Promise<Probe> => {
    const nodeRoot = opts.nodeRoot ?? nodeRootOf();
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-probe-'));
    try {
      const v = await run('bwrap', ['--version']);
      if (v.code !== 0) return { ok: false, reason: 'bubblewrap (bwrap) is not installed or not runnable' };
      fs.mkdirSync(path.join(dir, 'w', 'nm'), { recursive: true });
      const hostHome = os.homedir();
      const allowed = nodeRoot.startsWith(`${hostHome}${path.sep}`) ? nodeRoot.slice(hostHome.length + 1).split(path.sep)[0]! : '';
      const args = bwrapArgs({ work: path.join(dir, 'w'), nodeRoot, nodeModules: path.join(dir, 'w', 'nm'), cwdRel: '.' }, [path.join(nodeRoot, 'bin', 'node'), '-e', PROBE_SCRIPT, hostHome, allowed]);
      const r = await run('bwrap', args, { env: { PATH: '/usr/bin:/bin', KUDBEE_CANARY_KEY: 'must-not-appear' }, timeoutMs: 20_000 });
      let seen: { home_leak?: string[]; system?: string; env_leak?: string[]; network?: string };
      try { seen = JSON.parse(r.out.trim().split('\n').pop() ?? ''); } catch { return { ok: false, reason: `the sandbox probe could not run: ${r.out.trim().slice(0, 160)}` }; }
      if (seen.network !== 'blocked') return { ok: false, reason: `the sandbox does not block the network (${String(seen.network)})` };
      if (seen.home_leak?.length) return { ok: false, reason: `the sandbox shows the host's home contents: ${seen.home_leak.slice(0, 5).join(', ')}` };
      if (seen.system !== 'read_only') return { ok: false, reason: 'the sandbox lets the system be written' };
      if (seen.env_leak?.length) return { ok: false, reason: `the sandbox inherited environment variables: ${seen.env_leak.join(', ')}` };
      return { ok: true, attestation: { tool: 'bwrap', version: v.out.trim().replace(/^bubblewrap\s*/i, ''), network: 'blocked', home_hidden: true, system_read_only: true, env_cleared: true } };
    } finally { fs.rmSync(dir, { recursive: true, force: true }); }
  })();
  return probeCache;
}

// ─── running a check ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export interface CheckResult {
  check: CheckName; file?: string; argv: string[]; exit_code: number | null; signal: string | null; timed_out: boolean; duration_ms: number;
  output_tail: string; output_truncated: boolean; tests?: { pass: number; fail: number }; passed: boolean;
}

/** node:test's summary lines, if present. */
export function parseTestSummary(output: string): { pass: number; fail: number } | undefined {
  const pass = /ℹ pass (\d+)/.exec(output); const fail = /ℹ fail (\d+)/.exec(output);
  return pass && fail ? { pass: Number(pass[1]), fail: Number(fail[1]) } : undefined;
}

export function runCheckInSandbox(p: SandboxPaths, name: CheckName, file: string | undefined, opts: { timeoutMs?: number } = {}): Promise<CheckResult> {
  const cmd = checkCommand(name, file);
  if (!cmd.ok) return Promise.reject(new Error(cmd.error));
  const timeoutMs = opts.timeoutMs ?? cmd.timeoutMs;
  const started = Date.now();
  return new Promise((resolve) => {
    // prlimit caps the size of any one file a check writes (a runaway writer); the sandbox has its own pid namespace, so killing it kills everything inside
    const child = spawn('prlimit', [`--fsize=${FILE_SIZE_LIMIT_BYTES}`, '--', 'bwrap', ...bwrapArgs(p, cmd.argv)], { env: { PATH: '/usr/bin:/bin' }, stdio: ['ignore', 'pipe', 'pipe'], detached: true });
    let buf = ''; let truncated = false; let timedOut = false;
    const take = (d: Buffer): void => { buf += d.toString('utf8'); if (buf.length > OUTPUT_TAIL_BYTES * 2) { buf = buf.slice(-OUTPUT_TAIL_BYTES); truncated = true; } };
    child.stdout.on('data', take); child.stderr.on('data', take);
    const timer = setTimeout(() => { timedOut = true; try { process.kill(-child.pid!, 'SIGKILL'); } catch { /* already gone */ } }, timeoutMs);
    const finish = (code: number | null, signal: NodeJS.Signals | null): void => {
      clearTimeout(timer);
      const tail = buf.length > OUTPUT_TAIL_BYTES ? ((truncated = true), buf.slice(-OUTPUT_TAIL_BYTES)) : buf;
      const tests = name === 'test' || name === 'test_file' ? parseTestSummary(buf) : undefined;
      resolve({ check: name, ...(file ? { file } : {}), argv: cmd.argv, exit_code: code, signal, timed_out: timedOut, duration_ms: Date.now() - started, output_tail: tail, output_truncated: truncated, ...(tests ? { tests } : {}), passed: code === 0 && !timedOut });
    };
    child.on('error', (err) => { buf += `\n[could not start the sandbox: ${err.message}]`; finish(null, null); });
    child.on('close', finish);
  });
}

// ─── the whole run ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

export interface ScratchRequest {
  repoRoot: string;
  /** A commit-ish of the local repository: a sha, branch or tag. The working tree is never used. */
  ref: string;
  /** A unified git diff applied to the COPY. */
  patch?: string;
  checks: Array<{ check: CheckName; file?: string }>;
  scratchRoot?: string;
  /** Overrides the per-check timeout (tests). */
  timeoutMs?: number;
}
export interface ScratchReport {
  ref: string; sha: string; patch_sha256: string | null; files_touched: string[]; flags: string[];
  sandbox: Attestation; checks: CheckResult[]; verified: boolean; started_at: string; duration_ms: number;
}

/** "Verified" means every requested check ran to a zero exit inside the proven sandbox: nothing less, and never on a check that was not run. */
export function verdict(checks: CheckResult[], requested: number): boolean {
  return requested > 0 && checks.length === requested && checks.every((c) => c.passed);
}

const REF = /^[A-Za-z0-9][A-Za-z0-9._/@-]{0,99}$/;
let queue: Promise<unknown> = Promise.resolve();

/** One run at a time. Throws (never half-runs) when the request or the sandbox is not acceptable; the scratch copy is always removed. */
export function runScratch(req: ScratchRequest): Promise<ScratchReport> {
  const result = queue.then(() => runOne(req));
  queue = result.catch(() => undefined);
  return result;
}

async function runOne(req: ScratchRequest): Promise<ScratchReport> {
  const started = Date.now();
  if (!REF.test(req.ref) || req.ref.includes('..')) throw new Error('the ref must be a commit, branch or tag name');
  if (!req.checks.length) throw new Error('name at least one check');
  for (const c of req.checks) { const k = checkCommand(c.check, c.file); if (!k.ok) throw new Error(k.error); }
  let review: Extract<PatchReview, { ok: true }> | null = null;
  if (req.patch !== undefined) { const r = reviewPatch(req.patch); if (!r.ok) throw new Error(`patch refused: ${r.error}`); review = r; }
  const probe = await probeSandbox();
  if (!probe.ok) throw new Error(`no sandbox, so nothing was run: ${probe.reason}`);
  const repoRoot = path.resolve(req.repoRoot);
  const nodeModules = path.join(repoRoot, 'apps', 'web', 'node_modules');
  if (!fs.existsSync(nodeModules)) throw new Error('dependencies are not installed in apps/web (node_modules is missing)');
  const sha = (await run('git', ['rev-parse', '--verify', '--quiet', `${req.ref}^{commit}`], { cwd: repoRoot })).out.trim();
  if (!/^[0-9a-f]{40}$/.test(sha)) throw new Error(`the ref "${req.ref}" is not a commit in this repository`);

  const root = fs.mkdtempSync(path.join(req.scratchRoot ?? os.tmpdir(), 'kudbee-scratch-'));
  try {
    const work = path.join(root, 'work');
    fs.mkdirSync(work);
    const tar = path.join(root, 'tree.tar');
    const arch = await run('git', ['archive', '--format=tar', '-o', tar, sha], { cwd: repoRoot });
    if (arch.code !== 0) throw new Error(`could not export the commit: ${arch.out.slice(0, 160)}`);
    const ext = await run('tar', ['-x', '--no-same-owner', '-f', tar, '-C', work]);
    if (ext.code !== 0) throw new Error(`could not unpack the commit: ${ext.out.slice(0, 160)}`);
    // a fresh local repository with no remote: the tests that look at git still work, and nothing can be pushed
    const git = (...a: string[]) => run('git', ['-c', 'user.email=scratch@localhost', '-c', 'user.name=scratch', '-c', 'commit.gpgsign=false', ...a], { cwd: work, env: { PATH: '/usr/bin:/bin', HOME: root, GIT_CONFIG_NOSYSTEM: '1' } });
    await git('init', '-q'); await git('add', '-A'); await git('commit', '-q', '-m', 'scratch', '--no-verify');
    if (review) {
      const env = { PATH: '/usr/bin:/bin', HOME: root, GIT_CONFIG_NOSYSTEM: '1' };
      const check = await run('git', ['apply', '--check', '--whitespace=nowarn', '-'], { cwd: work, input: req.patch, env });
      if (check.code !== 0) throw new Error(`the patch does not apply to ${sha.slice(0, 8)}: ${check.out.trim().slice(0, 200)}`);
      const apply = await run('git', ['apply', '--whitespace=nowarn', '-'], { cwd: work, input: req.patch, env });
      if (apply.code !== 0) throw new Error(`the patch could not be applied: ${apply.out.trim().slice(0, 200)}`);
    }
    const paths: SandboxPaths = { work, nodeRoot: nodeRootOf(), nodeModules, cwdRel: 'apps/web' };
    fs.mkdirSync(path.join(work, 'apps', 'web', 'node_modules'), { recursive: true });
    const results: CheckResult[] = [];
    for (const c of req.checks) results.push(await runCheckInSandbox(paths, c.check, c.file, { timeoutMs: req.timeoutMs }));
    return { ref: req.ref, sha, patch_sha256: review?.sha256 ?? null, files_touched: review?.files ?? [], flags: review?.flags ?? [], sandbox: probe.attestation, checks: results, verified: verdict(results, req.checks.length), started_at: new Date(started).toISOString(), duration_ms: Date.now() - started };
  } finally {
    if (path.basename(root).startsWith('kudbee-scratch-')) fs.rmSync(root, { recursive: true, force: true });
  }
}
