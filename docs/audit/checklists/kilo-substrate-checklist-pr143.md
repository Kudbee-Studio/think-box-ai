# Checklist — KILO substrate-checklist gate (PR #143)

- [ ] `thinkbox/kilo_substrate_checklist.py` contract module present
- [ ] Layered on `thinkbox/kilo_env_matrix.py` (no duplicate matrix)
- [ ] `python3 scripts/verify_kilo_substrate_checklist.py` exit 0
- [ ] `python3 scripts/verify_kilo_spine.py` includes `substrate_checklist` block
- [ ] `python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr143 -v` OK
- [ ] Runbook substrate-checklist section + H8 prerequisite
- [ ] `docs/CONTINUITY.md` + `docs/STATUS.md` + root `STATUS.md` mention PR #143
- [ ] Audit pass `docs/audit/passes/2026-09-23-pr143.json` registered
- [ ] No affirmative KILO LIVE VERIFIED / PRODUCTION READY on spine paths
- [ ] Four-state capped at TEST VERIFIED on branch
- [ ] `gate_for_pr(143).gate_id == substrate-checklist` via unit tests
- [ ] PR #145 `governance-evidence` layers on this gate (`kilo-governance-evidence-pr145.md`)
