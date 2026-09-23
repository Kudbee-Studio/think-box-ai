# KILO → Live proof readiness arc (#141–#150)

**Owner:** Founder-directed arc (2026-09-23)  
**Goal:** Prepare KILO so a later **Live proof** can be earned honestly — not to run Live proof in the spine PRs.

**Season status (PR #150 merged):** Arc checklist **closed** at CODE COMPLETE / TEST VERIFIED. **PR #151** (founder-directed) is post-season ops harden — not a Live proof gate.

## Post-season (#151)

| Work | PR | Outcome |
|------|-----|---------|
| CI + branch hygiene + docs sync | **#151** | `post-season-harden` hermetic ops gate (draft) |

## Scope

| Phase | PRs | Outcome |
|-------|-----|---------|
| Spine | **#141** | Docs, runbook, hermetic contract module, gate stubs (**merged**) |
| Readiness | **#142–#149** | Close env, substrate, governance, Mercury hermetic, swarm, proof schema, dashboard gates (**merged**) |
| Season close | **#150** | `live-proof-exec` execution plan + operator verify (**hermetic**; not Live proof run) |

| Gate | PR | Module |
|------|-----|--------|
| env-matrix | #142 | `thinkbox/kilo_env_matrix.py` |
| substrate-checklist | #143 | `thinkbox/kilo_substrate_checklist.py` |
| governance-evidence | #145 | `thinkbox/kilo_governance_evidence.py` |
| mercury-hermetic | #146 | `thinkbox/kilo_mercury_hermetic.py` |
| swarm-instrumentation | #147 | `thinkbox/kilo_swarm_instrumentation.py` |
| proof-schema | #148 | `thinkbox/kilo_proof_schema.py` |
| dashboard-slots | #149 | `thinkbox/kilo_dashboard_slots.py` |
| live-proof-exec | #150 | `thinkbox/kilo_live_proof_exec.py` |

## Four-state (arc-wide)

Until a **founder-run** bounded Live proof completes with artifacts:

- **Allowed:** CODE COMPLETE, TEST VERIFIED  
- **Forbidden:** LIVE VERIFIED, PRODUCTION READY for the **KILO Live proof** product claim

Subsystem-specific LIVE VERIFIED history (e.g. Mercury swarm at scale) remains historical context — it does not satisfy the KILO Live proof gate.

## Canonical artifacts

- Runbook: `docs/runbooks/kilo-live-proof-readiness.md`
- Contract: `thinkbox/kilo_live_proof_readiness.py`
- Live-proof exec: `thinkbox/kilo_live_proof_exec.py`
- Post-season ops: `thinkbox/kilo_post_season_harden.py` (PR #151, not arc gate)
- Tests: `tests/unit/test_kilo_live_proof_readiness_pr141.py` … `pr151.py`
- Audit: `docs/audit/passes/2026-09-23-pr141.json` … `pr151.json` (`live_verified: false`)

See runbook: [`docs/runbooks/kilo-live-proof-readiness.md`](runbooks/kilo-live-proof-readiness.md)

## Earning LIVE VERIFIED (post-#150)

Founder-run only: bounded smoke per runbook, artifact `data/thinkboxmd/artifacts/kilo_live_proof_*.json`, audit pass with `live_verified: true`, CONTINUITY entry with hash. Not part of PR #150 merge.
