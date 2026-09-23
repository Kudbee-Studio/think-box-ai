# ADR 003: KILO substrate-checklist Box readiness (PR #143)

**Date:** 2026-09-23  
**Status:** Accepted

## Context

PR #142 closed `env-matrix` with generic substrate env contracts. Live-proof prep
needs a dedicated Box URL + token readiness checklist that fails closed on accidental
production credentials in hermetic unittest/CI paths without re-implementing the matrix.

## Decision

Add `thinkbox/kilo_substrate_checklist.py` that:

1. Requires `evaluate_env_matrix` / `hermetic_operator_check` to pass for the same mode.
2. Allows mock/loopback/placeholder Box shapes in `hermetic_unit` and `hermetic_ci`.
3. Enforces `https://*.box.upstash.com` URL + token shape rules in `live_proof_prep`.
4. Redacts token/URL values in JSON summaries via `redact_box_*` helpers.

## Consequences

- `scripts/verify_kilo_substrate_checklist.py` and `verify_kilo_spine.py` enforce the gate.
- Unit tests use `minimal_substrate_hermetic_environ()` built on `minimal_hermetic_environ()`.
- LIVE VERIFIED remains forbidden until PR #150 proof artifacts exist.
