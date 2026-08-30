# THINK BOX AI — Project Foundation

**Status:** Phase 0 — Foundation (verified 2026-08-30)
**Date:** 2026-08-20
**Repository:** `Kudbee-Studio/think-box-ai`
**Inspection Report:** See `docs/inspection-report-2026-08-30.md`

---

## 1. Current State

The repository contains two parallel systems:

1. **`core/` — Phase 0 Python runtime** (complete, tested, stdlib-only)
2. **`backend/` + `apps/web/` — Stage 1 FastAPI web app** (code exists, deps NOT installed)

### What exists (verified 2026-08-30)

| Item | State | Location |
|------|-------|----------|
| Think Token logic | Implemented | `think_box_ai/token.py` |
| Token CLI | Minimal (`--version`, `--info`) | `think_box_ai/cli.py` |
| Foundation layer (config, logging, errors, bootstrap) | Complete | `core/foundation/` |
| Memory layer (SQLite + 3 adapters + schemas) | Complete | `core/memory/` |
| Governance layer (audit, permissions, approval) | Complete | `core/governance/` |
| Provider layer (protocol + OpenAI-compatible) | Partial | `core/providers/` |
| Tool registry + 5 built-in tools | Complete | `core/tools/` |
| Agent runtime (Agent/ThinkBox/Planner/Actor/Observer) | Skeleton | `core/runtime/` |
| FastAPI backend + WebSocket + SSE | Code exists, not runnable | `backend/main.py` |
| Backend plugins (6 tools) | Code exists | `backend/plugins/` |
| Ollama streaming client | Code exists, needs aiohttp | `backend/models/ollama_client.py` |
| Frontend (vanilla HTML/CSS/JS) | Code exists | `apps/web/public/` |
| Unit + integration tests | 23/24 pass | `tests/unit/`, `tests/integration/` |

### Verified environment (2026-08-30)

| Resource | Value |
|----------|-------|
| Python | 3.10.12 |
| pip | NOT available |
| External packages | NONE installed (no aiohttp, fastapi, pydantic, upstash-box) |
| Tests passing | 23/24 (test_token.py fails — no pytest) |
| Bootstrap | Works — registers 5 tools, provider=None |

### What does NOT exist (and should not be assumed)

- No agent framework is vendored or copied.
- No AI model is downloaded or embedded.
- No microservices are scaffolded.
- No KUDBEE protocol implementation (THINK primitives, HATS, COMMONS, SWARM).
- No Upstash Box SDK installed.
- No UpCloud integration code.
- No connection between `core/` and `backend/` systems.

---

## 2. Detected Environment

### Runtime (verified 2026-08-30)

| Tool | Version | Path |
|------|---------|------|
| Python | 3.10.12 | `/usr/bin/python3` |
| pip | NOT available | — |
| Node.js | v22.22.3 | `/usr/local/bin/node` |
| npm | 10.9.8 | `/usr/local/bin/npm` |
| Bun | 1.3.12 | `/usr/local/bin/bun` |
| Git | 2.55.0 | `/usr/bin/git` |

### Hardware (container)

| Resource | Value |
|----------|-------|
| CPUs | 4 |
| RAM | 12 GB |
| Disk | 18 GB total, 17 GB available |

### Network

- Outbound HTTPS is available.
- GitHub remote: `https://github.com/Kudbee-Studio/think-box-ai.git`

### Available Python libraries (verified 2026-08-30)

**Standard library only.** No external packages installed:

- `aiohttp` — NOT installed
- `fastapi` — NOT installed
- `pydantic` — NOT installed
- `upstash-box` — NOT installed
- `httpx` — NOT installed
- `pytest` — NOT installed
- `pydantic` — NOT installed
- `llama-index` — NOT installed
- `langchain` — NOT installed
- `llama-cpp-python` — NOT installed
- `ollama` — NOT installed

### Provisioned Cloud Resources (verified 2026-08-30)

| Resource | Type | Status |
|----------|------|--------|
| Upstash Box | Sandbox container | Provisioned (API key + URL set), SDK NOT installed |
| UpCloud GPU | GPU server | API token set, SSH key NOT provisioned to this container |

---

## 3. Language Choice

**Primary language: Python.**

Rationale:

1. AI/ML ecosystem, tooling, and research are predominantly Python.
2. The runtime already ships Python 3.10.
3. Python's standard library is sufficient to prototype the agent runtime
   without external dependencies.
4. Python has first-class support for async I/O (`asyncio`), which is
   required for concurrent tool execution and streaming model calls.

**Secondary: TypeScript/Node** for the CLI wrapper and any future web
frontend. This is deferred. The core must be runnable from Python first.

