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
- `execution_substrate` + `exec_command` — **paired** governed shell path (see below)

### Governed shell execution (`execution_substrate` + `exec_command`)

Use these fields when the Think Job should run one **bounded shell command** through the
execution adapter contract (receipt, hash-verified artifact, checkpoint) instead of the
default model `execute_goal` path.

| Field | Type | Required with shell | Purpose |
|--------|------|-------------------|---------|
| `execution_substrate` | string | Yes (with `exec_command`) | Explicit substrate id — **never inferred** from `detect_substrate()` |
| `exec_command` | string | Yes (with `execution_substrate`) | Single `/bin/sh -c` command (bounded timeout; no interactive shell) |

**Pairing rule:** If exactly one of the two fields is non-empty, the API returns **422**
`exec_command_and_substrate_required_together` (fail-closed).

**Supported substrates:**

| `execution_substrate` | Adapter | Notes |
|----------------------|---------|--------|
| `local` | `LocalExecutionAdapter` | Runs in the API process worktree (`provider=local`). Hermetic proof only — **not LIVE VERIFIED**. |
| `upstash-box` | `UpstashBoxExecutionAdapter` | Requires `UPSTASH_PUBLIC_BOX_URL` and `UPSTASH_PUBLIC_BOX_TOKEN`. **No silent fallback to `local`.** Misconfiguration fails the job with `remote_not_configured`. |

**Flow (HTTP):** `POST /api/v1/run` → governance admission → background
`execute_governed_shell_background` → adapter → `ExecutionReceipt` → HTTP run receipt +
optional proof artifact under `THINKBOX_HTTP_RUN_ARTIFACTS` → Think Job status `result`
includes `execution_substrate`, `adapter_provider`, and redacted `execution_proof`.

**Job polling:** Same as model runs — `GET /api/v1/run/job/{engine_id}/status` until
`poll.terminal` is true. Shell successes set `governed_shell: true` in `result`; failures
include structured `error` codes (`unknown_substrate`, `remote_not_configured`, etc.).

**Example (local, hermetic):**

```json
{
  "goal": "governed local shell proof",
  "agent_id": "<registered-agent>",
  "governance_token": "<token>",
  "execution_substrate": "local",
  "exec_command": "echo THINKBOX_GOVERNED_LOCAL_PROOF"
}
```

Do **not** claim LIVE VERIFIED for `local` or for `upstash-box` unless founder-run
external evidence exists outside CI.

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
- `tests/e2e/test_f135_governed_shell_local_http.py` — full HTTP shell path (`local` substrate)
- `tests/unit/test_run_governed.py`
- `tests/unit/test_run_receipts.py`
- `tests/e2e/test_f134_think_job_status_poll.py`
- `tests/unit/test_run_job_status.py`
- `tests/unit/test_governed_job_execution.py`
- `tests/unit/test_local_execution_adapter.py`
