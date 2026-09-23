# Checklist — KILO swarm-instrumentation gate (PR #147)

- [ ] `thinkbox/kilo_swarm_instrumentation.py` gate module (`swarm-instrumentation`)
- [ ] `thinkbox/swarm_instrumentation_checks.py` shared hermetic checks
- [ ] `experiments/verify_instrumentation.py` imports shared checks (10/10 hermetic)
- [ ] `scripts/verify_kilo_swarm_instrumentation.py` layers mercury operator first
- [ ] `verify_kilo_spine.py` requires swarm-instrumentation block
- [ ] Runbook swarm-instrumentation section + H11 prerequisite
- [ ] `docs/CONTINUITY.md` + `docs/STATUS.md` + root `STATUS.md` mention PR #147
- [ ] `tests/unit/test_kilo_live_proof_readiness_pr147.py` (25+ cases)
- [ ] `gate_for_pr(147).gate_id == swarm-instrumentation` via unit tests
- [ ] `live_verified: false` in audit pass JSON
- [ ] Optional non-binding #148 proof-schema next

