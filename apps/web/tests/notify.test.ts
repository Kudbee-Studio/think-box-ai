import assert from 'node:assert/strict';
import { test } from 'node:test';
import { AuditLog } from '../audit-log.ts';
import { createNotifier, describeEvent, notifyConfig } from '../notify.ts';
import { openAuditLog } from '../audit-notify.ts';

const URL_ = 'https://hooks.example.test/services/T000/B000/SECRETTOKEN123';
const ev = (kind: string, summary: string, over: Record<string, unknown> = {}) => ({ seq: 1, ts: 0, kind, actor: 'dashboard', run_id: 'abcdef123456', summary, detail: {}, prev_hash: '', hash: '', ...over }) as any;

test('config: no webhook means off; http(s) only; default topics are approvals, budget and failures', () => {
  assert.equal(notifyConfig({}).url, null);
  assert.equal(notifyConfig({ KUDBEE_NOTIFY_WEBHOOK: 'ftp://x/y' }).url, null);
  assert.equal(notifyConfig({ KUDBEE_NOTIFY_WEBHOOK: 'not a url' }).url, null);
  const c = notifyConfig({ KUDBEE_NOTIFY_WEBHOOK: URL_ });
  assert.equal(c.url, URL_); assert.deepEqual([...c.on].sort(), ['approvals', 'budget', 'failures']);
  assert.deepEqual([...notifyConfig({ KUDBEE_NOTIFY_WEBHOOK: URL_, KUDBEE_NOTIFY_ON: 'finished, nonsense' }).on], ['finished']);
});

test('describeEvent: approvals, budget warnings and stops, failed runs; finished runs only when asked; resolved approvals never', () => {
  const on = new Set(['approvals', 'budget', 'failures']);
  assert.match(describeEvent(ev('approval_requested', 'write_file: overwrite notes.txt'), on)!, /Approval needed.*overwrite notes\.txt/);
  assert.match(describeEvent(ev('budget_warning', 'Daily spend at 80%'), on)!, /Budget.*80%/);
  assert.match(describeEvent(ev('budget_stop', 'Daily limit reached'), on)!, /Budget.*limit reached/);
  assert.match(describeEvent(ev('run_finished', 'failed: fix the bug'), on)!, /Run failed.*fix the bug/);
  assert.equal(describeEvent(ev('run_finished', 'completed: fix the bug'), on), null);
  assert.match(describeEvent(ev('run_finished', 'completed: fix the bug'), new Set(['finished']))!, /Run finished.*fix the bug/);
  assert.equal(describeEvent(ev('approval_resolved', 'approved'), on), null);
  assert.equal(describeEvent(ev('draft_pr', 'x'), on), null);
});

test('a matching event is posted as JSON that Slack and Discord both read, with a timeout, and never to a private address', async () => {
  const calls: Array<{ url: string; init: RequestInit; allowPrivate: boolean }> = [];
  const n = createNotifier({ env: { KUDBEE_NOTIFY_WEBHOOK: URL_ }, send: async (url, init, allowPrivate) => { calls.push({ url, init, allowPrivate }); return new Response('ok'); } });
  await n.handle(ev('approval_requested', 'write_file: overwrite notes.txt'));
  assert.equal(calls.length, 1); assert.equal(calls[0].url, URL_); assert.equal(calls[0].allowPrivate, false);
  const body = JSON.parse(String(calls[0].init.body)); assert.equal(body.text, body.content); assert.match(body.text, /Approval needed/);
  assert.ok(calls[0].init.signal, 'has a timeout');
  assert.equal(JSON.stringify(calls[0].init.headers).includes('SECRETTOKEN'), false);
});

test('KUDBEE_NOTIFY_ALLOW_PRIVATE is the operator opting in to a webhook on their own network', async () => {
  let allow: boolean | null = null;
  const n = createNotifier({ env: { KUDBEE_NOTIFY_WEBHOOK: URL_, KUDBEE_NOTIFY_ALLOW_PRIVATE: '1' }, send: async (_u, _i, a) => { allow = a; return new Response('ok'); } });
  await n.handle(ev('budget_stop', 'limit')); assert.equal(allow, true);
});

