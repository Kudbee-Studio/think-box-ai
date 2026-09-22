# End-to-end tests (Phase 1)

**PR #127** implements comprehensive Phase 1 evidence in `test_governed_runtime_loop.py`:

## Coverage (5 categories)

| Test | Category | Verifies |
|------|----------|----------|
| `test_valid_token_admission_success` | VALID ADMISSION | Valid token → admission succeeds → goal executes → ledger records |
| `test_invalid_token_admission_denied` | INVALID TOKEN | Invalid token → admission denied → execution blocked → ledger records rejection |
| `test_permission_denied_for_unauthorized_capability` | PERMISSION DENIAL | Missing capability → admission denied → ledger records `capability_not_granted` |
| `test_authorized_tool_execution_success` | TOOL EXECUTION | Authorized tool → VerifiedRetrySession executes → result recorded → ledger inspectable |
| `test_full_phase1_five_tool_lifecycle` | FULL 5-TOOL LOOP | submit → admission → execute → proof → verify (complete lifecycle) |

## What is now proven (CODE_COMPLETE + TEST_VERIFIED)

- **AdmissionGate + ActionLedger state observability**: Every admission decision (allowed/denied) is recorded with reason, agent_id, capability, timestamp, and hash-chain integrity
- **VerifiedRetrySession governance**: 5-tool exact-JSON emission family (direct, fenced, prefixed, spaced, stringnum) executed through the governed runtime with full proof telemetry
- **Deterministic replay**: No network, no external credentials, no paid infrastructure
- **Full Think Job lifecycle automation** (F023 enabled): submit → admission → execute → proof → verify

## What remains hermetic/mock-provider evidence

- **Model provider boundary**: The `AsyncModelClient` / `complete_async` function is mocked with deterministic JSON responses. No live LLM calls.
- **Upstash Vector**: Not exercised (requires separate credentials)
- **UpCloud compute**: Not used (control-plane only per ADR 004)
- **Mercury-2 / Inception API**: Not called (requires `INCEPTION_API_KEY`)

## What requires LIVE infrastructure

- **LIVE_VERIFIED swarm scaling** (PR #121–#124): Requires `INCEPTION_API_KEY` + Mercury-2
- **Upstash Box PATH A** (PR #118): Requires `UPSTASH_PUBLIC_BOX_TOKEN` (service not provisioned)
- **Full distributed governance** (PR #108): Requires founder governance token

## Running the tests

```bash
# Phase 1 e2e only (deterministic, no network)
python3 -m unittest tests.e2e.test_governed_runtime_loop -v

# Full suite (includes all unit + integration + e2e)
python3 -m unittest discover tests/
```

## Test gate

```bash
python3 -m unittest discover tests/
```

Expected: **2243 OK, 7 skipped, 3 expected failures** (or higher as tests are added)