## CNC Manufacturing Intelligence Platform

**Status:** Complete

### Module Structure

- `thinkbox/cnc/job.py` — CNCJob, Material, Tool, MachineProfile, Operation, ValidationResult, InspectionResult, ApprovalRecord, ExecutionRecord
- `thinkbox/cnc/memory.py` — ManufacturingMemory, KnowledgeEntry
- `thinkbox/cnc/proof.py` — ProofPackage, ProofStore
- `thinkbox/cnc/adapter.py` — CADInterface, MachineControllerInterface, InspectionSystemInterface, SimulatorInterface, ShopDatabaseInterface, CNCAdapterRegistry
- `thinkbox/cnc/safety.py` — SafetyGate, ApprovalGate, SafetyGateStore
- `thinkbox/cnc/tenant.py` — Tenant, TenantPermission, TenantBoundary, TenantStore
- `thinkbox/cnc/dashboard.py` — ROIStats, ROIDashboard
- `thinkbox/cnc/demo.py` — DemoMode, DemoResult
- `thinkbox/cnc/engine.py` — CNCManufacturingEngine
- `thinkbox/cnc/__init__.py` — All exports

### CLI Integration

- `think_box_ai/commands/cnc.py` — CNC CLI commands (job, demo, memory, proof, safety, tenant, replay, dashboard, engine)
- `think_box_ai/cli.py` — CNC subcommand registered

### Backend Integration

- `backend/api/v1/router.py` — CNC endpoints (POST /cnc/job, POST /cnc/demo, GET /cnc/dashboard, POST /cnc/safety/approve, GET /cnc/tenant)

### Tests

- `tests/unit/test_cnc.py` — 43 tests
- Full suite: 477 tests, 1 skip

## Experiment + Learning Dashboard

**Status:** Complete

### Module Structure

- `thinkbox/experiment.py` — `ExperimentRecord`, `ExperimentManager`, `ExperimentDB`, `AgentSessionRecord`, `ParameterProvenance`, `ParameterClassification`, `ExperimentStatus`, `FourState`, `ProvenanceSource`, `get_experiment_manager`
- `tests/unit/test_experiment.py` — 45 tests covering all experiment features

### Key Features

- **Persistent Experiment Records**: Every agent run becomes a tracked experiment with durable session ID, inputs, execution evidence, outputs, tests, outcome, and learned parameters
- **SQLite Persistence**: Zero-dollar, stdlib-only persistence layer with migrations for `experiments`, `experiment_parameters`, `experiment_events`, `artifacts`, `proof_records`, `outcomes`, `lessons`, `agent_sessions`
- **Parameter Provenance**: Every parameter carries `value`, `unit`, `source`, `confidence`, `classification` (OBSERVED/ESTIMATED/SIMULATED), `session_id`, `timestamp`
- **Learning Loop**: Intent → Hypothesis → Parameters → Plan → Execute → Test → Artifact → Proof → Outcome → Learn → Updated Parameters → Next Experiment
- **Four-State Classification**: CODE_COMPLETE, TEST_VERIFIED, LIVE_VERIFIED, PRODUCTION_READY
- **Session Continuity**: Parent/child session relationships, start/end state, last completed action, blockers, next larger improvement
- **Zero-Server Execution**: Complete lifecycle works without Docker, Kubernetes, SSH, cloud server, or external database
- **Dashboard Aggregation**: Dashboard data generated from persisted SQLite data, not manually maintained status text
- **Restart/Recovery**: Full recovery from SQLite after restart
- **Corrupted/Missing Artifact Handling**: Graceful handling of missing or corrupted artifacts

### Backend Integration

- `backend/api/v1/router.py` — Experiment endpoints: POST /experiment, GET /experiment/{id}, POST /experiment/{id}/parameter, POST /experiment/{id}/outcome, GET /experiment/dashboard, POST /experiment/zero-server, GET /experiment/restart

### Tests

- `tests/unit/test_experiment.py` — 46 tests (incl. learning-loop provenance round-trip)
- `tests/unit/test_cnc.py` — 44 tests (UpCloud control-plane config: no stale defaults, explicit-server)
- `tests/unit/test_providers.py` — 10 tests (openai_compat incl. Mercury-2 endpoint contract, mocked)
- `tests/unit/test_swarm_instrumentation.py` — incl. `TestPipelineDashboard` 4 tests (rebuild-from-storage, singleton-reset recovery, learning provenance, no-secrets)
- Full suite: **614 tests, 6 skipped**

