# Governed `POST /api/v1/run` (hermetic)

Branch contract for PR #132–#134. **Not LIVE VERIFIED. Not PRODUCTION READY.**

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

## Immediate response (PR #133)

`RunResponse.summary` includes `receipt_id`, `experiment_id`, and `session_id` bound at admission time.

## Receipt read surfaces

- `GET /api/v1/run/receipt/{receipt_id}` — redacted SQLite receipt
- `GET /api/v1/run/receipt/by-engine/{engine_id}` — lookup via engine id

## Think Job status polling (PR #134)

Poll after `POST /run` using `engine_id` (same as `job_id`):

- `GET /api/v1/run/job/{engine_id}/status` — phase, receipt linkage, `poll.terminal`, `receipt_card`
- `GET /api/v1/run/job/by-receipt/{receipt_id}/status` — resolve via receipt id
- `GET /api/v1/run/jobs/status?limit=N` — recent jobs (redacted, max 200)
- `GET /api/v1/dashboard/think-job/{engine_id}/receipt-card` — dashboard card payload only

Unknown ids return **404** `think_job_not_found` (fail-closed). Poll clients should stop when `poll.terminal` is true.

## Fail-closed

HTTP **403** when token is missing, invalid, expired, revoked, agent mismatch, or capability not granted.

Background completion **fails the Think Job** if receipt persistence raises (`run_receipt_persist_failed`) — never silent success.

## Inspection

`GET /api/v1/run/governance/status` — redacted ledger/identity counts + receipt persistence counters + `think_job_status` snapshot (no token values).

## Persistence

- SQLite: `THINKBOX_HTTP_RUN_DB` (default `data/thinkboxmd/db/http_run_experiments.db`)
- Artifacts: `THINKBOX_HTTP_RUN_ARTIFACTS` (default `data/thinkboxmd/artifacts/http_run`)
- Verified runs reuse `GovernedEngine._persist_verified_goal` with hermetic `persist_profile` (`TEST_VERIFIED`, `hermetic-mock`)

## Tests

- `tests/e2e/test_f132_governed_run_admission.py`
- `tests/e2e/test_f133_governed_run_receipts.py`
- `tests/unit/test_run_governed.py`
- `tests/unit/test_run_receipts.py`
- `tests/e2e/test_f134_think_job_status_poll.py`
- `tests/unit/test_run_job_status.py`
