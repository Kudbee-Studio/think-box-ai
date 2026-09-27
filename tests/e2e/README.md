# End-to-end tests (Phase 1 — hermetic)

Phase 1 mock-provider coverage lives here. **No network**, no Upstash/Mercury credentials, no live substrate.

## Governed runtime loop (F009)

| File | Purpose |
|------|---------|
| `hermetic_scaffold.py` | Shared harness: `make_governed`, mock `complete_async` router, five-subtask Think Job specs |
| `test_governed_runtime_loop.py` | Admission, denial, tool-capability denial, verified tasks, five-tool DAG loop |

### Run only these tests

```bash
python3 -m unittest tests.e2e.test_governed_runtime_loop
```

### What is covered

- Valid governance token → `execute_goal` / `execute_verified_goal` → `ActionLedger.verify()`
- Invalid, revoked, and wrong-capability tokens → fail-closed + ledger denial entries
- Permission-style tool denial via `tool:filesystem:write` without grant
- Scripted mock-provider completions (`deterministic_emission_v2`) for verified tasks and DAGs
- Five-subtask Think Job shape: submit → admission → execute → per-task proof → goal-level ledger metadata

### F023 prep (PR #128)

| File | Purpose |
|------|---------|
| `test_f023_prep.py` | Hermetic `ModelProvider` protocol wiring, `ExperimentManager` SQLite round-trip, Think Job `POST /run` API surface (source contract) |

### F023 Think Job lifecycle (PR #130)

| File | Purpose |
|------|---------|
| `hermetic_scaffold.py` | `HermeticModelProvider`, `provider_complete_async`, persistence/dashboard helpers, proof verification |
| `test_f023_think_job_lifecycle.py` | Full hermetic lifecycle: admit → execute → proof on disk → ledger; dashboard `JOB_COMPLETED`; edge cases |

```bash
python3 -m unittest tests.e2e.test_f023_think_job_lifecycle
```

**FourState (branch only):** CODE COMPLETE / TEST VERIFIED — hermetic mock provider only; no LIVE Mercury, no PRODUCTION READY.

### F131 POST /run HTTP contracts (PR #131)

| File | Purpose |
|------|---------|
| `api_run_hermetic.py` | Starlette TestClient harness: auth middleware, mocked `ThinkBoxEngine`, synchronous background drain |
| `test_f131_post_run_think_job_contract.py` | 25 hermetic tests: schema, dashboard upsert/events, API-key fail-closed, OpenAPI, engine failure path |

```bash
python3 -m unittest tests.e2e.test_f131_post_run_think_job_contract
```

**FourState (branch only):** CODE COMPLETE / TEST VERIFIED — ASGI/TestClient + mock engine; no LIVE Mercury, no PRODUCTION READY.

### F132 governed admission (PR #132, merged)

| File | Purpose |
|------|---------|
| `test_f132_governed_run_admission.py` | GovernedEngine on HTTP background task; ledger; hermetic verified subtasks |

### F133 run receipts (PR #133, merged)

| File | Purpose |
|------|---------|
| `backend/api/v1/run_receipts.py` | SQLite receipts + proof artifacts for HTTP runs |
| `test_f133_governed_run_receipts.py` | Persist + GET receipt + fail-closed persist errors |

### F138 Think Job status UI (PR #138 draft)

| File | Purpose |
|------|---------|
| `public/control-plane/think_job_status.html` | Control-plane watch UI |
| `public/control-plane/think_job_status_client.js` | SSE subscribe + poll fallback |
| `thinkbox/think_job_status_ui.py` | Hermetic client helpers (unit-tested) |
| `test_f138_think_job_status_ui.py` | Poll hints → stream plan; SSE merge parity |

```bash
python3 -m unittest tests.e2e.test_f138_think_job_status_ui tests.unit.test_think_job_status_ui
```

### F134 Think Job status poll (PR #134 draft)

| File | Purpose |
|------|---------|
| `backend/api/v1/run_job_status.py` | Poll schema, receipt card, dashboard/SQLite resolution |
| `test_f134_think_job_status_poll.py` | POST → poll status → receipt linkage; 404 fail-closed |

```bash
python3 -m unittest tests.e2e.test_f134_think_job_status_poll
```

```bash
python3 -m unittest tests.e2e.test_f133_governed_run_receipts tests.unit.test_run_receipts
```

### F139 receipt-keyed watch + digest multiplex (PR #139)

| File | Purpose |
|------|---------|
| `test_f139_think_job_receipt_multiplex.py` | Receipt poll/stream plan, digest SSE hello merge, 404 fail-closed |

```bash
python3 -m unittest tests.e2e.test_f139_think_job_receipt_multiplex
```

### F140 receipt deep-link + shared etag (PR #140)

| File | Purpose |
|------|---------|
| `test_f140_receipt_deep_link_etag.py` | Deep-link href ↔ by-receipt poll, shared etag 304 merge, invalid receipt 404 |

```bash
python3 -m unittest tests.e2e.test_f140_receipt_deep_link_etag
```

### F162 control-plane receipt-chain / END_LINK (PR #162)

| File | Purpose |
|------|---------|
| `control_plane_hermetic.py` | FastAPI TestClient harness (no Mercury HTTP) |
| `test_f162_cp_validate_single_e2e.py` | Single validate + ops timing |
| `test_f162_cp_batch_validate_e2e.py` | Batch validate + Idempotency-Key |
| `test_f162_cp_chain_filters_e2e.py` | Chain list filters + 400 fail-closed |
| `test_f162_cp_integrity_fields_e2e.py` | `prev_receipt_id` / `link_integrity` |
| `test_f162_cp_ops_envelope_e2e.py` | Ops stack inside 200 envelopes |
| `test_f162_cp_fail_closed_e2e.py` | Batch body errors + auth 401 |

```bash
python3 -m unittest discover tests/e2e -p 'test_f162_*'
python3 scripts/verify_kilo_control_plane_e2e_deepen.py
```

## Full gate

```bash
python3 -m unittest discover tests/
```
