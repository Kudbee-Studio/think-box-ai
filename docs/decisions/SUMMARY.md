## Goal
- Establish the Firecracker execution boundary for KUDBEE Think Box microVMs on UpCloud infrastructure.

## Constraints & Preferences
- Do NOT modify Kubernetes, containerd, host kernel, or cluster config
- Do NOT install OLEMARCHY/Atomic Agents yet — evaluation only
- Do NOT treat Docker/containers as a substitute for Firecracker microVMs
- Do NOT fake the Firecracker test
- Stdlib-only Python for core (Phase 0)

## Progress

### Done
- Comprehensive repository inspection: AGENTS.md, core/runtime/, core/foundation/,
  core/providers/, core/tools/, core/memory/, core/governance/, tests/, docs/
- READ-ONLY infrastructure discovery on UpCloud server (kudbee-host-v1, 212.147.250.183)
- Verified Firecracker v1.16.1 binary exists at /tmp/firecracker and responds to API
  requests over Unix socket (machine-config GET/PUT work)
- Verified vsock support: /dev/vsock, /dev/vhost-vsock, /dev/vhost-net all present
  and kernel modules loaded
- Downloaded and verified minimal Firecracker kernel (vmlinux.bin) and rootfs
  (boottime-rootfs.ext4) from official S3 bucket (spec.ccfc.min)
- Performed REAL microVM boot test with Firecracker InstanceStart
- Evaluated OLEMARCHY / Atomic Agents framework — documented in ADR-001, deferred

### In Progress
- None

### Blocked
- Firecracker microVM boot is BLOCKED: UpCloud API catalog confirms no
  bare-metal/nested-virt plans exist (DEV, STARTER, PREMIUM, CLOUDNATIVE,
  HIMEM, HICPU, GPU, GPU-SPOT only). Current host kudbee-host-v1
  (PREMIUM-4xCPU-8GB, fi-hel2) empirically lacks /dev/kvm. No other provider
  credentials are configured, so a KVM-capable host cannot be provisioned
  in this environment. Path forward documented in ADR-002.

## Optimization Research (Firecracker Best Practices)

### PVM — Pagetable Virtual Machine
- Proposed by Ant Group / Alibaba at SOSP 2023, LWN coverage Feb 2024
- Enables Firecracker on cloud VMs **without** nested virt or `/dev/kvm`
- x86_64 only (no arm64 support yet)
- Requires custom host kernel patches (~7000 lines, 73 patches) + patched Firecracker fork
  (`kvcache-ai/firecracker-next` or `leether/firecracker-next`)
- Packaging available via SlicerVM.com — automated deployment
- Status: RC — may remain internal at Alibaba per Phoronix coverage
- **Relevance for KUDBEE:** PVM kernel patches would need to be applied to the UpCloud
  node kernel. However, UpCloud Managed K8s restricts kernel modifications. A new
  non-managed (or dedicated) server would be required to use PVM.

### firecracker-containerd (AWS Official)
- Official project: containerd manages containers as Firecracker microVMs
- Daemon-based: containerd ↔ firecracker-control plugin ↔ firecracker-containerd ↔ Firecracker
- Complex setup: custom snapshotter, VM runtime shim, in-VM agent, custom rootfs builder
- CRI conformance / K8s compatibility on roadmap
- **Relevance:** NOT needed for KUDBEE Phase 1. We use direct Firecracker API over
  Unix socket. Future option for K8s orchestration integration (Phase 2+).

### firecracker-shim (PipeOpsHQ)
- Newer containerd shim v2 architecture (no middleman daemon)
- Converts OCI images → ext4 rootfs on-the-fly via `fsify`
- Standard CNI networking (bridge + host-local)
- VM pooling for <50ms warm starts
- 64–128MB memory per VM, ~2.5MB static agent binary
- Still requires `/dev/kvm` — NOT a PVM alternative
- **Relevance:** Excellent reference implementation for KUDBEE's
  `FirecrackerExecProvider` patterns: VM pooling, vsock communication,
  CNI networking, `fsify` for rootfs conversion, `fcctl`-style debug CLI

### Snapshotting & Forking Optimizations (Kernel Blog, Feb 2025)
- **Snapshot + fork pattern:** Boot microVM once → create snapshot → fork CoW clones
  - Cold start: boot → init → snapshot
  - Warm start: fork from CoW snapshot → resume → inject identity
- **CoW forking:** Clone overlay disk + guest memory via filesystem CoW
  (btrfs/XFS reflink) — child allocates blocks only on write
- **UFFD (User Fault File Descriptor):** Lazy memory paging during restore
  — multiple forks share snapshot page cache, hundreds of VMs in parallel
  - Requires Linux 5.7+ with `CONFIG_USERFAULT_FD`
- **Hot pools:** Pre-warmed VMs for <30ms handoff (10–30ms hit, <80ms connect)
- **Snapshot security:** Poor entropy when resuming from same snapshot
  — guest must reseed RNG on restore (`MADV_WIPEONSUSPEND` / VmGenId)
- **Host kernel:** cgroups V2 required (V1 causes high snapshot latency)
- **Relevance for KUDBEE:** `FirecrackerExecProvider` should implement
  snapshot+fork pattern once KVM is available. CoW requires btrfs or XFS
  with reflink. UFFD requires kernel 5.7+.

