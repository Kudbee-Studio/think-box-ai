// Dashboard user authentication for the governed execution routes.
// - Credentials: KUDBEE_DASHBOARD_USER (default "admin") + KUDBEE_DASHBOARD_PASSWORD_HASH, a scrypt hash
//   produced by `node --experimental-strip-types scripts/hash-password.ts`. No plaintext passwords, nothing
//   in source. If no hash is configured, protected routes fail closed (503).
// - Sessions: opaque 256-bit random ids held server-side (in memory), sent as an HttpOnly, SameSite=Strict
//   cookie. The id rotates at login. Sessions expire after 30 min idle or 12 h total. Logout deletes the session.
// - Failed logins are rate-limited per client address.
import { randomBytes, scryptSync, timingSafeEqual } from 'node:crypto';
import type { Request, Response, NextFunction } from 'express';

export const SESSION_COOKIE = 'kudbee_sid';
const SCRYPT = { N: 16384, r: 8, p: 1, keylen: 32 };

export function hashPassword(password: string, salt = randomBytes(16)): string {
  const key = scryptSync(password, salt, SCRYPT.keylen, { N: SCRYPT.N, r: SCRYPT.r, p: SCRYPT.p });
  return `scrypt$${SCRYPT.N}$${SCRYPT.r}$${SCRYPT.p}$${salt.toString('base64')}$${key.toString('base64')}`;
}

export function verifyPassword(password: string, stored: string): boolean {
  const parts = stored.split('$');
  if (parts.length !== 6 || parts[0] !== 'scrypt') return false;
  const [N, r, p] = parts.slice(1, 4).map(Number);
  const salt = Buffer.from(parts[4], 'base64');
  const expected = Buffer.from(parts[5], 'base64');
  if (!N || !r || !p || salt.length < 8 || expected.length < 16) return false;
  const got = scryptSync(password, salt, expected.length, { N, r, p, maxmem: 64 * 1024 * 1024 });
  return timingSafeEqual(got, expected);
}

export interface AuthConfig {
  user: string;
  passwordHash: string;
  idleMs: number;
  absoluteMs: number;
  secureCookie: boolean;
  maxFailures: number;
  lockoutMs: number;
}

export function authConfigFromEnv(env: NodeJS.ProcessEnv = process.env): AuthConfig {
  return {
    user: (env.KUDBEE_DASHBOARD_USER || 'admin').trim(),
    passwordHash: (env.KUDBEE_DASHBOARD_PASSWORD_HASH || '').trim(),
    idleMs: 30 * 60 * 1000,
    absoluteMs: 12 * 60 * 60 * 1000,
    secureCookie: env.KUDBEE_COOKIE_SECURE === '1',
    maxFailures: 5,
    lockoutMs: 15 * 60 * 1000,
  };
}

interface Session { user: string; createdAt: number; lastSeen: number }

function parseCookies(header: string | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  for (const part of (header || '').split(';')) {
    const i = part.indexOf('=');
    if (i > 0) out[part.slice(0, i).trim()] = decodeURIComponent(part.slice(i + 1).trim());
  }
  return out;
}

export class DashboardAuth {
  private sessions = new Map<string, Session>();
  private failures = new Map<string, { count: number; until: number }>();
  private cfg: AuthConfig;
  private now: () => number;
  constructor(cfg: AuthConfig, now: () => number = Date.now) {
    this.cfg = cfg;
    this.now = now;
  }

  get configured(): boolean {
    return Boolean(this.cfg.user && this.cfg.passwordHash.startsWith('scrypt$'));
  }

  private cookie(value: string, maxAgeSec: number): string {
    return `${SESSION_COOKIE}=${value}; HttpOnly; SameSite=Strict; Path=/; Max-Age=${maxAgeSec}${this.cfg.secureCookie ? '; Secure' : ''}`;
  }

  /** Returns the authenticated session for this request, expiring stale sessions as a side effect. */
  current(req: Request): (Session & { id: string }) | null {
    const id = parseCookies(req.headers.cookie)[SESSION_COOKIE];
    if (!id) return null;
    const s = this.sessions.get(id);
    if (!s) return null;
    const t = this.now();
    if (t - s.lastSeen > this.cfg.idleMs || t - s.createdAt > this.cfg.absoluteMs) {
      this.sessions.delete(id);
      return null;
    }
    s.lastSeen = t;
    return { ...s, id };
  }

  private fromDashboard(req: Request, res: Response): boolean {
    // A custom header cannot be set by a cross-site form post, so this blocks login/logout CSRF.
    if (req.get('x-kudbee-client') === 'dashboard') return true;
    res.status(403).json({ error: 'missing x-kudbee-client header' });
    return false;
  }

  login = (req: Request, res: Response): void => {
    if (!this.fromDashboard(req, res)) return;
    if (!this.configured) {
      res.status(503).json({ error: 'dashboard authentication not configured (KUDBEE_DASHBOARD_PASSWORD_HASH)' });
      return;
    }
    const who = req.ip || req.socket.remoteAddress || 'unknown';
    const t = this.now();
    const f = this.failures.get(who);
    if (f && f.until > t) {
      res.status(429).json({ error: 'too many failed logins; try later' });
      return;
    }
    const username = typeof req.body?.username === 'string' ? req.body.username : '';
    const password = typeof req.body?.password === 'string' ? req.body.password : '';
    // Always run the hash so a wrong username costs the same as a wrong password.
    const passOk = verifyPassword(password, this.cfg.passwordHash);
    const userOk = username.length === this.cfg.user.length && timingSafeEqual(Buffer.from(username), Buffer.from(this.cfg.user));
    if (!(passOk && userOk)) {
      const count = (f && f.until <= t && f.count >= this.cfg.maxFailures ? 0 : f?.count ?? 0) + 1;
      this.failures.set(who, { count, until: count >= this.cfg.maxFailures ? t + this.cfg.lockoutMs : 0 });
      res.status(401).json({ error: 'invalid credentials' });
      return;
    }
    this.failures.delete(who);
    const old = parseCookies(req.headers.cookie)[SESSION_COOKIE];
    if (old) this.sessions.delete(old); // rotate: never reuse a pre-login id
    const id = randomBytes(32).toString('base64url');
    this.sessions.set(id, { user: this.cfg.user, createdAt: t, lastSeen: t });
    res.setHeader('Set-Cookie', this.cookie(id, Math.floor(this.cfg.absoluteMs / 1000)));
    res.json({ authenticated: true, user: this.cfg.user });
  };

  logout = (req: Request, res: Response): void => {
    if (!this.fromDashboard(req, res)) return;
    const id = parseCookies(req.headers.cookie)[SESSION_COOKIE];
    if (id) this.sessions.delete(id);
    res.setHeader('Set-Cookie', this.cookie('', 0));
    res.json({ authenticated: false });
  };

  me = (req: Request, res: Response): void => {
    const s = this.current(req);
    res.json({ configured: this.configured, authenticated: Boolean(s), user: s?.user ?? null });
  };

  /** Middleware: fail closed unless configured and the request carries a live session. */
  require = (req: Request, res: Response, next: NextFunction): void => {
    if (!this.configured) {
      res.status(503).json({ error: 'dashboard authentication not configured' });
      return;
    }
    if (!this.current(req)) {
      res.status(401).json({ error: 'authentication required' });
      return;
    }
    next();
  };
}
