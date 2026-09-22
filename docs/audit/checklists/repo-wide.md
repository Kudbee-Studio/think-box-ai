# Repo-wide audit checklist (PR #125)

- [ ] Layer imports respect AGENTS.md §1.1 (no cross-layer runtime imports)
- [ ] No new undocumented third-party dependencies (Phase 1 stdlib-first)
- [ ] Governance: tools default RESTRICTED; AdmissionGate on side effects
- [ ] Provider independence: runtime uses `ModelProvider` protocol only
- [ ] Evidence labels on dashboard / pipeline claims (simulated vs verified)
- [ ] `python3 -m unittest discover tests/` green locally before PR
- [ ] No secrets committed (scan `AGENTS.md` chronicle blocks — redact to env refs)
- [ ] `docs/CONTINUITY.md` + `docs/STATUS.md` test counts match local run
- [ ] Audit pass JSON lists exactly 25 ranked findings
- [ ] `scripts/audit_ledger.py stale` reviewed after substantive edits
