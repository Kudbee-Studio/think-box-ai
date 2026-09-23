# KILO → Live proof readiness arc (#141–#150)

**Owner:** Founder-directed arc (2026-09-23)  
**Goal:** Prepare KILO so a later **Live proof** can be earned honestly — not to run Live proof in the spine PR.

## Scope

| Phase | PRs | Outcome |
|-------|-----|---------|
| Spine | **#141** | Docs, runbook, hermetic contract module, gate stubs (**merged**) |
| Readiness | **#142–#149** | Close env, substrate, governance, Mercury hermetic, swarm, proof schema, dashboard, founder ack gates |
| Env matrix | **#142** (merged) | `thinkbox/kilo_env_matrix.py` + `verify_kilo_env_matrix.py` |
| Substrate checklist | **#143** (draft) | `thinkbox/kilo_substrate_checklist.py` + `verify_kilo_substrate_checklist.py` |
| Execution | **#150** | Live proof **procedure** + rehearsal; LIVE VERIFIED only when proof is actually run and recorded |

## Four-state (arc-wide)

Until #150 Live proof completes with artifacts:

- **Allowed:** CODE COMPLETE, TEST VERIFIED  
- **Forbidden:** LIVE VERIFIED, PRODUCTION READY for the **KILO Live proof** product claim

Subsystem-specific LIVE VERIFIED history (e.g. Mercury swarm at scale) remains historical context — it does not satisfy the KILO Live proof gate.

## Canonical artifacts

- Runbook: `docs/runbooks/kilo-live-proof-readiness.md`
- Contract: `thinkbox/kilo_live_proof_readiness.py`
- Env matrix: `thinkbox/kilo_env_matrix.py`
- Substrate checklist: `thinkbox/kilo_substrate_checklist.py`
- Tests: `tests/unit/test_kilo_live_proof_readiness_pr141.py`, `tests/unit/test_kilo_live_proof_readiness_pr142.py`, `tests/unit/test_kilo_live_proof_readiness_pr143.py`
- Audit: `docs/audit/passes/2026-09-23-pr141.json`, `docs/audit/passes/2026-09-23-pr142.json`, `docs/audit/passes/2026-09-23-pr143.json` (draft)

See runbook: [`docs/runbooks/kilo-live-proof-readiness.md`](runbooks/kilo-live-proof-readiness.md)

## Non-binding #144 suggestion

**#143** ships `substrate-checklist` on top of `env-matrix`. Optional non-binding follow-on: **#144** `governance-evidence` (admission token + evidence shape for live burst) — must keep four-state honest.
