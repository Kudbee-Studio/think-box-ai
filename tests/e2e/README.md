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

### F133 run receipts (PR #133 draft)

| File | Purpose |
|------|---------|
| `backend/api/v1/run_receipts.py` | SQLite receipts + proof artifacts for HTTP runs |
| `test_f133_governed_run_receipts.py` | Persist + GET receipt + fail-closed persist errors |

```bash
python3 -m unittest tests.e2e.test_f133_governed_run_receipts tests.unit.test_run_receipts
```

## Full gate

```bash
python3 -m unittest discover tests/
```
