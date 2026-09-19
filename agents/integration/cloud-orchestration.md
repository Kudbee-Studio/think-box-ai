# KILO Cloud Agent Cloud Orchestration Integration — Platform Layer Hooks

**Purpose:** Defines how KILO Cloud Agents integrate with the cloud orchestration layer for provisioning, scaling, networking, and platform services.

---

## Orchestration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT                                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Orchestration Client                                   │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │   │
│  │  │ Capacity │ │ Service  │ │ Config   │ │  Secret    │  │   │
│  │  │ Request  │ │ Discovery│ │  Sync    │ │  Injection │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  CLOUD ORCHESTRATION LAYER                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────┐  │
│  │ SUPERVISOR│ │ PROVISION │ │  SERVICE │ │   CONFIG         │  │
│  │  AGENT   │ │  AGENT   │ │  MESH    │ │   MANAGER         │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Capacity Request Protocol

Agents request capacity; **SUPERVISOR_AGENT** or **PROVISION_AGENT** fulfills.

### Capacity Request
```python
class OrchestrationClient(Protocol):
    async def request_capacity(self, request: CapacityRequest) -> CapacityResponse: ...
    async def release_capacity(self, request: ReleaseRequest) -> None: ...
    async def discover_services(self, query: ServiceQuery) -> list[ServiceEndpoint]: ...
    async def watch_config(self, key: str) -> AsyncIterator[ConfigValue]: ...
    async def inject_secrets(self, spec: SecretInjectionSpec) -> SecretHandles: ...

class CapacityRequest:
    request_id: str
    agent_id: str
    tenant_id: str
    resource_profile: ResourceProfile
    duration_hint_seconds: int
    priority: "low" | "normal" | "high" | "critical"
    constraints: PlacementConstraints
    required_capabilities: list[str]

class CapacityResponse:
    request_id: str
    granted: bool
    allocation_id: str | None
    resources: AllocatedResources
    expires_at: datetime
    endpoints: dict[str, str]  # service_name -> endpoint
```

### Resource Profile (from agent-categories.md)
```json
{
  "cpu_cores": 2,
  "memory_mb": 4096,
  "gpu_required": true,
  "gpu_type": "L40S",
  "gpu_count": 1,
  "network_egress": true,
  "network_mbps": 1000,
  "disk_mb": 50000,
  "max_duration_seconds": 3600
}
```

### Placement Constraints
```json
{
  "zone": "us-chi1",
  "region": "us",
  "provider": "upcloud",
  "instance_types": ["CLOUDNATIVE-16xCPU-48GB"],
  "require_gpu": true,
  "gpu_types": ["L40S", "H100"],
  "tenancy": "dedicated",
  "compliance": ["SOC2", "ISO27001"],
  "data_residency": "US"
}
```

---

## Service Discovery

### Query Model
```json
{
  "service_name": "memory-store",
  "namespace": "kilo-platform",
  "tags": {"tier": "primary"},
  "health": "HEALTHY"
}
```

### Response
```json
{
  "endpoints": [
    {
      "service_name": "memory-store",
      "endpoint": "memory-store.kilo-platform.svc.cluster.local:8080",
      "protocol": "grpc",
      "health": "HEALTHY",
      "metadata": {"version": "1.2.0", "zone": "us-chi1"}
    }
  ],
  "ttl_seconds": 30
}
```

### Built-in Services
| Service | Protocol | Purpose |
|---------|----------|---------|
| `memory-store` | gRPC | Organizational memory |
| `vector-store` | gRPC/HTTP | Embeddings & search |
| `experiment-manager` | gRPC | Experiment tracking |
| `action-ledger` | gRPC | Audit trail |
| `scheduler` | gRPC | Work distribution |
| `admission-gate` | gRPC | Governance admission |
| `policy-engine` | HTTP | Policy evaluation |
| `token-service` | gRPC | Governance tokens |
| `approval-service` | gRPC | Human approvals |
| `dashboard` | HTTP | Observability UI |

---

## Configuration Sync

### Config Watch
```python
# Agent watches config keys
async for config in orchestration.watch_config("agent.defaults.task_timeout"):
    apply_config(config)
```

### Config Schema
```json
{
  "key": "agent.defaults.task_timeout",
  "value": 300,
  "type": "integer",
  "unit": "seconds",
  "description": "Default task timeout",
  "version": 42,
  "updated_at": "2026-09-19T03:00:00Z",
  "updated_by": "config-manager"
}
```

### Config Categories
| Prefix | Scope | Examples |
|--------|-------|----------|
| `agent.defaults.*` | All agents | `task_timeout`, `max_retries` |
| `agent.{type}.*` | By category | `agent.TASK_AGENT.max_concurrent` |
| `agent.{id}.*` | Specific agent | `agent.01ARZ...custom_param` |
| `platform.*` | Platform-wide | `platform.maintenance_window` |
| `tenant.{id}.*` | Tenant-specific | `tenant.abc.quota.cpu` |

---

## Secret Injection

