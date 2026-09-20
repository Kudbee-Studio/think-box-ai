# GitHub Webhook — Signed PR Lifecycle Receiver

This guide covers the governed GitHub webhook that drives `PRLifecycleEventCoordinator`
after HMAC verification. **Auto-merge is never performed.**

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `WEBHOOK_SECRET` | Yes (production) | GitHub webhook secret; used for `X-Hub-Signature-256` verification. Alias: `GITHUB_WEBHOOK_SECRET`. |
| `THINKBOX_GITHUB_WEBHOOK_GOVERNANCE_TOKEN` | Yes (mutating events) | Governance token with capability `github:webhook:lifecycle_mutate` for agent `THINKBOX_GITHUB_WEBHOOK_AGENT_ID` (default `github-webhook-receiver`). |
| `THINKBOX_GOVERNANCE_SIGNING_KEY` | Yes | Signing key used by `GovernanceTokenService` to verify the governance token above. |
| `THINKBOX_GITHUB_WEBHOOK_AGENT_ID` | No | Agent id registered for webhook admission (default `github-webhook-receiver`). |
| `THINKBOX_GITHUB_WEBHOOK_TEST_MODE` | No | When `false`, lifecycle runs with `test_mode=False` on the coordinator (default `true`). |
| `THINKBOX_ORG_MEMORY_DB` | No | SQLite path for org-memory receipts (default `data/thinkboxmd/db/org_memory_receipts.db`). |

## GitHub configuration

1. In the repository **Settings → Webhooks**, add a webhook:
   - **Payload URL:** `https://<your-host>/api/v1/github/webhook`
   - **Content type:** `application/json`
   - **Secret:** same value as `WEBHOOK_SECRET`
   - **Events:** `Pull requests`, `Workflow runs`, `Check suites`, and optionally `Status`
2. The route is exempt from `X-API-Key` middleware; authentication is **only** via HMAC + governance token for mutating lifecycle effects.

## Evidence labels

| Stage | `evidence_label` |
|-------|------------------|
| Signature valid + lifecycle mutation admitted | `verified` |
| Signature invalid / missing | `rejected` (HTTP 401; no coordinator mutation) |
| Signature valid but admission denied | `simulated` on `BLOCKED` org-memory receipt (HTTP 403) |

## Local hermetic tests

```bash
python3 -m unittest tests.unit.test_github_webhook -v
python3 -m unittest tests.unit.test_org_memory_lifecycle tests.unit.test_pr_lifecycle -v
```

Optional live HMAC check (off by default):

```bash
export WEBHOOK_SECRET='your-github-secret'
export THINKBOX_GITHUB_WEBHOOK_LIVE_TEST=1
python3 -m unittest tests.unit.test_github_webhook.TestGitHubWebhookLiveOptional -v
```

## Related PR

- Builds on merged **PR #106** (org-memory + CI/PR hooks).
- Tracked as **PR #107** — branch `feat/lifecycle-github-webhook-admission`.
