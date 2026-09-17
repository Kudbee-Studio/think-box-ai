# Think Box AI — Agent Execution Environment

**Think Box AI** is an agent execution environment that decomposes goals,
executes bounded reasoning loops, uses tools, records outcomes, and improves
over time.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Phase Progress](#phase-progress)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Think Box AI is an AI-driven agent execution platform. It uses:

- **Think Token (THNK)** — native utility token for rewards, staking, and governance
- **Multi-Model Consensus** — aggregate outputs from multiple LLMs with Bayesian confidence scoring
- **Agent Coalition Protocol** — CRDT-based shared memory, task bidding markets, and pub/sub coordination
- **Token Economy** — contribution mining, staking, and slash conditions for agent incentives
- **Self-Healing** — automated bug patching, regression detection, and circuit breakers
- **Knowledge Graph** — concept extraction, semantic search, and memory consolidation
- **Federated Learning** — multi-agent model aggregation with gradient compression and differential privacy
- **Post-Quantum Security** — Kyber KEM, Dilithium signatures, and hybrid handshakes

---

## Architecture

The system follows a layered architecture (see `docs/architecture-v1.md`):

```
Layer 5: Agent Implementations
Layer 4: Agent Runtime (Engine, Decomposer, Swarm, Autoscaler)
Layer 3: Tool Registry & Governance (Security, Permissions, Audit)
Layer 2: Memory Subsystem (Session, Task, Organizational)
Layer 1: Provider Abstraction (OpenAI-compatible, Anthropic, Local)
Layer 0: Foundation (Config, Schemas, Logging, Errors)
```

Phase 9 adds new subsystems:
- `thinkbox/coalition.py` — Multi-agent coordination protocols
- `thinkbox/consensus.py` — Cross-model consensus and confidence scoring
- `thinkbox/economy.py` — Agent token economy and governance
- `thinkbox/intelligence.py` — Knowledge graph, self-healing, reputation, federated learning, post-quantum security

---

## Phase Progress

| Phase | Status | Description |
|-------|--------|-------------|
| 0 | Complete | Foundation: config, logging, error handling |
| 1 | Complete | Single agent, single provider, 5 tools |
| 2 | Complete | Provider independence, pattern extraction |
| 3 | Complete | Security: auth, CORS, rate limiting, path jail |
| 4 | Complete | DAG task decomposition, async model client |
| 5 | Complete | Autoscaler, pruner, git engine |
| 6 | Complete | Unified engine pipeline, API router, CLI |
| 7 | Complete | Dynamic Token Whip Protocol |
| 8 | Complete | Session tracking with Upstash Vector sync |
| 9 | **Complete** | Coalition, consensus, economy, intelligence (55 innovations) |
| 12 | **Complete** | KUDBEE control fabric: identity, governance tokens, Think Boxes, occupancy mesh, ledger, think traces |
| — | **Verified** | THINKBOXMD-RESEARCH end-to-end research workflow (live model, swarm, proof) — `docs/THINKBOXMD_REPORT.md` |

### Honest capability notes

- **Live model provider:** Inception **Mercury 2** works from the cloud sandbox
  (`api.inceptionlabs.ai/v1`). OpenAI-compatible and Ollama providers exist;
  Anthropic is **not implemented**. Both existing providers raise
  `NotImplementedError` for `embed()`.
- **Simulated, not settled:** the token economy (`thinkbox/economy.py`) moves
  integers in a dict — no chain, no settlement. "Minting" is conceptual.
- **Not built:** MCP client/server, Upstash Redis client, Upstash Box execution
  client (metadata only), `benchmarks/` evidence, `tests/e2e/` tests, `mayor`.
- **Known defect:** Upstash Vector writes fail against the dense index
  (`data/findings/thinkboxmd_upstash_vector_defect.md`).

## KUDBEE Control Fabric

Governance admission + portable workspaces + occupancy-based security, as a
single fabric above any model session (see the KUDBEE white paper and
`docs/kudbee-control-fabric.md`).

```bash
python3 examples/control_fabric_demo.py
```

Modules: `identity`, `governance_token`, `admission`, `workspace`, `handoff`,
`occupancy`, `capacity`, `ledger`, `thinktrace`, `governed`.

### THINKBOXMD-RESEARCH — end-to-end research test

`experiments/thinkboxmd_research.py` runs a **real** research workflow with live
model calls through the control fabric: Think Box creation, a five-worker swarm
(`PHARMA`, `TOX`, `VALIDATOR`, `SAFETY`, `SYNTH`), tiered findings
(`EVIDENCE` / `INFERENCE` / `HYPOTHESIS` / `UNVERIFIED`), reconciliation, an
injected-failure recovery test, persistent memory, and a hash-chain proof.

```bash
python3 experiments/thinkboxmd_research.py     # stdlib only; needs INCEPTION_API_KEY
```

Latest run: 9 PASS / 2 PARTIAL / 0 FAIL. Report: `docs/THINKBOXMD_REPORT.md`.

**Research/infrastructure test only — not clinical advice. Synthetic scenarios only.**

### Swarm Instrumentation — experimental layer for collective AI behaviour

Ten instruments, all on SQLite (stdlib, free, zero-config, always available),
turning a swarm run into a measurable experiment rather than a spectacle:

| # | Instrument | Module |
|---|-----------|--------|
| 1 | **Flight Recorder** — permanent per-worker record | `thinkbox/flightrecorder.py` |
| 2 | **Challenge Arena** — adversarial traps + detection/recovery rates | `thinkbox/arena.py` |
| 3 | **Strength Index + learning curve** | `thinkbox/metrics.py` |
| 4 | **Memory Evolution** — created/reinforced/contradicted/corrected/promoted/decayed | `thinkbox/memory_evolution.py` |
| 5 | **Proof-Carrying Decisions** — verifiable claim→…→proof chain | `thinkbox/flightrecorder.py` |
| 6 | **Worker Reputation** — from demonstrated validation accuracy | `thinkbox/reputation.py` |
| 7 | **A/B Experiments** — configs as the experimental variable | `thinkbox/experiments.py` |
| 8 | **Self-Improvement Loop** — weakest component → change → retest → accept/reject | `thinkbox/experiments.py` |
| 9 | **Cost / Intelligence Efficiency** — cost per validated insight | `thinkbox/experiments.py` |
| 10 | **Swarm Genome / Replay** — configuration hash for exact reproduction | `thinkbox/flightrecorder.py` |

**THINK Swarm Strength Index (TSSI)** is a weighted mean of six measured ratios
(reliability, grounding, evidence quality, challenge resolution, validator
calibration, reproducibility). Challenge activity and tier inflation are
**reported as signals, never penalised** — disagreeing is the adversarial layer
doing its job.

### Execution substrate (2026-09-17 decision)

- **Upstash Box = primary execution substrate** — selected from env (`UPSTASH_PUBLIC_BOX_URL` first; never hard-coded). Think Jobs execute in-Box with SQLite persistence, Vector snapshots, ledger proof, and dashboard events.
- **UpCloud = infrastructure / control-plane ONLY** (read-only REST). No UpCloud machine execution, no GPU execution, no SSH — removed from the roadmap.
- Proof: `data/thinkboxmd/artifacts/box_primary_proof_20260917.json` (Box job + restart + identical replay verified; model execution not yet verified).

### Experiment + Learning Dashboard

Persistent, zero-server experiment tracking with SQLite persistence and
parameter provenance. Every agent run becomes a tracked experiment with
durable session ID, inputs, execution evidence, outputs, tests, outcome,
and learned parameters.

**Learning loop**: Intent → Hypothesis → Parameters → Plan → Execute → Test →
Artifact → Proof → Outcome → Learn → Updated Parameters → Next Experiment.

**Four-state classification**: CODE_COMPLETE, TEST_VERIFIED, LIVE_VERIFIED, PRODUCTION_READY.

**Key features**:
- SQLite persistence (stdlib, zero-dollar)
- Parameter provenance with source, confidence, classification
- Parent/child session relationships
- Restart/recovery from SQLite
- Dashboard aggregation from persisted data
- Zero-server execution (no Docker, SSH, cloud required)

```bash
python3 -m unittest tests.unit.test_experiment -v
```

---

## Getting Started

### Prerequisites

- Python ≥ 3.10
- [pip](https://pip.org/)

### Installation

```bash
# Clone the repository
git clone https://github.com/Kudbee-Studio/think-box-ai.git
cd think-box-ai

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Set API key (required)
export THINKBOX_API_KEY=$(python -c "import secrets; print('tb_' + secrets.token_urlsafe(32))")
```

### Running the engine

```bash
# Run a goal through the engine
python -m thinkbox.cli run --goal "Build a simple web server"

# Run the benchmark suite
python -m thinkbox.cli benchmark --workers 16,64,128,256,512
```

---

## Project Structure

```
think-box-ai/
├── thinkbox/                  # Core execution engine package
│   ├── __init__.py            # Package exports
│   ├── engine.py              # Unified pipeline wiring
│   ├── decomposer.py          # DAG task decomposition
│   ├── model_client.py        # Async model client
│   ├── swarm.py               # Speculative execution pool
│   ├── autoscaler.py          # Dynamic worker scaling
│   ├── pruner.py              # Context pruning
│   ├── git_engine.py          # Auto-commit for verified results
│   ├── session.py             # Session tracking + Upstash Vector sync
│   ├── whip.py                # Dynamic Token Whip Protocol
│   ├── benchmark.py           # High-throughput benchmark suite
│   ├── coalition.py           # Phase 9: CRDT memory, task market, governance
│   ├── consensus.py           # Phase 9: multi-model voting, confidence scoring
│   ├── economy.py             # Phase 9: token economy, contribution mining
│   ├── intelligence.py        # Phase 9: KG, self-healing, reputation, FL, PQC
│   └── cli.py                 # CLI entrypoint
├── core/                      # Core runtime (Phase 0-3)
│   ├── foundation/            # Config, logging, errors, bootstrap
│   ├── providers/             # Model provider abstraction
│   ├── tools/                 # Built-in tool registry
│   ├── memory/                # Session, task, organizational memory
│   ├── runtime/               # Agent, ThinkBox, Planner, Actor, Observer
│   └── governance/            # Audit, permissions, approval gates
├── backend/                   # Backend API (security-hardened)
│   ├── main.py                # FastAPI app with timeouts, session limits
│   ├── security.py            # Strict auth, CORS, rate limiting
│   ├── audit_storage.py       # SQLite audit log with session tracking
│   └── api/v1/router.py       # API v1 endpoints
├── tests/
│   ├── unit/                  # Unit tests (no I/O, no network)
│   ├── integration/           # Integration tests
│   └── e2e/                   # End-to-end tests
├── experiments/               # End-to-end proof experiments
│   ├── kudbee_orchestrator.py # Autonomous proof-of-work loop + interrupt/resume
│   ├── thinkboxmd_research.py # THINKBOXMD-RESEARCH research workflow test
│   └── test_interrupt_resume.py
├── docs/                      # Architecture and project documentation
│   └── THINKBOXMD_REPORT.md   # Latest end-to-end research report
├── AGENTS.md                  # Development rules
├── STATUS.md                  # Phase progress tracker
├── PHASE9_INDEX.md            # Phase 9 innovations index
└── README.md
```

---

## Testing

```bash
# Run all tests
python3 -m unittest discover tests/

# Run specific test modules
python3 -m unittest tests.unit.test_session_tracker
python3 -m unittest tests.unit.test_phase1_2_security
python3 -m unittest tests.unit.test_whip_protocol
python3 -m unittest tests.integration.test_e2e_engine
```

Current test count: **275 tests** (all passing)

---

## TypeScript 7 (apps/web)

The web runtime is TypeScript, checked with the **TypeScript 7 native compiler**
(`tsgo`, ~10x faster than the JS compiler on large codebases).

```bash
cd apps/web
npm install
npm run typecheck      # tsgo --noEmit  (TypeScript 7 native)
npm run typecheck:tsc  # tsc  --noEmit  (classic, for comparison)
npm start              # runs server.ts via Node 22 type stripping
```

- `strict` mode enabled; `noEmit` typecheck.
- Sources: `server.ts`, `services/plugins.ts`, shared types in `types.ts`.
- Node ≥ 22.6 runs the `.ts` files directly via `--experimental-strip-types`
  (no build step required).

---

## Demo in 10

Run the full burst→harvest→scores loop in under 10 minutes. No GPU, no public bind, no AWS.

```bash
bash scripts/demo_in_10.sh
```

What it does:
1. Starts mock vLLM on `127.0.0.1:8001` (deterministic responses, no API key needed)
2. Runs `python3 -m thinkbox.burst --live --pairs 2 --minutes 1 --max-calls 8 --budget 1.0 --out data/evals/burst-smoke`
3. Harvests and replays the burst output: `python3 -m thinkbox.harvest --dir data/evals/burst-smoke`
4. Prints groundedness / bind-failure / reasoning coverage

### What you'll see

| Metric | Meaning |
|--------|---------|
| **Contrast pairs** | Grounded vs ungrounded twins per question |
| **Reasoning coverage** | % of records with captured reasoning channel |
| **Groundedness score** | How often grounded answers are correctly scored grounded |
| **Bind-failure rate** | How often ungrounded answers are correctly rejected |
| **Budget spent** | Elastic-cash ceiling per burst (default $1.00) |

The mock server and burst/harvest modules are shared infrastructure — see `thinkbox/mock_vllm.py`, `thinkbox/burst.py`, `thinkbox/harvest.py`. Do not duplicate.

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) and
[AGENTS.md](AGENTS.md) before opening a pull request.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
