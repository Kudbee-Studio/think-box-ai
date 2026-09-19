# KILO Cloud Agent Telemetry Expectations — Required Signals

**Purpose:** Defines the mandatory telemetry signals that every KILO Cloud Agent must emit. This ensures consistent observability across the platform.

---

## Telemetry Pillars

| Pillar | Purpose | Transport | Retention |
|--------|---------|-----------|-----------|
| **Metrics** | Quantitative measurements | Prometheus Pushgateway / OTLP | 90 days hot, 2 years cold |
| **Traces** | Request flows & latency | OTLP (Jaeger/Tempo) | 7 days hot, 90 days cold |
| **Logs** | Structured events | OTLP (Loki/Elastic) | 30 days hot, 1 year cold |
| **Profiles** | Continuous profiling | PySpy/eBPF → OTLP | 7 days |

---

## Metrics Contract

### Mandatory Metrics (Every Agent)

#### Agent Lifecycle
| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `kilo_agent_up` | Gauge | `agent_id`, `agent_type`, `tenant_id` | 1 if agent healthy, 0 if not |
| `kilo_agent_info` | Gauge | `agent_id`, `agent_type`, `agent_version`, `protocol_version`, `governance_tier` | Static info (value=1) |
| `kilo_agent_uptime_seconds` | Counter | `agent_id` | Total uptime |
| `kilo_agent_state` | Gauge | `agent_id`, `state` | Current state (1=active) |

#### Task Execution
| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `kilo_task_total` | Counter | `agent_id`, `task_type`, `outcome` | Total tasks (success/failed/cancelled) |
| `kilo_task_duration_seconds` | Histogram | `agent_id`, `task_type` | Task execution latency |
| `kilo_task_queue_wait_seconds` | Histogram | `agent_id`, `task_type` | Time waiting for task |
| `kilo_task_retries_total` | Counter | `agent_id`, `task_type` | Retry attempts |

#### Resource Usage
| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `kilo_agent_cpu_usage_percent` | Gauge | `agent_id` | Current CPU % |
| `kilo_agent_memory_usage_bytes` | Gauge | `agent_id` | Current RSS |
| `kilo_agent_memory_limit_bytes` | Gauge | `agent_id` | Memory limit |
| `kilo_agent_gpu_usage_percent` | Gauge | `agent_id`, `gpu_id` | GPU utilization |
| `kilo_agent_gpu_memory_bytes` | Gauge | `agent_id`, `gpu_id` | GPU memory used |
| `kilo_agent_network_egress_bytes_total` | Counter | `agent_id`, `destination` | Network egress |
| `kilo_agent_disk_read_bytes_total` | Counter | `agent_id` | Disk reads |
| `kilo_agent_disk_write_bytes_total` | Counter | `agent_id` | Disk writes |

#### Governance
| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `kilo_admission_requests_total` | Counter | `agent_id`, `action_type`, `decision` | Admission decisions |
| `kilo_admission_latency_seconds` | Histogram | `agent_id`, `action_type` | Admission check latency |
| `kilo_approval_requests_total` | Counter | `agent_id`, `gate_type`, `decision` | Approval outcomes |
| `kilo_approval_latency_seconds` | Histogram | `agent_id`, `gate_type` | Approval wait time |
| `kilo_governance_token_active` | Gauge | `agent_id` | Active tokens count |
| `kilo_audit_events_total` | Counter | `agent_id`, `event_type` | Audit events emitted |

#### Errors
| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `kilo_agent_errors_total` | Counter | `agent_id`, `error_type`, `error_code` | Error count by type |
| `kilo_agent_panics_total` | Counter | `agent_id` | Panic/crash count |
| `kilo_agent_restarts_total` | Counter | `agent_id`, `reason` | Restart count |

### Telemetry Profiles by Category

| Category | Profile | Additional Metrics |
|----------|---------|-------------------|
| **TASK_AGENT** | `standard` | — |
| **WORKFLOW_AGENT** | `standard` | `kilo_workflow_steps_total`, `kilo_workflow_step_duration_seconds` |
| **BATCH_AGENT** | `high-cardinality` | `kilo_batch_items_processed_total`, `kilo_batch_throughput_per_sec` |
| **STREAM_AGENT** | `streaming` | `kilo_stream_lag_seconds`, `kilo_stream_backpressure_total` |
| **SUPERVISOR_AGENT** | `supervisor` | `kilo_supervised_agents_count`, `kilo_supervisor_actions_total` |
| **CNC_AGENT** | `cnc` | `kilo_cnc_jobs_total`, `kilo_cnc_material_usage_kg`, `kilo_cnc_tool_wear_mm` |
| **PRIVILEGED** | `audit` | `kilo_privileged_ops_total`, `kilo_privileged_ops_duration_seconds` |

---

## Traces Contract

### Mandatory Spans

Every agent operation that crosses a boundary MUST create a trace span:

| Operation | Span Name | Attributes |
|-----------|-----------|------------|
| **Task Accept** | `agent.accept_task` | `agent.id`, `task.id`, `task.type`, `tenant.id` |
| **Task Execute** | `agent.execute_task` | `agent.id`, `task.id`, `task.type`, `resource.profile` |
| **Admission Check** | `governance.admission.check` | `agent.id`, `task.id`, `action.type`, `decision` |
| **Approval Wait** | `governance.approval.wait` | `agent.id`, `task.id`, `gate.type`, `duration_ms` |
| **Action Execute** | `agent.action.execute` | `agent.id`, `task.id`, `action.type`, `duration_ms`, `outcome` |
| **Checkpoint** | `agent.checkpoint` | `agent.id`, `task.id`, `checkpoint.id`, `size_bytes` |
| **Restore** | `agent.restore` | `agent.id`, `task.id`, `checkpoint.id`, `verified` |
| **Cloud API** | `cloud.api.call` | `agent.id`, `provider`, `service`, `operation`, `duration_ms` |
| **Storage Read** | `storage.read` | `agent.id`, `path`, `size_bytes`, `classification` |
| **Storage Write** | `storage.write` | `agent.id`, `path`, `size_bytes`, `classification` |

