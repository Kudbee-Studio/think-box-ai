# Governed `POST /api/v1/run` (hermetic)

Branch-only contract for PR #132. **Not LIVE VERIFIED. Not PRODUCTION READY.**

## Required headers

| Header | Required | Purpose |
|--------|----------|---------|
| `X-API-Key` | Yes | API middleware (fail-closed) |
| `X-Governance-Token` | Yes (or body field) | Governance admission token |
| `X-Agent-Id` | Recommended | Must match token identity |
| `X-Capability` | Optional | Overrides default `goal:execute` |

## Body (`RunRequest`)

- `goal` (required)
- `governance_token` / `agent_id` / `capability`
- `verified` + `subtasks` for F023 DAG path (`model=hermetic-mock` in tests)

## Fail-closed

HTTP **403** when token is missing, invalid, expired, revoked, agent mismatch, or capability not granted.

## Inspection

`GET /api/v1/run/governance/status` — redacted ledger/identity counts (no token values).

## Tests

- `tests/e2e/test_f132_governed_run_admission.py`
- `tests/unit/test_run_governed.py`
