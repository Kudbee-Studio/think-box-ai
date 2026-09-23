# Audit checklist — KILO live-proof-exec (PR #150)

- [ ] `thinkbox/kilo_live_proof_exec.py` present
- [ ] `scripts/verify_kilo_live_proof_exec.py` exit 0 hermetic
- [ ] `verify_kilo_spine.py` includes live_proof_exec block
- [ ] Fixtures valid/invalid under `data/kilo_live_proof_exec/fixtures/`
- [ ] `tests/unit/test_kilo_live_proof_readiness_pr150.py` green
- [ ] Runbook H14 + live-proof-exec section
- [ ] `live_verified: false` in audit pass JSON
- [ ] No affirmative KILO LIVE VERIFIED in spine paths
- [ ] Season close noted in CONTINUITY / STATUS / arc doc
- [ ] `arc_season_complete` true in spine summary (hermetic)
