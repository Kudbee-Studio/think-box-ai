# Audit checklist — PR #153 live-smoke-operator

- [ ] `thinkbox/kilo_live_smoke_operator.py` gate id `live-smoke-operator`
- [ ] Delegates to `thinkbox/kilo_live_smoke_evidence` (no duplicate binder)
- [ ] `scripts/kilo_live_smoke_operator.py` write + audit-flip-candidate subcommands
- [ ] `scripts/verify_kilo_live_smoke_operator.py` exit 0 (default, no HTTP)
- [ ] `scripts/verify_kilo_spine.py` includes `live_smoke_operator.hermetic_operator_ok`
- [ ] `tests/unit/test_kilo_live_proof_readiness_pr153.py` green (≥25 tests)
- [ ] `python3 scripts/scan_doc_secrets.py` exit 0
- [ ] Audit pass `docs/audit/passes/2026-09-23-pr153.json` has `live_verified: false`
- [ ] No affirmative KILO LIVE VERIFIED / PRODUCTION READY claims in spine docs