### KUDBEE Dashboard — Learning Pipeline View (2026-09-17)

- **Existing dashboard only** (`experiments/swarm_dashboard.py`; no parallel system): new `_pipeline()` reader (read-only SQLite across experiments/outcomes/proofs/artifacts/lessons/events/params + memory.db + ledger verify) at `/api/pipeline` + Pipeline HTML tab (KPIs, jobs table, lessons/retrieval/memory/blockers)
- **Restart-proof:** pipeline rebuilds from storage after singleton reset (tested); served live from fresh module load over HTTP (200 on `/api/pipeline` + `/healthz`)
- **Live state shown:** 6 experiments / 6 outcomes / 4 proofs / 9 artifacts / 6 lessons / 3 memory keys / ledger verified; 3 Mercury-2 jobs VALID; lesson `learn:exact-json:directive`; 2 retrieval events; CODE/TEST/LIVE/MODEL verified, ARENA NOT_RUN
- **Blockers shown:** SSH-to-UpCloud unsupported; `record_outcome` status stays pending

### End-to-End Learning Think Job (2026-09-17)

- **Path (existing only):** ExperimentManager lessons/events + MemoryStore provenance + ActionLedger + ExperimentStore/SelfImprovementLoop; no competing architecture; no EvidenceDrivenLearningEngine/OutcomeClassifier classes in repo (vocabulary used as plain classification)
- **Baseline:** job `tb_exp_20260917170533_fbb1ec84` — exact-JSON answer=7, live Mercury-2 VALID, 0.39s, 98 tokens, artifact `6cc76885…bd0f5`
- **Lesson:** row id 5 + memory `learn:exact-json:directive` (conf 0.9, task=baseline; known/unknown recorded)
- **Learned:** job `tb_exp_20260917170605_a1ae355e` — same family answer=9, lesson retrieved (event + param + ledger provenance), live Mercury-2 VALID, 0.433s, 91 tokens, artifact `814b63e0…150f2`
- **Compare:** True/True, 0 retries, reuse proven, latency 0.39/0.433, tokens 98/91 — no invented score. Classification: NO_MEASURABLE_IMPROVEMENT (ceiling at 1.0; valid, model NOT smarter)
- **Restart/replay:** both experiments + lessons + memory + hashes + ledger reload OK; property replay True/True
- **Evidence:** `data/thinkboxmd/artifacts/learn_loop_proof_20260917.json` (SHA256 `e05be996…22ffb7f90`, secrets-clean); FourState MODEL_EXECUTION_VERIFIED + TEST_VERIFIED

### Real Model-Backed Think Job (2026-09-17)

- **Path (existing, no new architecture):** `openai_compat` provider + `MercuryClient` contract (`api.inceptionlabs.ai/v1`, `mercury-2`, key from `INCEPTION_API_KEY` presence only)
- **Live call (ONE, bounded):** temp 0.2, max_tokens 3500, 60s timeout; response 14 chars → parsed `{"answer": 42}` → property VALID; 36/77/113 tokens, 0.774s latency
- **Job:** session `tb_sess_20260917165841_b7bdb508`, box `box_950e971d6d1b` (Vector persisted), job `tb_exp_20260917165842_4b92d477`, artifact SHA256 `e41e8f9e…caf8f6`, ledger verified, memory + proof + outcome TEST_VERIFIED + dashboard; executed from in-Box runtime via existing provider POST `{base}/chat/completions` — no SSH, no UpCloud compute, no GPU
- **Replay:** fresh-process reload + property re-validation True (byte-identical response explicitly NOT required)
- **Safety:** no keys/headers/env in artifacts; single call; honest FAILED path on invalid property
- **Evidence:** `data/thinkboxmd/artifacts/model_job_proof_20260917.json` (SHA256 `a4171cdc…356c12`); FourState MODEL_EXECUTION_VERIFIED (path proven, no intelligence claim)

### Upstash Box as Primary Execution Substrate (2026-09-17)

