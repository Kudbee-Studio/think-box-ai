// Local access token for the kudbee CLI (P3.11). A random token lives in a 0600 file inside the Agent OS data directory; the server creates it and
// requires it from a client that claims to be the CLI, the CLI reads it and sends it on the WebSocket upgrade. Never printed, logged or put in a URL.
// This identifies the CLI to the server (so its runs can be mirrored and labeled); it does not widen who can connect: the server still listens on
// 127.0.0.1 only and still checks Host and Origin.
import { randomBytes, timingSafeEqual } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

export const TOKEN_FILE = '.kudbee-token';
export const TOKEN_HEADER = 'x-kudbee-token';

export function localTokenPath(dataDir: string): string {
  return path.join(dataDir, TOKEN_FILE);
}

/** Server side: read the token, creating it (mode 0600) if the file does not exist. */
export function ensureLocalToken(dataDir: string): string {
  const file = localTokenPath(dataDir);
  try {
    const existing = fs.readFileSync(file, 'utf8').trim();
    if (/^[0-9a-f]{64}$/.test(existing)) return existing;
  } catch { /* create below */ }
  fs.mkdirSync(dataDir, { recursive: true });
  const token = randomBytes(32).toString('hex');
  fs.writeFileSync(file, `${token}\n`, { mode: 0o600 });
  fs.chmodSync(file, 0o600);
  return token;
}

/** CLI side: the token if the file exists and is well formed, else null (older server, or never started). */
export function readLocalToken(dataDir: string): string | null {
  try {
    const t = fs.readFileSync(localTokenPath(dataDir), 'utf8').trim();
    return /^[0-9a-f]{64}$/.test(t) ? t : null;
  } catch {
    return null;
  }
}

export function tokensMatch(expected: string, given: unknown): boolean {
  if (typeof given !== 'string' || given.length !== expected.length) return false;
  return timingSafeEqual(Buffer.from(expected), Buffer.from(given));
}

/** Only loopback hosts: the CLI refuses to talk to (or send its token to) anything else. */
export function isLoopbackUrl(url: string): boolean {
  try {
    const h = new URL(url).hostname.toLowerCase();
    return h === '127.0.0.1' || h === 'localhost' || h === '[::1]' || h === '::1';
  } catch {
    return false;
  }
}
