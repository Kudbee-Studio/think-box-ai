# PR #149 dashboard-slots checklist

- [ ] `thinkbox/kilo_dashboard_slots.py` gate module (`dashboard-slots`)
- [ ] `data/kilo_dashboard_slots/fixtures/` valid + invalid hermetic fixtures
- [ ] `scripts/verify_kilo_dashboard_slots.py` layers proof-schema operator first
- [ ] `verify_kilo_spine.py` requires `dashboard_slots` block
- [ ] `spine_contract_summary` includes `pr149_gate_id`
- [ ] `tests/unit/test_kilo_live_proof_readiness_pr149.py`
- [ ] Runbook H13 + dashboard-slots section
- [ ] ADR 008 + audit pass `live_verified: false`
