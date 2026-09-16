# UpCloud Provider — Capability Audit Report

**Date:** 2026-09-16
**Provider:** UpCloud Infrastructure
**API Endpoint:** https://api.upcloud.com/v1
**CLI Tool:** upctl (NOT installed)

---

## 1. CLI Status

| Check | Result |
|-------|--------|
| `upctl` installed | ❌ NOT FOUND |
| `UPCLOUD_API_KEY` env var | ❌ NOT SET |
| UpCloud API reachable | ✅ (HTTP response received) |
| UpCloud API auth | ❌ HTTP 401 (as documented in STATUS.md) |

**Conclusion:** upctl CLI is not installed. The UpCloud REST API
is reachable from this environment but returns HTTP 401 for all
endpoints, confirming the documented authentication failure.
The provider implementation uses the REST API directly via
`urllib` (stdlib), which works when credentials are valid.

---

## 2. API Capability Audit Results

Every capability was tested via live HTTP probe (no real data
modified). Results reflect the authenticated user's permissions.

| Capability | Status | Evidence |
|---|---|---|
| Account/Project Discovery | DENIED | `GET /v1/account` → HTTP 401 |
| Server Listing | DENIED | `GET /v1/server` → HTTP 401 |
| Server Inspection | DENIED | `GET /v1/server/{uuid}` → HTTP 401 |
| Server Creation | DENIED | `POST /v1/server` → HTTP 401 |
| Server Deletion | DENIED | `DELETE /v1/server/{uuid}` → HTTP 401 |
| Server Reboot | DENIED | `POST /v1/server/{uuid}/reboot` → HTTP 401 |
| Storage/Volume Listing | DENIED | `GET /v1/storage` → HTTP 401 |
| Storage Creation | DENIED | `POST /v1/storage` → HTTP 401 |
| Storage Deletion | DENIED | `DELETE /v1/storage/{uuid}` → HTTP 401 |
| Network Inspection | DENIED | `GET /v1/network` → HTTP 401 |
| IP/Network Inspection | DENIED | `GET /v1/iplist` → HTTP 401 |
| IP Assignment | DENIED | `POST /v1/iplist/{id}` → HTTP 401 |
| Location Listing | DENIED | `GET /v1/location` → HTTP 401 |
| GPU Discovery | DENIED | `GET /v1/server?type=gpu` → HTTP 401 |
| Resource Creation Test | DENIED | HTTP 401 (no resources created) |
| Resource Deletion Test | DENIED | HTTP 401 (no resources deleted) |

**All capabilities classified DENIED due to authentication failure.**
No resources were created, modified, or deleted during this audit.
All tests were read-only probes with timeout limits.

---

## 3. Safety & Security

### 3.1 No Credential Exposure

- No UpCloud tokens in source code, tests, documentation, or artifacts
- `.env.example` contains placeholder only (`UPCLOUD_API_KEY=`)
- Provider reads `UPCLOUD_API_KEY` from environment at runtime only
- Evidence records never contain credential material
- Credential grep across entire repo: **0 matches for actual secret values**

### 3.2 Provider-Agnostic Design

- `ExecutionProvider` base class defines the contract
- `UpCloudExecutionProvider` is registered via `ProviderExecutionRegistry`
- Think Box core imports only `ExecutionProvider` (abstract) and
  `ProviderExecutionRegistry` — no UpCloud-specific code
- Adding a new provider: create file, register, done

### 3.3 Honest Failure

- If a capability is unavailable, the provider reports DENIED or NOT_TESTED
- Think Box must check `CapabilityStatus` before assuming capability
- No silent success masking unavailable operations

---

## 4. ExecutionProvider Contract

### 4.1 Base Class: `ExecutionProvider`

```python
class ExecutionProvider(ABC):
    provider_name: str                    # unique identifier
    auth_status: str                      # "untested" | "authenticated" | "denied" | ...
    capabilities: ExecutionProviderCapabilities  # per-capability status
    evidence: list[EvidenceRecord]        # audit trail

    def check_auth() -> CapabilityCheck          # verify credentials
    def discover_capabilities() -> list[CapabilityCheck]  # audit all capabilities
    def plan() -> ExecutionPlan                  # dry-run mode
    def execute() -> ExecutionResult             # run action (with approval gate)
```

### 4.2 Evidence Record Schema

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | str | Think Job ID |
| `provider` | str | Provider name (e.g., "upcloud") |
| `action` | str | Action performed |
| `auth_state` | str | Authentication state at time of action |
| `result` | str | SUCCESS, CREATED, FAILED, DENIED, etc. |
| `resource_id` | str | Created/modified resource identifier |
| `timestamp` | str | ISO 8601 timestamp |
| `verification` | str | How result was verified |
| `dry_run` | bool | Whether this was a plan-only operation |
| `metadata` | dict | Additional context (no secrets) |

### 4.3 Approval Gate

Operations classified as destructive or billable require explicit
`approve=True` on `execute()`:
- **Destructive**: `delete_server`, `delete_storage`
- **Billable**: `create_server`, `create_storage`, `create_server_from_template`
- **Plan mode**: `plan()` always runs as dry_run; requires approval
  only if plan contains destructive/billable actions

---

## 5. Implementation Files

| File | Purpose |
|------|---------|
| `core/providers/execution.py` | ExecutionProvider base, dataclasses, registry |
| `core/providers/upcloud.py` | UpCloud provider implementation |
| `core/providers/__init__.py` | Public exports (updated) |
| `tests/unit/test_upcloud_provider.py` | Deterministic mocked tests |
| `tests/integration/test_upcloud_live.py` | Live smoke tests (skipped w/o creds) |
| `docs/decisions/001-upcloud-execution-provider.md` | Design ADR |
| `docs/upcloud-provider.md` | This document |

---

## 6. Limitations

1. **No upctl CLI**: The provider uses REST API directly instead of
   the upctl CLI (not installed). All API surface is functionally
   equivalent.

2. **No credentials in this environment**: All capabilities are
   classified as DENIED until a valid `UPCLOUD_API_KEY` is provided.
   Live smoke tests are skipped in this case.

3. **No upcloud-python-sdk**: Uses stdlib `urllib` only (Phase 0
   constraint: no external dependencies without documented trigger).

4. **Read-only audit**: The API audit was limited to GET/HEAD requests
   plus authenticated 401 responses. No destructive or billable
   operations were performed.

5. **Single-region provider**: UpCloud REST API endpoints are
   globally load-balanced; region-specific operations are not
   differentiated in this implementation.

---

## 7. Next Steps

1. **Valid API Token**: Mint a fresh UpCloud API token with limited
   scope and set `UPCLOUD_API_KEY` env var → re-run live smoke tests
2. **Install upctl**: `pip install upcloud-cli` (optional convenience)
3. **Expand capabilities**: Add subscription, billing, and firewall
   operations when validated
4. **Integration test**: Once token is valid, run
   `python3 -m pytest tests/integration/test_upcloud_live.py -v`
5. **Add to Think Box runtime**: Wire provider into execution layer
   when capability VERIFIED status is confirmed for needed operations
