# KILO → Live proof readiness arc (#141–#150)

**Owner:** Founder-directed arc (2026-09-23)  
**Goal:** Prepare KILO so a later **Live proof** can be earned honestly — not to run Live proof in the spine PR.

## Scope

| Phase | PRs | Outcome |
|-------|-----|---------|
| Spine | **#141** | Docs, runbook, hermetic contract module, gate stubs |
| Readiness | **#142–#149** | Close env, substrate, governance, Mercury hermetic, swarm, proof schema, dashboard, founder ack gates |
| Execution | **#150** | Live proof **procedure** + rehearsal; LIVE VERIFIED only when proof is actually run and recorded |

## Four-state (arc-wide)

Until #150 Live proof completes with artifacts:

- **Allowed:** CODE COMPLETE, TEST VERIFIED  
- **Forbidden:** LIVE VERIFIED, PRODUCTION READY for the **KILO Live proof** product claim

Subsystem-specific LIVE VERIFIED history (e.g. Mercury swarm at scale) remains historical context — it does not satisfy the KILO Live proof gate.

## Canonical artifacts

- Runbook: `docs/runbooks/kilo-live-proof-readiness.md`
- Contract: `thinkbox/kilo_live_proof_readiness.py`
- Tests: `tests/unit/test_kilo_live_proof_readiness_pr141.py`
- Audit: `docs/audit/passes/2026-09-23-pr141.json` (draft)

## Non-binding #142 suggestion

If founder prefers UI-first inside this arc: **#142** could ship cross-tab control-plane telemetry export (hermetic) instead of env-matrix first — either path must keep four-state honest.
