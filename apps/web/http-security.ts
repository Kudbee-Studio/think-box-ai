// Browser-facing HTTP hardening for the local dashboard (no login; see ROADMAP Phase 3 item 7, deferred).
// Pure functions so they can be unit-tested without a server.

export interface HeaderRes { setHeader(name: string, value: string): unknown; status(code: number): { json(body: unknown): unknown } }
export interface HeaderReq { method?: string; headers: Record<string, string | string[] | undefined> }

/**
 * `script-src 'self'` blocks injected <script> elements and remote scripts, and `script-src-attr 'none'` blocks inline event-handler
 * attributes (an injected <img onerror=...> does not run). The dashboard has no inline handlers; tests/http-security.test.ts fails if one
 * is added. Inline styles are still allowed (generated markup uses style attributes). No eval, no plugins, no <base>, no framing, forms
 * only to ourselves.
 */
export function contentSecurityPolicy(port: number): string {
  // The Host/Origin gate also accepts `[::1]` (server.ts LOOPBACK_HOSTNAMES), but a bracketed IPv6 literal is not valid in a CSP source list:
  // Chromium reports a console error and ignores it. A dashboard opened at http://[::1]:PORT/ reaches its own WebSocket through 'self'.
  const ws = `ws://127.0.0.1:${port} ws://localhost:${port}`;
  return [
    "default-src 'self'",
    "script-src 'self'",
    "script-src-attr 'none'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src 'self' ${ws}`,
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join('; ');
}

export function securityHeaders(port: number) {
  const csp = contentSecurityPolicy(port);
  return (_req: HeaderReq, res: HeaderRes, next: () => void): void => {
    res.setHeader('Content-Security-Policy', csp);
    res.setHeader('X-Frame-Options', 'DENY');
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Referrer-Policy', 'no-referrer');
    res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=(), usb=()');
    res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
    res.setHeader('Cross-Origin-Resource-Policy', 'same-origin');
    next();
  };
}

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

/**
 * A web page in the operator's browser can POST to 127.0.0.1 (a "simple" cross-site request needs no CORS preflight), and the
 * dashboard has no login. Browsers always send Origin on such writes, so a write whose Origin is not our own is refused; so is
 * any write the browser itself labels cross-site. Requests with no Origin (curl, the CLI, tests) are not browser-driven and pass.
 */
export function rejectCrossOriginWrites(isAllowedOrigin: (origin: string | undefined) => boolean) {
  return (req: HeaderReq, res: HeaderRes, next: () => void): void => {
    if (SAFE_METHODS.has((req.method ?? 'GET').toUpperCase())) return next();
    const origin = first(req.headers.origin);
    const site = first(req.headers['sec-fetch-site'])?.toLowerCase();
    if ((origin !== undefined && !isAllowedOrigin(origin)) || site === 'cross-site') {
      res.status(403).json({ error: 'cross_origin_write_refused', detail: 'Writes must come from the dashboard origin' });
      return;
    }
    next();
  };
}

/**
 * Fixed-window request cap. The dashboard is single-user and every request arrives from 127.0.0.1, so the key is not the address:
 * requests the browser itself labels cross-site (a web page firing at 127.0.0.1; sending needs no CORS) get their own, much smaller
 * budget, so such a page cannot use up the dashboard's allowance and lock the operator out.
 */
export function rateLimit(options: { windowMs: number; max: number; crossSiteMax?: number; now?: () => number }) {
  const now = options.now ?? Date.now;
  const crossSiteMax = options.crossSiteMax ?? Math.max(1, Math.floor(options.max / 10));
  const buckets = { local: { start: now(), count: 0 }, cross: { start: now(), count: 0 } };
  return (req: HeaderReq, res: HeaderRes, next: () => void): void => {
    const cross = first(req.headers['sec-fetch-site'])?.toLowerCase() === 'cross-site';
    const bucket = cross ? buckets.cross : buckets.local;
    const max = cross ? crossSiteMax : options.max;
    const t = now();
    if (t - bucket.start >= options.windowMs) { bucket.start = t; bucket.count = 0; }
    bucket.count += 1;
    if (bucket.count > max) {
      res.setHeader('Retry-After', String(Math.max(1, Math.ceil((bucket.start + options.windowMs - t) / 1000))));
      res.status(429).json({ error: 'rate_limited', detail: 'Too many requests; slow down' });
      return;
    }
    next();
  };
}