- **Contract (LIVE_VERIFIED):** precedence `UPSTASH_PUBLIC_BOX_URL` > `THINKBOX_UPCLOUD_API_TOKEN` > `CI` > `local`; live selection `wanted-tuna-71803-3000.preview.box.upstash.com`
- **Box job (TEST_VERIFIED):** session `tb_sess_20260917164614_26d2aca3`, box `box_62f30c9d3adc` (Vector snapshot persisted), job `tb_exp_20260917164615_32b3ee9c`, artifact SHA256 `8bac2b52…57662550`, validation PASS, ledger verified, memory + outcome + dashboard recorded; executed in-Box (Firecracker runtime, Box env) — no remote-exec API exists so no remote-dispatch claim
- **Restart/replay (TEST_VERIFIED):** fresh-process reload of box/session/job/artifact/hash/proof/memory/outcome all verified; replay identical `[1,2,3,4,5]`; dashboard reconstructed
- **Model readiness:** BOX EXECUTION VERIFIED; MODEL EXECUTION VERIFIED 2026-09-17 (single bounded Mercury-2 call via existing openai_compat path: `{"answer": 42}` property VALID, 0.774s; job `tb_exp_20260917165842_4b92d477`; proof `model_job_proof_20260917.json`)
- **Classification:** UpCloud = infrastructure/control-plane ONLY; Upstash Box = current execution substrate; SSH-to-UpCloud = unsupported/not required (`thinkbox/upcloud.py` defaults fixed, history preserved)
- **Evidence:** `data/thinkboxmd/artifacts/box_primary_proof_20260917.json` (SHA256 `972f2b6e3081db1b0e38e61c67c0553c2cdbfdd6f05978c697188259f1d725e3`)

### Live UpCloud Host Verification (2026-09-17)

- **API (LIVE_VERIFIED, read-only):** account `kudbee` (200); server `kudbeev3` (`0046a589-81a2-4c0b-aacd-8e6f678c7c41`, CLOUDNATIVE-16xCPU-48GB, us-chi1, started, 16 cores, 49152MB, 209.50.56.169 + 209.50.53.93, 50GB virtio, firewall off) via `https://api.upcloud.com/1.3` Bearer auth (`/v1`→404, `/1.6`→400)
- **SSH (BLOCKED at auth layer):** port 22 open on .169 (banner OpenSSH_10.2p1 Ubuntu-2ubuntu3.6), timeout on .93; historical recovered keypair consistent but NOT authorized (Permission denied publickey); configured key path file absent; no SSH adapter class in codebase; UpCloudConfig defaults stale (kudbee-host-v1/212.147.250.183)
- **Reconciliation:** same-machine NOT_PROVEN (no shell); GPU absence inferred from CPU-only plan, unmeasured
- **Substrate:** current run substrate is Upstash Box; smallest wiring point is `core/providers/upcloud.py` read-only execute → `UpCloudConfig` (API-sourced IP/UUID) → `substrate.bind_think_box` live-server branch (not built)
- **Evidence:** experiment `tb_exp_20260917162855_5eb93b1c`, artifact `data/thinkboxmd/artifacts/upcloud_host_verify_20260917.json` (SHA256 `400f4cc92b300a0553cdc9448d89c4cc7f22157985805af9c36fa9737e7bd20d`); FourState TEST_VERIFIED with LIVE_VERIFIED API inventory, SSH proof FAILED (blocker)

### UpCloud Runtime State Diagnostic (2026-09-17)

- **Server IS running:** API `/1.3/server/<uuid>` → state `started`, host 8388362883, boot_order=disk, firewall off; user report of stopped server contradicted by live API + open port 22 on 209.50.56.169 (209.50.53.93 secondary IP times out — normal)
- **Separate statuses:** API reachable ✅ / server running ✅ / port 22 (.169) ✅ / port 22 (.93) ❌ / SSH key available ❌ / SSH auth successful ❌
- **Substrate boundary:** execution substrate = Upstash Box preview; UpCloud control plane = reachable (GET-only); UpCloud server execution path = NOT WIRED (provider is control-plane REST only; stale defaults; no SSH adapter; no bind_think_box live branch); UpCloud GPU execution path = NOT PRESENT (CPU-only server, 68 GPU plans in catalog unassigned)
- **Evidence:** experiment `tb_exp_20260917164001_073516d8`, artifact `data/thinkboxmd/artifacts/upcloud_runtime_state_20260917.json` (SHA256 `e333faa4d1886d102d808ec3fffc4a1deef3a6af9eb02ee95226c1d10d711ff8`); zero mutation; FourState LIVE_VERIFIED for control-plane state only, machine NOT reached
- **Blocker:** no authorized SSH key on kudbeev3 (single BatchMode attempt denied publickey)

### CLI Integration

- `think_box_ai/cli.py` — Experiment subcommand registered

## Phase 9 — Zero-to-One Innovations

**Status:** Complete (55 innovations across 13 categories)

### Phase 9 Modules

