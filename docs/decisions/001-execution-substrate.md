# ADR 001: Execution Substrate — Upstash Box as Agent Computer, Kilo as Bootstrap-Only

**Date:** 2026-08-21
**Status:** Accepted (proposed — design phase, not yet implemented)

## Context

The original KUDBEE / Think Box design treated the cloud-agent worker (Kilo,
cheap model) as the agent brain AND execution environment. This creates a
scaling ceiling: intelligence is bounded by the bootstrap tool's model, not by
the user's chosen provider.

We need an architecture where:
- Intelligence scales with BYOK (bring-your-own-key) LLM choice.
- Execution happens in a real computer (shell, filesystem, network, git,
  durable storage) that can freeze when idle and resume with state intact.
- The control plane (Mayor) stays cheap and always-on; the expensive,
  model-heavy work happens inside the execution substrate.

## Options Considered

1. **Kilo worker runs the agent directly** (original implicit design).
   - Rejected: couples intelligence to the bootstrap tool's model; no real
     computer boundary; secrets tend to land in the worker FS.

2. **Upstash Box as execution substrate, Kilo as bootstrap-only.**
   - Accepted. Mayor = control plane, QStash = orchestration, Box = body,
     Vector + structured DB = memory, Kilo = provisioning, LLM = BYOK.

3. **Self-hosted containers / VMs instead of Box.**
   - Deferred: higher ops burden; Box gives freeze/resume and managed
     durable storage out of the box.

## Decision

Adopt the four-layer separation:

```
MAYOR        → control plane (decides what / which size)
QSTASH       → orchestration / async dispatch (nervous system)
UPSTASH BOX  → execution substrate / agent computer (body)
VECTOR + STRUCTURED DB → memory system
KILO         → bootstrap / provisioning ONLY (not permanent worker brain)
LLM PROVIDER → configurable through the Box runtime / BYOK
```

Hard rules:
- Kilo is the **provisioning layer only**. Once a Box exists, the real worker
  lives inside the Box. Kilo is never a permanent dependency per task.
- **Secrets are references, not `.env` files in the Box FS.** The Box runtime
  resolves a secret handle at LLM-call time. This follows Upstash's stated
  agent-workflow guidance (keep secrets out of the container).
- Upstash is an *implementation* of the execution substrate, not the
  architecture itself. All access goes through provider-agnostic interfaces
  (see ADR-002 once written).

## Consequences

- Intelligence now scales with the user's BYOK provider, not the bootstrap
  tool.
- Mayor can fan out N independent Boxes (coding / research / security) via
  QStash.
- New failure modes: QStash availability, Box freeze/resume integrity, secret
  resolver availability. These must be designed (see follow-up phases).
- Vendor lock-in risk concentrated in Box + QStash + Vector; mitigated by
  abstracting them behind interfaces.
- Implementation is explicitly deferred. This ADR is design-only.

## Open Items (to be resolved in follow-up design phases)

- Deterministic Box-sizing policy (SMALL / MEDIUM / LARGE scoring model).
- Box lifecycle (CREATE → BOOTSTRAP → … → FREEZE → RESUME → DESTROY).
- Provider-agnostic interface set: AgentRuntime, BoxRuntime, QueueProvider,
  MemoryProvider, VectorProvider, StructuredStateStore, LLMProvider,
  SecretProvider.
- Conflict analysis against existing `core/` (foundation, memory, governance,
  providers, tools, runtime) and `backend/` (FastAPI/Ollama) implementations.
