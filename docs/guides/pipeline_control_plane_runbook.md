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

## Four-State

LIVE_VERIFIED and PRODUCTION_READY remain blocked until a documented live exercise with production tokens (not performed in CI).