**Not chosen:** Go, Rust, or other compiled languages. They add deployment
friction and slow iteration on a system whose shape is not yet known.

---

## 4. Dependencies

### Phase 0 — Zero external dependencies

The foundation must run with **Python standard library only**. This is a
deliberate constraint:

- It proves the architecture works without magic.
- It avoids dependency rot before the design stabilizes.
- It makes the system trivially installable.

### Phase 1+ — Planned (added only when needed)

| Dependency | Trigger | Purpose |
|------------|---------|---------|
| `pydantic` | When schemas need validation | Config + event schema validation |
| `httpx` | When HTTP providers ship | Async HTTP client for cloud models |
| `sqlite3` | Built-in | Task/memory persistence (stdlib has it) |
| `numpy` | When embeddings are needed | Vector memory / similarity search |
| `sentence-transformers` | When local embeddings ship | Bounded-context embeddings |

**Rule:** Every dependency must justify itself with a concrete Phase. No
"maybe we'll need it" imports.

---

## 5. Assumptions

These are assumptions, not facts. They must be validated or revised as the
system evolves.

| # | Assumption | Validation |
|---|-----------|------------|
| A1 | An agent runtime can be expressed as a pure loop: goal → plan → act → observe → remember | Build a prototype and measure |
| A2 | Memory can be separated into session / task / organizational layers | Implement and observe retention needs |
| A3 | Provider abstraction can be a thin interface over OpenAI-compatible APIs | Implement 2 providers and verify swap cost |
| A4 | Tool governance can be expressed as a permission model + audit log | Implement and test bypass attempts |
| A5 | Local models will be used eventually; they are not required for Phase 1 | Track when model portability becomes a blocker |
| A6 | The system does not need a UI to be useful in Phase 1 | Revisit when UX becomes the bottleneck |

---

## 6. Security Concerns

### Immediate (verified 2026-08-30)

1. **No secrets in this repo.** No `.env`, no API keys, no credentials in code.
   Secrets are injected via environment variables at runtime only.

2. **API keys in container environment.** The following are set as env vars
   in the sandboxed container: `UPSTASH_BOX_API_TOKEN`, `THINKBOX_UPCLOUD_API_TOKEN`,
   `GH_TOKEN`, `KILO_AUTH_CONTENT`. These are ephemeral to this container but
   must not be logged, committed, or exposed.

3. **No pip available.** Cannot install dependencies without bootstrapping pip
   first (`python3 -m ensurepip`).

### Architectural (future)

- Tool execution must run in a permission-checked sandbox.
- Audit logs must be append-only and tamper-evident.
- Memory writes must be attributable to a specific agent + task.

---

## 7. Architecture Notes (verified 2026-08-30)

### Two Parallel Systems

The codebase contains two disconnected systems:

1. **`core/`** — Pure Python agent runtime (Phase 0). Stdlib-only, fully tested.
   Uses `bootstrap()` to create a `RuntimeContext` with memory, governance,
   tools, and optional provider. The Planner, Actor, and Observer classes
   exist but are not yet model-driven (Planner returns a hardcoded step,
   Actor returns mock results).

2. **`backend/` + `apps/web/`** — FastAPI web app (Stage 1). Requires external
   dependencies (fastapi, uvicorn, aiohttp, pydantic). Has its own tool system
   (`backend/plugins/`) that duplicates the `core/tools/` concepts. Connects
   to a vanilla JS frontend via WebSocket.

**These systems are not connected.** `backend/main.py` does not import from
`core/`. They share no code, no memory store, no tool registry.

### KUDBEE Direction (documented intent, not yet implemented)

The KUDBEE vision extends beyond the current implementation:

- **THINK Protocol**: opportunity → outcome (broader than MCP)
- **Primitives**: Intent, Opportunity, Capability, Swarm, Outcome, Proof
- **Think Boxes**: isolated agent execution environments (currently a dataclass, not an environment)
- **THINK HATS**: professional capabilities
- **THINK COMMONS**: governed, provenance-aware collective intelligence
- **THINK SWARM**: coordinates/competes capabilities
- **Execution substrates**: Upstash Box, Firecracker, UpCloud GPU, local/external runtimes

None of these are implemented in code. They are architectural intent documented
for future phases.

---

## 8. What This Document Is

This is a **snapshot**, not a spec. It records what was found at the moment of
initialization and verified on 2026-08-30. It will be revised when reality
contradicts it.

**Next step:** `docs/architecture-v1.md` translates these findings into a
design. `docs/inspection-report-2026-08-30.md` contains the full inspection
details.