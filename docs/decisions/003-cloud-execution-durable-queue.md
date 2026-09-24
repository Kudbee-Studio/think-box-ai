# ADR 003: Cloud execution durable queue (Phase 2)

**Date:** 2026-09-24
**Status:** Accepted

## Context

PR #197 introduced a provider-neutral in-memory execution substrate. Phase 2 requires durable queued jobs, worker claims, restart recovery, and retries without introducing live cloud providers.

## Decision

- Add `DurableExecutionJobStore` (SQLite) for job + queue fields; keep `ExecutionJobStore` in-memory for backward-compatible #197 paths.
- Add `ExecutionJobQueue` with enqueue/claim/complete/fail/cancel/retry and lease-based stale claim detection.
- Add `DurableCloudExecutionEngine` wrapping `CloudExecutionEngine` admission, workspace registry, and hermetic provider execution.
- On restart: QUEUED jobs preserved; stale claims re-queued; ADMITTED/STARTING/RUNNING rows become `BLOCKED` with recovery metadata (never silent success).
- Optional `AdmissionTokenHook` defaults disabled.

## Consequences

- Workspace binding registry and admission gate remain process-local (documented).
- Live cloud adapters and distributed scheduling are out of scope for #198.