### Span Attributes (Standard)
```json
{
  "agent.id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "agent.type": "TASK_AGENT",
  "agent.version": "1.0.0",
  "tenant.id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "task.id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "task.type": "container_build",
  "governance.tier": "GOVERNED",
  "deployment.environment": "production",
  "kubernetes.pod.name": "kilo-agent-abc123",
  "kubernetes.namespace": "kilo-agents"
}
```

### Sampling
| Agent Category | Sample Rate |
|----------------|-------------|
| **TASK_AGENT** | 10% (tail-based: 100% on error) |
| **WORKFLOW_AGENT** | 25% (tail-based: 100% on error) |
| **BATCH_AGENT** | 1% (tail-based: 100% on error) |
| **STREAM_AGENT** | 5% (tail-based: 100% on error) |
| **PRIVILEGED** | 100% |
| **All Errors** | 100% (tail-based sampling) |

---

## Logs Contract

### Structured Log Format (JSON)
```json
{
  "timestamp": "2026-09-19T04:00:00.123456Z",
  "level": "INFO",
  "logger": "kilo.agent.task_agent",
  "message": "Task accepted for execution",
  "agent_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "task_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "tenant_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "trace_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "span_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "fields": {
    "task_type": "container_build",
    "queue_wait_ms": 45
  }
}
```

### Mandatory Log Events

| Event | Level | When |
|-------|-------|------|
| Agent started | INFO | Spawn |
| Agent initialized | INFO | Initialize complete |
| Task accepted | INFO | Task received |
| Task started | INFO | Execution begins |
| Checkpoint created | DEBUG | Periodic |
| Task completed | INFO | Success |
| Task failed | ERROR | Failure (with error context) |
| Task cancelled | WARN | Cancellation |
| Admission denied | WARN | Gate denies |
| Approval requested | INFO | Human approval needed |
| Approval received | INFO | Decision received |
| Resource limit warning | WARN | > 80% utilization |
| Resource limit exceeded | ERROR | Hard limit hit |
| Boundary violation | ERROR | Sandbox escape attempt |
| Agent terminating | INFO | Shutdown initiated |
| Agent terminated | INFO | Shutdown complete |

### Log Levels
- **DEBUG:** High-frequency, detailed (checkpoint, metrics flush)
- **INFO:** Normal operations (task start/end, state changes)
- **WARN:** Recoverable issues (retry, queue backup, soft limits)
- **ERROR:** Failures requiring attention (task fail, hard limits, violations)
- **CRITICAL:** Agent/Platform instability (panic, data corruption)

---

## Health Reporting

### Health Check Endpoint
Every agent MUST expose: `GET /health` (HTTP) or `HealthCheck` (gRPC)

### Health Response
```json
{
  "status": "HEALTHY",  // HEALTHY | DEGRADED | UNHEALTHY
  "agent_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "agent_type": "TASK_AGENT",
  "checks": [
    {
      "name": "dependencies",
      "status": "HEALTHY",
      "latency_ms": 12,
      "details": {"memory_store": "ok", "vector_store": "ok", "ledger": "ok"}
    },
    {
      "name": "resources",
      "status": "HEALTHY",
      "details": {"cpu_percent": 45, "memory_percent": 60, "disk_percent": 30}
    },
    {
      "name": "governance",
      "status": "HEALTHY",
      "details": {"admission_gate": "reachable", "token_valid": true}
    },
    {
      "name": "boundaries",
      "status": "HEALTHY",
      "details": {"seccomp": "active", "network_policy": "enforced"}
    }
  ],
  "uptime_seconds": 3600,
  "last_task_completed_at": "2026-09-19T03:55:00Z"
}
```

### Health Status Definitions
| Status | Meaning | Action |
|--------|---------|--------|
| **HEALTHY** | All checks pass, ready for work | Normal scheduling |
| **DEGRADED** | Non-critical issues (slow dep, high memory) | Schedule with caution, alert |
| **UNHEALTHY** | Critical failure (dep down, resource exhausted) | Remove from pool, alert, investigate |

### Readiness vs Liveness
| Probe | Purpose | Failure Action |
|-------|---------|----------------|
| **Liveness** (`/health/live`) | Process alive | Restart container |
| **Readiness** (`/health/ready`) | Ready for traffic | Remove from load balancer |

---

## Implementation Requirements (PR89+)

- Telemetry library: shared (OpenTelemetry SDK + custom instruments)
- Metrics: Prometheus exposition format + OTLP export
- Traces: W3C TraceContext propagation mandatory
- Logs: Structured JSON, level filtering, sampling
- Health: HTTP + gRPC, sub-second response
- Cardinality control: label value allowlists, automatic cleanup
- Cost: Telemetry budget < 5% of agent resources

---

## References

- `agent-kernel.md` — Telemetry emission as kernel responsibility
- `agent-lifecycle.md` — Health reporting at each transition
- `agent-categories.md` — Telemetry profiles by category
- `execution-boundaries.md` — Resource metrics from boundary
- `governance/governance-hooks.md` — Governance metrics
- `governance/approval-gates.md` — Approval latency metrics
- `integration/cloud-orchestration.md` — Cloud API tracing