// Reading and writing the evidence files the opt-in live scripts produce. Reads never check-then-read (a missing file is just ENOENT); writes go
// through the confined, symlink-safe writer, so evidence can only land inside its own folder.
import fs from 'node:fs';
import { writeConfined } from '../../workspace-fs.ts';

export function readTextIfPresent(file: string): string {
  try { return fs.readFileSync(file, 'utf8'); } catch (err) { if ((err as NodeJS.ErrnoException).code === 'ENOENT') return ''; throw err; }
}

export function readJsonIfPresent<T>(file: string, fallback: T): T {
  const text = readTextIfPresent(file);
  return text ? (JSON.parse(text) as T) : fallback;
}

/** Writes `data` as pretty JSON to `file`, which must sit inside `dir` (created if missing). */
export async function writeEvidence(dir: string, file: string, data: unknown): Promise<void> {
  fs.mkdirSync(dir, { recursive: true });
  await writeConfined(dir, file, `${JSON.stringify(data, null, 2)}\n`, { mkdirs: true });
}
