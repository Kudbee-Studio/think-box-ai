# THINK BOX AI — 10 Improvements

**Date:** 2026-08-28
**Status:** Proposed
**Reference:** `docs/architecture-v1.md`, `docs/roadmap.md`, `docs/project-foundation.md`

---

## 1. Complete the Runtime Execution Loop

### Current State

The runtime loop structure exists in `core/runtime/agent.py` but is not wired end-to-end:

- `Agent.run()` accepts `planner`, `actor`, `observer` as parameters but does **not** pass the `provider` to the `Planner`.
- `Planner` in `core/runtime/planner.py` returns a single hardcoded `Step` regardless of the goal. It does not use a model provider for decomposition.
- `Actor` in `core/runtime/actor.py` accepts `tool_registry`, `approval_gate`, `audit_log`, and `memory_store` but **never uses any of them**. `execute_step()` returns a static success result without invoking tools.
- `Observer.validate()` only checks `result.get("status") == "success"` — it does not validate against `expected_output` or goal alignment.

The loop compiles and runs but produces no real work.

### Why It Matters

The execution loop is the core value proposition of the system. Without it, Think Box AI is a collection of disconnected components rather than an agent runtime. Every other improvement (providers, tools, governance, memory) depends on this loop being functional.

### Architecture Mapping

| Layer | Component | Change |
|-------|-----------|--------|
| Layer 4 — Agent Runtime | `agent.py` | Pass `provider` to `Planner`; wire `Actor` with `tool_registry`, `approval_gate`, `audit_log` |
| Layer 4 — Agent Runtime | `planner.py` | Accept `provider`; call `provider.complete()` to generate real steps from goals |
| Layer 4 — Agent Runtime | `actor.py` | Look up tool in `ToolRegistry`; check `ApprovalGate`; invoke tool handler; record in `AuditLog` |
| Layer 4 — Agent Runtime | `observer.py` | Validate structural output against `expected_output`; check goal alignment |

---

## 2. Bridge core/providers/ and backend/models/ollama_client.py (Add OllamaProvider)

### Current State

- `core/providers/` has `ModelProvider` protocol, `ProviderRegistry`, and `OpenAICompatProvider`.
- `core/providers/ollama.py` does **not exist**.
- `backend/models/ollama_client.py` implements `list_models()`, `stream_chat()`, and `chat_completion()` using `aiohttp` against `http://localhost:11434`.
- The backend's Ollama client is completely disconnected from the core provider abstraction.

### Why It Matters

Ollama enables local-first inference without cloud dependencies. Per architecture principle 1.2 (Provider Independence), swapping between OpenAI and Ollama must be a configuration change, not a code change. Without `OllamaProvider` in `core/providers/`, local models are inaccessible to the core runtime.

### Architecture Mapping

| Layer | Component | Change |
|-------|-----------|--------|
| Layer 1 — Provider Abstraction | `core/providers/ollama.py` | New file implementing `ModelProvider` protocol |
| Layer 1 — Provider Abstraction | `core/providers/__init__.py` | Export `OllamaProvider` |
| Layer 0 — Foundation | `core/foundation/bootstrap.py` | Register OllamaProvider when `THINKBOX_PROVIDER=ollama` |

The `OllamaProvider` wraps `ollama_client.py` logic (`stream_chat`, `chat_completion`, `list_models`) behind the `ModelProvider` interface. No modification to `backend/models/ollama_client.py` is required.

---

## 3. Implement the Approval Gate End-to-End

### Current State

- `core/governance/audit.py` contains `ApprovalGate`, `ApprovalPolicy`, `PermissionChecker` — all fully implemented.
- `ApprovalGate.require_approval()` checks permission level and records audit entries.
- The `Actor` accepts `approval_gate` in its constructor but **never calls** `require_approval()`.
- The Actor does not check `approval_required` on tool definitions before execution.

### Why It Matters

Per architecture principle 1.4 (Governance by Default), tools with `RESTRICTED` permission or `approval_required=True` must not execute without explicit approval. Currently, any tool can be invoked without governance checks. This is a security gap: `shell_exec`, `file_write`, and `http_request` all require approval per the architecture but the runtime does not enforce this.

### Architecture Mapping