| Module | Category | Features |
|--------|----------|----------|
| `thinkbox/session.py` | Foundation | SessionContext, generate_session_id, create/get/clear_session, UpstashVectorSync |
| `thinkbox/coalition.py` | COAL (1–5) | CRDT shared memory, task bidding market, pub/sub bus, capability registry, governance voting |
| `thinkbox/consensus.py` | CONS (11–15) | Multi-model voting, Bayesian confidence scoring, disagreement resolution, model ranking, audit trail |
| `thinkbox/economy.py` | ECON (16–20) | Token economy, contribution mining, staking mechanism, slash conditions, treasury governance |
| `thinkbox/intelligence.py` | INTEL (36–40, 51–55) | Knowledge graph, self-healing, reputation, federated learning, post-quantum security |
| `thinkbox/benchmark.py` | BENCH (26–30) | Concurrency scaling sweeps (16–512 workers), system metrics, markdown report generation |

### Phase 9 Bug Fixes

| Bug | File | Fix |
|-----|------|-----|
| Missing treasury account | `thinkbox/economy.py` | Added treasury existence check in `AgentTokenEconomy.transfer()` |
| `_threshold` attribute | `thinkbox/consensus.py` | Added validation in `DisagreementResolver.__init__` |

### Test Count

**137 tests** (Phase 1/2 security, Phase 5 features, integration tests, Phase 9 session tracker)

## How to Run Tests

```bash
python3 -m unittest discover tests/
python3 -m unittest tests.unit.test_session_tracker
python3 -m unittest tests.unit.test_phase1_2_security
python3 -m unittest tests.unit.test_whip_protocol
python3 -m unittest tests.integration.test_e2e_engine
```

## Verified Tool Count: 18

| # | Tool | Status |
|---|------|--------|
| 1 | file_read | ✅ |
| 2 | file_write | ✅ |
| 3 | shell_exec | ✅ |
| 4 | http_request | ✅ |
| 5 | memory_query | ✅ |
| 6 | fs_read | ✅ |
| 7 | fs_write | ✅ |
| 8 | fs_list | ✅ |
| 9 | http_get | ✅ |
| 10 | memory_put | ✅ |
| 11 | memory_get | ✅ |
| 12 | memory_search | ✅ |
| 13 | indexer_health | ✅ |
| 14 | doge_tx | ✅ |
| 15 | doginals_inscription | ✅ |
| 16 | compare_inscription | ✅ |
| 17 | parse_drc20 | ✅ |
| 18 | load_fixture | ✅ |

## Source Reachability (2026-08-31)

### Live (returned data)
- **api.doginals.org** — /v1/health OK; inscription endpoints 404 (not public)
- **api.github.com** — OK
- **example.com** — OK

### Blocked (TLS OK, app-layer block)
- **dogechain.info** — HTTP 403 (Cloudflare anti-bot challenge)

### Dead (network-level failure)
- **wonky-ordinals.fly.dev** — DNS resolution failure
- **ordinalswallet.com** — HTTP 522 (connection timeout)
- **api.inception.ai** — TLS alert 112 (CDN SNI reject from AWS IPs)

## Model Provider Status

| Provider | Box | Cloud Local | Notes |
|----------|-----|-------------|-------|
| Ollama | ❌ Not installed | ❌ Not installed | Install locally |
| Inception (Mercury 2) | ✅ **Working** | ✅ **Working** | `https://api.inceptionlabs.ai/v1`, model `mercury-2`. Verified 2026-09-15: live completion, ~0.4–5 s. Reasoning model — give it ≥3500 `max_tokens` or reasoning tokens consume the budget and `content` comes back `null`. |
| OpenAI | ✅ Reachable | ✅ Reachable | Needs key |
| Groq | ✅ Reachable | ✅ Reachable | Needs key |

**Correction (2026-09-15):** earlier status listed Inception as TLS-blocked
(`api.inception.ai`, 525). The working host is **`api.inceptionlabs.ai`** and it
answers normally from the cloud sandbox. `think_box_ai/commands/inception.py`
still only *simulates* calls and does not use this endpoint.

---

## THINKBOXMD-RESEARCH — End-to-End Research Test (2026-09-15)

**Verdict:** 9 PASS / 2 PARTIAL / 0 FAIL.

Ran a real research workflow (`experiments/thinkboxmd_research.py`) with live
Mercury 2 model calls through the existing control fabric: Think Box creation,
five-worker swarm (PHARMA/TOX/VALIDATOR/SAFETY/SYNTH), tiered findings
(EVIDENCE/INFERENCE/HYPOTHESIS/UNVERIFIED), reconciliation, injected-failure
recovery, persistent memory, and hash-chain proof.

