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

```bash
# run a swarm with the instrumented path
python3 experiments/big_swarm.py --primary 256 --validators 64 --concurrency 32 --arena

# verify all ten instruments (add --live for a real end-to-end swarm)
python3 experiments/verify_instrumentation.py --live

# view it (mobile-first, stdlib server, no build step)
python3 experiments/swarm_dashboard.py --port 8787
cloudflared tunnel --url http://127.0.0.1:8787
```

Verified 2026-09-15: `11/11` instrumentation checks pass; learning curve
observed `0.6405 → 0.7318 (+0.0913)` across two sessions; ledger and proof
chains verify. Connect-it-up plan: `docs/DASHBOARD_BUILDOUT.md`.

### THINK BOX Command Center v2

The ten instruments above, made observable across ten surfaces in one stdlib
process: Swarm Command, Causal Trace, Proof Explorer, Learning, Arena Replay,
Memory Evolution, Worker Reputation, Cost × Intelligence, Genome/Replay, and
Mission Control.

```bash
python3 experiments/swarm_dashboard.py --port 8787
cloudflared tunnel --url http://127.0.0.1:8787
```

Details, traceability rules and honest limitations: `docs/COMMAND_CENTER.md`.

### Agent work templates

The procedure for a class of agent work is versioned, not prompted. A template
branch carries the contract; a feature branch is one execution of it.

```bash
python3 scripts/agent_work.py list
python3 scripts/agent_work.py check  --template dashboard-evolution
python3 scripts/agent_work.py verify --template dashboard-evolution
```

See `docs/agent-templates/README.md`. Templates are long-lived remote branches
(`agent-template/*`) and are not merged into `main`.

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

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) and
[AGENTS.md](AGENTS.md) before opening a pull request.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
