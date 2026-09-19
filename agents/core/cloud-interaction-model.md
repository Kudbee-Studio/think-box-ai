# KILO Cloud Agent Cloud Interaction Model — Environment & Platform Integration

**Purpose:** Defines how KILO Cloud Agents interact with cloud environments — provisioning, networking, storage, identity, and platform services. This model ensures consistent, secure, and governable cloud operations across providers.

---

## Cloud Provider Abstraction

Agents interact with cloud resources through **Platform Abstraction Layer (PAL)** — never directly with provider SDKs.

```
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT                                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Platform Abstraction Layer (PAL)            │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────┐  │   │
│  │  │ Compute │ │ Storage │ │ Network │ │  Identity    │  │   │
│  │  │  API    │ │  API    │ │  API    │ │  & Secrets   │  │   │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └──────┬───────┘  │   │
│  └───────┼───────────┼───────────┼───────────┼────────────┘   │
└──────────┼───────────┼───────────┼───────────┼────────────────┘
           │           │           │           │
           ▼           ▼           ▼           ▼
    ┌─────────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐
    │  UpCloud    │ │ Upstash │ │Cloudflare│ │  Vault   │
    │  (Compute)  │ │ (Vector)│ │ (DNS/WAF)│ │ (Secrets)│
    └─────────────┘ └─────────┘ └─────────┘ └──────────┘
```

### PAL Principles
1. **No provider SDKs in agent code** — All via PAL interfaces
2. **Capability-based access** — Agents request capabilities, PAL enforces
3. **Audit-first** — Every PAL call emits audit event
4. **Governance-gated** — Destructive/billable ops require approval
5. **Failure transparency** — Errors map to standard taxonomy

---

## Compute Interaction

### Provisioning Model
- Agents do NOT provision compute directly
- **SUPERVISOR_AGENT** or **PROVISION_AGENT** handles provisioning
- Agents request capacity via **Capacity Request** protocol:
  ```json
  {
    "request_id": "uuid",
    "agent_id": "uuid",
    "resource_profile": { ... },
    "duration_hint_seconds": 3600,
    "priority": "normal",
    "tenant_id": "uuid"
  }
  ```

### Supported Compute Targets (via PAL)
| Target | Provider | Use Case | Governance |
|--------|----------|----------|------------|
| **VM** | UpCloud, AWS, GCP, Azure | General workloads | Standard |
| **Container** | Kubernetes (EKS/GKE/AKS), Cloud Run | Stateless, scalable | Standard |
| **Serverless** | AWS Lambda, Cloud Functions | Event-driven, burst | Standard |
| **GPU Instance** | UpCloud, AWS (p4/p5), GCP (A2/A3) | ML, rendering | Elevated |
| **Bare Metal** | UpCloud, Equinix Metal | High-perf, licensed | Restricted |

### Lifecycle via PAL
| Operation | PAL Method | Approval | Audit |
|-----------|------------|----------|-------|
| **Start** | `compute.start(instance_spec)` | If new instance | Yes |
| **Stop** | `compute.stop(instance_id)` | No | Yes |
| **Reboot** | `compute.reboot(instance_id)` | No | Yes |
| **Resize** | `compute.resize(instance_id, new_spec)` | Yes (billing) | Yes |
| **Snapshot** | `compute.snapshot(instance_id)` | No | Yes |
| **Terminate** | `compute.terminate(instance_id)` | Yes (data loss) | Yes |

---

## Storage Interaction

### Storage Abstractions
| Abstraction | PAL Interface | Use Case | Persistence |
|-------------|---------------|----------|-------------|
| **Object Store** | `storage.object.*` | Artifacts, logs, models | Durable |
| **Block Volume** | `storage.block.*` | Databases, scratch | Durable |
| **File Share** | `storage.file.*` | Shared workspaces | Durable |
| **Cache** | `storage.cache.*` | Temporary, high-speed | Ephemeral |
| **Vector Store** | `storage.vector.*` | Embeddings, search | Durable |

### Default Providers
| Abstraction | Primary | Fallback |
|-------------|---------|----------|
| Object Store | Upstash (Vector) / S3-compatible | Local MinIO |
| Block Volume | UpCloud Block Storage | Cloud provider native |
| File Share | NFS (managed) | EFS/Cloud Filestore |
| Cache | Upstash Redis | Local Redis |
| Vector Store | Upstash Vector | Local pgvector |

### Governance
- All storage operations via PAL (no direct SDK)
- Encryption at rest enforced by PAL
- Access controlled by tenant-scoped credentials
- Audit log for all read/write/delete/list

---

## Network Interaction

### Network Abstractions
| Abstraction | PAL Interface | Use Case |
|-------------|---------------|----------|
| **VPC/Network** | `network.vpc.*` | Isolation domain |
| **Subnet** | `network.subnet.*` | IP allocation |
| **Security Group** | `network.sg.*` | Firewall rules |
| **Load Balancer** | `network.lb.*` | Traffic distribution |
| **DNS Zone** | `network.dns.*` | Service discovery |
| **VPN/Tunnel** | `network.tunnel.*` | Hybrid connectivity |
| **Service Mesh** | `network.mesh.*` | mTLS, observability |

### Default Provider: Cloudflare + Provider VPC
- **DNS/WAF/CDN:** Cloudflare (global)
- **VPC/Subnet/SG:** Provider-native (UpCloud, AWS, etc.)
- **Service Mesh:** Istio (platform-managed)
- **Ingress:** Cloudflare Tunnel → Service Mesh

### Governance
- Network changes require NETWORK_AGENT or PRIVILEGED approval
- All security group changes audited
- DNS changes require change management process