### Injection Spec
```json
{
  "request_id": "uuid",
  "agent_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "secrets": [
    {
      "name": "DATABASE_URL",
      "path": "secret/data/tenant/abc/database",
      "version": "latest",
      "format": "env"
    },
    {
      "name": "TLS_CERT",
      "path": "secret/data/tenant/abc/tls",
      "version": "2026-09-01",
      "format": "file",
      "mount_path": "/etc/tls"
    }
  ],
  "injection_method": "env_file",  // env_file, memory, volume
  "rotation_policy": "auto"
}
```

### Injection Methods
| Method | Description | Use Case |
|--------|-------------|----------|
| `env_file` | Write `.env` file, source at startup | Most secrets |
| `memory` | Inject via process memory (no disk) | High-value keys |
| `volume` | Mount as files (tmpfs) | Certs, large configs |

### Rotation
- Platform manages rotation (Vault/Cloud KMS)
- Agent receives `SECRET_ROTATED` event via config watch
- Agent reloads secrets without restart (SIGHUP or callback)

---

## Network Orchestration

### Service Mesh Integration
- All agents auto-enrolled in Istio/Linkerd
- mTLS enforced for all service-to-service
- Sidecar injected at spawn (platform-managed)

### Traffic Policies (via Orchestration)
```json
{
  "policies": [
    {
      "from": "agent.TASK_AGENT",
      "to": "memory-store",
      "allow": true,
      "mtls": "STRICT",
      "rate_limit": "1000/s"
    },
    {
      "from": "agent.CNC_AGENT",
      "to": "external.manufacturing_api",
      "allow": true,
      "mtls": "STRICT",
      "egress_gateway": "manufacturing-egress"
    }
  ]
}
```

### DNS & Service Identity
- Agent identity: `spiffe://kilo.platform/agent/{agent_id}`
- Service identity: `spiffe://kilo.platform/service/{service_name}`
- DNS: `{service}.{namespace}.svc.cluster.local`

---

## Scaling Integration

### Horizontal Pod Autoscaler (K8s) / Instance Groups (VM)
```yaml
# Agent declares scaling hints
scaling:
  min_replicas: 2
  max_replicas: 100
  target_cpu_percent: 70
  target_memory_percent: 80
  target_queue_depth: 10
  scale_up_stabilization: 60s
  scale_down_stabilization: 300s
```

### Custom Metrics for Scaling
| Metric | Source | Description |
|--------|--------|-------------|
| `kilo_scheduler_queue_depth` | Scheduler | Tasks waiting per agent type |
| `kilo_agent_task_duration_seconds` | Agent | Latency pressure |
| `kilo_agent_error_rate` | Agent | Health pressure |
| `kilo_resource_cpu_usage_percent` | Agent | Resource pressure |

### Cluster Autoscaler Integration
- SUPERVISOR_AGENT triggers node group scaling
- Based on pending capacity requests
- Respects budget limits (cost accounting)

---

## Multi-Region / Hybrid

### Region Affinity
```json
{
  "region_preference": ["us-chi1", "us-sfo1", "eu-de1"],
  "failover_regions": ["us-lax1", "eu-fr1"],
  "data_residency": "US",
  "latency_slo_ms": 50
}
```

### Cross-Region Replication
| Data | Replication | RPO | RTO |
|------|-------------|-----|-----|
| Action Ledger | Sync (primary) + Async (secondary) | 0 | < 1 min |
| Memory Store | Async | < 1 hour | < 15 min |
| Vector Store | Async | < 1 hour | < 15 min |
| Artifacts (S3) | Cross-region replication | < 15 min | < 1 hour |

---

## Cost Accounting Integration

Every orchestration action emits cost events:
```json
{
  "event": "orchestration.capacity.allocated",
  "allocation_id": "uuid",
  "agent_id": "uuid",
  "tenant_id": "uuid",
  "provider": "upcloud",
  "instance_type": "CLOUDNATIVE-16xCPU-48GB",
  "region": "us-chi1",
  "estimated_hourly_usd": 2.50,
  "allocated_at": "2026-09-19T04:00:00Z",
  "expires_at": "2026-09-19T05:00:00Z"
}
```

### Budget Enforcement
- Per-tenant budgets (daily/monthly)
- Per-agent spend limits
- Real-time enforcement at orchestration layer
- Alerts at 50%, 80%, 100%

---

## Implementation Requirements (PR89+)

- Orchestration client: gRPC (primary) + HTTP (fallback)
- Service discovery: TTL-based caching (30s), background refresh
- Config watch: Long-polling, exponential backoff on disconnect
- Secret injection: At spawn + rotation callbacks
- Mesh: Platform-managed (agent declares requirements only)
- Scaling hints: Advisory (scheduler + SUPERVISOR_AGENT decide)
- Cost events: Fire-and-forget to cost accounting service

---

## References

- `core/cloud-interaction-model.md` — PAL interfaces for cloud ops
- `core/agent-categories.md` — Resource profiles by category
- `core/execution-boundaries.md` — Network/storage limits
- `governance/governance-hooks.md` — Provisioning requires approval
- `integration/scheduler-integration.md` — Scheduler capacity requests
- `telemetry/telemetry-expectations.md` — Orchestration metrics
- `telemetry/health-reporting.md` — Health for scaling decisions