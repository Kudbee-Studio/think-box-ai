# ADR 016: KILO API / ops harden after dashboard bind

**Date:** 2026-09-23
**Status:** Accepted

## Context

PR #154–#156 shipped control-plane HTTP, receipt-chain ETag deepen, and dashboard END_LINK bind.
Operators need fail-closed error envelopes, idempotency, abuse guards, and hermetic regression gates
without claiming live Mercury or production readiness.

## Decision

Add PR #157 gate `api-ops-harden` with `thinkbox/control_plane_ops_harden.py`, spine verify script,
and backend wiring for structured errors, rate limits, and idempotency replay.

## Consequences

- Spine and CI run `verify_kilo_api_ops_harden.py`.
- Audit pass ships `live_verified: false`.
- No new product features; reliability depth only.
