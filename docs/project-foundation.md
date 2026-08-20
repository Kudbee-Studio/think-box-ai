# THINK BOX AI — Project Foundation

**Status:** Phase 0 — Foundation
**Date:** 2026-08-20
**Repository:** `Kudbee-Studio/think-box-ai`

---

## 1. Current State

The repository is a **blank slate**. A single initial commit contains only a
`README.md` with the project name. There is no existing code, no configuration
files, no dependencies, and no tests.

This is intentional. The goal of Phase 0 is to build a **correct architectural
foundation**, not a feature-complete product.

### What exists

| Item | State |
|------|-------|
| Code | None |
| Tests | None |
| Configuration | None |
| Dependencies | None |
| Documentation | Only a title in README |
| Git history | Single initial commit on `main` |
| Remote | `origin` → `Kudbee-Studio/think-box-ai` (GitHub) |

### What does NOT exist (and should not be assumed)

- No agent framework is vendored or copied.
- No AI model is downloaded or embedded.
- No microservices are scaffolded.
- No UI exists. UI is explicitly deferred.

---

## 2. Detected Environment

### Runtime

| Tool | Version | Path |
|------|---------|------|
| Python | 3.10.12 | `/usr/bin/python3` |
| Node.js | v22.22.3 | `/usr/local/bin/node` |
| npm | 10.9.8 | `/usr/local/bin/npm` |
| Bun | 1.3.12 | `/usr/local/bin/bun` |
| Git | 2.55.0 | `/usr/bin/git` |

### Hardware

| Resource | Value |
|----------|-------|
| CPUs | 4 |
| RAM | 12 GB |
| Disk | 18 GB total, 17 GB available |

### Network

- Outbound HTTPS is available (pypi.org reachable).
- GitHub remote is authenticated via a personal access token embedded in the
  remote URL. Treat this as a **security concern** (see Risks).

### Available Python libraries (system)

Standard library plus OS-level packaging tools only. **No AI/ML libraries**
are installed:

- `pydantic` — NOT installed
- `llama-index` — NOT installed
- `langchain` — NOT installed
- `llama-cpp-python` — NOT installed
- `ollama` — NOT installed

### Available Node packages (global)

- `@kilocode/cli` (the tool running this session)
- `corepack`, `npm`, `pnpm`

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

### Immediate

1. **Token in remote URL.** The `origin` remote contains a GitHub personal
   access token in the URL. This is a **credential leak risk**. It must be
   removed from the config and rotated on GitHub. Do not commit it further.

2. **No secrets in this repo.** No `.env`, no API keys, no credentials. Any
   secret must be injected at runtime via environment variables or a
   secrets manager, never stored.

3. **LFS filter configured.** Git LFS is set in `.git/config`. Large binary
   artifacts (models, datasets) must go through LFS if committed at all.
   Prefer not committing models.

### Architectural (future)

- Tool execution must run in a permission-checked sandbox.
- Audit logs must be append-only and tamper-evident.
- Memory writes must be attributable to a specific agent + task.

---

## 7. What This Document Is

This is a **snapshot**, not a spec. It records what was found at the moment of
initialization. It will be revised when reality contradicts it.

**Next step:** `docs/architecture-v1.md` translates these findings into a
design.