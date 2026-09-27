# ADR 004: Cloud execution worker orchestrator (Phase 3)

**Date:** 2026-09-24
**Status:** Accepted

## Context

PR #198 added a durable SQLite queue with claims, leases, and restart recovery. Phase 3 needs a governed, process-local worker loop that claims jobs, renews leases, executes via the existing provider, and settles terminal states without distributed infrastructure or live cloud providers.

## Decision

- Add `CloudExecutionWorker` with explicit lifecycle states (`STARTING` … `STOPPED`/`FAILED`) and fail-closed transitions.
- Drive execution through `DurableCloudExecutionEngine.run_claimed` with optional `worker_id` claim fencing before provider execution.
- Extend `ExecutionJobQueue` with `renew_claim`, `validate_claim_for_execution`, and `requeue_claim` for heartbeat renewal and safe shutdown.
- Persist worker inspection snapshots in SQLite table `cloud_execution_workers` (same DB file as jobs; process-local semantics).
- Reuse PR #198 `recover_after_restart` on engine construction; worker startup does not bypass recovery.
- Hermetic provider remains the only executable provider in tests and gates.

## Consequences

- Workers are not distributed; multiple workers on one SQLite file rely on DB-level claim atomicity (single host, cooperative testing only).
- Claim fencing is lease + token + worker_id validation — not cross-region distributed fencing.
- Live cloud execution and external schedulers remain out of scope until a future authorized provider PR.
