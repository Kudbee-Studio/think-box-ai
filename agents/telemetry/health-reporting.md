# KILO Cloud Agent Health Reporting — Readiness & Liveness

**Purpose:** Defines the health reporting requirements for KILO Cloud Agents, including health check endpoints, status definitions, and integration with platform orchestration.

---

## Health Check Endpoints

### HTTP Endpoints (Required)

| Endpoint | Purpose | Method | Auth |
|----------|---------|--------|------|
| `/health/live` | Liveness probe | GET | None |
| `/health/ready` | Readiness probe | GET | None |
| `/health` | Full health status | GET | Optional (Bearer) |
| `/health/metrics` | Prometheus metrics | GET | None |

### gRPC Endpoint (Required)
```protobuf
service Health {
  rpc Check(HealthCheckRequest) returns (HealthCheckResponse);
  rpc Watch(HealthCheckRequest) returns (stream HealthCheckResponse);
}
```

---

## Health Response Format

### Liveness (`/health/live`)
```json
{
  "status": "ALIVE",
  "agent_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "timestamp": "2026-09-19T04:00:00.123Z"
}
```
- **ALIVE:** Process responding
- **DEAD:** Not responding (triggers restart)

### Readiness (`/health/ready`)
```json
{
  "status": "READY",  // READY | NOT_READY
  "agent_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "checks": [
    {"name": "dependencies", "status": "PASS", "latency_ms": 5},
    {"name": "resources", "status": "PASS", "details": {"cpu": 45, "memory": 60}},
    {"name": "governance", "status": "PASS", "details": {"admission_gate": "reachable"}}
  ],
  "timestamp": "2026-09-19T04:00:00.123Z"
}
```
- **READY:** Can accept work
- **NOT_READY:** Remove from scheduler pool

### Full Health (`/health`)
```json
{
  "status": "HEALTHY",  // HEALTHY | DEGRADED | UNHEALTHY
  "agent_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "agent_type": "TASK_AGENT",
  "agent_version": "1.0.0",
  "protocol_version": "1.0",
  "governance_tier": "GOVERNED",
  "tenant_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "uptime_seconds": 3600,
  "checks": [
    {
      "name": "dependencies",
      "status": "PASS",
      "latency_ms": 12,
      "details": {
        "memory_store": "ok",
        "vector_store": "ok", 
        "ledger": "ok",
        "scheduler": "ok"
      }
    },
    {
      "name": "resources",
      "status": "PASS",
      "details": {
        "cpu_percent": 45,
        "cpu_limit_percent": 80,
        "memory_percent": 60,
        "memory_limit_percent": 75,
        "disk_percent": 30,
        "disk_limit_percent": 50,
        "gpu_percent": 0,
        "network_connections": 12
      }
    },
    {
      "name": "governance",
      "status": "PASS",
      "details": {
        "admission_gate": "reachable",
        "policy_engine": "reachable",
        "token_valid": true,
        "token_expires_in_seconds": 300
      }
    },
    {
      "name": "boundaries",
      "status": "PASS",
      "details": {
        "seccomp": "active",
        "network_policy": "enforced",
        "filesystem_isolation": "active"
      }
    },
    {
      "name": "task_execution",
      "status": "PASS",
      "details": {
        "current_task_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "task_progress_percent": 45,
        "task_started_at": "2026-09-19T03:58:00Z"
      }
    }
  ],
  "metrics_summary": {
    "tasks_completed": 150,
    "tasks_failed": 2,
    "tasks_cancelled": 1,
    "avg_task_duration_ms": 1200,
    "error_rate_5m": 0.001
  },
  "last_task_completed_at": "2026-09-19T03:55:00Z",
  "timestamp": "2026-09-19T04:00:00.123Z"
}
```

---

## Check Definitions

### 1. Dependencies Check
Verifies connectivity to required platform services:
| Dependency | Check | Timeout | Failure Status |
|------------|-------|---------|----------------|
| Memory Store | gRPC health | 2s | DEGRADED |
| Vector Store | HTTP /health | 2s | DEGRADED |
| Action Ledger | SQLite ping | 1s | UNHEALTHY |
| Scheduler | gRPC health | 2s | DEGRADED |
| Admission Gate | gRPC health | 2s | UNHEALTHY |
| Policy Engine | HTTP /health | 2s | UNHEALTHY |
| Governance Token | Token introspect | 1s | UNHEALTHY |

