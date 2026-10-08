// `kudbee doctor`: one pass over the things that most often go wrong with a local agent OS: who can read the data, secrets in the repo and its history,
// where the server listens, and known-vulnerable or old dependencies. Offline mode skips the two network checks and says so.
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { auditVerdict, parseAudit } from './dep-audit.ts';
import { looseEntries } from './data-permissions.ts';
import { loadBaseline, scanHistory, scanTracked, withoutBaseline, type Finding } from './secret-scan.ts';

export type CheckStatus = 'ok' | 'warn' | 'fail' | 'skipped';
export interface Check { id: string; status: CheckStatus; detail: string }
export interface DoctorReport { checks: Check[]; ok: boolean }
export interface DoctorOptions { repoRoot: string; dataDir: string; env: Record<string, string | undefined>; online: boolean; webDir?: string }

const where = (f: Finding): string => `${f.file}${f.line ? `:${f.line}` : ''} (${f.rule}${f.commit ? `, commit ${f.commit}` : ''})`;
const list = (fs_: Finding[]): string => `${fs_.length} found: ${fs_.slice(0, 5).map(where).join('; ')}${fs_.length > 5 ? '; …' : ''}`;

function npmJson(cwd: string, args: string[]): string {
  try { return execFileSync('npm', args, { cwd, encoding: 'utf8', timeout: 60_000, stdio: ['ignore', 'pipe', 'ignore'] }); } catch (e) { return (e as { stdout?: string }).stdout ?? ''; }
}

export async function runDoctor(o: DoctorOptions): Promise<DoctorReport> {
  const checks: Check[] = [];
  const add = (id: string, status: CheckStatus, detail: string): void => { checks.push({ id, status, detail }); };

  const loose = looseEntries(o.dataDir);
  add('data-permissions', loose.length ? 'fail' : 'ok', loose.length ? `${loose.length} entries in the data folder can be read by other users (fix: kudbee doctor --fix)` : 'only the owner can read the data folder');

  const baseline = loadBaseline(o.repoRoot);
  const tracked = withoutBaseline(scanTracked(o.repoRoot), baseline);
  add('tracked-secrets', tracked.length ? 'fail' : 'ok', tracked.length ? list(tracked) : 'no new secrets in tracked files');
  const hist = withoutBaseline(scanHistory(o.repoRoot), baseline);
  const known = scanHistory(o.repoRoot).length - hist.length;
  add('history-secrets', hist.length ? 'fail' : known ? 'warn' : 'ok', hist.length ? `${list(hist)}. Removing the file does not remove it from history; rotate the key.` : known ? `${known} accepted findings in history (listed in the baseline); a real key among them must still be rotated` : 'no secrets in git history');

  const addr = o.env.LISTEN_ADDR || '127.0.0.1';
  const local = addr === '127.0.0.1' || addr === 'localhost' || addr === '::1';
  add('bind-address', local ? 'ok' : o.env.KUDBEE_ALLOW_NON_LOOPBACK === '1' ? 'fail' : 'warn', local ? 'listens on this machine only' : `listens on ${addr}; the dashboard has no login yet`);

  const envFile = path.join(o.repoRoot, '.env');
  let envStatus: CheckStatus = 'ok';
  let envDetail = 'no .env file';
  if (fs.existsSync(envFile)) {
    const mode = fs.statSync(envFile).mode & 0o777;
    envStatus = mode & 0o077 ? 'fail' : 'ok';
    envDetail = envStatus === 'ok' ? '.env is private to the owner' : `.env is readable by other users (mode ${mode.toString(8)}); chmod 600`;
  }
  add('env-file', envStatus, envDetail);

  if (!o.online) {
    add('dependency-audit', 'skipped', 'offline: not run');
    add('outdated-packages', 'skipped', 'offline: not run');
  } else {
    const web = o.webDir ?? o.repoRoot;
    const v = auditVerdict(parseAudit(npmJson(web, ['audit', '--json'])));
    add('dependency-audit', v.status === 'pass' ? 'ok' : v.status === 'fail' ? 'fail' : 'skipped', v.detail);
    let outdated = 0;
    try { outdated = Object.keys(JSON.parse(npmJson(web, ['outdated', '--json']) || '{}')).length; } catch { outdated = -1; }
    add('outdated-packages', outdated < 0 ? 'skipped' : outdated ? 'warn' : 'ok', outdated < 0 ? 'could not read the registry' : outdated ? `${outdated} packages have a newer version` : 'all packages current');
  }

  return { checks, ok: checks.every((c) => c.status !== 'fail') };
}

export function renderDoctor(r: DoctorReport): string {
  const mark: Record<CheckStatus, string> = { ok: 'OK     ', warn: 'WARN   ', fail: 'FAIL   ', skipped: 'SKIPPED' };
  return [...r.checks.map((c) => `${mark[c.status]} ${c.id.padEnd(18)} ${c.detail}`), r.ok ? 'doctor: no failures' : 'doctor: failures found'].join('\n');
}
