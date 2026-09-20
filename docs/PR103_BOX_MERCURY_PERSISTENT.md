# PR #103 — Live Box + Mercury-2 Experiment: Persistent Results & Comparison

**Status:** Draft
**Branch:** `feat/byoc-box-mercury-live-v2`
**Base:** `main` (includes merged PR #102)
**Implementer:** KILO (follow-on commits)
**Merge:** Founder on GitHub only

---

## Goal

Take the PR #102 live experiment to the next level by adding:
- **Persistent experiment results** via SQLite (ExperimentManager) for historical comparison
- **Configurable experiment parameters** (concurrency levels, calls per level, model)
- **Multiple iterations** per concurrency level for statistical significance
- **API endpoint** for retrieving experiment results
- **Dashboard panel** for visualizing and comparing experiment runs
- **Integration tests** for the full experiment flow
- **Substrate probe tests** for SubstrateProbe/SubstrateReport

## Ten planned commits

| # | Commit (conventional) | Deliverable |
|---|------------------------|-------------|
| 1 | `docs(think): PR103 plan — persistent box experiment` | This plan document |
| 2 | `feat(experiment): persistent box mercury results` | `experiments/box_mercury_live.py` v2 — configurable, persistent, multi-iteration |
| 3 | `feat(api): GET /think/box-mercury/results` | `backend/api/v1/box_mercury.py` — experiment results API |
| 4 | `feat(dashboard): Box Mercury-2 results panel` | `public/control-plane/box_mercury.html` — results comparison dashboard |
| 5 | `feat(experiment): experiment manager integration` | `experiments/box_mercury_live.py` — SQLite persistence via ExperimentManager |
| 6 | `feat(api): box mercury status endpoint` | `backend/api/v1/box_status.py` — live substrate + model status |
| 7 | `test(byoc): integration tests` | `tests/unit/byoc/test_integration.py` — stash + box + mercury integration |
| 8 | `test(experiment): substrate probe tests` | `tests/unit/test_substrate.py` additions — SubstrateProbe/SubstrateReport |
| 9 | `feat(demo): demo_in_10_box_mercury_v2.sh` | `scripts/demo_in_10_box_mercury_v2.sh` — enhanced demo flow |
| 10 | `docs(status): PR #103 map + THINK_BOX_BOUND tag` | `STATUS.md` / `AGENTS.md` |

## Detailed Feature Breakdown

### 1. Enhanced Experiment Script (`experiments/box_mercury_live.py`)

**New features:**
- CLI arguments via env vars: `BOX_MERCURY_LEVELS` (default: 1,4,8,16), `BOX_MERCURY_CALLS` (default: 4), `BOX_MERCURY_ITERATIONS` (default: 3)
- Multiple iterations per concurrency level for statistical significance
- Results stored in SQLite via `ExperimentManager` for historical comparison
- Aggregate statistics across iterations: mean, median, p95, p99, std dev per concurrency level
- Comparison with previous runs (when available)

**Key functions:**
- `run_experiment(config)` — main entry point with configurable parameters
- `run_iteration(provider, level, calls)` — single iteration at a concurrency level
- `aggregate_results(all_iterations)` — aggregate across iterations
- `compare_with_previous(current, previous)` — compare with previous run data
- `persist_results(experiment_id, results)` — persist via ExperimentManager

### 2. API Endpoint (`backend/api/v1/box_mercury.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/think/box-mercury/status` | GET | Live substrate + model status |
| `/think/box-mercury/results` | GET | Experiment results (latest, with optional limit param) |
| `/think/box-mercury/compare` | GET | Compare two runs by experiment ID |

### 3. Dashboard Panel (`public/control-plane/box_mercury.html`)

- Box + Mercury-2 status card (substrate, model, version)
- Results comparison table across concurrency levels
- Throughput chart (RPS by concurrency)
- Latency distribution (p50, p95, p99 by concurrency)
- Run history with timestamps and proof hashes
- Evidence labels on all data

### 4. Integration Tests (`tests/unit/byoc/test_integration.py`)

| Test | Description |
|------|-------------|
| `test_stash_box_mercury_integration` | Stash store + experiment results end-to-end |
| `test_box_status_api_shape` | API response shape validation |
| `test_dashboard_emit_experiment` | Dashboard state emit on experiment completion |
| `test_proof_artifact_chain` | Proof artifact generated and hash-verifiable |

### 5. Substrate Probe Tests (`tests/unit/test_substrate.py`)

| Test | Description |
|------|-------------|
| `test_substrate_probe_detection` | SubstrateProbe returns valid SubstrateReport |
| `test_substrate_probe_history` | Probe history tracks multiple probes |
| `test_substrate_report_to_dict` | SubstrateReport.to_dict() returns expected keys |
| `test_detect_substrate_local` | detect_substrate() returns local without env vars |
| `test_detect_substrate_box` | detect_substrate() returns upstash-box with env var |
| `test_substrate_probe_isolation_tools` | Isolation tools are detected correctly |

### 6. Demo Script (`scripts/demo_in_10_box_mercury_v2.sh`)

Enhanced demo flow:
1. Env guards (INCEPTION_API_KEY, UPSTASH_PUBLIC_BOX_URL)
2. Substrate check (detect_substrate)
3. Run experiment with configurable parameters
4. Show results summary (aggregate across iterations)
5. Show comparison with previous run (if available)
6. Show proof artifact summary

## Evidence labels

All dashboard and API responses use evidence labels: `simulated`, `inferred`, `verified`, or `physically_measured`. Live Mercury-2 calls are **verified** only after documented smoke with real credentials.

## Out of scope

- Multi-agent coalition / economy modules
- New non-stdlib dependencies without ADR
- Exposing inference ports publicly
- GPU execution claims (Upstash Box is CPU Firecracker VMs)
- SSH-to-UpCloud execution (unsupported per investigation)
- Real-time WebSocket streaming of results (batch API only)

## References

- PR #100 — Demo-in-10 × control-plane × durable proof
- PR #101 — BYOC Mercury-2 + Upstash THINK stash
- PR #102 — Live Box + Mercury-2 throughput experiment
- `thinkbox/substrate.py` — SubstrateProbe, detect_substrate, bind_think_box
- `thinkbox/experiment.py` — ExperimentManager, ExperimentRecord
- `thinkbox/burst.py` — BurstRunner, BurstConfig
- `experiments/box_mercury_live.py` — PR #102 experiment script
- `experiments/concurrent_goals_live.py` — live experiment pattern
