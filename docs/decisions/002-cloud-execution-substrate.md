# ADR 002: Cloud execution substrate (Phase 1)

**Date:** 2026-09-24
**Status:** Accepted

## Context

Think Box needs a provider-neutral execution substrate for cloud agent jobs (intent → admission → workspace → worker → receipt) without coupling the runtime to Cursor, Upstash, UpCloud, or other vendors.

## Decision

Introduce `thinkbox/cloud_execution/` with:

- `CloudExecutionProvider` adapter protocol (distinct from `core.providers.execution.ExecutionProvider` infrastructure API)
- Persistent `ExecutionJob` model and explicit lifecycle states
- `WorkspaceRegistry` for exclusive workspace identity per job
- Fail-closed `ExecutionAdmissionGate`
- Structured `ExecutionAttemptReceipt` with `verification_class` capped at TEST_VERIFIED for hermetic providers
- Default `HermeticCloudExecutionProvider` for automated tests only

Repository worktree metadata integrates via `repository_bridge.py` without replacing `thinkbox/repository.py`.

## Consequences

- Phase 2+ may add distributed orchestration, live providers, and dashboard bindings.
- LIVE VERIFIED requires separate founder-run proof with real external infrastructure; hermetic provider must never set `live_api_called: true`.
