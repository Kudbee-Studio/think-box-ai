# ADR 002: Firecracker Execution Boundary

**Date:** 2026-08-29
**Status:** Accepted (conditional on KVM availability)

## Context

KUDBEE's runtime currently executes tools via local subprocesses (`shell_exec` in
`core/tools/shell_exec.py`). For production safety, agent tool execution must be
isolated in a sandboxed microVM. The repository architecture defines five layers:
Foundation, Provider, Memory, Governance/Tools, Runtime. A new **Execution**
concern is needed that sits between the Governance/Tools layer (where `ToolRegistry`
lives) and the Runtime layer (where `Actor` dispatches `Step` actions).

The UpCloud server (`kudbee-host-v1`, 212.147.250.183) is an UpCloud Managed
Kubernetes worker node on the `PREMIUM-4xCPU-8GB` plan in zone `fi-hel2`:

- Firecracker v1.16.1 binary verified running (API responds over Unix socket)
- `/dev/vsock`, `/dev/vhost-vsock`, `/dev/vhost-net` all available
- `/dev/kvm` NOT available — `/dev/kvm` is a directory, not a character device
- CPU flags include `hypervisor` but NO `vmx` or `svm` (no nested virtualization)
- `modprobe kvm_amd` fails: "SVM not supported by CPU"
- `modprobe kvm_intel` fails: "VMX not supported by CPU"
- `systemd-detect-virt --vm` returns `kvm` (host is itself a KVM guest)
- 4 vCPUs, 6.6GB available RAM, 90GB free disk
- Internet access (~3MB/s download from S3)

## Options Considered

1. **Firecracker as ExecutionProvider (chosen, CONDITIONAL)** — Implement a new
   `core/execution/` package with an `ExecutionProvider` protocol. The
   `FirecrackerExecProvider` manages microVM lifecycle via the Firecracker
   API over a Unix socket, executes commands inside the guest via serial console,
   and captures stdout/stderr/exit_code. This preserves all existing layers —
   ThinkBox, Planner, Actor, Observer, Memory, Governance, ToolRegistry,
   ProviderRegistry, ModelProvider remain untouched. **CONDITIONAL on KVM
   availability — blocked on this host.**

2. **Kubernetes pods as execution boundary** — Rejected. The acceptance criterion
   explicitly requires a real Firecracker microVM, not a container.

3. **Docker/containerd containers** — Rejected. Same reason as K8s. Containers
   do not provide the same isolation as a microVM.

4. **QEMU/KVM without /dev/kvm** — Rejected. Firecracker REQUIRES `/dev/kvm`.
   Tested empirically: `InstanceStart` fails with
   `Kvm error: Error creating KVM object: Is a directory (os error 21)`.

5. **OLEMARCHY (Atomic Agents)** — Deferred. See ADR-001. OLEMARCHY is an
   agent framework, not an execution boundary.

## Decision

Implement `core/execution/` with `ExecutionProvider` protocol, `ExecResult`
dataclass, `LocalExecProvider` (real local subprocess — NOT a mock), and
`FirecrackerExecProvider` (ready for KVM-capable hosts). The
`FirecrackerExecProvider` will be wired into the system but will gracefully
report "not available" when KVM is absent.

### Architecture

```
Governance/Tools layer          Runtime layer
┌──────────────────────┐      ┌─────────────────┐
│  ToolRegistry          │      │  Actor            │
│  (file_read, shell, ..) │───►│  dispatches Step  │
└──────────────────────┘      └─────────────────┘
         │                              │
         │ Step.action == "execute"     │
         ▼                              ▼
┌──────────────────────┐      ┌─────────────────┐
│  ExecutionProvider    │◄─────│  ExecResult      │
│  (Protocol)           │      │  (dataclass)     │
└──────────────────────┘      └─────────────────┘
         │
         │ Registered as "firecracker" (BLOCKED — no /dev/kvm)
         │ Registered as "local" (real subprocess fallback)
         ▼
┌──────────────────────┐
│  FirecrackerExec      │
│  (Unix socket API)    │
│  → boot microVM        │
│  → exec via serial     │
│  → capture stdout      │
│  → destroy microVM     │
└──────────────────────┘
```

### ExecutionProvider Protocol

```python
class ExecutionProvider(Protocol):
    name: str

    async def execute(self, command: str, timeout: float = 30.0) -> ExecResult: ...
    async def health_check(self) -> bool: ...
    async def shutdown(self) -> None: ...
```

### ExecResult Dataclass

```python
@dataclass
class ExecResult:
    stdout: str
    stderr: str
    return_code: int
    duration: float
    microvm_id: str | None = None
    provider: str = ""
    error: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
```

### FirecrackerExecProvider Behavior

1. Creates a Unix socket path for the Firecracker API
2. Starts `firecracker --api-sock <socket> --id <id>` as a background process
3. PUTs `/boot-source` with kernel image path + boot args
4. PUTs `/drive/rootfs` with rootfs ext4 path
5. PUTs `/machine-config` (vcpu_count=1, mem_size_mib=128, smt=false)
6. PUTs `/actions` with `InstanceStart`
7. Reads serial console output via GET `/console_output`
8. Parses stdout/stderr/exit code from serial output
9. PUTs `/actions` with `SendCtrlAltDel` to shut down
10. Cleans up the socket and process

## Optimization Research (Firecracker Best Practices)

### PVM — Pagetable Virtual Machine (alternative to KVM)

