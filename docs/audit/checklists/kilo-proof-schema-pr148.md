# Checklist — KILO proof-schema gate (PR #148)

- [ ] `thinkbox/kilo_proof_schema.py` gate module (`proof-schema`)
- [ ] `data/kilo_proof_schema/fixtures/` valid + invalid hermetic fixtures
- [ ] `scripts/verify_kilo_proof_schema.py` layers swarm operator first
- [ ] `verify_kilo_spine.py` requires proof_schema block
- [ ] Runbook proof-schema section + H11 prerequisite
- [ ] `docs/CONTINUITY.md` + `docs/STATUS.md` + root `STATUS.md` mention PR #148
- [ ] `tests/unit/test_kilo_live_proof_readiness_pr148.py` (25+ cases)
- [ ] `gate_for_pr(148).gate_id == proof-schema` via unit tests
- [ ] `live_verified: false` in audit pass JSON
- [ ] ADR 007 cites kirocrew patterns (not code copy)
- [ ] Optional non-binding #149 dashboard-slots next
