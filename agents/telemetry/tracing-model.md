# KILO Cloud Agent Tracing Model — Distributed Tracing Integration

**Purpose:** Defines the distributed tracing model for KILO Cloud Agents, including span semantics, context propagation, sampling, and integration with OpenTelemetry.

---

## Tracing Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT                                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  OpenTelemetry SDK                                      │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │   │
│  │  │  Tracer  │ │  Span    │ │ Context  │ │  Exporter  │  │   │
│  │  │ Provider │ │ Processor│ │ Propagator│ │  (OTLP)    │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OTEL COLLECTOR                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────┐  │
│  │ Receiver │ │ Processor│ │  Exporter│ │  Tail Sampling     │  │
│  │ (OTLP)   │ │ (batch,  │ │ (Jaeger, │ │  (error=100%,      │  │
│  │          │ │  filter) │ │  Tempo)  │ │   latency>1s=100%) │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Context Propagation

### W3C TraceContext (Mandatory)
All agents MUST propagate `traceparent` and `tracestate` headers:

```
traceparent: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
tracestate: kilo=agent_id:01ARZ3NDEKTSV4RRFFQ69G5FAV,tenant_id:01ARZ3NDEKTSV4RRFFQ69G5FAV
```

### Propagation Formats
| Transport | Headers |
|-----------|---------|
| **HTTP** | `traceparent`, `tracestate` |
| **gRPC** | `traceparent`, `tracestate` metadata |
| **Message Queue** | Message headers/properties |
| **Internal** | Context.Context (Go) / contextvars (Python) |

### Baggage (Optional)
Additional context for correlation:
```
baggage: agent_id=01ARZ3NDEKTSV4RRFFQ69G5FAV,tenant_id=01ARZ3NDEKTSV4RRFFQ69G5FAV,task_type=container_build
```

---

## Span Semantics

### Span Kinds
| Kind | Use Case | Examples |
|------|----------|----------|
| **SERVER** | Incoming request handled | Task acceptance, health check |
| **CLIENT** | Outbound call | Cloud API, storage, governance |
| **PRODUCER** | Message sent | Event emission, queue publish |
| **CONSUMER** | Message received | Event consumption, queue poll |
| **INTERNAL** | Internal operation | Computation, checkpoint, validation |

### Standard Span Attributes (All Spans)
```json
{
  "kilo.agent.id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "kilo.agent.type": "TASK_AGENT",
  "kilo.agent.version": "1.0.0",
  "kilo.tenant.id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "kilo.task.id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "kilo.task.type": "container_build",
  "kilo.governance.tier": "GOVERNED",
  "deployment.environment": "production",
  "service.name": "kilo-agent",
  "service.version": "1.0.0",
  "service.instance.id": "kilo-agent-abc123"
}
```

### Operation-Specific Attributes

#### Task Execution (`agent.execute_task`)
```json
{
  "span.name": "agent.execute_task",
  "span.kind": "INTERNAL",
  "attributes": {
    "kilo.task.spec_hash": "sha256:...",
    "kilo.task.priority": "normal",
    "kilo.task.timeout_seconds": 300,
    "kilo.resource.profile.cpu_cores": 2,
    "kilo.resource.profile.memory_mb": 2048
  }
}
```

#### Governance Admission (`governance.admission.check`)
```json
{
  "span.name": "governance.admission.check",
  "span.kind": "CLIENT",
  "attributes": {
    "kilo.governance.action_type": "SHELL_EXEC",
    "kilo.governance.decision": "allowed",
    "kilo.governance.decision_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
    "kilo.governance.policy_version": "v3.2.1",
    "kilo.governance.evaluation_ms": 12
  }
}
```

#### Approval Wait (`governance.approval.wait`)
```json
{
  "span.name": "governance.approval.wait",
  "span.kind": "INTERNAL",
  "attributes": {
    "kilo.governance.gate_type": "HUMAN",
    "kilo.governance.request_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
    "kilo.governance.timeout_seconds": 3600,
    "kilo.governance.wait_ms": 45000
  }
}
```

#### Cloud API (`cloud.api.call`)
```json
{
  "span.name": "cloud.api.call",
  "span.kind": "CLIENT",
  "attributes": {
    "cloud.provider": "upcloud",
    "cloud.service": "compute",
    "cloud.operation": "start_instance",
    "cloud.region": "us-chi1",
    "cloud.request_id": "req-abc123",
    "http.status_code": 200,
    "kilo.cost.estimated_usd": 0.05
  }
}
```