| Layer | Component | Change |
|-------|-----------|--------|
| Layer 3 — Tool Registry & Governance | `core/governance/audit.py` | No change needed — already implemented |
| Layer 4 — Agent Runtime | `core/runtime/actor.py` | Before tool invocation: check `approval_required`, call `approval_gate.require_approval()` |
| Layer 5 — Bootstrap | `core/foundation/bootstrap.py` | Pass `approval_gate` to `Actor` construction (already wired in bootstrap but not used by Actor) |

---

## 4. Unify the Two Plugin Systems (core/tools/ vs backend/plugins/)

### Current State

Two completely separate plugin systems exist:

1. **`core/tools/`**: Uses `@tool` decorator, `ToolRegistry`, `ToolDefinition`. Tools: `file_read`, `file_write`, `shell_exec`, `http_request`, `memory_query`.
2. **`backend/plugins/`**: Uses `Tool` ABC, `PluginRegistry`, `ToolResult`. Tools: `FileReadTool`, `FileWriteTool`, `FileListTool`, `TerminalTool`, `GitTool`, `HttpTool`.

The backend's `run_agent_task()` uses `PluginRegistry` and never touches `core/tools/`. The core's `ToolRegistry` is never used by the backend.

### Why It Matters

Maintaining two parallel plugin systems doubles the maintenance burden and creates inconsistency. A tool added to one system is invisible to the other. The architecture specifies a single `Tool Registry` (Layer 3). The backend should delegate to the core's `ToolRegistry` rather than maintaining its own.

### Architecture Mapping

| Layer | Component | Change |
|-------|-----------|--------|
| Layer 3 — Tool Registry | `backend/plugins/` | Refactor to register tools with core `ToolRegistry` instead of maintaining separate `PluginRegistry` |
| Layer 5 — Agent Runtime | `backend/agent_loop.py` | Replace direct plugin calls with `ToolRegistry` lookups |
| Layer 3 — Tool Registry | `core/tools/` | Extend with any tools from `backend/plugins/` that are missing (e.g., `git_operations`) |

---

## 5. Add Secrets/Capabilities Resolution (SecretResolver)

### Current State

- `core/foundation/config.py` loads configuration from env vars with `THINKBOX_` prefix.
- `core/foundation/secrets.py` does **not exist**.
- API keys and secrets are read directly from environment variables without abstraction.
- No distinction between "capability available" (e.g., AWS credentials present) and "capability configured" (e.g., `THINKBOX_PROVIDER=bedrock`).

### Why It Matters

The architecture requires that secrets are never hardcoded or logged (AGENTS.md §9). A `SecretResolver` provides a single point of control for secret resolution with lazy evaluation, fallback to defaults, and audit logging of access (not values). It also enables capability detection — the runtime can query "is AWS Bedrock available?" without exposing credentials.

### Architecture Mapping

| Layer | Component | Change |
|-------|-----------|--------|
| Layer 0 — Foundation | `core/foundation/secrets.py` | New file: `SecretResolver` class with `resolve()`, `has_capability()`, lazy evaluation, no logging of values |
| Layer 0 — Foundation | `core/foundation/__init__.py` | Export `SecretResolver` |
| Layer 0 — Foundation | `core/foundation/config.py` | Integrate `SecretResolver` into `ThinkBoxConfig` |

---

## 6. Implement Compute Fabric Pattern (Nested Think Boxes, Sub-goals)

### Current State

- The architecture defines Think Boxes as nestable (`architecture-v1.md` §4.2): "A parent Think Box may spawn child Think Boxes for sub-goals."
- `core/runtime/thinkbox.py` has `ThinkBoxState` and `ThinkBoxLifecycle` but no nesting support.
- `core/runtime/planner.py` returns a single step — no sub-goal decomposition.
- The `Agent` creates one Think Box per `run()` call and cannot spawn child Think Boxes.

### Why It Matters

The Compute Fabric pattern is the foundation for multi-agent coordination and complex goal decomposition. Without nesting, the system can only handle flat, sequential tasks. Nested Think Boxes enable:

- Hierarchical goal decomposition (root goal → sub-goals → leaf tasks)
- Parallel execution of independent sub-goals (future)
- Isolated memory scopes per sub-goal
- Sub-goal approval and rollback

### Architecture Mapping

