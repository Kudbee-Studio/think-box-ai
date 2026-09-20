# PR #110 — LIVE_VERIFIED Staging Drill Contract

**Branch:** `feat/pipeline-live-verification-pr110`  
**Lineage:** PR #109 → PR #108  
**Tag:** `PR_PIPELINE_LIVE_VERIFICATION`

## Absolute rules

1. Never call GitHub merge APIs.
2. Never auto-merge.
3. `LIVE_VERIFIED` is **only** true when `LIVE_VERIFICATION_ATTESTATION.live_verified` is true after a real staging drill with all prerequisites satisfied.
4. Hermetic tests alone cannot set `LIVE_VERIFIED`.

## Prerequisites (all required)

| Variable | Purpose |
|----------|---------|
| `THINKBOX_PIPELINE_STAGING=1` | Staging mode |
| `THINKBOX_LIVE_DRILL_ENABLED=1` | Explicit drill consent |
| `THINKBOX_ORG_MEMORY_DB` | Path containing `staging` segment |
| `WEBHOOK_SECRET` or `GITHUB_WEBHOOK_SECRET` | Real GitHub HMAC |
| `THINKBOX_FOUNDER_MERGE_PROOF_KEY` | PR-bound founder proof |
| `THINKBOX_GITHUB_WEBHOOK_GOVERNANCE_TOKEN` | Webhook admission |
| `THINKBOX_GOVERNANCE_SIGNING_KEY` | Token validation |

## Attestation schema

`LIVE_VERIFICATION_ATTESTATION` — see `thinkbox/pipeline_live_drill.py::build_live_verification_attestation`.

## Four-State

| State | Criterion |
|-------|-----------|
| CODE_COMPLETE | Drill modules + API + runbook |
| TEST_VERIFIED | Hermetic + attestation gate tests |
| LIVE_VERIFIED | Real staging drill + attestation `live_verified=true` |
| PRODUCTION_READY | Founder sign-off + production hardening (out of scope) |
