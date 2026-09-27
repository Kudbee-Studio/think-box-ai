# KILO control-plane E2E deepen — PR #162 checklist

- [ ] Hermetic only — no Box/Mercury HTTP
- [ ] `live_verified: false` on audit pass `docs/audit/passes/2026-09-23-pr162.json`
- [ ] `python3 scripts/verify_kilo_control_plane_e2e_deepen.py` exit 0
- [ ] `python3 scripts/verify_kilo_spine.py` exit 0
- [ ] F162 e2e modules under `tests/e2e/test_f162_cp_*`
