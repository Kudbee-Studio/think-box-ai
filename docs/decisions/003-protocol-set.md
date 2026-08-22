# ADR 003: Provider-Agnostic Protocol Set (Design Phase — Signatures Only)

**Date:** 2026-08-22
**Status:** Accepted (scoped — implementation deferred)

## Context

ADR-002 (Phase 3) identified a concrete interface set required to abstract the
execution substrate (Upstash Box, QStash, Vector DB) behind provider-agnostic
contracts. The previous Mayor boot hit an output/reasoning limit when it tried
to carry the whole architecture in one pass. To keep the next mission chunked
and shippable, we scope ADR-003 to **signatures only** — no implementation,
no Upstash wiring.

This ADR is the NEXT chunked Mayor mission after the Mayor Boot Runtime
(`core/mayor/boot.py`) and the `/mayor-boot` command are in place.

## Decision

Define the following `typing.Protocol` stubs in `core/`, matching existing
module locations and avoiding layer violations (see AGENTS.md §1.1):

- `AgentRuntime` — orchestrates an agent loop inside a Box (core/runtime/).
- `BoxRuntime` — CREATE/BOOTSTRAP/FREEZE/RESUME/DESTROY lifecycle + Box sizing
  policy (SMALL/MEDIUM/LARGE, defined in ADR-002 Phase 4) (core/runtime/).
- `QueueProvider` — async dispatch / orchestration (QStash analog) (core/providers/).
- `MemoryProvider` — unified 4-layer memory access; `core/memory/store.py`
  already implements the SQLite backing and should satisfy this (core/memory/).
- `VectorProvider` — semantic memory; MISSING today, to be added (core/memory/).
- `StructuredStateStore` — durable task/session/org state (core/memory/).
- `LLMProvider` — BYOK-capable model access; `core/providers/base.py` already
  defines `ModelProvider`, reuse/extend rather than duplicate (core/providers/).
- `SecretProvider` — resolves a secret handle at call time; secrets are
  REFERENCES, never `.env` in the Box FS (per ADR-001) (core/providers/).

Hard rules carried from ADR-001/002:
- No provider-specific SDK imported at the runtime layer.
- Secrets are handles, resolved at LLM-call time.
- Consolidate the 3 competing runtimes into `core/runtime/`; deprecate
  `backend/main.py` and `apps/web/server.js` agent loops.

## Consequences

- The Mayor can fan out N Boxes via `QueueProvider` without knowing the vendor.
- Future implementation chunks (Box sizing, lifecycle, Upstash wiring) implement
  these protocols rather than redesigning them.
- This ADR is design-only: no execution substrate is built here.

## Next Chunk

Implement the `Protocol` stubs (signatures + docstrings, no bodies) and a test
that asserts each protocol is structurally satisfiable by an in-memory fake.
