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

## KUDBEE Control Fabric

Governance admission + portable workspaces + occupancy-based security, as a
single fabric above any model session (see the KUDBEE white paper and
`docs/kudbee-control-fabric.md`).

```bash
python3 examples/control_fabric_demo.py
```

Modules: `identity`, `governance_token`, `admission`, `workspace`, `handoff`,
`occupancy`, `capacity`, `ledger`, `thinktrace`, `governed`.

### Disruptor + Verifier evaluation

Automated adversarial evaluation of the fabric — *measured refusal and
containment under disruptor load* (see `docs/disruptor-evaluation.md`).

```python
from thinkbox.verifier import EvalHarness

report = EvalHarness().run()
print(report.metrics.verdict, report.metrics.overall_score)
```

Modules: `disruptor` (pass framework), `verifier` (metrics, reports, harness),
`reasoning` (preserves the `openai/gpt-oss-20b` reasoning channel).

### THINK burst protocol

Short bounded GPU windows on `openai/gpt-oss-20b` become high-signal
contrast pairs (grounded vs disruptor twin), captured to jsonl with
reasoning, scored, and capped by an elastic-cash ceiling.

```bash
python3 examples/think_burst_demo.py                 # offline, no GPU
python3 -m thinkbox.burst --live --pairs 24 --minutes 12 --budget 5.00
```

See `docs/think-burst-protocol.md`.

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
├── docs/                      # Architecture and project documentation
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

Current test count: **325 tests** (all passing)

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
