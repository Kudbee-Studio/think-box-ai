# KILO bounded live smoke evidence (PR #152)

**Gate id:** `live-smoke-evidence`  
**Four-state cap on branch:** CODE COMPLETE / TEST VERIFIED only.

## Purpose

Bind receipt ids, etags, and gate-chain hops into a evidence JSON artifact so
`audit_flip_candidate` can refuse or produce a **candidate** audit pass with
`live_verified: true` only when:

- `founder_ack_marker_present` is true (founder set `THINKBOX_SWARM_LIVE_ACK`)
- `box_url_present` is true (`UPSTASH_PUBLIC_BOX_URL` recorded at smoke time)
- `live_api_called` is true in the evidence document (founder-run smoke only)
- `evidence_artifact_path` points at an on-disk file under `data/thinkboxmd/artifacts/`

Hermetic CI never performs live HTTP and never commits `live_verified: true`.

## Operator verify

```bash
python3 scripts/verify_kilo_live_smoke_evidence.py
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr152 -v
```

Optional env-only prep (still no HTTP):

```bash
python3 scripts/verify_kilo_live_smoke_evidence.py --live
```

Fails closed without founder ack + Box URL.

## Founder procedure (post-merge)

1. Export `THINKBOX_SWARM_LIVE_ACK=1` and `UPSTASH_PUBLIC_BOX_URL` (preview Box host).
2. Run bounded smoke per `docs/runbooks/kilo-live-proof-readiness.md` § Bounded live smoke (#152).
3. Write `data/thinkboxmd/artifacts/kilo_live_smoke_<timestamp>.json` matching schema `kilo-live-smoke-evidence-v1`.
4. Run `audit_flip_candidate` in a founder shell; write resulting pass under `docs/audit/passes/` only when predicates pass.
5. Update `docs/CONTINUITY.md` with artifact SHA256 — do not claim KILO PRODUCTION READY.

Hermetic operator CLI (PR #153): `docs/guides/kilo_live_smoke_operator.md`
