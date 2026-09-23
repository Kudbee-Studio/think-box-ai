# KILO → Live proof readiness arc (#141–#150)

**Owner:** Founder-directed arc (2026-09-23)  
**Goal:** Prepare KILO so a later **Live proof** can be earned honestly — not to run Live proof in the spine PR.

## Scope

| Phase | PRs | Outcome |
|-------|-----|---------|
| Spine | **#141** | Docs, runbook, hermetic contract module, gate stubs (**merged**) |
| Readiness | **#142–#149** | Close env, substrate, governance, Mercury hermetic, swarm, proof schema, dashboard gates |
| Env matrix | **#142** (merged) | `thinkbox/kilo_env_matrix.py` + `verify_kilo_env_matrix.py` |
| Substrate checklist | **#143** (merged) | `thinkbox/kilo_substrate_checklist.py` + `verify_kilo_substrate_checklist.py` |
| CI fix | **#144** (merged) | Post-merge unittest discover green — **not** a readiness gate closure |
| Governance evidence | **#145** (merged) | `thinkbox/kilo_governance_evidence.py` + `verify_kilo_governance_evidence.py` |
| Mercury hermetic | **#146** (this arc step) | `thinkbox/kilo_mercury_hermetic.py` + `verify_kilo_mercury_hermetic.py` |
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
- Governance evidence: `thinkbox/kilo_governance_evidence.py`
- Mercury hermetic: `thinkbox/kilo_mercury_hermetic.py`
- Tests: `tests/unit/test_kilo_live_proof_readiness_pr141.py` … `pr146.py`
- Audit: `docs/audit/passes/2026-09-23-pr141.json` … `pr146.json` (draft)

See runbook: [`docs/runbooks/kilo-live-proof-readiness.md`](runbooks/kilo-live-proof-readiness.md)

## Non-binding #147 suggestion

**#146** ships `mercury-hermetic` on top of `governance-evidence`. Optional non-binding follow-on: **#147** `swarm-instrumentation` (11/11 `verify_instrumentation.py` prereq) — must keep four-state honest.