| Layer | Component | Change |
|-------|-----------|--------|
| Layer 4 — Agent Runtime | `core/runtime/thinkbox.py` | Add `parent` reference, `children` list, sub-goal spawning |
| Layer 4 — Agent Runtime | `core/runtime/planner.py` | Decompose goals into sub-goals; generate child Think Boxes |
| Layer 4 — Agent Runtime | `core/runtime/agent.py` | Support nested execution: spawn child Think Boxes, await results |
| Layer 2 — Memory Subsystem | `core/memory/task.py` | Namespace memory by `task_id` for sub-goal isolation |

---

## 7. Add AWS Bedrock Provider

### Current State

- `core/providers/` has `OpenAICompatProvider` and (after improvement #2) `OllamaProvider`.
- `core/providers/bedrock.py` does **not exist**.
- The architecture's Provider Strategy (§6) lists only OpenAI-compatible and Anthropic for Phase 1.

### Why It Matters

AWS Bedrock is the primary enterprise inference route for organizations already in the AWS ecosystem. Adding it as a provider demonstrates that the `ModelProvider` abstraction works for non-OpenAI-compatible APIs (Bedrock uses `InvokeModel` API, not `/v1/chat/completions`). This validates architecture principle 1.2 (Provider Independence) with a third, structurally different provider.

### Architecture Mapping

| Layer | Component | Change |
|-------|-----------|--------|
| Layer 1 — Provider Abstraction | `core/providers/bedrock.py` | New file: `BedrockProvider` implementing `ModelProvider` for AWS Bedrock `InvokeModel` API |
| Layer 1 — Provider Abstraction | `core/providers/__init__.py` | Export `BedrockProvider` |
| Layer 0 — Foundation | `core/foundation/bootstrap.py` | Register `BedrockProvider` when `THINKBOX_PROVIDER=bedrock` |
| Layer 0 — Foundation | `core/foundation/secrets.py` | Resolve `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` via `SecretResolver` |

---

## 8. Connect Core Runtime to Backend WebSocket (Replace run_agent_task with Agent.run())

### Current State

- `backend/main.py` has `run_agent_task()` which calls `stream_chat()` from `backend/models/ollama_client.py` directly.
- The backend does **not** import or use `core.runtime.Agent`.
- The backend maintains its own event loop, tool execution, and approval flow separately from the core.
- Events are emitted via `backend/core/event_bus.py` but are generated by backend code, not the core runtime.

### Why It Matters

The backend should be a thin transport layer over the core runtime. Currently, all agent logic is duplicated: tool execution, approval, and streaming exist in both `backend/` and `core/`. This creates drift — improvements to the core (e.g., new tools, governance) are not reflected in the backend.

### Architecture Mapping

| Layer | Component | Change |
|-------|-----------|--------|
| Layer 5 — Agent Runtime | `backend/main.py` | Replace `run_agent_task()` with `core.runtime.Agent.run()` |
| Layer 5 — Agent Runtime | `backend/core/event_bus.py` | Subscribe to core runtime events (tool call, result, memory write) and broadcast via WebSocket |
| Layer 4 — Agent Runtime | `core/runtime/agent.py` | Emit events at each loop iteration (plan, act, observe, remember) for the backend to consume |
| Layer 3 — Tool Registry | `backend/plugins/` | Delegate to core `ToolRegistry` (see improvement #4) |

---

## 9. Implement Memory Persistence on Session Completion (Fix No-op flush())

### Current State

- `core/memory/session.py`: `SessionMemoryAdapter.flush()` is a no-op (only logs).
- `core/memory/task.py`: `TaskMemoryAdapter.flush()` is a no-op (only logs).
- `core/memory/org.py`: `OrganizationalMemoryAdapter.flush()` is a no-op (only logs).
- Data written during execution uses `store.put()` directly to SQLite, but `flush()` was designed as the session-end persistence hook and does nothing.

### Why It Matters

While `store.put()` writes immediately, `flush()` is the architecture's designated point for:

- **Session Memory**: Flushing in-memory reasoning chain to SQLite before session destruction.
- **Task Memory**: Atomically persisting step results, validation outcomes, and error logs at task completion.
- **Organizational Memory**: Promoting verified patterns with full provenance and evidence links.

Without `flush()`, there is no explicit persistence boundary. If the process crashes mid-task, in-memory state is lost even though the architecture claims durability.

### Architecture Mapping

| Layer | Component | Change |
|-------|-----------|--------|
| Layer 2 — Memory Subsystem | `core/memory/session.py` | Implement `flush()`: write buffered reasoning chain to SQLite with session metadata |
| Layer 2 — Memory Subsystem | `core/memory/task.py` | Implement `flush()`: write step results, validation, errors as atomic transaction |
| Layer 2 — Memory Subsystem | `core/memory/org.py` | Implement `flush()`: write verified patterns with provenance |
| Layer 4 — Agent Runtime | `core/runtime/agent.py` | Call `flush()` on session/task/org adapters at `run()` completion |
| Layer 0 — Foundation | `core/foundation/bootstrap.py` | Call `flush()` in `shutdown()` for graceful degradation |

---

## 10. Add CLI Commands for Compute Fabric Management

### Current State

- `think_box_ai/cli.py` only supports `--version` and `--info` flags.
- No commands for managing Think Boxes, sub-goals, providers, or memory.
- No way to inspect or control the compute fabric from the command line.

### Why It Matters

The CLI is the primary interface for operators and developers. Without compute fabric commands, users cannot:

- List active Think Boxes and their status
- Inspect sub-goal trees and progress
- Approve/reject pending actions
- Query memory contents
- Switch providers at runtime
- Run benchmarks

The CLI must expose the full capabilities of the runtime to be useful as a debugging and operational tool.

### Architecture Mapping

| Layer | Component | Change |
|-------|-----------|--------|
| Layer 5 — Agent Implementations | `think_box_ai/cli.py` | Add subcommands: `thinkbox list`, `thinkbox status <id>`, `goal tree <task_id>`, `approve <request_id>`, `memory query <key>`, `provider list`, `benchmark run` |
| Layer 4 — Agent Runtime | `core/runtime/agent.py` | Expose introspection API: `list_think_boxes()`, `get_goal_tree()`, `get_pending_approvals()` |
| Layer 3 — Tool Registry | `core/tools/registry.py` | Add `list_all()` with full tool metadata for CLI display |
| Layer 1 — Provider Abstraction | `core/providers/base.py` | Add `provider_status()` method to protocol for health checks |

---

## Implementation Priority

| # | Improvement | Priority | Depends On |
|---|-------------|----------|------------|
| 1 | Complete the Runtime Execution Loop | **Critical** | — |
| 2 | Add OllamaProvider | **High** | — |
| 3 | Implement Approval Gate End-to-End | **High** | #1 |
| 4 | Unify Plugin Systems | **Medium** | #1 |
| 5 | Add Secrets/Capabilities Resolution | **Medium** | — |
| 6 | Implement Compute Fabric Pattern | **Medium** | #1, #3 |
| 7 | Add AWS Bedrock Provider | **Medium** | #5 |
| 8 | Connect Core Runtime to Backend | **Medium** | #1, #4 |
| 9 | Implement Memory Persistence | **Medium** | #1 |
| 10 | Add CLI Commands | **Low** | #1, #6 |

---

## KUDBEE COMPUTE FABRIC ROADMAP

The Compute Fabric is the architectural pattern of nested Think Boxes that enables hierarchical goal decomposition, parallel execution, and multi-agent coordination.

### Phase 1: Foundation (Current)

- Single Think Box, sequential execution
- One provider (OpenAI-compatible or Ollama)
- Core runtime loop functional but unwired

### Phase 2: Wire the Loop

Implement improvements #1, #2, #3, #5:
- Provider → Planner → Actor → Tools → Observer → Memory
- Ollama and OpenAI providers
- Approval gate enforced
- Secrets resolution

### Phase 3: Nested Execution

Implement improvements #6, #9:
- Think Boxes can spawn child Think Boxes
- Sub-goal trees with isolated memory scopes
- Memory flush on session/task completion

### Phase 4: Enterprise Providers

Implement improvements #7, #4:
- AWS Bedrock provider
- Unified plugin system (core tools only)
- Backend delegates to core runtime

### Phase 5: Operational Interface

Implement improvements #8, #10:
- Backend fully uses core runtime via `Agent.run()`
- CLI exposes compute fabric introspection and control
- WebSocket events sourced from core runtime

---

*This document is a living reference. As improvements are implemented, update the "Current State" sections to reflect reality.*
