// Opens the audit log with notifications attached: every recorded event is offered to the notifier, which sends only what the person asked to hear about (notify.ts).
import { AuditLog } from './audit-log.ts';
import { createNotifier, type SendFn } from './notify.ts';

export { AuditLog, summarizeArgs } from './audit-log.ts';

export function openAuditLog(file: string, env: Record<string, string | undefined> = process.env, send?: SendFn): AuditLog {
  const log = new AuditLog(file);
  const notifier = createNotifier({ env, send });
  if (notifier.enabled) log.onRecord = (event) => { void notifier.handle(event); };
  return log;
}

let lastTest = 0;
/** Sends one test message to the configured webhook, so a person can check it works. At most once every 10 seconds. */
export async function sendTestNotification(env: Record<string, string | undefined> = process.env, send?: SendFn, now: () => number = Date.now): Promise<{ ok: boolean; error?: string }> {
  if (now() - lastTest < 10_000) return { ok: false, error: 'Wait a few seconds between tests' };
  lastTest = now();
  const n = createNotifier({ env, send, log: () => {}, now });
  if (!n.enabled) return { ok: false, error: 'No webhook is set (KUDBEE_NOTIFY_WEBHOOK)' };
  await n.handle({ kind: 'budget_warning', summary: 'This is a test notification from kudbEE Agent OS.' });
  return n.stats().sent === 1 ? { ok: true } : { ok: false, error: 'The webhook did not accept the message (check the URL; a local or private address needs KUDBEE_NOTIFY_ALLOW_PRIVATE=1)' };
}
