# KUDBEE Think Box — Firecracker VM Architecture

## Overview

Each KUDBEE Think Box runs as an isolated Firecracker microVM. This provides:

- **Strong isolation** — Each box is a separate VM, not just a container
- **Security** — Hardware-enforced boundaries between agents
- **Persistence** — VM state survives agent restarts
- **Resource control** — CPU, memory, and GPU allocation per box
- **Snapshot support** — Save/restore box state

## Architecture Diagram

```
UPCLOUD HOST (GPU Server)
┌─────────────────────────────────────────────────────────────┐
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Firecracker MicroVM (Think Box)                       │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │ Guest OS (Ubuntu 24.04 minimal)                 │  │  │
│  │  │  ┌───────────────────────────────────────────┐  │  │  │
│  │  │  │ KUDBEE Agent Runtime                      │  │  │  │
│  │  │  │  ├─ Agent identity + credentials          │  │  │  │
│  │  │  │  ├─ Planner                               │  │  │  │
│  │  │  │  ├─ Actor (tool execution)                │  │  │  │
│  │  │  │  ├─ Observer (result validation)           │  │  │  │
│  │  │  │  ├─ Memory (session/task/org)             │  │  │  │
│  │  │  │  └─ Capability tokens                     │  │  │  │
│  │  │  └───────────────────────────────────────────┘  │  │  │
│  │  │  ┌───────────────────────────────────────────┐  │  │  │
│  │  │  │ Tools / Capabilities                      │  │  │  │
│  │  │  │  ├─ shell_exec (scoped)                   │  │  │  │
│  │  │  │  ├─ filesystem (scoped)                   │  │  │  │
│  │  │  │  ├─ http_request (filtered)               │  │  │  │
│  │  │  │  ├─ memory_query / memory_write           │  │  │  │
│  │  │  │  ├─ model_inference (via provider)        │  │  │  │
│  │  │  │  └─ media_generation (ACE-Step, SD)       │  │  │  │
│  │  │  └───────────────────────────────────────────┘  │  │  │
│  │  │  ┌───────────────────────────────────────────┐  │  │  │
│  │  │  │ Model Providers                           │  │  │  │
│  │  │  │  ├─ Ollama (local: GPT-OSS, LLaMA)        │  │  │  │
│  │  │  │  ├─ ACE-Step (local: music)               │  │  │  │
│  │  │  │  ├─ Stable Diffusion (local: images)       │  │  │  │
│  │  │  │  ├─ Coqui TTS (local: voice)               │  │  │  │
│  │  │  │  └─ Cloud APIs (fallback)                  │  │  │  │
│  │  │  └───────────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  │  ├─ virtio-block (root filesystem)                    │  │
│  │  ├─ virtio-net (network via tap)                      │  │
│  │  ├─ vsock (host communication)                        │  │
│  │  └─ GPU (mediated via vGPU or MIG)                    │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Firecracker MicroVM (Think Box #2)                    │  │
│  │  └─ ... (same structure, isolated)                   │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ KUDBEE Control Plane                                  │  │
│  │  ├─ Box lifecycle (create/start/stop/snapshot)       │  │
│  │  ├─ Resource scheduler                                │  │
│  │  ├─ Capability registry                               │  │
│  │  ├─ Token/identity service                            │  │
│  │  ├─ Memory persistence (SQLite/Vector)                │  │
│  │  ├─ Health monitoring + auto-heal                     │  │
│  │  └─ Audit logging                                     │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Resource Allocation

| Box Type | vCPUs | RAM | GPU | Storage | Use Case |
|----------|-------|-----|-----|---------|----------|
| **Minimal** | 1 | 2 GB | shared | 10 GB | Simple tasks, chat |
| **Standard** | 2 | 4 GB | shared | 20 GB | Multi-tool agents |
| **GPU Worker** | 4 | 16 GB | 1x L40S | 50 GB | Image/video generation |
| **Memory** | 2 | 8 GB | shared | 100 GB | Knowledge-intensive |
| **Full** | 8 | 32 GB | 2x L40S | 200 GB | Production pipelines |

## Boot Flow

```
1. User requests Think Box creation
2. Control Plane selects resource profile
3. Firecracker API creates microVM
4. Guest OS boots from rootfs snapshot
5. Agent identity injected via vsock
6. Agent runtime starts
7. Box registers with Control Plane
8. Box appears in dashboard
9. User interacts via web/CLI
```

## Security Boundary

| Layer | Protection |
|-------|------------|
| **Hardware** | VT-x/AMD-V isolation |
| **Hypervisor** | Firecracker KVM |
| **Guest** | Minimal attack surface (no shell, no SSH) |
| **Network** | MicroVM tap + iptables filtering |
| **Filesystem** | Read-only rootfs + tmpfs overlays |
| **GPU** | MIG (Multi-Instance GPU) partitioning |
| **Communication** | vsock with capability tokens |

## Communication Paths

```
┌──────────────┐     vsock      ┌──────────────────┐
│  Think Box   │◄──────────────►│  Control Plane   │
│  (Firecracker)│                │  (Host)          │
└──────────────┘                └──────────────────┘
       │                                │
       │  capability token              │  API calls
       ▼                                ▼
┌──────────────┐                ┌──────────────────┐
│  Tools /     │                │  UpCloud API     │
│  Models      │                │  Cloud Resources │
└──────────────┘                └──────────────────┘
```

## Snapshot & Restore

```bash
# Pause box for snapshot
curl --unix socket /tmp/firecracker.sock \
  -X PATCH 'http://localhost/vm' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{ "state": "Paused" }'

# Create snapshot
curl --unix socket /tmp/firecracker.sock \
  -X PUT 'http://localhost/snapshot/create' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "snapshot_type": "Full",
    "snapshot_path": "/opt/kudbee/snapshots/box-uuid.mem",
    "mem_file_path": "/opt/kudbee/snapshots/box-uuid.vmstate"
  }'

# Restore from snapshot
curl --unix socket /tmp/firecracker.sock \
  -X PUT 'http://snapshot/load' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "snapshot_path": "/opt/kudbee/snapshots/box-uuid.mem",
    "mem_backend": {
      "backend_type": "File",
      "backend_path": "/opt/kudbee/snapshots/box-uuid.vmstate"
    }
  }'
```

## Implementation Phases

### Phase 1: Foundation ✅
- [x] GPU server with 3x L40S
- [x] Docker containers for models
- [x] Ollama with GPT-OSS
- [x] ACE-Step music generation
- [x] Basic CLI and web UI

### Phase 2: Container Orchestration ✅
- [x] Docker-based Think Boxes
- [x] Resource limits per container
- [x] Network isolation
- [x] Persistent storage

### Phase 3: Firecracker Isolation ⏳ (CURRENT)
- [ ] Install Firecracker binary
- [ ] Create minimal rootfs images
- [ ] Configure vsock communication
- [ ] Implement snapshot/restore
- [ ] GPU passthrough (MIG)

### Phase 4: Production Hardening ⏳
- [ ] Capential-based auth between boxes
- [ ] Automated snapshot scheduling
- [ ] Health monitoring per box
- [ ] Auto-heal and restart policies
- [ ] Audit logging and evidence chains

### Phase 5: Enterprise Features ⏳
- [ ] Multi-tenant isolation
- [ ] Compliance frameworks
- [ ] SOC 2 evidence collection
- [ ] RBAC and governance
- [ ] Usage-based billing
