# ADR 003: Execution Provider Abstraction

**Date:** 2026-08-29
**Status:** Accepted

## Context

KUDBEE runs agent tool execution as local host subprocesses (`shell_exec` in
`core/tools/shell_exec.py`). For production safety, untrusted Think Box work
must run inside an isolated boundary (a Firecracker microVM when KVM is
available, else a real local subprocess). ADR-002 established that Firecracker
is the target execution substrate but is **blocked** on the current UpCloud
Managed Kubernetes worker because `/dev/kvm` is not a usable KVM character
device.

We needed an abstraction that:

- keeps Firecracker behind a provider boundary (runtime never sees Firecracker internals),
- works today with a real `LocalExecProvider` fallback,
- is ready for `FirecrackerExecProvider` the moment a KVM-capable host exists,
- preserves the separation of runtime / governance / providers / tools / memory,
- keeps governance (permissions, audit, approval) strictly ABOVE execution.

## Options Considered

1. **ExecutionProvider protocol + registry (chosen).** Mirrors the existing
   `ProviderRegistry` shape for model providers, so discovery is consistent.
   `LocalExecProvider` is fully functional; `FirecrackerExecProvider` is fully
   implemented but gated by an honest `health_check()`.

2. **Put execution logic inside `core/tools/shell_exec.py`.** Rejected — tools
   describe *capabilities*; execution is the *substrate* where work happens.
   Mixing them would violate the layer separation in AGENTS.md §1.1.

3. **Make Firecracker a hard requirement for the runtime to start.** Rejected —
   the runtime must run on hosts without KVM (the current one). Execution
   unavailability is a per-provider condition, not a fatal bootstrap error.

## Decision

Create a new `core/execution/` package (Execution layer):

- `base.py` — `ExecResult` dataclass, `ExecutionProvider` Protocol,
  `ExecutionProviderRegistry`, `ExecutionUnavailableError`.
- `local.py` — `LocalExecProvider` (REAL asyncio subprocess; not a mock).
- `firecracker.py` — `FirecrackerExecProvider` (real Firecracker REST API over
  a Unix socket; vsock guest-command transport; full lifecycle).
- `__init__.py` — public surface.

Wiring:

- `ThinkBoxConfig` gains `exec_provider` (default `"local"`) and
  `firecracker_config` (dict).
- `core/foundation/bootstrap.py` gains `_create_execution_provider()` and the
  `RuntimeContext.execution_provider` field. The `core.execution` import is
  **lazy** inside the factory (see Consequences) to respect layer discipline.
- `core/runtime/actor.py` routes `Step(action="execute", command=...)` to the
  execution provider. Governance (approval gate + audit) is consulted *before*
  the command is handed to the substrate, so governance stays above execution.
- `core/runtime/planner.py` `Step` gains an optional `command` field.

### FirecrackerExecProvider honesty constraints

- `health_check()` returns `False` unless: the firecracker binary exists, the
  kernel + rootfs exist, `/dev/kvm` is a **real character device** exposing a
  working `KVM_GET_API_VERSION` ioctl (a directory named `/dev/kvm` fails), and
  a virtio-vsock (`AF_VSOCK`) transport is usable.
- `execute()` raises `ExecutionUnavailableError` when health is false. It never
  returns a fake `KUDBEE_FIRECRACKER_OK`.
- Lifecycle: start VMM (optionally via `jailer`) → configure
  machine/boot/drive via the REST API → `InstanceStart` → send command to a
  guest agent over vsock → capture structured stdout/stderr/exit-code →
  `SendCtrlAltDel` + process terminate → cleanup socket.

### Guest agent protocol (host side)

The host sends one JSON line `{"cmd": "<command>"}` over vsock; the guest
streams JSON lines `{"stream":"stdout|stderr","data":"..."}` and terminates
with `{"exit": <code>}`. A reference guest agent is out of scope for Phase 1
(the host side is implemented; a minimal guest init implementing this protocol
is required only when a KVM host is provisioned).

## Consequences

- `core/execution/` is a new package; it depends only on `core.foundation`
  (logging, errors). It does **not** import runtime/governance/tools/memory.
- `core/foundation/bootstrap.py` is the composition root. To avoid a static
  upward import (Foundation importing a layer above it), `core.execution` is
  imported lazily inside `_create_execution_provider()`. This keeps the
  module-level import graph compliant with AGENTS.md §1.1 while still assembling
  all layers in one place.
- `LocalExecProvider` is the default and is genuinely functional today, so the
  runtime's execution contract is satisfied even on the KVM-less host.
- `FirecrackerExecProvider` is implemented and correct by construction, but on
  the current host `health_check()` returns `False` and `execute()` raises —
  exactly as required by the "do not fake Firecracker" constraint.
- The unit tests mock Firecracker and exercise the full lifecycle orchestration.
  The integration test `tests/integration/test_firecracker_execution.py`
  performs the real `echo "KUDBEE_FIRECRACKER_OK"` proof-of-life but **skips
  automatically** when KVM/kernel/rootfs are absent.

## References

- ADR-002: Firecracker Execution Boundary (KVM blocker documented)
- AGENTS.md §1.1 (Layer Discipline), §9 (Security), §13.4–13.6 (Infra)
- `core/providers/base.py` — `ProviderRegistry` (design model)
- `tests/unit/test_execution.py`, `tests/integration/test_firecracker_execution.py`