- Proposed by Ant Group / Alibaba in Feb 2024, presented at SOSP 2023
- Enables Firecracker on cloud VMs without nested virt or `/dev/kvm`
- x86_64 only (no arm64)
- Requires custom host kernel patches (~7000 lines, 73 patches spread across 73 patches)
- Requires patched Firecracker fork: `kvcache-ai/firecracker-next` or `leether/firecracker-next`
- Packaging available via SlicerVM.com (automated)
- Production status: RC — Phoronix coverage suggests it may remain internal at Alibaba
- **Relevance:** If PVM kernel patches could be applied to the UpCloud node kernel, Firecracker could run without nested virt. However, UpCloud managed K8s nodes restrict kernel modifications. This would require a new non-managed server.

### firecracker-containerd

- Official AWS project enabling containerd to manage containers as Firecracker microVMs
- Daemon-based architecture (containerd ↔ firecracker-control plugin ↔ firecracker-containerd ↔ Firecracker)
- Complex operational setup: custom snapshotter, VM runtime shim, in-VM agent, custom rootfs builder
- Longer-term roadmap includes CRI conformance and Kubernetes compatibility
- **Relevance:** Not needed for KUDBEE Phase 1. We use direct Firecracker API over Unix socket, not containerd integration. Future option for K8s orchestration.

### firecracker-shim (PipeOpsHQ)

- Newer containerd shim v2 architecture (no middleman daemon)
- Converts OCI images to ext4 rootfs on-the-fly (via fsify), standard CNI networking
- VM pooling for <50ms warm starts, 64-128MB memory per VM
- Still requires `/dev/kvm` — not a PVM solution
- **Relevance:** Excellent reference for KUDBEE's FirecrackerExecProvider implementation patterns (VM pooling, vsock communication, CNI networking)

### Snapshotting & Forking Optimizations (Kernel Blog, Feb 2025)

- **Snapshot + fork pattern:** Boot microVM once, create snapshot, fork clones via copy-on-write (CoW)
  - Cold start path: boot → initialization → snapshot
  - Warm start path: fork from CoW snapshot → resume → inject identity
- **CoW forking:** Clone overlay disk + guest memory via filesystem CoW (btrfs/XFS reflink), child only allocates blocks on write
- **UFFD (User Fault File Descriptor):** Lazy memory paging during restore — multiple forks share snapshot page cache, hundreds of VMs launch in parallel
- **Hot pools:** Pre-warmed VMs ready for <30ms handoff (10-30ms hit, <80ms connect)
- **Snapshot security:** Poor entropy/replayable randomness when resuming from same snapshot — guest must reseed RNG on restore (MADV_WIPEONSUSPEND / VmGenID)
- **Host kernel requirement:** cgroups V2 required (cgroups V1 causes high snapshot latency)
- **Relevance:** KUDBEE's FirecrackerExecProvider should implement snapshot+fork pattern once KVM available. CoW requires btrfs or XFS with reflink support. UFFD requires Linux 5.7+ with CONFIG_USERFAULT_FD.

### Cloud Hypervisor vs Firecracker

- Cloud Hypervisor: Rust-based VMM, more features (live migration, CPU/memory hotplug, better debugging)
- Firecracker: purpose-built microVM, simpler device model, faster boot
- **Relevance:** Firecracker remains the right choice for KUDBEE Phase 1 (simple, proven, AWS-native). Cloud Hypervisor is a Phase 2+ option for advanced features.

## KVM Requirement (BLOCKER)

**This host CANNOT run Firecracker microVMs.** Empirical test:

```
PUT /actions {"action_type": "InstanceStart"}
→ 400 Bad Request:
  Start microvm error: Kvm error: Error creating KVM object: Is a directory
  (os error 21) Make sure the user launching the firecracker process is
  configured on the /dev/kvm file's ACL.
```

**Root cause:** The host is an UpCloud Managed Kubernetes worker running
as a KVM guest. Nested virtualization is not exposed — CPU flags lack `vmx`/`svm`,
and `/dev/kvm` is a directory rather than a character device. `kvm_amd` and
`kvm_intel` kernel modules cannot be loaded.

**UpCloud plan:** `PREMIUM-4xCPU-8GB` in zone `fi-hel2`. All UpCloud plan
families (PREMIUM, CLOUDNATIVE, HIMEM, HICPU, STARTER, DEV) run as KVM guests
without nested virt passthrough. UpCloud does not currently offer bare-metal
or dedicated-host plans with nested virtualization support.

## Consequences

- `core/execution/` is a new package — does not modify any existing layer.
- `ThinkBoxConfig` gets new fields: `exec_provider`, `firecracker_config`.
- `core/foundation/bootstrap.py` gets a `create_execution_provider()` factory.
- `core/runtime/actor.py` will route `Step(action="execute")` to the configured
  `ExecutionProvider` — addition, not replacement of `ToolRegistry`.
- `FirecrackerExecProvider.health_check()` returns `False` on this host.
- `LocalExecProvider` remains the functional fallback for local execution.
- First real Firecracker microVM execution is BLOCKED until a KVM-capable
  host is available.

## References

- ADR-001: OLEMARCHY / Atomic Agents Evaluation (deferred)
- Firecracker docs: https://github.com/firecracker-microvm/firecracker/blob/main/docs/getting-started.md
- KUDBEE architecture: `docs/architecture-v1.md`
- AGENTS.md §1.1 (Layer Discipline)