### 2. Resources Check
Verifies resource utilization within limits:
| Resource | Warning Threshold | Critical Threshold | Failure Status |
|----------|-------------------|-------------------|----------------|
| CPU | > 80% | > 95% | DEGRADED / UNHEALTHY |
| Memory | > 80% | > 95% | DEGRADED / UNHEALTHY |
| Disk | > 80% | > 95% | DEGRADED / UNHEALTHY |
| GPU Memory | > 80% | > 95% | DEGRADED / UNHEALTHY |
| File Descriptors | > 80% | > 95% | DEGRADED / UNHEALTHY |
| Threads | > 80% | > 95% | DEGRADED / UNHEALTHY |

### 3. Governance Check
Verifies governance connectivity and authorization:
| Component | Check | Failure Status |
|-----------|-------|----------------|
| Admission Gate | gRPC reachable + auth | UNHEALTHY |
| Policy Engine | HTTP reachable | UNHEALTHY |
| Token Service | Token valid + not expiring < 60s | UNHEALTHY |
| Audit Ledger | Write test entry | DEGRADED |

### 4. Boundaries Check
Verifies sandbox enforcement:
| Boundary | Check | Failure Status |
|----------|-------|----------------|
| Seccomp | Filter active | UNHEALTHY |
| Network Policy | Egress allowlist enforced | UNHEALTHY |
| Filesystem | Overlay mount valid | UNHEALTHY |
| Capabilities | Minimal caps only | DEGRADED |

### 5. Task Execution Check
Verifies task processing health:
| Check | Warning | Critical |
|-------|---------|----------|
| Task stuck (> 2x timeout) | — | UNHEALTHY |
| No heartbeat (> 30s) | — | UNHEALTHY |
| Error rate 5m > 10% | DEGRADED | UNHEALTHY |
| Queue depth > 100 | DEGRADED | — |

---

## Health Status Definitions

| Status | Meaning | Scheduler Action | Alerting |
|--------|---------|------------------|----------|
| **HEALTHY** | All checks PASS | Normal scheduling | None |
| **DEGRADED** | Non-critical checks WARN | Schedule with reduced weight | Warning (PagerDuty/Slack) |
| **UNHEALTHY** | Critical checks FAIL | Remove from pool immediately | Critical (PagerDuty + On-call) |

### State Transitions
```
HEALTHY ──degraded check──▶ DEGRADED ──critical check──▶ UNHEALTHY
   ▲                        │                          │
   │                        │ recovered                │ recovered
   └────────────────────────┴──────────────────────────┘
```

---

## Integration with Platform Orchestration

### Kubernetes Probes
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
```

### Scheduler Integration
- Scheduler polls `/health/ready` every 10s
- `READY` → Agent in pool, receives tasks
- `NOT_READY` → Agent removed from pool, in-flight tasks allowed to complete
- `UNHEALTHY` → SUPERVISOR_AGENT notified for replacement

### SUPERVISOR_AGENT Actions
| Health Status | Action |
|---------------|--------|
| **DEGRADED** (persistent > 5m) | Drain tasks, schedule replacement |
| **UNHEALTHY** | Immediate termination, spawn replacement |
| **Liveness FAIL** | Immediate restart (K8s) or respawn (VM) |

---

## Health Reporting via Telemetry

### Metrics
| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `kilo_agent_health_status` | Gauge | `agent_id`, `status` | 1 for current status |
| `kilo_agent_health_check_duration_seconds` | Histogram | `agent_id`, `check_name` | Check latency |
| `kilo_agent_health_check_failures_total` | Counter | `agent_id`, `check_name` | Failed checks |

### Structured Log
```json
{
  "timestamp": "2026-09-19T04:00:00Z",
  "level": "INFO",
  "logger": "kilo.agent.health",
  "message": "Health check completed",
  "agent_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "status": "HEALTHY",
  "checks_passed": 5,
  "checks_warned": 0,
  "checks_failed": 0,
  "duration_ms": 45
}
```

---

## Implementation Requirements (PR89+)

- Health server: Separate goroutine/thread, non-blocking
- Check execution: Parallel with timeout, cached results (5s TTL)
- Dependency checks: Circuit breaker (fail fast after 3 failures)
- Resource checks: Read from cgroups / `/proc` / platform APIs
- Governance checks: Token validation without network call (local JWKS cache)
- Response time: < 100ms for `/health/ready`, < 50ms for `/health/live`
- No secrets in health response (token hash only)

---

## References

- `telemetry/telemetry-expectations.md` — Health as telemetry signal
- `telemetry/metrics-contract.md` — Health metrics definitions
- `core/agent-lifecycle.md` — Health at lifecycle transitions
- `core/execution-boundaries.md` — Boundary health checks
- `governance/governance-hooks.md` — Governance connectivity
- `integration/scheduler-integration.md` — Scheduler health integration