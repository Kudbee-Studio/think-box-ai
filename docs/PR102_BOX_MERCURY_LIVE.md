# PR #102 — Upstash Box + Inception Mercury-2 Live Experiment

**Status:** Draft
**Branch:** `feat/byoc-box-mercury-live`
**PR:** https://github.com/Kudbee-Studio/think-box-ai/pull/102
**Base:** `main` (includes merged PR #101 BYOC)
**Implementer:** KILO (follow-on commits)
**Merge:** Founder on GitHub only  

---

## Goal

Run the **first live experiment** that executes on the **Upstash Box** substrate (Firecracker microVMs) using **Inception Mercury-2** as the model provider, measuring real throughput with substrate-bound execution tracking, proof chain binding, and dashboard state emit.

This is the convergence of all prior work:
- **Upstash Box** (PR #100 substrate detection, `detect_substrate()`)
- **Inception Mercury-2** (PR #101 BYOC client, `MercuryClient`)
- **Proof chain** (PR #97-99, `ActionReceiptStore`, `verify_chain`)
- **Dashboard state** (PR #98, `DashboardState.emit`)

## Ten planned commits

| # | Commit (conventional) | Deliverable | Status |
|---|------------------------|-------------|--------|
| 1 | `docs(think): PR102 plan — live Box + Inception experiment` | This plan document | ✅ Done |
| 2 | `feat(experiment): live Box + Mercury-2 throughput experiment` | `experiments/box_mercury_live.py` — substrate verify, burst, throughput, proof | ✅ Done |
| 3 | `feat(experiment): substrate report + dashboard emit` | `thinkbox/substrate.py` — `SubstrateProbe` + `bind_think_box` live usage | ✅ Done (PR #101 `detect_substrate()` + live usage) |
| 4 | `feat(api): GET /think/box-status` | `backend/api/v1/box_status.py` — live substrate + model status | ⬜ Todo |
| 5 | `feat(dashboard): Box + Mercury-2 status panel` | `public/control-plane/box_status.html` | ⬜ Todo |
| 6 | `feat(demo): demo_in_10_box_mercury.sh` | `scripts/demo_in_10_box_mercury.sh` — live demo flow | ✅ Done |
| 7 | `test(byoc): hermetic tests for box_mercury_live` | `tests/unit/byoc/test_box_mercury.py` | ✅ Done |
| 8 | `test(byoc): integration tests — stash + box + mercury` | `tests/unit/byoc/test_integration.py` | ⬜ Todo |
| 9 | `test(experiment): substrate probe tests` | `tests/unit/test_substrate.py` additions | ⬜ Todo |
| 10 | `docs(status): PR #102 map + THINK_BOX_BOUND tag` | `STATUS.md` / `AGENTS.md` | ✅ Done |

---

## Evidence labels

All dashboard and API responses use evidence labels: `simulated`, `inferred`, `verified`, or `physically_measured`. Live Mercury-2 calls are **verified** only after documented smoke with real credentials.

---

## Out of scope

- Multi-agent coalition / economy modules
- New non-stdlib dependencies without ADR
- Exposing inference ports publicly
- GPU execution claims (Upstash Box is CPU Firecracker VMs)
- SSH-to-UpCloud execution (unsupported per investigation)

---

## References

- PR #100 — Demo-in-10 × control-plane × durable proof
- PR #101 — BYOC Mercury-2 + Upstash THINK stash
- `thinkbox/substrate.py` — SubstrateProbe, detect_substrate, bind_think_box
- `thinkbox/burst.py` — BurstRunner, BurstConfig
- `experiments/concurrent_goals_live.py` — live experiment pattern
- `experiments/dag_verified_live.py` — live DAG experiment pattern
