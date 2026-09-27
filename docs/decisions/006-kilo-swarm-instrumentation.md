# ADR 006: KILO swarm-instrumentation gate (PR #147)

**Date:** 2026-09-23
**Status:** Accepted

## Context

Live-proof readiness arc PR #147 must close gate `swarm-instrumentation` so operators can
require instrumentation checks without running Live Mercury or GPU workloads. The existing
`experiments/verify_instrumentation.py` script encodes ten hermetic instrument checks plus
an optional eleventh live swarm path (`--live`).

## Options Considered

1. Subprocess-only gate wrapping the experiments script
2. Shared check module in `thinkbox/` consumed by experiments and KILO gate
3. Duplicate check logic inside the gate module

## Decision

We chose option 2: `thinkbox/swarm_instrumentation_checks.py` holds the ten hermetic checks;
`thinkbox/kilo_swarm_instrumentation.py` layers on `mercury-hermetic` and adds an eleventh
catalog entry deferring live swarm execution (`live_swarm_invoked=false`,
`live_api_called=false`).

## Consequences

- `experiments/verify_instrumentation.py` imports shared checks (10/10 hermetic unchanged).
- Spine operator verify adds `scripts/verify_kilo_swarm_instrumentation.py` and extends
  `verify_kilo_spine.py`.
- Four-state remains capped at TEST VERIFIED until PR #150 Live proof.
