# KILO Cloud Agent Execution Boundaries — Sandbox & Resource Isolation

**Purpose:** Defines the execution boundaries, sandboxing model, and resource isolation guarantees for KILO Cloud Agents. These boundaries ensure safe multi-tenancy, prevent resource exhaustion, and enforce governance policies.

---

## Boundary Model

Each agent executes within a **Boundary Context** that enforces:

```
┌─────────────────────────────────────────────────────────────────┐
│                      BOUNDARY CONTEXT                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Compute     │  │  Memory      │  │  Network             │  │
│  │  Isolation   │  │  Isolation   │  │  Isolation           │  │
│  │  (cgroups/   │  │  (cgroups/   │  │  (egress allowlist,  │  │
│  │   namespaces)│  │   namespaces)│  │   rate limits, TLS)  │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Filesystem  │  │  Device      │  │  Time                │  │
│  │  Isolation   │  │  Access      │  │  (monotonic, no sys  │  │
│  │  (chroot/    │  │  (GPU, USB,  │  │   time manipulation)  │  │
│  │   overlayfs) │  │   etc.)      │  │                      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Compute Isolation

### CPU Limits
| Mechanism | Description | Enforcement |
|-----------|-------------|-------------|
| **CPU Quota** | CFS quota/period (cgroups v2) | Hard limit — throttling |
| **CPU Shares** | Relative weight for scheduling | Soft limit — proportional |
| **CPU Affinity** | Pin to specific cores | Hard limit — placement |
| **Thread Limit** | Max threads per agent | Hard limit — `RLIMIT_NPROC` |

### Default Profiles by Category

| Category | CPU Quota | CPU Shares | Thread Limit | Affinity |
|----------|-----------|------------|--------------|----------|
| TASK_AGENT | 50% (1 core) | 512 | 64 | None |
| WORKFLOW_AGENT | 100% (2 cores) | 1024 | 128 | None |
| BATCH_AGENT | 400% (4 cores) | 2048 | 512 | Optional |
| STREAM_AGENT | 100% (1 core) | 1024 | 256 | Recommended |
| SUPERVISOR_AGENT | 50% (1 core) | 1024 | 64 | None |
| CNC_AGENT | 200% (2 cores) | 1024 | 128 | Recommended |

---

## Memory Isolation

### Memory Limits
| Mechanism | Description | Enforcement |
|-----------|-------------|-------------|
| **Memory Limit** | Hard limit (cgroups v2 `memory.max`) | OOM kill on exceed |
| **Memory Swap** | Swap limit (disabled by default) | OOM kill on exceed |
| **Memory Reservation** | Guaranteed minimum (cgroups v2 `memory.low`) | Best effort |

### Default Profiles by Category

| Category | Memory Limit | Memory Low | Swap |
|----------|--------------|------------|------|
| TASK_AGENT | 512 MB | 128 MB | Disabled |
| WORKFLOW_AGENT | 2 GB | 512 MB | Disabled |
| BATCH_AGENT | 8 GB | 2 GB | 2 GB |
| STREAM_AGENT | 1 GB | 256 MB | Disabled |
| SUPERVISOR_AGENT | 512 MB | 128 MB | Disabled |
| CNC_AGENT | 4 GB | 1 GB | 1 GB |

### OOM Handling
- Agent process receives `SIGKILL` on hard limit exceed
- Boundary context captures: memory usage at kill, allocation stack trace (if available)
- Telemetry: `agent.oom_killed` event with context
- Governance: Automatic quarantine, alert to SUPERVISOR_AGENT

---

## Network Isolation

### Egress Control
| Control | Description | Default |
|---------|-------------|---------|
| **Allowlist** | CIDR/hostname allowlist for outbound | Empty (deny all) |
| **Denylist** | CIDR/hostname blocklist | RFC1918 private ranges (configurable) |
| **Rate Limit** | Max requests/second per destination | 100 req/s |
| **Bandwidth Limit** | Max egress bandwidth | 100 Mbps |
| **TLS Enforcement** | Require TLS 1.2+ for all egress | Enforced |
| **DNS Control** | Custom DNS resolvers, blocked domains | Platform DNS only |

### Ingress Control
- Agents do NOT accept inbound connections by default
- Ingress allowed only via platform service mesh (sidecar)
- All inbound traffic authenticated & authorized

### Default Profiles by Category

| Category | Egress Allowlist | Rate Limit | Bandwidth | TLS |
|----------|------------------|------------|-----------|-----|
| TASK_AGENT | Platform APIs only | 50 req/s | 10 Mbps | Required |
| WORKFLOW_AGENT | Platform APIs + configured deps | 100 req/s | 50 Mbps | Required |
| BATCH_AGENT | Data sources + sinks | 500 req/s | 500 Mbps | Required |
| STREAM_AGENT | Stream sources + sinks | 1000 req/s | 1 Gbps | Required |
| CNC_AGENT | Manufacturing systems (configured) | 100 req/s | 100 Mbps | Required |

---

## Filesystem Isolation

### Isolation Layers
1. **Root filesystem** — Read-only base image (shared)
2. **Overlay filesystem** — Per-agent writable layer (copy-on-write)
3. **Volume mounts** — Explicitly declared, governed mounts
4. **Tmpfs** — Scratch space (size-limited, no persistence)

### Mount Policies
| Mount Type | Persistence | Governance | Default Size |
|------------|-------------|------------|--------------|
| **Overlay (root)** | Ephemeral | Automatic | 1 GB |
| **Workspace** | Durable (per task) | Task-scoped | 10 GB |
| **Cache** | Durable (shared) | Tenant-scoped | 5 GB |
| **Secrets** | Ephemeral (injected) | Runtime-injected | 64 KB |
| **Tmpfs** | Ephemeral | Automatic | 100 MB |

### Path Restrictions
- No access to host filesystem outside declared mounts
- No `/proc`, `/sys`, `/dev` access (except whitelisted virtual files)
- No absolute symlinks escaping overlay
- No `ptrace`, `debugfs`, `tracefs` access

---

## Device Access

### GPU Access
- **Mediated via** platform GPU scheduler (NVIDIA MIG / AMD MxGPU / Intel SR-IOV)
- **Allocation:** Exclusive per agent (no sharing in PR88)
- **Accounting:** GPU memory, compute %, encoder/decoder usage
- **Revocation:** On checkpoint, termination, or preemption

### Other Devices
| Device | Access Model | Governance |
|--------|--------------|------------|
| **USB** | Denied by default | Explicit approval |
| **Serial** | Denied by default | Explicit approval |
| **FPGA** | Mediated scheduler | Explicit approval |
| **TPM/HSM** | Platform-managed | Policy-controlled |

---

## Time Isolation

- **Monotonic clock** — `CLOCK_MONOTONIC` only (no `CLOCK_REALTIME` manipulation)
- **No `settimeofday`, `clock_settime`, `adjtimex`** — Blocked by seccomp
- **Time source** — Platform-provided NTP-synced time via VDSO
- **Deadline enforcement** — Wall-clock deadlines converted to monotonic at task start

---

## Seccomp / Syscall Filtering

### Default Policy: `default-deny` with explicit allowlist

**Always Allowed:**
- Process management: `fork`, `clone`, `execve`, `exit`, `wait4`
- Memory: `mmap`, `munmap`, `mprotect`, `brk`
- File I/O: `openat`, `read`, `write`, `close`, `stat`, `lseek`
- Network: `socket`, `connect`, `sendto`, `recvfrom`, `epoll`
- Time: `clock_gettime` (MONOTONIC only), `nanosleep`
- Sync: `futex`, `pselect6`, `ppoll`

**Conditionally Allowed (by capability):**
- `ptrace` — Only for DEBUG_AGENT category
- `bpf` — Only for MONITOR_AGENT category
- `mount`/`umount` — Only for PROVISION_AGENT category
- `ioctl` (GPU) — Only for GPU-allocated agents

**Always Denied:**
- `reboot`, `kexec_load`, `init_module`, `delete_module`
- `ptrace` (except DEBUG_AGENT)
- `process_vm_readv`, `process_vm_writev`
- `kcmp`, `userfaultfd`
- All `keyctl`, `add_key`, `request_key`

---

## Boundary Violation Handling

| Violation Type | Detection | Response |
|----------------|-----------|----------|
| **CPU Throttle** | cgroups throttled time > threshold | Telemetry alert, possible preemption |
| **OOM Kill** | Process killed by OOM | Quarantine, alert, forensic snapshot |
| **Network Policy** | Egress to non-allowlisted destination | Block connection, audit event, alert |
| **Filesystem Escape** | Path resolution outside mounts | Block syscall, audit event, terminate |
| **Syscall Violation** | Seccomp filter match | Block syscall, audit event, terminate |
| **GPU Overuse** | Memory/compute > allocation | Throttle, then revoke on persistent |
| **Time Manipulation** | Realtime syscall attempt | Block, audit, terminate |

---

## Multi-Tenancy Guarantees

| Guarantee | Mechanism | Verification |
|-----------|-----------|--------------|
| **CPU Fairness** | cgroups v2 CPU controller | Scheduler fairness index |
| **Memory Isolation** | cgroups v2 memory controller | No cross-tenant OOM |
| **Network Isolation** | Network namespaces + eBPF | No cross-tenant traffic |
| **Filesystem Isolation** | Overlayfs + mount namespaces | No cross-tenant file access |
| **Device Isolation** | Device cgroup + mediated passthrough | No cross-tenant device access |
| **Audit Isolation** | Per-tenant audit log streams | Immutable, tamper-evident |

---

## Implementation Requirements (PR89+)

- Boundary context creation MUST be atomic (all-or-nothing)
- Resource limits MUST be applied before agent code executes
- Violations MUST be detected synchronously (in-kernel where possible)
- All violations MUST emit audit events before response action
- Boundary context MUST be auditable (full configuration snapshot)

---

## References

- `agent-kernel.md` — Resource profile declaration
- `agent-categories.md` — Default profiles by category
- `governance/governance-hooks.md` — Violation → governance flow
- `governance/compliance-model.md` — Compliance expectations
- `telemetry/telemetry-expectations.md` — Boundary telemetry signals
- `integration/cloud-orchestration.md` — Platform boundary enforcement