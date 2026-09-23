# Checklist — KILO governance-evidence gate (PR #145)

- [ ] `thinkbox/kilo_governance_evidence.py` contract module present
- [ ] Layered on `thinkbox/kilo_env_matrix.py` + `thinkbox/kilo_substrate_checklist.py`
- [ ] `python3 scripts/verify_kilo_governance_evidence.py` exit 0
- [ ] `python3 scripts/verify_kilo_spine.py` includes `governance_evidence` block
- [ ] `python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr145 -v` OK
- [ ] Runbook governance-evidence section + H9 prerequisite
- [ ] `docs/CONTINUITY.md` + `docs/STATUS.md` + root `STATUS.md` mention PR #145
- [ ] Audit pass `docs/audit/passes/2026-09-23-pr145.json` registered
- [ ] No affirmative KILO LIVE VERIFIED / PRODUCTION READY on spine paths
- [ ] Four-state capped at TEST VERIFIED on branch
- [ ] `gate_for_pr(145).gate_id == governance-evidence` via unit tests
- [ ] PR #144 documented as CI fix only (not governance-evidence)
