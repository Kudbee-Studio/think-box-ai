# Checklist — KILO mercury-hermetic gate (PR #146)

- [ ] `thinkbox/kilo_mercury_hermetic.py` contract module present
- [ ] Layered on governance-evidence + env-matrix + substrate-checklist
- [ ] `python3 scripts/verify_kilo_mercury_hermetic.py` exit 0
- [ ] `python3 scripts/verify_kilo_spine.py` includes `mercury_hermetic` block
- [ ] `python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr146 -v` OK
- [ ] Runbook mercury-hermetic section + H10 prerequisite
- [ ] `docs/CONTINUITY.md` + `docs/STATUS.md` + root `STATUS.md` mention PR #146
- [ ] Audit pass `docs/audit/passes/2026-09-23-pr146.json` registered
- [ ] No affirmative KILO LIVE VERIFIED / PRODUCTION READY on spine paths
- [ ] Four-state capped at TEST VERIFIED on branch
- [ ] `gate_for_pr(146).gate_id == mercury-hermetic` via unit tests
- [ ] Optional non-binding #147 swarm-instrumentation next
