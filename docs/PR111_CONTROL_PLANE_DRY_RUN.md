# PR #111 — Demo-in-10 Control Plane Dry Run

**GitHub PR:** #111 (draft)  
**Branch:** `feat/demo-in-10-control-plane-dry-run`  
**Builds on:** #106 org-memory lifecycle, #107 GitHub webhook admission, #108 pipeline dashboard + founder merge gate, #109 (merged on `main`)

## Purpose

Hermetic operator ceremony that walks the control-plane stack end-to-end **without** physical staging, GitHub merge, or external services. This is **not** LIVE verification. Staging LIVE drill remains **PR #110** (`feat/pipeline-live-verification-pr110`) — parked separately.

## Run

```bash
bash scripts/demo_in_10_control_plane_dry_run.sh
# or
python3 -m thinkbox.control_plane_dry_run
```

Optional: `python3 -m thinkbox.control_plane_dry_run --skip-api-handlers` (modules-only).

## What it proves

1. Org-memory receipt append + hash-chain verify  
2. Signed GitHub webhook path (local HMAC) + fail-closed bad signature  
3. Pipeline dashboard rollups, denial ledger, per-PR integrity  
4. FastAPI route handlers wired in-process (patched singletons)  
5. Founder-gated `request-merge` with governance token + PR-bound proof  
6. `github_merge_called=false` always  

## Four-State (honest)

| State | Dry-run |
|-------|---------|
| CODE_COMPLETE | ✅ |
| TEST_VERIFIED | ✅ (ceremony + unit tests) |
| LIVE_VERIFIED | ❌ blocked — dry-run only |
| PRODUCTION_READY | ❌ blocked — no GitHub merge |

## Tests

```bash
python3 -m unittest tests.unit.demo.test_control_plane_dry_run -v
```

## NEXT

When founder is ready: execute PR #110 LIVE staging drill; do not conflate with this dry-run.
