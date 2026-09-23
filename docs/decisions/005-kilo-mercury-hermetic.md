# ADR 005: KILO mercury-hermetic gate (PR #146)

**Date:** 2026-09-23
**Status:** Accepted

## Context

The #141–#150 Live-proof readiness arc needs bounded Mercury mock completions and
live-gate stub alignment before any bounded Live proof (#150). PR #145 closed
`governance-evidence`; mercury-hermetic is PR #146.

## Options Considered

1. Call live Mercury in hermetic tests with recorded VCR fixtures
2. Bounded in-process mock client + `cli_live_gate` authorization-only reporting

## Decision

We chose option 2: `thinkbox/kilo_mercury_hermetic.py` layers on governance-evidence,
exposes `BoundedMercuryMockClient` fixtures, aligns live-gate reports with
`THINKBOX_SWARM_LIVE_ACK` + provider credential presence, and keeps
`live_api_called=False` in all hermetic modes.

## Consequences

- `scripts/verify_kilo_mercury_hermetic.py` and spine summary include `mercury_hermetic`
- Hermetic tests in `test_kilo_live_proof_readiness_pr146.py` enforce mock + redaction
- Four-state remains capped at TEST VERIFIED until Live proof artifacts exist
