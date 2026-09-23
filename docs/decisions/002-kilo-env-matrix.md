# ADR 002: KILO env-matrix hermetic contract (PR #142)

**Date:** 2026-09-23  
**Status:** Accepted

## Context

The #141–#150 Live-proof readiness arc needs a fail-closed description of which
environment variables, modes, and mock endpoints are allowed before any Live proof
execution (PR #150).

## Decision

Add `thinkbox/kilo_env_matrix.py` with explicit modes (`hermetic_unit`, `hermetic_ci`,
`live_proof_prep`), contract metadata, and operator checks that forbid founder live ack
and KILO claim flags without requiring provider API keys to be absent in founder CI.

## Consequences

- `scripts/verify_kilo_env_matrix.py` and `verify_kilo_spine.py` enforce operator gates.
- Unit tests use `minimal_hermetic_environ()` for strict matrix assertions.
- LIVE VERIFIED remains forbidden until PR #150 proof artifacts exist.
