# KILO live-smoke operator path (PR #153)

**Gate id:** `live-smoke-operator`  
**Four-state cap on branch:** CODE COMPLETE / TEST VERIFIED only.

## Purpose

Hermetic CLI + verify gate that **writes** valid `kilo_live_smoke_*.json` artifacts and
produces audit-flip **candidate** passes under `docs/audit/passes/*-live-candidate.json`.
Delegates validation and `audit_flip_candidate` to PR #152 — no duplicate binder.

## Operator verify

```bash
python3 scripts/verify_kilo_live_smoke_operator.py
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr153 -v
python3 scripts/verify_kilo_spine.py
python3 scripts/scan_doc_secrets.py
```

Optional env-only prep (still no HTTP):

```bash
python3 scripts/verify_kilo_live_smoke_operator.py --live
```

## CLI

```bash
# Hermetic write (default flags: no live API)
python3 scripts/kilo_live_smoke_operator.py write --evidence-id founder_smoke_dry_run

# Validate an on-disk or fixture path
python3 scripts/kilo_live_smoke_operator.py validate --path data/kilo_live_smoke_evidence/fixtures/valid_hermetic_minimal.json

# Audit flip candidate (refuses live_verified without founder predicates)
python3 scripts/kilo_live_smoke_operator.py audit-flip-candidate --evidence-path data/thinkboxmd/artifacts/kilo_live_smoke_....json
```

## Founder procedure (post-merge)

1. `python3 scripts/verify_kilo_spine.py` and operator verify scripts (hermetic).
2. Export `THINKBOX_SWARM_LIVE_ACK=1` and `UPSTASH_PUBLIC_BOX_URL`.
3. Run bounded smoke; set markers in evidence JSON per `docs/guides/kilo_live_smoke_evidence.md`.
4. `python3 scripts/kilo_live_smoke_operator.py write` (or merge recorded fields) → artifact under `data/thinkboxmd/artifacts/`.
5. `python3 scripts/kilo_live_smoke_operator.py audit-flip-candidate` → review `*-live-candidate.json`; founder promotes only when predicates pass.

Do **not** claim KILO LIVE VERIFIED until audit + artifacts are earned honestly.