#### Storage (`storage.read` / `storage.write`)
```json
{
  "span.name": "storage.write",
  "span.kind": "CLIENT",
  "attributes": {
    "storage.system": "upstash_vector",
    "storage.operation": "upsert",
    "storage.path": "vectors/tenant_abc/agent_xyz",
    "storage.size_bytes": 1048576,
    "storage.classification": "CONFIDENTIAL",
    "storage.duration_ms": 45
  }
}
```

---

## Span Events

### Standard Events
| Event Name | When | Attributes |
|------------|------|------------|
| `checkpoint.created` | Checkpoint persisted | `checkpoint.id`, `size_bytes`, `hash` |
| `checkpoint.restored` | State restored | `checkpoint.id`, `verified` |
| `resource.allocated` | Resources granted | `resource_type`, `amount` |
| `resource.released` | Resources returned | `resource_type`, `amount` |
| `boundary.violation` | Sandbox violation | `violation_type`, `syscall`, `blocked` |
| `approval.requested` | Human approval needed | `gate_type`, `request_id` |
| `approval.received` | Decision received | `decision`, `decided_by` |

---

## Sampling Strategy

### Head Sampling (At Span Creation)
| Condition | Sample Rate |
|-----------|-------------|
| **PRIVILEGED agents** | 100% |
| **Error spans** (span.status=ERROR) | 100% |
| **Governance spans** (admission, approval) | 100% |
| **TASK_AGENT** | 10% |
| **WORKFLOW_AGENT** | 25% |
| **BATCH_AGENT** | 1% |
| **STREAM_AGENT** | 5% |
| **CNC_AGENT** | 50% |

### Tail Sampling (At Collector)
| Condition | Sample Rate |
|-----------|-------------|
| **Error spans** | 100% |
| **Latency > 1s** | 100% |
| **Latency > 100ms** | 50% |
| **Governance spans** | 100% |
| **Resource exhaustion** | 100% |
| **Default** | Per-category head rate |

### Sampling Configuration (OTEL Collector)
```yaml
processors:
  tailsampling:
    decision_wait: 30s
    num_traces: 50000
    expected_new_traces_per_sec: 1000
    policies:
      - name: errors
        type: string_attribute
        string_attribute:
          key: "span.status"
          values: ["ERROR"]
      - name: high_latency
        type: latency
        latency:
          threshold_ms: 1000
      - name: governance
        type: string_attribute
        string_attribute:
          key: "kilo.governance.action_type"
          values: ["*"]
      - name: default
        type: probabilistic
        probabilistic:
          sampling_percentage: 10
```

---

## Span Status

| Status | Code | When |
|--------|------|------|
| **OK** | 0 | Normal completion |
| **ERROR** | 1 | Task failed, action denied, exception thrown |
| **TIMEOUT** | 2 | Deadline exceeded (mapped to ERROR + timeout attribute) |

### Error Recording
```python
span.set_status(Status(StatusCode.ERROR, "Task failed: compilation error"))
span.record_exception(exception, attributes={
    "kilo.error.type": "COMPILATION_ERROR",
    "kilo.error.code": "E001",
    "kilo.error.retryable": True
})
```

---

## Trace Correlation with Metrics & Logs

### Exemplars (Metrics → Traces)
Every histogram observation includes trace ID:
```go
histogram.Observe(duration, 
    labels,
    prometheus.Exemplar{TraceID: traceID, SpanID: spanID})
```

### Log Correlation (Logs → Traces)
Structured logs include trace context:
```json
{
  "trace_id": "0af7651916cd43dd8448eb211c80319c",
  "span_id": "b7ad6b7169203331",
  "trace_flags": "01"
}
```

---

## Performance Requirements

| Metric | Target |
|--------|--------|
| **Span Creation Overhead** | < 5 µs |
| **Context Propagation Overhead** | < 1 µs |
| **Export Batch Size** | 512 spans |
| **Export Interval** | 5 seconds |
| **Memory Overhead** | < 10 MB per 1000 spans/sec |
| **CPU Overhead** | < 2% of agent CPU |

---

## Implementation Requirements (PR89+)

- SDK: OpenTelemetry (language-native)
- Exporter: OTLP HTTP/gRPC (configurable endpoint)
- Processor: Batch (schedule: 5s, max queue: 2048)
- Sampler: Parent-based + Tail (collector-side)
- Resource Detectors: Kubernetes, Cloud, Process, Host
- Attribute Limits: 128 attributes/span, 256 char values
- Event Limits: 32 events/span
- Link Limits: 128 links/span

---

## References

- `telemetry/telemetry-expectations.md` — Mandatory spans by category
- `telemetry/metrics-contract.md` — Exemplar correlation
- `governance/governance-hooks.md` — Governance span definitions
- `core/cloud-interaction-model.md` — Cloud API tracing
- `integration/scheduler-integration.md` — Scheduler trace integration