- Proof hash: `0723be5ea848a96fa85ad61c7ecf225139dff8efc6d527797fcb1f998c0bd6f5`
- Ledger: 12 entries, chain valid; traces: 9 grounded / 1 ungrounded
- PARTIAL layers: MEMORY (Upstash Vector broken), THINK INTEGRATION (token economy is simulated integers)

Full report: `docs/THINKBOXMD_REPORT.md`.

---

## Swarm Instrumentation Layer (2026-09-15)

**Verdict:** 11/11 checks pass (`python3 experiments/verify_instrumentation.py --live`).

Ten instruments added on SQLite (free, zero-config, always available):
flight recorder, challenge arena, TSSI + learning curve, memory evolution,
proof-carrying decisions, worker reputation, A/B experiments, self-improvement
loop, cost/intelligence efficiency, swarm genome/replay.

- Learning curve observed: **0.6405 → 0.7318 (+0.0913)** across two sessions
- Proof chain + genome both **verify**; tampering is detected
- Dashboard (mobile-first, stdlib, no build step) reads all of it read-only
- Found and fixed a real deadlock in `thinkbox/economy.py::transfer()`
  (`create_account()` called while holding a non-reentrant lock)

Modules: `thinkbox/{metrics,flightrecorder,arena,memory_evolution,reputation,experiments}.py`
Entrypoints: `experiments/{big_swarm,swarm_dashboard,verify_instrumentation,probe_mercury_throughput}.py`
Plan: `docs/DASHBOARD_BUILDOUT.md`

### Measured Mercury 2 throughput (single client, cloud sandbox)

| Concurrency | rps | p50 | errors |
|---|---|---|---|
| 1 | 2.67 | 0.36 s | 0 |
| 4 | 8.98 | 0.39 s | 0 |
| 16 | 17.21 | 0.81 s | 0 |
| 32 | 24.02 | 1.13 s | 0 |
| 64 | 23.67 | 2.01 s | 0 |

Ceiling ≈ **24 rps** from one client (client-bound, not server). 320 workers
complete in ~15 s.

---

## Access Inventory (2026-09-15)

| Service | Env present | Status |
|---------|-------------|--------|
| Inception Mercury 2 | `INCEPTION_API_KEY` | ✅ live and used |
| Upstash Vector | `UPSTASH_VECTOR_REST_URL/TOKEN` | ⚠️ reachable, writes require embedder env |
| Upstash Box | `UPSTASH_BOX_API_KEY`, `UPSTASH_PUBLIC_BOX_URL` | ❌ host reachable, preview `not found` |
| UpCloud `kudbee-host-v1` (212.147.250.183) | `THINKBOX_UPCLOUD_API_TOKEN` | ❌ token 401 invalid; no SSH key; IP behind Cloudflare 1003 |
| Redis | — | ❌ no client, no env |
| MCP | — | ❌ none configured |

**Known defect:** `thinkbox/session.py::UpstashVectorSync.upsert()` cannot write
to a dense index and swallows the error. See
`data/findings/thinkboxmd_upstash_vector_defect.md`.

### Upstash Vector Fix (require embedder env)

`UpstashVectorSync.upsert()` now requires a working embedder. To enable:

```bash
export THINKBOX_OPENAI_COMPAT_API_KEY=sk-your-key       # same key as completion
export THINKBOX_OPENAI_COMPAT_BASE_URL=https://api.inceptionlabs.ai/v1
export THINKBOX_EMBED_MODEL=mercury-2                    # optional, defaults to THINKBOX_DEFAULT_MODEL
```

Post to `{base_url}/embeddings` (OpenAI-compatible endpoint).
If the provider has no `/embeddings` route, set `THINKBOX_OPENAI_COMPAT_API_KEY` to empty
and pass a `DeterministicEmbedder` instance in tests only — never in production.

`DeterministicEmbedder` (hash-based, 1536-dim, stable) is available in `thinkbox/embedder.py`
strictly for unit tests.

---

## How to Run Locally


```bash
git checkout session/agent_79e656bf-37c6-46f2-833e-1eb027b99152
pip install -r backend/requirements.txt

# Option A: Local Ollama
ollama pull llama3.1:8b
python3 -m uvicorn backend.main:app --port 8000 &

# Option B: Groq (free tier)
export THINKBOX_DEFAULT_PROVIDER=openai_compat
export THINKBOX_OPENAI_COMPAT_API_KEY=gsk_your_key
export THINKBOX_OPENAI_COMPAT_BASE_URL=https://api.groq.com/openai/v1
export THINKBOX_DEFAULT_MODEL=llama-3.1-8b-instant
python3 -m uvicorn backend.main:app --port 8000 &

# Run proof
python3 scripts/prove_dogi.py
```

