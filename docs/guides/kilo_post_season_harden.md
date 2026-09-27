# KILO post-season harden (PR #151)

Hermetic ops gate **`post-season-harden`** — not part of arc #141–#150.

## Scope

- CI workflow references spine + `scan_doc_secrets.py`
- `scripts/cleanup_merged_cursor_branches.py` (dry-run default)
- Checklist: `data/kilo_post_season_harden/checklist.json`
- Runbook: `docs/runbooks/branch-hygiene.md`

## Verify

```bash
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr151 -v
python3 scripts/verify_kilo_post_season_harden.py
python3 scripts/verify_kilo_spine.py
python3 scripts/scan_doc_secrets.py
```

## Four-state

CODE COMPLETE / TEST VERIFIED only — **not** KILO LIVE VERIFIED.
