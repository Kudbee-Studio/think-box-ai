# ADR 004: KILO governance-evidence gate (PR #145)

**Date:** 2026-09-23
**Status:** Accepted

## Context

The #141–#150 Live-proof readiness arc needs a hermetic contract for admission tokens and
live-burst evidence before any bounded Live proof (#150). PR #144 was a CI/post-merge fix
only; governance-evidence moves to PR #145.

## Options Considered

1. Duplicate env-matrix / substrate rules inside a new module
2. Layer governance evidence on existing evaluators and reuse AdmissionGate

## Decision

We chose option 2: `thinkbox/kilo_governance_evidence.py` calls `evaluate_env_matrix` and
`evaluate_substrate_checklist`, binds `AdmissionGate` decisions into `LiveBurstEvidence` with
token fingerprints only, and exposes operator verify layered on spine checks.

## Consequences

- `scripts/verify_kilo_governance_evidence.py` and spine summary include `governance_evidence`
- Hermetic tests in `test_kilo_live_proof_readiness_pr145.py` enforce deny paths and redaction
- Four-state remains capped at TEST VERIFIED until Live proof artifacts exist
