# KILO Cloud Agent Metrics Contract — Schema & Emission

**Purpose:** Defines the precise metrics schema, naming conventions, and emission requirements for KILO Cloud Agents. This ensures consistent, queryable, and actionable metrics across the platform.

---

## Naming Conventions

### Metric Name Format
```
kilo_<subsystem>_<entity>_<action>_<unit>
```

| Component | Format | Examples |
|-----------|--------|----------|
| **Prefix** | `kilo_` | Always |
| **Subsystem** | `agent`, `task`, `governance`, `resource`, `cloud`, `storage`, `network` | `kilo_agent_`, `kilo_task_` |
| **Entity** | Singular noun | `agent`, `task`, `cpu`, `memory`, `gpu` |
| **Action** | Verb phrase | `up`, `usage`, `duration`, `total`, `errors` |
| **Unit** | `_total` (counter), `_seconds` (histogram), `_bytes` (gauge/counter), `_percent` (gauge), `_ratio` (gauge) | `kilo_task_duration_seconds` |

### Label Naming
- **Snake_case:** `agent_id`, `task_type`, `error_code`
- **Standard labels (always present):** `agent_id`, `agent_type`, `tenant_id`
- **High-cardinality labels (avoid):** `task_id`, `request_id`, `trace_id` → use `trace_id` in exemplars instead
- **Units in label names:** Never (unit in metric name)

---

## Complete Metrics Registry

### Agent Subsystem (`kilo_agent_*`)

| Metric | Type | Labels | Unit | Description |
|--------|------|--------|------|-------------|
| `kilo_agent_up` | Gauge | `agent_id`, `agent_type`, `tenant_id`, `governance_tier` | 0/1 | Agent health |
| `kilo_agent_info` | Gauge | `agent_id`, `agent_type`, `agent_version`, `protocol_version`, `governance_tier` | 1 | Static metadata |
| `kilo_agent_uptime_seconds_total` | Counter | `agent_id` | seconds | Cumulative uptime |
| `kilo_agent_state` | Gauge | `agent_id`, `state` | 0/1 | Current state (spawned/initialized/idle/executing/checkpointed/completed/failed/cancelled/terminated) |
| `kilo_agent_state_transitions_total` | Counter | `agent_id`, `from_state`, `to_state` | count | State transition count |
| `kilo_agent_restarts_total` | Counter | `agent_id`, `reason` | count | Restart count |
| `kilo_agent_panics_total` | Counter | `agent_id` | count | Panic count |
| `kilo_agent_errors_total` | Counter | `agent_id`, `error_type`, `error_code` | count | Error count |
| `kilo_agent_last_task_completed_timestamp` | Gauge | `agent_id` | unix_ts | Last task completion time |

### Task Subsystem (`kilo_task_*`)

| Metric | Type | Labels | Unit | Description |
|--------|------|--------|------|-------------|
| `kilo_task_total` | Counter | `agent_id`, `task_type`, `outcome` | count | Task outcomes (success/failed/cancelled/timeout) |
| `kilo_task_duration_seconds` | Histogram | `agent_id`, `task_type` | seconds | End-to-end task latency |
| `kilo_task_execution_seconds` | Histogram | `agent_id`, `task_type` | seconds | Execution phase latency |
| `kilo_task_queue_wait_seconds` | Histogram | `agent_id`, `task_type` | seconds | Queue wait time |
| `kilo_task_retries_total` | Counter | `agent_id`, `task_type`, `retry_reason` | count | Retry attempts |
| `kilo_task_checkpoints_total` | Counter | `agent_id`, `task_type` | count | Checkpoints created |
| `kilo_task_checkpoint_size_bytes` | Histogram | `agent_id`, `task_type` | bytes | Checkpoint size |
| `kilo_task_restores_total` | Counter | `agent_id`, `task_type`, `outcome` | count | Restore attempts |
| `kilo_task_resource_cpu_seconds_total` | Counter | `agent_id`, `task_type` | cpu_seconds | CPU time consumed |
| `kilo_task_resource_memory_peak_bytes` | Gauge | `agent_id`, `task_type` | bytes | Peak memory |
| `kilo_task_resource_gpu_seconds_total` | Counter | `agent_id`, `task_type`, `gpu_id` | gpu_seconds | GPU time consumed |

### Governance Subsystem (`kilo_governance_*`)

