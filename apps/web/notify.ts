// Notifications: tell a person when something needs them, without them watching the dashboard. Sends selected audit events to a webhook (Slack, Discord, Mattermost and
// anything that takes {"text": ...}). The webhook URL carries its own secret, so it is never logged, never put in an error message and never returned by an API.
import { fetchChecked } from './net-guard.ts';
import type { AuditEvent } from './audit-log.ts';

export type Topic = 'approvals' | 'budget' | 'failures' | 'finished';
const TOPICS: readonly Topic[] = ['approvals', 'budget', 'failures', 'finished'];
const DEFAULT_TOPICS: Topic[] = ['approvals', 'budget', 'failures'];
export interface NotifyConfig { url: string | null; on: Set<Topic>; allowPrivate: boolean }
export type SendFn = (url: string, init: RequestInit, allowPrivate: boolean) => Promise<Response>;

export function notifyConfig(env: Record<string, string | undefined>): NotifyConfig {
  let url: string | null = null;
  const raw = env.KUDBEE_NOTIFY_WEBHOOK?.trim();
  if (raw) { try { const u = new URL(raw); if (u.protocol === 'https:' || u.protocol === 'http:') url = raw; } catch { /* not a URL: notifications stay off */ } }
  const asked = (env.KUDBEE_NOTIFY_ON ?? '').split(',').map((s) => s.trim().toLowerCase()).filter((s): s is Topic => (TOPICS as readonly string[]).includes(s));
  return { url, on: new Set(asked.length ? asked : DEFAULT_TOPICS), allowPrivate: env.KUDBEE_NOTIFY_ALLOW_PRIVATE === '1' };
}

/** The message for an audit event, or null when this person did not ask to hear about it. The summary was already scrubbed of secrets when it was recorded. */
export function describeEvent(e: Pick<AuditEvent, 'kind' | 'summary'>, on: Set<Topic> | Set<string>): string | null {
  const has = (t: Topic): boolean => (on as Set<string>).has(t);
  const short = e.summary.slice(0, 200);
  if (e.kind === 'approval_requested' && has('approvals')) return `Approval needed: ${short}`;
  if ((e.kind === 'budget_warning' || e.kind === 'budget_stop') && has('budget')) return `Budget: ${short}`;
  if (e.kind === 'run_finished') {
    if (/^failed:/.test(e.summary) && has('failures')) return `Run failed: ${short.replace(/^failed:\s*/, '')}`;
    if (/^completed:/.test(e.summary) && has('finished')) return `Run finished: ${short.replace(/^completed:\s*/, '')}`;
  }
  return null;
}

const REPEAT_MS = 30_000; const WINDOW_MS = 60_000; const MAX_PER_WINDOW = 20; const TIMEOUT_MS = 5000;

export function createNotifier(o: { env: Record<string, string | undefined>; send?: SendFn; now?: () => number; log?: (m: string) => void }) {
  const cfg = notifyConfig(o.env);
  const send: SendFn = o.send ?? ((url, init, allow) => fetchChecked(url, init, allow));
  const now = o.now ?? Date.now;
  const log = o.log ?? ((m: string) => console.warn(m));
  const recent = new Map<string, number>(); let windowStart = now(); let inWindow = 0;
  const counts = { sent: 0, failed: 0, dropped: 0 };
  return {
    stats: () => ({ ...counts }),
    enabled: cfg.url !== null,
    async handle(e: Pick<AuditEvent, 'kind' | 'summary'>): Promise<void> {
      if (!cfg.url) return;
      const text = describeEvent(e, cfg.on);
      if (!text) return;
      const t = now();
      if (t - windowStart >= WINDOW_MS) { windowStart = t; inWindow = 0; }
      const last = recent.get(text);
      if ((last !== undefined && t - last < REPEAT_MS) || inWindow >= MAX_PER_WINDOW) { counts.dropped++; return; }
      recent.set(text, t); inWindow++;
      try {
        const res = await send(cfg.url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ text, content: text }), signal: AbortSignal.timeout(TIMEOUT_MS) }, cfg.allowPrivate);
        if (!res.ok) throw new Error(`webhook answered ${res.status}`);
        counts.sent++;
      } catch (err) {
        counts.failed++;
        log(`notification not delivered: ${String(err instanceof Error ? err.message : err).replaceAll(cfg.url, '[webhook]')}`);
      }
    },
  };
}
