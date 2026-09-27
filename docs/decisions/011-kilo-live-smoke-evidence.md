# ADR 011: Bounded live smoke evidence binder (PR #152)

**Date:** 2026-09-23
**Status:** Accepted

## Context

PR #150 shipped the live-proof-exec plan; PR #151 hardened CI and branch hygiene.
Founders still need a fail-closed evidence artifact + audit flip helper so a later
bounded live smoke (with `THINKBOX_SWARM_LIVE_ACK` and `UPSTASH_PUBLIC_BOX_URL`) can
honestly set `live_verified: true` only when recorded evidence exists on disk.

## Options Considered

1. Extend `live-proof-exec` execution plan JSON only
2. New `live-smoke-evidence` module layered on `post-season-harden`
3. Manual audit edits without validators

## Decision

We chose option 2: `thinkbox/kilo_live_smoke_evidence.py` with gate id
`live-smoke-evidence` and `pr152_gate_id` in `spine_contract_summary`. Hermetic
default path never calls live HTTP and never sets `live_verified: true` in-repo.

## Consequences

- `scripts/verify_kilo_live_smoke_evidence.py` runs in CI after post-season gate.
- `audit_flip_candidate` produces candidate passes only; founders write audit files.
- Four-state remains TEST VERIFIED on branch until founder-run smoke + artifact.
