# ADR 023: KILO governance-evidence Live-proof readiness gate (PR #164)

**Date:** 2026-09-23
**Status:** Accepted

## Context

After PR #163 merged control-plane E2E deepen, the governance-evidence path (#145) still
needed an explicit Live-proof **readiness** gate that documents founder ack and Box URL
prerequisites without performing live Box/Mercury HTTP or claiming LIVE VERIFIED.

## Options Considered

1. Extend PR #145 `governance-evidence` in place
2. Add a layered PR #164 gate on `control-plane-e2e-deepen` + `governance-evidence`

## Decision

We chose option 2: a dedicated `governance-evidence-live-proof-readiness` gate with
hermetic fixtures, verify script, and audit pass (`live_verified: false`), reusing
four-state honesty from PR #152/#153 live-smoke patterns.

## Consequences

- Spine and CI gain `verify_kilo_governance_evidence_live_proof_readiness.py`
- Operators document `THINKBOX_SWARM_LIVE_ACK` and `UPSTASH_PUBLIC_BOX_URL` before live prep
- No change to live execution; founder-run Live proof remains a later step