| Metric | Type | Labels | Unit | Description |
|--------|------|--------|------|-------------|
| `kilo_governance_admission_requests_total` | Counter | `agent_id`, `action_type`, `decision` | count | Admission decisions (allowed/denied/error) |
| `kilo_governance_admission_latency_seconds` | Histogram | `agent_id`, `action_type` | seconds | Admission check latency |
| `kilo_governance_approval_requests_total` | Counter | `agent_id`, `gate_type`, `decision` | count | Approval outcomes (approved/denied/expired) |
| `kilo_governance_approval_latency_seconds` | Histogram | `agent_id`, `gate_type` | seconds | Approval wait time |
| `kilo_governance_token_active` | Gauge | `agent_id` | count | Active governance tokens |
| `kilo_governance_token_issued_total` | Counter | `agent_id`, `action_type` | count | Tokens issued |
| `kilo_governance_token_revoked_total` | Counter | `agent_id`, `reason` | count | Tokens revoked |
| `kilo_governance_policy_evaluations_total` | Counter | `agent_id`, `policy_version`, `decision` | count | Policy evaluations |
| `kilo_governance_policy_evaluation_seconds` | Histogram | `agent_id` | seconds | Policy evaluation latency |
| `kilo_governance_audit_events_total` | Counter | `agent_id`, `event_type` | count | Audit events emitted |
| `kilo_governance_audit_flush_latency_seconds` | Histogram | `agent_id` | seconds | Audit buffer flush latency |

### Resource Subsystem (`kilo_resource_*`)

| Metric | Type | Labels | Unit | Description |
|--------|------|--------|------|-------------|
| `kilo_resource_cpu_usage_percent` | Gauge | `agent_id` | percent | Current CPU usage |
| `kilo_resource_cpu_limit_percent` | Gauge | `agent_id` | percent | CPU limit (quota) |
| `kilo_resource_cpu_throttled_seconds_total` | Counter | `agent_id` | seconds | CPU throttled time |
| `kilo_resource_memory_usage_bytes` | Gauge | `agent_id` | bytes | Current RSS |
| `kilo_resource_memory_limit_bytes` | Gauge | `agent_id` | bytes | Memory limit |
| `kilo_resource_memory_cache_bytes` | Gauge | `agent_id` | bytes | Page cache |
| `kilo_resource_memory_swap_bytes` | Gauge | `agent_id` | bytes | Swap usage |
| `kilo_resource_memory_oom_kills_total` | Counter | `agent_id` | count | OOM kills |
| `kilo_resource_gpu_usage_percent` | Gauge | `agent_id`, `gpu_id` | percent | GPU compute utilization |
| `kilo_resource_gpu_memory_usage_bytes` | Gauge | `agent_id`, `gpu_id` | bytes | GPU memory used |
| `kilo_resource_gpu_memory_limit_bytes` | Gauge | `agent_id`, `gpu_id` | bytes | GPU memory limit |
| `kilo_resource_gpu_encoder_usage_percent` | Gauge | `agent_id`, `gpu_id` | percent | Encoder utilization |
| `kilo_resource_gpu_decoder_usage_percent` | Gauge | `agent_id`, `gpu_id` | percent | Decoder utilization |
| `kilo_resource_network_egress_bytes_total` | Counter | `agent_id`, `destination` | bytes | Network egress |
| `kilo_resource_network_ingress_bytes_total` | Counter | `agent_id`, `source` | bytes | Network ingress |
| `kilo_resource_network_connections_active` | Gauge | `agent_id` | count | Active connections |
| `kilo_resource_disk_read_bytes_total` | Counter | `agent_id`, `mount_point` | bytes | Disk reads |
| `kilo_resource_disk_write_bytes_total` | Counter | `agent_id`, `mount_point` | bytes | Disk writes |
| `kilo_resource_disk_usage_bytes` | Gauge | `agent_id`, `mount_point` | bytes | Disk usage |
| `kilo_resource_disk_limit_bytes` | Gauge | `agent_id`, `mount_point` | bytes | Disk limit |
| `kilo_resource_file_descriptors_open` | Gauge | `agent_id` | count | Open FDs |
| `kilo_resource_file_descriptors_limit` | Gauge | `agent_id` | count | FD limit |
| `kilo_resource_threads_active` | Gauge | `agent_id` | count | Active threads |
| `kilo_resource_threads_limit` | Gauge | `agent_id` | count | Thread limit |

### Cloud Subsystem (`kilo_cloud_*`)

