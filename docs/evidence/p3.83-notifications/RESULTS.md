# P3.83 notifications (product idea 5)

Selected audit events go to a webhook (`KUDBEE_NOTIFY_WEBHOOK`; body `{"text","content"}` so Slack, Discord and Mattermost-style webhooks accept it). Topics (`KUDBEE_NOTIFY_ON`, default `approvals,budget,failures`; also `finished`): approval requested, budget warning/stop, run failed/finished. Get started lists the step and offers "Send a test message" (`POST /api/notify/test`, at most once every 10 s).

| Claim | State | Basis |
|---|---|---|
| Off without a valid http(s) webhook; topic selection; only the chosen events are described; resolved approvals never | PROVEN | tests/notify.test.ts |
| The POST body, timeout, no secret in headers, no private-address targets unless the operator sets `KUDBEE_NOTIFY_ALLOW_PRIVATE=1` | PROVEN | same file (injected sender) |
| Repeats within 30 s dropped; at most 20 per minute | PROVEN | same file |
| A failing webhook never throws, is counted, and the webhook URL (which holds its secret) never appears in the log or the test-endpoint answer | PROVEN | same file |
| A throwing listener never breaks the audit trail; recording an event reaches the notifier | PROVEN | same file (real AuditLog) |
| Checklist step and test button; the URL is never returned | PROVEN | tests/setup-status, setup-route, setup-panel |
| Delivery to a real Slack/Discord/Teams webhook | UNPROVEN | no real webhook was used; only an injected sender |
| Email, SMS, desktop pop-ups, browser notifications | NOT BUILT | |
| Per-person routing | NOT CLAIMED | one webhook for the whole install |
| Delivery is best effort | By design | a send that fails is counted and logged, not retried |