### Cloud Hypervisor vs Firecracker
- Cloud Hypervisor: Rust-based VMM, more features (live migration, CPU/memory hotplug)
- Firecracker: purpose-built microVM, simpler device model, faster boot
- **Relevance:** Firecracker remains correct for KUDBEE Phase 1. Cloud Hypervisor
  is a Phase 2+ option for advanced features (live migration, dynamic resizing).

## Key Findings

### Virtualization Status — BLOCKER
- **Host is a KVM guest** (systemd-detect-virt --vm returns "kvm")
- **No nested virtualization**: CPU flags have "hypervisor" but no "vmx"/"svm"
- **kvm_amd module fails**: "SVM not supported by CPU"
- **kvm_intel module fails**: "VMX not supported by CPU"
- **/dev/kvm is a directory**, not a character device — cannot be created with mknod
- **Firecracker InstanceStart fails** with: "Kvm error: Error creating KVM object:
  Is a directory (os error 21)"
- **UpCloud does not support nested virtualization** on any plan family
  (PREMIUM, CLOUDNATIVE, HIMEM, HICPU, STARTER, DEV)
- UpCloud does not currently offer bare-metal or dedicated-host plans

### Firecracker API Details (v1.16.1)
- Boot source: PUT /boot-source
- Rootfs (not /drive): PUT /drive/rootfs — wait, actually it's /drives/rootfs
  CORRECTION: In v1.16.1, the drive endpoint is PUT /drive/<drive_id> (singular)
- Machine config: PUT /machine-config — uses "smm" not "ht_enabled", uses "smt" field
- Actions: PUT /actions — action_type values are "InstanceStart", "SendCtrlAltDel"
  (NOT "InstanceHalt" which doesn't exist in v1.16.1)
- Console: GET /console_output — valid in v1.16.1

### Repository State
- `core/execution/` package now EXISTS: `base.py` (ExecResult, ExecutionProvider
  Protocol, ExecutionProviderRegistry, ExecutionUnavailableError), `local.py`
  (LocalExecProvider), `firecracker.py` (FirecrackerExecProvider), `__init__.py`.
- `ThinkBoxConfig` now has `exec_provider` (default "local") and `firecracker_config`.
- `core/foundation/config.py` Path import bug FIXED (added `from pathlib import Path`).
- `core/foundation/bootstrap.py` wires `execution_provider` into `RuntimeContext`
  via a lazy import inside `_create_execution_provider()` (composition root).
- `core/runtime/actor.py` routes `Step(action="execute", command=...)` to the
  execution provider; governance (approval gate + audit) stays above execution.
- `core/runtime/planner.py` `Step` gained an optional `command` field.
- `LocalExecProvider` is REAL and functional (asyncio subprocess) — the runtime's
  execution contract is satisfied today on the KVM-less host.
- `FirecrackerExecProvider` is fully implemented (REST API + vsock + lifecycle)
  but `health_check()` returns False here (no real /dev/kvm) and `execute()`
  raises ExecutionUnavailableError. Nothing is faked.
- Tests: `tests/unit/test_execution.py` (14 tests, mock Firecracker),
  `tests/integration/test_firecracker_execution.py` (real KUDBEE_FIRECRACKER_OK
  proof-of-life, auto-skips without KVM).
- Existing architecture: AGENTS.md §1.1 defines 5 layers: Foundation → Provider →
  Memory → Governance/Tools → Runtime → Agent Implementations. Execution is a NEW
  layer between Governance/Tools and Runtime. Firecracker stays behind it.

## ADRs
- ADR-001: OLEMARCHY / Atomic Agents Evaluation — DEFERRED (Python 3.12+, stdlib violation)
- ADR-002: Firecracker Execution Boundary — ACCEPTED (conditional on KVM availability)
- ADR-003: Execution Provider Abstraction — ACCEPTED (local + firecracker providers,
  honest KVM gating, governance above execution)

## Relevant Files
- @AGENTS.md: §13.4-13.6 updated with KVM/Firecracker blocker findings
- @docs/decisions/001-olemarchy-atomic-agents-evaluation.md: ADR-001
- @docs/decisions/002-firecracker-execution-boundary.md: ADR-002 (KVM blocker)
- @docs/decisions/003-execution-provider.md: ADR-003 (execution provider design)
- @core/execution/__init__.py: public surface (ExecResult, ExecutionProvider, registry)
- @core/execution/base.py: ExecResult, ExecutionProvider Protocol, ExecutionProviderRegistry
- @core/execution/local.py: LocalExecProvider (real subprocess)
- @core/execution/firecracker.py: FirecrackerExecProvider (KVM-gated, lifecycle)
- @core/runtime/actor.py: Actor — routes execute steps to execution provider
- @core/runtime/planner.py: Step — added optional command field
- @core/runtime/agent.py: Agent class, ThinkBox dataclass, lifecycle
- @core/runtime/thinkbox.py: ThinkBoxState enum, ThinkBoxLifecycle
- @core/foundation/bootstrap.py: RuntimeContext + _create_execution_provider (lazy import)
- @core/foundation/config.py: ThinkBoxConfig — exec_provider, firecracker_config (Path import fixed)
- @core/providers/base.py: ProviderRegistry pattern — model for ExecutionProviderRegistry
- @core/tools/registry.py: ToolRegistry, ToolDefinition, tool decorator
- @core/governance/audit.py: PermissionChecker, ApprovalGate, AuditLog
- @core/memory/store.py: MemoryStore (SQLite)
- @tests/unit/test_execution.py: 14 unit tests (mock Firecracker)
- @tests/integration/test_firecracker_execution.py: real proof-of-life, skips w/o KVM
