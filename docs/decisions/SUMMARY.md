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
- Firecracker microVM boot is BLOCKED: no /dev/kvm (directory, not char device)
  on UpCloud Managed Kubernetes worker (PREMIUM-4xCPU-8GB plan)

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
- No existing ExecutionProvider, FirecrackerExecProvider, or core/execution/ package
- No execution-related config in ThinkBoxConfig
- core/foundation/config.py has a bug (uses Path without import)
- Existing architecture: AGENTS.md §1.1 defines 5 layers: Foundation → Provider →
  Memory → Governance/Tools → Runtime → Agent Implementations
- Firecracker belongs as a NEW "Execution" concern, NOT replacing any existing layer

## ADRs
- ADR-001: OLEMARCHY / Atomic Agents Evaluation — DEFERRED (Python 3.12+, stdlib violation)
- ADR-002: Firecracker Execution Boundary — ACCEPTED (conditional on KVM availability)

## Relevant Files
- @AGENTS.md: §13.4-13.6 updated with KVM/Firecracker blocker findings
- @docs/decisions/001-olemarchy-atomic-agents-evaluation.md: ADR-001
- @docs/decisions/002-firecracker-execution-boundary.md: ADR-002 (updated with KVM blocker)
- @core/runtime/agent.py: Agent class, ThinkBox dataclass, lifecycle
- @core/runtime/actor.py: Actor class — future execution routing point
- @core/runtime/planner.py: Step dataclass — action field determines execution
- @core/runtime/thinkbox.py: ThinkBoxState enum, ThinkBoxLifecycle
- @core/foundation/bootstrap.py: RuntimeContext, bootstrap() — future exec provider wiring
- @core/foundation/config.py: ThinkBoxConfig — needs exec_provider field
- @core/providers/base.py: ProviderRegistry pattern — model for ExecutionProviderRegistry
- @core/tools/registry.py: ToolRegistry, ToolDefinition, tool decorator
- @core/governance/audit.py: PermissionChecker, ApprovalGate, AuditLog
- @core/memory/store.py: MemoryStore (SQLite)