## DOGI Proof Result

**Status:** Partial — tools work, but inscription data inaccessible via public APIs.

See: `data/findings/dogi_indexer_split.md`

## FreeToken Integration

**Status:** Documented, not yet deployed.

See: `data/findings/freetoken_integration.md`

KudbeeZero fork: https://github.com/KudbeeZero/kudbee-freetoken (identical to upstream FlashML).

**Plan:** Run FreeToken on UpCloud GPU spot → point Think Box at its OpenAI-compatible API.

## Key Finding

The indexer-split thesis is **not provable via public APIs alone**. Most inscription
indexers don't expose public endpoints, require auth, or are unreachable. To prove
the thesis, we need a paid API, residential proxy, or local indexer.

## Frontend v1

Landing page, jobs listing, findings browser, job detail, about.
Design system with dark theme, responsive layout, animations.
Pure HTML/CSS/JS — no build step.

Serve: `python3 scripts/serve_frontend.py 8080`
PR: https://github.com/Kudbee-Studio/think-box-ai/pull/58

## Phase 12 — KUDBEE Control Fabric

**Status:** Complete (25 commits, branch `feat/phase12-kudbee-control-fabric`)

New modules in `thinkbox/`:
- `identity.py` — IdentityLedger, capability scopes, policy version
- `governance_token.py` — token issuance, verification, revocation
- `admission.py` — fail-closed AdmissionGate
- `workspace.py` — Think Box registry + SQLite store
- `handoff.py` — cross-substrate handoff with integrity hashing
- `occupancy.py` — OccupancyMonitor, MeshCellManager (horizontal isolation)
- `capacity.py` — elastic CapacityController
- `ledger.py` — append-only tamper-evident ActionLedger
- `thinktrace.py` — ThinkTraceCapture (grounded vs ungrounded)
- `governed.py` — admission-gated GovernedEngine

New tests: identity, token, admission, workspace, workspace store, handoff,
occupancy, mesh, capacity, ledger, thinktrace, governed + control-fabric E2E.

Test count: **266 tests passing**.

## Disruptor + Verifier Evaluation Harness

**Status:** Complete (branch `feat/disruptor-evaluation`)

New modules in `thinkbox/`:
- `disruptor.py` — `DisruptorPass`, `DisruptorSuite` (adversarial pass framework)
- `verifier.py` — `Verifier`, `EvalHarness`, `VerificationReport`

Standard suite: 12 passes covering token forgery/expiry/revocation/mismatch,
capability escalation, cell hopping (blast radius), grounding detection,
contrast pairs, elastic capacity contraction, ledger tamper evidence, and
Think Box handoff integrity.

Measured result (live fabric): **12/12 passes, overall 1.0, verdict STRONG**.

See `docs/disruptor-evaluation.md`.

Test count: **294 tests passing**.

## THINK Burst Protocol

**Status:** Complete (branch `feat/disruptor-evaluation`)

New modules:
- `thinkbox/burst.py` — `BurstRunner`, `BurstBudget` (elastic-cash stub), `LiveVLLMClient`
- `thinkbox/reasoning.py` — `ReasoningNormalizer`, `capture_completion`

Burst runner produces grounded vs disruptor contrast pairs, captures the
`openai/gpt-oss-20b` reasoning channel, records the governance token id,
and hard-stops on calls/spend/time. Refuses to start without a valid token.

Docs: `docs/think-burst-protocol.md`. Offline demo: `examples/think_burst_demo.py`.

Test count: **325 tests passing**.

## Harvest & Replay

**Status:** Complete (branch `feat/disruptor-evaluation`)

New modules:
- `thinkbox/grounding.py` — `GroundingScorer` (deterministic evidence/numeric/reasoning scoring)
- `thinkbox/factcards.py` — `FactCardRegistry` (least-used-first coverage scheduling)
- `thinkbox/harvest.py` — `HarvestReplay`, `HarvestReport` (score jsonl offline; optional Verifier bridge)

`BurstRunner` now writes `evidence_text` and appends every admitted call to
the append-only `ActionLedger` (`ledger_valid` hash-chain check).

Offline: `data/evals/burst/*.jsonl`, `data/evals/harvest_report.{md,json}`.

Test count: **348 tests passing**.
