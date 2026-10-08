// Finds secrets that were committed: in the files git tracks, and in every commit ever made. A finding names the file, line and rule, never the secret.
// Same idea as the run-record redaction, but stricter about false alarms: placeholders, env lookups and lines marked `secret-scan:ignore` are skipped.
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

export interface Finding { file: string; line: number; rule: string; preview: string; fingerprint: string; commit?: string }

const RULES: Array<[string, RegExp]> = [
  ['private-key', /-----BEGIN [A-Z ]*PRIVATE KEY-----/],
  ['key', /(?<![A-Za-z0-9_])(?:(?:sk|pk|rk)[-_](?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{20,}|(?:ghp|gho|ghs)_[A-Za-z0-9]{30,}|xox[abprs]-[A-Za-z0-9-]{20,}|AKIA[A-Z0-9]{16}|AIza[A-Za-z0-9_-]{30,})/],
  ['jwt', /\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}/],
  ['assigned-secret', /\b[\w-]*(?:api[_-]?key|secret|token|password|passwd|private[_-]?key|mnemonic)\s*[:=]\s*["']((?=[^\s"',;]*\d)(?=[^\s"',;]*[A-Za-z])[^\s"',;]{12,})["']/i],
];
const PLACEHOLDER = /^(<.*>|\$\{.*\}|\{\{.*\}\}|x+|\*+|changeme|your[-_ ].*|example.*|dummy.*|test.*|fake.*|placeholder.*|process\.env.*)$/i;
const IGNORE = 'secret-scan:ignore';

const mask = (s: string): string => `${s.slice(0, 4)}…(${s.length} chars)`;

export function scanText(text: string, file: string): Finding[] {
  const out: Finding[] = [];
  text.split('\n').forEach((raw, i) => {
    if (raw.includes(IGNORE)) return;
    for (const [rule, re] of RULES) {
      const m = re.exec(raw);
      if (!m) continue;
      if (rule === 'assigned-secret' && PLACEHOLDER.test(m[1])) continue;
      const hit = m[1] ?? m[0];
      out.push({ file, line: i + 1, rule, preview: mask(hit), fingerprint: createHash('sha256').update(`${file}|${rule}|${hit}`).digest('hex').slice(0, 16) });
      break;
    }
  });
  return out;
}

const git = (root: string, args: string[], max = 256 * 1024 * 1024): string => execFileSync('git', args, { cwd: root, encoding: 'utf8', maxBuffer: max, stdio: ['ignore', 'pipe', 'ignore'] });
const SKIP_EXT = /\.(png|jpe?g|gif|webp|ico|pdf|woff2?|ttf|db|lock|map|min\.js)$/i;
const MAX_FILE = 1_000_000;

/** The files git tracks right now. Untracked and ignored files (a local .env) are not the repository's business. */
export function scanTracked(root: string): Finding[] {
  const out: Finding[] = [];
  for (const rel of git(root, ['ls-files', '-z']).split('\0').filter(Boolean)) {
    if (SKIP_EXT.test(rel)) continue;
    let text: string;
    let fd = -1;
    try {
      fd = fs.openSync(path.join(root, rel), 'r'); // one handle for the size check and the read, so the file cannot change in between
      const st = fs.fstatSync(fd);
      if (!st.isFile() || st.size > MAX_FILE) continue;
      text = fs.readFileSync(fd, 'utf8');
    } catch { continue; } finally { if (fd >= 0) fs.closeSync(fd); }
    if (text.includes('\0')) continue;
    out.push(...scanText(text, rel));
  }
  return out;
}

/** Lines ever added in any commit on any branch. A secret removed later is still public in history, so it still counts. */
export function scanHistory(root: string): Finding[] {
  let log: string;
  try { log = git(root, ['log', '--all', '-p', '--no-color', '--no-ext-diff', '--format=@@commit %H', '-U0']); } catch { return []; }
  const out: Finding[] = [];
  const seen = new Set<string>();
  let commit = '';
  let file = '';
  for (const line of log.split('\n')) {
    if (line.startsWith('@@commit ')) { commit = line.slice(9, 17); continue; }
    if (line.startsWith('+++ ')) { file = line.slice(6); continue; }
    if (!line.startsWith('+') || SKIP_EXT.test(file)) continue;
    for (const f of scanText(line.slice(1), file)) {
      const key = f.fingerprint;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ ...f, line: 0, commit });
    }
  }
  return out;
}

export const BASELINE_FILE = path.join('docs', 'security', 'secret-scan-baseline.json');

/** Fingerprints of findings someone has looked at and accepted (test fixtures, keys already rotated). A fingerprint is a hash, so the file never holds a secret. */
export function loadBaseline(root: string): Set<string> {
  try {
    const v = JSON.parse(fs.readFileSync(path.join(root, BASELINE_FILE), 'utf8'));
    return new Set(Array.isArray(v?.fingerprints) ? v.fingerprints.filter((x: unknown) => typeof x === 'string') : []);
  } catch { return new Set(); }
}

export function withoutBaseline(found: Finding[], baseline: Set<string>): Finding[] {
  return found.filter((f) => !baseline.has(f.fingerprint));
}

/** Accepts everything found today, tracked files and history. Run it once, after looking at the list. */
export function writeBaseline(root: string): number {
  const fingerprints = [...new Set([...scanTracked(root), ...scanHistory(root)].map((f) => f.fingerprint))].sort();
  const file = path.join(root, BASELINE_FILE);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify({ note: 'Findings reviewed and accepted. Hashes only. A real key that is listed here must still be rotated.', fingerprints }, null, 2)}\n`);
  return fingerprints.length;
}