test('nothing is sent when off, for unwanted events, or for repeats within 30 seconds; a flood is capped', async () => {
  let sent = 0; const send = async () => { sent++; return new Response('ok'); };
  let t = 0;
  const off = createNotifier({ env: {}, send, now: () => t }); await off.handle(ev('budget_stop', 'x')); assert.equal(sent, 0);
  const n = createNotifier({ env: { KUDBEE_NOTIFY_WEBHOOK: URL_ }, send, now: () => t });
  await n.handle(ev('draft_pr', 'x')); assert.equal(sent, 0);
  await n.handle(ev('budget_warning', 'at 80%')); await n.handle(ev('budget_warning', 'at 80%')); assert.equal(sent, 1);
  t = 31_000; await n.handle(ev('budget_warning', 'at 80%')); assert.equal(sent, 2);
  for (let i = 0; i < 50; i++) await n.handle(ev('approval_requested', `tool ${i}`));
  assert.ok(sent <= 2 + 20, `sent ${sent}`);
});

test('a failing webhook never throws, never leaks the URL, and is counted', async () => {
  const logs: string[] = [];
  const n = createNotifier({ env: { KUDBEE_NOTIFY_WEBHOOK: URL_ }, send: async () => { throw new Error(`connect failed to ${URL_}`); }, log: (m) => logs.push(m) });
  await n.handle(ev('budget_stop', 'limit'));
  assert.equal(n.stats().failed, 1);
  assert.ok(logs.length === 1 && !logs.join('').includes('SECRETTOKEN'), logs.join('|'));
  const bad = createNotifier({ env: { KUDBEE_NOTIFY_WEBHOOK: URL_ }, send: async () => new Response('no', { status: 500 }), log: (m) => logs.push(m) });
  await bad.handle(ev('budget_stop', 'limit2')); assert.equal(bad.stats().failed, 1);
});

test('wired to the audit log: recording an event calls the notifier, and a throwing listener never breaks the audit', async () => {
  const seen: string[] = [];
  const log = new AuditLog(':memory:'); log.onRecord = (e) => { seen.push(e.kind); };
  log.record('budget_warning', 'system', 'at 80%'); assert.deepEqual(seen, ['budget_warning']);
  log.onRecord = () => { throw new Error('boom'); };
  assert.ok(log.record('budget_stop', 'system', 'limit')); assert.equal(log.chainStatus().entries, 2);
  const sent: string[] = [];
  const wired = openAuditLog(':memory:', { KUDBEE_NOTIFY_WEBHOOK: URL_ }, async (_u, init) => { sent.push(String(init.body)); return new Response('ok'); });
  wired.record('approval_requested', 'dashboard', 'write_file: overwrite a.txt');
  await new Promise((r) => setTimeout(r, 20));
  assert.equal(sent.length, 1); assert.match(sent[0], /Approval needed/);
});

test('the test message: sent once, refused when there is no webhook, rate limited, and a rejected webhook is reported without the URL', async () => {
  const { sendTestNotification } = await import('../audit-notify.ts');
  let t = 1_000_000; const bodies: string[] = [];
  assert.deepEqual(await sendTestNotification({}, undefined, () => t), { ok: false, error: 'No webhook is set (KUDBEE_NOTIFY_WEBHOOK)' });
  t += 20_000;
  const ok = await sendTestNotification({ KUDBEE_NOTIFY_WEBHOOK: URL_ }, async (_u, init) => { bodies.push(String(init.body)); return new Response('ok'); }, () => t);
  assert.equal(ok.ok, true); assert.match(bodies[0], /test notification/);
  assert.equal((await sendTestNotification({ KUDBEE_NOTIFY_WEBHOOK: URL_ }, async () => new Response('ok'), () => t + 1000)).ok, false, 'rate limited');
  t += 40_000;
  const bad = await sendTestNotification({ KUDBEE_NOTIFY_WEBHOOK: URL_ }, async () => new Response('no', { status: 404 }), () => t);
  assert.equal(bad.ok, false); assert.ok(!JSON.stringify(bad).includes('SECRETTOKEN'));
});