| Metric | Type | Labels | Unit | Description |
|--------|------|--------|------|-------------|
| `kilo_cloud_api_calls_total` | Counter | `agent_id`, `provider`, `service`, `operation`, `outcome` | count | Cloud API calls |
| `kilo_cloud_api_latency_seconds` | Histogram | `agent_id`, `provider`, `service`, `operation` | seconds | Cloud API latency |
| `kilo_cloud_api_errors_total` | Counter | `agent_id`, `provider`, `service`, `operation`, `error_code` | count | Cloud API errors |
| `kilo_cloud_cost_estimated_usd_total` | Counter | `agent_id`, `provider`, `service` | USD | Estimated cost |
| `kilo_cloud_quota_usage_percent` | Gauge | `agent_id`, `provider`, `quota_type` | percent | Quota utilization |
| `kilo_cloud_instances_total` | Gauge | `agent_id`, `provider`, `instance_type`, `state` | count | Managed instances |

### Storage Subsystem (`kilo_storage_*`)

| Metric | Type | Labels | Unit | Description |
|--------|------|--------|------|-------------|
| `kilo_storage_operations_total` | Counter | `agent_id`, `storage_type`, `operation`, `outcome` | count | Storage ops |
| `kilo_storage_latency_seconds` | Histogram | `agent_id`, `storage_type`, `operation` | seconds | Storage latency |
| `kilo_storage_bytes_total` | Counter | `agent_id`, `storage_type`, `direction` | bytes | Bytes read/written |
| `kilo_storage_errors_total` | Counter | `agent_id`, `storage_type`, `operation`, `error_code` | count | Storage errors |

---

## Histogram Buckets

### Latency (seconds)
```
[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0]
```

### Size (bytes)
```
[1024, 4096, 16384, 65536, 262144, 1048576, 4194304, 16777216, 67108864, 268435456, 1073741824]
```

### Percent (0-100)
```
[10, 25, 50, 75, 90, 95, 99, 100]
```

---

## Emission Requirements

### Transport
| Environment | Transport | Endpoint |
|-------------|-----------|----------|
| **Kubernetes** | Prometheus Operator (ServiceMonitor) | `/metrics` |
| **VM/Bare Metal** | Prometheus Pushgateway | `pushgateway:9091` |
| **Serverless** | OTLP HTTP | `otel-collector:4318/v1/metrics` |
| **Local/Dev** | Prometheus Pushgateway | `localhost:9091` |

### Frequency
| Metric Type | Emission Interval |
|-------------|-------------------|
| **Gauges** | 10 seconds |
| **Counters** | On increment (batched, flush 10s) |
| **Histograms** | On observe (batched, flush 10s) |
| **Info** | On startup + change |

### Cardinality Limits
| Label | Max Unique Values |
|-------|-------------------|
| `agent_id` | Unbounded (per agent) |
| `agent_type` | < 20 (fixed taxonomy) |
| `tenant_id` | < 10000 |
| `task_type` | < 100 |
| `action_type` | < 30 |
| `error_code` | < 500 |
| `destination` | < 1000 (egress allowlist) |
| `gpu_id` | < 8 |
| `mount_point` | < 10 |

---

## Exemplars (Trace Correlation)

Every histogram observation SHOULD include exemplars with trace IDs:

```go
// Example: task duration with exemplar
histogram.Observe(duration.Seconds(), 
    prometheus.Labels{"agent_id": agentID, "task_type": taskType},
    prometheus.Exemplar{TraceID: traceID, SpanID: spanID})
```

---

## Metric Validation

### Pre-Registration Checks
```bash
# Validate metric names
kilo-metrics validate --rules naming,cardinality,units

# Check for duplicates
kilo-metrics check-duplicates

# Verify histogram buckets
kilo-metrics verify-buckets
```

### Runtime Validation
- **Cardinality alerts:** > 100k series per metric → alert
- **Stale metrics:** No update for 5min (gauges) → alert
- **Histogram buckets:** Empty buckets > 50% → alert

---

## Implementation Requirements (PR89+)

- Metrics library: `github.com/prometheus/client_golang` / `prometheus_client` (Python)
- Auto-registration: Decorator/annotation based
- Cardinality enforcement: Wrapper that rejects high-cardinality labels
- Exemplar support: Automatic from OpenTelemetry context
- Pushgateway: Batch writes, retry with backoff, TTL grouping
- Testing: Contract tests for every metric (name, type, labels, buckets)

---

## References

- `telemetry/telemetry-expectations.md` — Mandatory metrics by category
- `telemetry/tracing-model.md` — Trace integration with exemplars
- `governance/governance-hooks.md` — Governance metric definitions
- `core/execution-boundaries.md` — Resource metric sources
- `integration/scheduler-integration.md` — Scheduler metric integration