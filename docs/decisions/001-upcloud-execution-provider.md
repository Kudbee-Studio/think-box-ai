# ADR 001: UpCloud ExecutionProvider

**Date:** 2026-09-16
**Status:** Proposed

## Context

Think Box requires the ability to provision and manage infrastructure
across multiple cloud providers (UpCloud, AWS, GCP, etc.). Currently,
the codebase only has `ModelProvider` (for AI inference). There is no
provider abstraction for infrastructure operations.

Additionally:
- UpCloud credentials are configured but authentication fails (HTTP 401)
- `upctl` CLI is not installed in the environment
- The system needs honest capability reporting (VERIFIED/DENIED/NOT_TESTED)
- Infrastructure actions require auditable evidence records
- Destructive/billable operations need explicit approval gates

## Decision

Create an `ExecutionProvider` abstraction in `core/providers/execution.py`
and an `UpCloudExecutionProvider` implementation in `core/providers/upcloud.py`.

### Key Design Decisions

1. **Provider-agnostic core**: The `ExecutionProvider` base class and
   `ProviderExecutionRegistry` are in `core/providers/`. No provider-specific
   code exists in Think Box core. Adding a new provider = new file + register.

2. **Honest capability reporting**: Every capability check returns one of:
   - `VERIFIED` — the API call succeeded
   - `DENIED` — auth/permission failure
   - `NOT_TESTED` — capability was not exercised (auth blocked test)
   - `REQUIRES_ADMIN_APPROVAL` — HTTP 403, needs manual escalation

3. **No secrets in code/tests/docs**: API keys come from `UPCLOUD_API_KEY`
   env var. No token values appear in source, tests, or documentation.
   Evidence records never contain credential material.

4. **Dry-run plan mode**: `plan()` generates an execution plan without
   performing actions. Destructive/billable operations require explicit
   approval via `approve=True` on `execute()`.

5. **Evidence records**: Every action produces an `EvidenceRecord` with
   job_id, provider, action, auth_state, result, resource_id, timestamp,
   and verification. No secrets recorded.

6. **REST API over CLI**: Uses UpCloud REST API directly via `urllib`
   (stdlib) instead of `upctl` (not installed, not in requirements).
   This keeps the provider dependency-free and controllable.

## Alternatives Considered

1. **upctl CLI wrapper**: Rejected — CLI not installed, adds dependency,
   harder to test, less control over error classification.

2. **Provider-specific SDK**: Rejected — `upcloud-python-api` not available
   without network install, violates Phase 0 stdlib-only principle.

3. **Inline UpCloud code in Think Box core**: Rejected — violates
   provider independence (AGENTS.md §1.2).

4. **Terraform/Infra-as-Code**: Rejected — overkill for Phase 1, adds
   external dependencies, harder to audit per-action.

## Consequences

- **Positive**: Think Box can safely evaluate UpCloud capabilities
  without assuming permissions or exposing credentials.
- **Positive**: Provider-agnostic design means adding AWS/GCP later
  follows the same pattern.
- **Negative**: REST API calls are more verbose than upctl CLI.
- **Negative**: Live testing requires actual credentials (mitigated
  by skipped tests when credentials absent).

## Implementation

- `core/providers/execution.py`: Base classes, dataclasses, registry
- `core/providers/upcloud.py`: UpCloud provider implementation
- `tests/unit/test_upcloud_provider.py`: Mocked tests (deterministic)
- `tests/integration/test_upcloud_live.py`: Live smoke tests (skipped
  when `UPCLOUD_API_KEY` absent)
