# Pipeline Control Plane — Operator Runbook (PR #109)

## Invariants

- Never enable GitHub merge from this control plane.
- Founder merge requires governance token + `THINKBOX_FOUNDER_MERGE_PROOF_KEY` PR-bound proof.
- Quarantine blocks `request-merge` fail-closed.

## Health checks

```bash
curl -sS -H "X-API-Key: $KEY" http://localhost:8000/api/v1/control-plane/pipeline/health
curl -sS -H "X-API-Key: $KEY" http://localhost:8000/api/v1/control-plane/pipeline/reconcile
```

## Verify receipt chain

```bash
curl -sS -H "X-API-Key: $KEY" http://localhost:8000/api/v1/control-plane/lifecycle/receipts/verify
curl -sS -H "X-API-Key: $KEY" http://localhost:8000/api/v1/control-plane/pipeline/pr/108/integrity
```

## Request merge (queues org-memory only)

```bash
curl -sS -X POST -H "X-API-Key: $KEY" \
  -H "X-Thinkbox-Governance-Token: $GOV_TOKEN" \
  -H "X-Thinkbox-Founder-Proof: $FOUNDER_PROOF" \
  -H "X-Thinkbox-Idempotency-Key: merge-108-1" \
  http://localhost:8000/api/v1/control-plane/pipeline/pr/108/request-merge \
  -d '{"branch":"feat/example"}'
```

## Staging live drill (PR #110)

```bash
export THINKBOX_PIPELINE_STAGING=1
export THINKBOX_LIVE_DRILL_ENABLED=1
export THINKBOX_ORG_MEMORY_DB=/path/to/staging/org_memory_receipts.db
# plus WEBHOOK_SECRET, THINKBOX_FOUNDER_MERGE_PROOF_KEY, governance tokens

python3 experiments/pipeline_live_drill_staging.py
curl -sS -H "X-API-Key: $KEY" http://localhost:8000/api/v1/control-plane/pipeline/live/preflight
```

Deliver GitHub webhooks with `X-GitHub-Delivery` and optional `X-Thinkbox-Live-Drill-Correlation`.

## Four-State

`LIVE_VERIFIED` requires a persisted `live_verification_attestation` receipt with `live_verified: true` — not hermetic tests alone. `PRODUCTION_READY` remains blocked until founder sign-off.
