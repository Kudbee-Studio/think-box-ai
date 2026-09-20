# PR #109 — Pipeline Control Plane Evolution Contract

**Branch:** `feat/pipeline-control-plane-pr109`  
**Stack order:** `main` → **PR #108** (`feat/pipeline-dashboard-admission-merge-gate`) → **PR #109** (this branch). Do not rebase #109 off `main` without #108.  
**Lineage:** builds on merged PR #106/#107 org-memory + PR #108 pipeline surface  
**Tag:** `PR_PIPELINE_CONTROL_PLANE_V4`

## Non-negotiables

1. **Never** call GitHub merge APIs or auto-merge.
2. Founder review remains external (Graphite/GitHub).
3. All mutating paths pass `AdmissionGate` with governance token.
4. Founder merge requires `THINKBOX_FOUNDER_MERGE_PROOF_KEY` PR-bound HMAC proof.
5. Receipts append-only via `OrgMemoryReceiptStore` (`THINKBOX_ORG_MEMORY_DB`).
6. Hash-chain integrity must verify (`store.verify()`).
7. Idempotency keys on `request-merge` must not double-queue.
8. Quarantine/kill-switch fail-closed on merge requests when armed.
9. Quarantine state is read via action-scoped org-memory lookup (`pipeline_quarantine`, newest first) — not a global receipt window.
10. GitHub webhook delivery replay: when `THINKBOX_ORG_MEMORY_DB` is shared, duplicate `X-GitHub-Delivery` IDs are suppressed via org-memory fingerprints (no raw delivery id or payload in receipts). In-memory-only replay cache is hermetic test fallback.
11. Pipeline lifecycle appends on the founder merge path (queue, admission denial, policy denial, quarantine toggle) serialize through `append_pipeline_lifecycle` (process-local lock; same DB for cross-worker ordering).
12. `pipeline_state_machine` is **advisory** reporting unless a caller explicitly enforces `validate_transition`.
13. Staging/production (`THINKBOX_PIPELINE_DEPLOYMENT_ENV`) require a non-default `THINKBOX_FOUNDER_MERGE_PROOF_KEY`.

## Four-State gates

| State | PR #109 criterion |
|-------|-------------------|
| CODE_COMPLETE | All contract modules + API routes + UI surfaces present |
| TEST_VERIFIED | Full PR109 matrix unittest green (hermetic) |
| LIVE_VERIFIED | **BLOCKED** until production control-plane exercise with real tokens |
| PRODUCTION_READY | **BLOCKED** until founder sign-off + live verification |

## Checkpoint map (25 commits)

See git log on branch for hashes; each commit maps to one capability in STATUS.md PR #109 section.

## Evidence

- `chain_verified` from org-memory on every integrity/overview response.
- `github_merge_called: false` on all merge request responses.
- `evidence_label` never claims `verified` for live GitHub without delivery proof.
