# Audit checklist — PR #152 live-smoke-evidence (merged)

Operator write path continues in PR #153 (`live-smoke-operator`).

- [ ] `thinkbox/kilo_live_smoke_evidence.py` gate id `live-smoke-evidence`
- [ ] Hermetic fixtures under `data/kilo_live_smoke_evidence/fixtures/`
- [ ] `scripts/verify_kilo_live_smoke_evidence.py` exit 0 (default, no `--live` HTTP)
- [ ] `scripts/verify_kilo_spine.py` includes `live_smoke_evidence.hermetic_operator_ok`
- [ ] `tests/unit/test_kilo_live_proof_readiness_pr152.py` green
- [ ] `python3 scripts/scan_doc_secrets.py` exit 0
- [ ] Audit pass `docs/audit/passes/2026-09-23-pr152.json` has `live_verified: false`
- [ ] No affirmative KILO LIVE VERIFIED / PRODUCTION READY claims in spine docs
