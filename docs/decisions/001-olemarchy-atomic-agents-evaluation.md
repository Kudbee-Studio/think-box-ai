# ADR 001: Atomic Agents (OLEMARCHY) Evaluation for Think Box Execution

**Date:** 2026-08-29
**Status:** Deferred — Requires clarification from user
**Deciders:** KUDBEE Architecture Team

---

## Context

The KUDBEE Think Box AI team is evaluating **Atomic Agents** (GitHub user `olemarch`'s fork of `Eigenwise/atomic-agents`; referred to internally as "OLEMARCHY") as a potential standard component inside every Think Box execution environment.

The project's existing architecture is defined in `docs/architecture-v1.md` and operationalized via `AGENTS.md`. It uses a 5-layer architecture:
- **Foundation** (config, schemas, logging, errors)
- **Provider** (model interface: OpenAI-compatible, Anthropic, local)
- **Memory** (session, task, organizational, verified knowledge)
- **Governance/Tools** (tool registry, permission checks, audit log, approval gates)
- **Runtime** (execution loop, Think Box, Planner, Actor, Observer, Improvement)

Phase 0 constraint: Python standard library only. No external dependencies without a documented trigger (see `docs/project-foundation.md` §4).

Phase 1 boundary: Single agent, single provider, 5 tools, no multi-agent, no benchmarks, no UI.

The current execution boundary uses Firecracker microVMs on an UpCloud managed Kubernetes node (`kudbee-host-v1`). The question is whether Atomic Agents can serve as the agent runtime layer within each isolated microVM.

---

## What is Atomic Agents (OLEMARCHY)?

### Summary

Atomic Agents is a Python-based, schema-driven AI agent framework (MIT licensed, 6.2k+ stars on GitHub) built on top of:
- **Instructor** — typed structured output for LLM calls
- **Pydantic v2** — input/output schema validation and serialization
- **Rich** — terminal output formatting
- **Textual** — TUI components
- **litellm** — multi-provider LLM routing
- **MCP** — tool integration via Model Context Protocol

**Repository:** https://github.com/Eigenwise/atomic-agents
**Forked by:** https://github.com/olemarch/atomic-agents-bio (user "olemarch" → "OLEMARCHY")
**Current version:** v2.10.2 (as of August 2026)
**Python requirement:** 3.12+ (requires modern Python features)
**License:** MIT

### What problem it solves

Atomic Agents addresses the lack of control and predictability in existing agent frameworks (LangGraph, CrewAI, AutoGen). It enforces:

1. **Typed schemas:** Every agent input/output is a Pydantic `BaseIOSchema` with required docstrings and field descriptions — both flow into the LLM prompt, making behavior more predictable.
2. **Composability:** Agents, tools, and context providers are "atomic" — single-purpose, reusable, swappable components wired into pipelines.
3. **Modularity:** Clear separation between system prompt, history, context providers, and tool execution.
4. **Testing:** Strongly-typed outputs enable unit testing individual agents by mocking outputs.

The framework includes:
- `AtomicAgent` class with sync/async/streaming execution (`run`, `run_async`, `run_stream`, `run_async_stream`)
- `AgentConfig` for client, model, history, system prompt, model API parameters
- `ChatHistory` for turn-based conversation management with automatic message management, overflow handling, serialization
- `SystemPromptGenerator` with background, steps, output instructions, and dynamic context providers
- `BaseTool` for tool wrapping with Instructor-based tool calling
- `BaseDynamicContextProvider` for injecting runtime context into system prompts
- Hooks system for monitoring, error handling, and retry mechanisms
- `atomic-assembler` CLI for tool management

### Resource Requirements

From `pyproject.toml` dependencies:
- `instructor==1.14.5` (pulls in httpx, pydantic, etc.)
- `pydantic>=2.11.0,<3.0.0`
- `rich>=13.7.1,<14.0.0`
- `gitpython>=3.1.43,<4.0.0`
- `pyfiglet>=1.0.2,<2.0.0`
- `textual>=5.3.0,<6.0.0`
- `pyyaml>=6.0.2,<7.0.0`
- `requests>=2.32.3,<3.0.0`
- `mcp[cli]>=1.6.0`
- `litellm>=1.50.0,<2.0.0`

**Estimated dependency footprint:** ~150-200MB disk (dominated by pydantic, litellm, textual, mcp, gitpython).
**Memory at idle:** ~50-100MB Python process.
**CPU:** Minimal at idle; LLM calls are I/O-bound.
**Python version:** Requires 3.12+ (KUDBEE Phase 0 targets 3.10+, current node has Python 3.10.12).

### Docker Deployment Support

The documentation includes a Dockerfile example using `python:3.12-slim` base, and a Docker Compose example with:
- 512MB memory limit per replica
- Redis for persistence
- 3 replicas for scaling

This indicates the framework is designed to run in containerized environments and explicitly supports resource-constrained deployments.

---

## Evaluation Against KUDBEE Requirements

### 1. What OLEMARCHY actually is and what problem it solves

**Assessment:** Atomic Agents is a typed, modular Python agent framework that enforces schema-driven agent behavior through Pydantic + Instructor. It solves the problem of unpredictability in agent outputs by making all inputs/outputs strictly typed with documentation that flows into prompts.

**Fit:** High conceptual alignment. KUDBEE's architecture (§4.2) already emphasizes typed schemas ("Every tool is a stateless function with a declarative schema"). Atomic Agents extends this philosophy to the agent layer itself.

### 2. Whether it can run inside an isolated Firecracker-based Think Box

**Assessment:** **Conditionally yes.** Atomic Agents is a pure Python package (no C extensions that would require specific kernel features). It can run inside a Firecracker microVM.

Key considerations:
- **Python 3.12+ requirement:** The current host node has Python 3.10.12. This would need Python 3.12+ inside the microVM rootfs.
- **No native dependencies:** All dependencies are pure Python, making packaging straightforward.
- **MicroVM compatibility:** No special kernel modules, no hardware acceleration needed, no privileged ports.
- **Local model support:** Supports Ollama for local inference, which can run within a microVM.
- **MCP support:** Built-in MCP client support via the `mcp[cli]` package.

**Risk:** The Python 3.12+ requirement conflicts with the Phase 0 constraint of Python 3.10+. This would either require upgrading the host or building microVMs with Python 3.12.

### 3. Resource requirements on 4-vCPU/8-GB UpCloud box

**Host specs (from docs/project-foundation.md):**
- 4 CPUs, 12 GB RAM, 18 GB disk (17 GB available)
- Firecracker microVMs are lightweight: ~5MB memory overhead per VM when idle

**Atomic Agents footprint:**
- ~150-200MB disk for dependencies
- ~50-100MB RAM at idle per agent process
- Minimal CPU when idle

**Verdict:** Practically feasible. With 12GB RAM and 17GB disk available:
- Each Firecracker microVM with Atomic Agents: ~120-150MB RAM (microVM + Python process + deps)
- Can comfortably run 20-40 concurrent isolated Think Box microVMs
- Disk space allows ~80-115 microVMs with deps cached
- CPU is sufficient for I/O-bound LLM calls (actual compute happens on GPU/remote)

**Constraint:** If each microVM needs Python 3.12, the rootfs image grows by ~30-50MB per VM (or use a shared overlay).

### 4. Architecture fit with KUDBEE's broader control plane

**Alignment matrix:**

| KUDBEE Layer | Atomic Agents Component | Fit |
|---|---|---|
| Foundation | pydantic (Phase 1 planned dep) | Atomic Agents brings pydantic + instructor as a dependency bundle |
| Provider | `ModelProvider` Protocol | Atomic Agents uses Instructor abstraction over OpenAI/Anthropic/Groq/etc. — different abstraction but compatible concept |
| Memory | Session/Task/Org memory | `ChatHistory` maps to session memory; custom backends possible via `BaseChatHistory` |
| Governance/Tools | ToolRegistry, permissions, audit | `BaseTool` maps to KUDBEE's `ToolDefinition`; no built-in permission model (gap) |
| Runtime | Agent, ThinkBox, Planner, Actor, Observer | `AtomicAgent` + `AgentConfig` maps to ThinkBox; hooks system maps to Observer pattern |

**Gaps identified:**
1. **No built-in permission/approval system:** KUDBEE requires `PermissionLevel` and `requires_approval` on tools. Atomic Agents' `BaseTool` has no such concept — would need wrapper/adapter layer.
2. **Different memory model:** KUDBEE's 4-layer memory (session/task/org/verified) is more elaborate than Atomic Agents' `ChatHistory`. Atomic Agents supports custom backends but doesn't natively have organizational memory.
3. **No audit log:** KUDBEE requires append-only audit logs for every tool call. Atomic Agents' hooks system could capture this, but it's not built-in.
4. **No structured error handling:** KUDBEE requires all errors to carry `agent_id`, `task_id`, `think_box_id`, `timestamp`, `error_type`, `context`. Atomic Agents doesn't have this pattern natively.
5. **Different provider model:** KUDBEE's `ProviderRegistry` selects providers by config. Atomic Agents uses Instructor's client abstraction. Not directly compatible — would need adapter.

**Conclusion:** Atomic Agents is a **runtime component**, not a drop-in replacement for KUDBEE's runtime layer. It could serve as the **agent execution engine** within a Think Box, with KUDBEE's governance/memory/provider layers wrapping it. The fit is architectural (same layering philosophy) but requires adapter layers.

### 5. Per-Think-Box vs. shared service deployment

**Per-Think-Box (one instance per microVM):**
- **Pros:** Full isolation (microVM-level), no cross-tenant data leakage, independent lifecycle, aligns with Firecracker architecture
- **Cons:** Dependency duplication (each microVM needs its own ~150-200MB), higher aggregate resource usage, configuration proliferation
- **Verdict:** **Recommended.** The Firecracker microVM isolation model makes per-instance deployment the natural choice. Atomic Agents' lightweight footprint makes this practical.

**Shared service (centralized Atomic Agents server):**
- **Pros:** Single dependency installation, shared model connections, easier updates
- **Cons:** Violates isolation model, creates cross-tenant risk, adds network latency for tool calls, contradicts the per-Think-Box sandboxing philosophy
- **Verdict:** Not recommended for the current architecture.

### 6. Security/isolation implications

**Positive:**
- Running inside Firecracker microVMs provides kernel-level isolation — stronger than containers
- Atomic Agents has no special privileges or system access requirements
- All LLM calls are HTTP-based, no local file system dependencies by default
- ChatHistory serialization is JSON-based (no pickle/code execution on deserialization)

**Negative:**
- **Python 3.12+ requirement** introduces a version skew risk — need to ensure the microVM rootfs is kept secure
- **No built-in secrets management** — API keys must be injected via environment variables (matches KUDBEE's approach)
- **No built-in sandboxing** — the framework is just a Python library; isolation must come from the Firecracker/microVM layer
- **mcp[cli] dependency** means each microVM could potentially install/run arbitrary MCP servers — needs governance gating
- **litellm dependency** routes through multiple providers — audit logging must capture which provider/model was used

**Security recommendation:** Deploy behind a network egress proxy with API key injection at microVM startup. Never let the agent process inherit host credentials.

### 7. Licensing and operational concerns

**License:** MIT — permissive, no issues for commercial use.

**Operational concerns:**
1. **Python version dependency:** Requires Python 3.12+ but the existing KUDBEE environment has 3.10.12. Upgrading is possible but must be coordinated with the Phase 0 stdlib-only constraint.
2. **Dependency chain depth:** `litellm` and `instructor` pull in large dependency trees (httpx, pydantic, etc.) — increases attack surface for supply chain attacks.
3. **Monorepo structure:** The framework uses a monorepo with uv. Syncing specific components (e.g., just the core agent library) into the Firecracker rootfs requires careful dependency resolution.
4. **Version stability:** v2.10.2 is recent; the framework has had breaking changes between v1.x and v2.x. The project is in active development.
5. **AGENTS.md compatibility:** Interestingly, Atomic Agents also uses an `AGENTS.md` convention — there may be synergy with KUDBEE's own AGENTS.md system.

### 8. Packaging and provisioning difficulty

**Assessment:** **Moderate difficulty** — feasible but requires work.

**Current approach (Kuclocode/skill-based):**
- KUDBEE uses `docs/decisions/` and `AGENTS.md` for process documentation
- The Firecracker microVM rootfs is built separately (no current rootfs builder in the repo)
- Tools are registered via Python imports + decorator pattern

**Atomic Agents packaging path:**
1. Install `pip install atomic-agents` inside the microVM rootfs builder
2. Configure via environment variables (API keys, model selection)
3. The `atomic-assembler` CLI can auto-download tools
4. MCP servers can be provisioned via the `mcp[cli]` package

**Bottlenecks:**
- Python 3.12+ must be installed in the rootfs (current host has 3.10)
- Need to create an adapter layer between Atomic Agents' `BaseTool` and KUDBEE's `ToolDefinition`
- Need to create an adapter between Atomic Agents' `AgentConfig` and KUDBEE's `ThinkBox` lifecycle

---

## Decision

**DEFERRED** — Do not adopt Atomic Agents yet.

Rationale:
1. **Phase 0 constraint violation:** KUDBEE Phase 0 requires Python stdlib only. Atomic Agents brings in pydantic, instructor, litellm, textual, mcp, gitpython, etc. This is incompatible.
2. **Python version conflict:** Requires Python 3.12+, but the established environment has 3.10.12.
3. **Architecture gap:** Atomic Agents is a runtime engine, not a governance/memory layer. Significant adapter code would be needed to bridge the gap with KUDBEE's 5-layer architecture.
4. **Redundancy risk:** KUDBEE already has its own `Agent`, `ThinkBox`, `ToolRegistry`, `ProviderRegistry`, and `ChatHistory`-equivalent (session/task memory). Adopting Atomic Agents wholesale would either duplicate or replace significant existing code.

---

## Recommendation: Integration Path (If Adopted Later)

If KUDBEE moves to Phase 2 (which allows external dependencies) and upgrades to Python 3.12+, the recommended integration pattern would be:

### Adapter Layer Architecture

```
┌─────────────────────────────────────────────────────┐
│  Layer 5 — KUDBEE Agent Implementations              │
├─────────────────────────────────────────────────────┤
│  Layer 4 — KUDBEE Runtime                           │
│  (ThinkBox lifecycle, Planner, Actor, Observer)     │
│  → Wraps Atomic Agents' AtomicAgent as execution     │
│  → Maps ThinkBox state ↔ AgentConfig lifecycle       │
├─────────────────────────────────────────────────────┤
│  Layer 3 — KUDBEE Tools + Governance                │
│  (ToolRegistry, permissions, audit, approval gates)  │
│  → Adapts Atomic Agents BaseTool → KUDBEE ToolDef    │
│  → Wraps all Atomic Agents tool calls in audit log   │
├─────────────────────────────────────────────────────┤
│  Layer 2 — KUDBEE Memory                            │
│  (session, task, org, verified)                     │
│  → Adapter: BaseChatHistory → KUDBEE SessionMemory  │
├─────────────────────────────────────────────────────┤
│  Layer 1 — KUDBEE Provider                          │
│  (ProviderRegistry, ModelProvider protocol)         │
│  → Adapter: Instructor client → ModelProvider        │
├─────────────────────────────────────────────────────┤
│  Layer 0 — Foundation                               │
│  (config, schemas, logging, errors)                  │
├─────────────────────────────────────────────────────┤
│  [Firecracker microVM boundary]                     │
├─────────────────────────────────────────────────────┤
│  Atomic Agents Runtime (inside microVM)             │
│  - AtomicAgent (execution loop)                      │
│  - ChatHistory (conversation)                        │
│  - BaseTool (tool calling)                           │
│  - SystemPromptGenerator (prompt management)         │
└─────────────────────────────────────────────────────┘
```

### Exact Next Step if Adopted

1. **Create a Phase 2 decision record** documenting the migration from stdlib-only to pydantic/instructor/litellm dependencies.
2. **Create an ADR for the adapter layer** mapping `ThinkBox` ↔ `AtomicAgent` (lifecycle states: CREATED→initializing, PLANNING→prompt-building, EXECUTING→run/run_async, OBSERVING→validation, COMPLETE→destroyed).
3. **Build a proof-of-concept** inside a single Firecracker microVM: install Python 3.12, `pip install atomic-agents`, run a basic chatbot agent, verify isolation holds.
4. **Create `core/execution/` package** with:
   - `ExecutionProvider` Protocol (parallel to `ModelProvider`, for execution backends)
   - `AtomicAgentsProvider` implementing the protocol
   - Adapters for `ThinkBox` → `AgentConfig`, `ToolDefinition` → `BaseTool`, `MemoryStore` → `ChatHistory`
5. **Implement audit logging** wrapping every `BaseTool.execute()` call with KUDBEE's structured error format.

### Why not now

- The Phase 0 constraint (stdlib only) is explicit and non-negotiable in AGENTS.md §2.3.
- KUDBEE's own runtime components are already scaffolded and tested (see `core/runtime/agent.py:24`, `core/tools/registry.py:40`, `core/providers/base.py:44`).
- Adding Atomic Agents would mean either replacing 80% of existing code or building a complex adapter layer for minimal Phase 1 gain.
- The Firecracker microVM test (Phase 3 of the current session) should be completed first to establish the execution boundary before deciding what runs inside it.

---

## References

- **Atomic Agents GitHub:** https://github.com/Eigenwise/atomic-agents
- **Atomic Agents documentation:** https://eigenwise.github.io/atomic-agents/
- **olemarch fork:** https://github.com/olemarch/atomic-agents-bio
- **Instructor (structured output):** https://github.com/jxnl/instructor
- **MCP (tool integration):** https://modelcontextprotocol.io
- **Instructor provider compatibility:** https://github.com/jxnl/instructor/blob/main/extras/docs/README.md
- **KUDBEE Architecture:** `docs/architecture-v1.md`
- **KUDBEE Project Foundation:** `docs/project-foundation.md`
- **KUDBEE Development Rules:** `AGENTS.md`