---

## Identity & Secrets

### Identity Model
| Identity Type | PAL Interface | Lifetime | Rotation |
|---------------|---------------|----------|----------|
| **Agent Identity** | `identity.agent.*` | Agent lifetime | On restart |
| **Workload Identity** | `identity.workload.*` | Task lifetime | Per task |
| **Service Account** | `identity.sa.*` | Long-lived | 90 days |
| **Federated Token** | `identity.federated.*` | Short-lived (1hr) | Auto |

### Secrets Management
- **Vault:** HashiCorp Vault (platform-managed) or cloud KMS
- **Access:** PAL `secrets.*` interface only
- **Injection:** At agent spawn (env vars, files, memory)
- **Rotation:** Automatic (platform-managed)
- **Audit:** Every read/write/rotate logged

### Secret Types
| Type | Rotation | Access Pattern |
|------|----------|----------------|
| **API Keys** | 90 days | Read at startup |
| **Database Credentials** | 30 days | Read per connection |
| **TLS Certificates** | 90 days | Read at startup |
| **Signing Keys** | 1 year | Sign operation |
| **Encryption Keys** | 1 year | Encrypt/decrypt |

---

## Platform Services

### Core Platform Services (Always Available)
| Service | PAL Interface | Description |
|---------|---------------|-------------|
| **Experiment Manager** | `platform.experiment.*` | Experiment tracking |
| **Memory Store** | `platform.memory.*` | Organizational memory |
| **Action Ledger** | `platform.ledger.*` | Audit trail |
| **Scheduler** | `platform.scheduler.*` | Work distribution |
| **Dashboard** | `platform.dashboard.*` | Observability UI |
| **Vector Store** | `platform.vector.*` | Embeddings & search |

### Optional Platform Services
| Service | PAL Interface | Enablement |
|---------|---------------|------------|
| **CNC Engine** | `platform.cnc.*` | Tenant-licensed |
| **Burst Runner** | `platform.burst.*` | GPU quota required |
| **Swarm Coordinator** | `platform.swarm.*` | Multi-agent enabled |
| **Marketplace** | `platform.market.*` | PR92+ |

---

## Cloud Provider Support Matrix

| Capability | UpCloud | AWS | GCP | Azure | Local/Edge |
|------------|---------|-----|-----|-------|------------|
| **VM Provision** | ✅ Primary | ✅ | ✅ | ✅ | ✅ (KVM) |
| **Kubernetes** | ❌ | ✅ EKS | ✅ GKE | ✅ AKS | ✅ k3s |
| **Serverless** | ❌ | ✅ Lambda | ✅ Cloud Run | ✅ Functions | ❌ |
| **GPU** | ✅ L4/L40S/H100 | ✅ | ✅ | ✅ | ✅ (local) |
| **Object Storage** | ✅ | ✅ S3 | ✅ GCS | ✅ Blob | ✅ MinIO |
| **Block Storage** | ✅ | ✅ EBS | ✅ PD | ✅ Disk | ✅ LVM |
| **Managed DB** | ❌ | ✅ RDS | ✅ Cloud SQL | ✅ | ❌ |
| **Vector Store** | ❌ | ✅ OpenSearch | ✅ Vertex AI | ✅ | ✅ pgvector |
| **Service Mesh** | ❌ | ✅ App Mesh | ✅ ASM | ✅ | ✅ Istio |
| **WAF/DNS** | ❌ | ✅ Shield/Route53 | ✅ Armor/Cloud DNS | ✅ | ✅ Cloudflare |

---

## Multi-Cloud Strategy

### Primary-Secondary Model
- **Primary:** UpCloud (compute, block storage, GPU)
- **Secondary:** AWS/GCP/Azure (managed services, global reach)
- **Edge:** Cloudflare (DNS, WAF, CDN, Workers)
- **Data:** Upstash (Vector, Redis) + Provider object storage

### Failover
- Compute: Re-schedule on secondary (SUPERVISOR_AGENT)
- Storage: Cross-region replication (async)
- Network: DNS failover (Cloudflare)
- Identity: Federated across providers

---

## Cost Accounting

Every cloud interaction via PAL emits:
```json
{
  "event": "cloud.operation",
  "agent_id": "uuid",
  "tenant_id": "uuid",
  "provider": "upcloud|aws|gcp|azure|cloudflare|upstash",
  "service": "compute|storage|network|identity",
  "operation": "start|stop|read|write|...",
  "resource_id": "string",
  "estimated_cost_usd": "number",
  "currency": "USD",
  "timestamp": "ISO8601"
}
```

### Budget Enforcement
- Per-tenant daily/monthly budgets
- Per-agent spend limits
- Real-time enforcement at PAL layer
- Alerts at 50%, 80%, 100% thresholds

---

## Implementation Requirements (PR89+)

- PAL interfaces defined as Protocol classes (Python) / Interfaces (Go/TS)
- Each provider implements PAL SPI (Service Provider Interface)
- PAL handles: retry, timeout, circuit breaker, rate limiting
- All PAL calls: structured logging, distributed tracing, metrics
- Secrets: never in agent code, never in logs, never in artifacts

---

## References

- `agent-kernel.md` — Agent declares cloud capabilities needed
- `execution-boundaries.md` — Network/storage limits enforced at boundary
- `governance/governance-hooks.md` — Approval gates for cloud operations
- `governance/compliance-model.md` — Data residency, sovereignty
- `integration/cloud-orchestration.md` — Orchestration layer integration
- `integration/scheduler-integration.md` — Capacity requests via scheduler