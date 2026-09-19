# KILO Cloud Agent Protocol Responsibilities — Message Formats & Duties

**Purpose:** Defines the protocol responsibilities, message formats, and communication contracts for KILO Cloud Agents. This ensures interoperability across agent implementations and platform services.

---

## Protocol Overview

### Communication Patterns
| Pattern | Use Case | Transport |
|---------|----------|-----------|
| **Request-Response** | Synchronous operations | gRPC / HTTP |
| **Streaming** | High-frequency telemetry, logs | gRPC streaming / WebSocket |
| **Pub/Sub** | Events, notifications | NATS / Kafka / gRPC streaming |
| **Long-Polling** | Work pull, config watch | HTTP |

### Protocol Versions
- **v1.0** (PR88): Initial protocol — this document
- **Versioning:** Semantic (MAJOR.MINOR.PATCH)
- **Compatibility:** MAJOR = breaking, MINOR = additive, PATCH = fixes
- **Negotiation:** Client declares supported versions at registration

---

## Core Protocol: Agent ↔ Scheduler

### Registration
```protobuf
// Agent registers with scheduler
message AgentRegistration {
  string agent_id = 1;
  string agent_type = 2;
  string agent_version = 3;
  string protocol_version = 4;
  repeated string capabilities = 5;
  ResourceProfile resource_profile = 6;
  string governance_tier = 7;
  string tenant_id = 8;
  map<string, string> metadata = 9;
}

message RegistrationResponse {
  bool accepted = 1;
  string scheduler_version = 2;
  repeated string supported_protocol_versions = 3;
  map<string, string> config = 4;
  string error = 5;
}
```

### Work Pull
```protobuf
message PullWorkRequest {
  string agent_id = 1;
  int32 max_tasks = 2;
  int32 accept_timeout_seconds = 3;
  repeated string preferred_task_types = 4;
}

message PullWorkResponse {
  repeated TaskAssignment tasks = 1;
  int32 next_pull_after_seconds = 2;
  string scheduler_time = 3;  // ISO8601
}

message TaskAssignment {
  string task_id = 1;
  string task_type = 2;
  google.protobuf.Struct task_spec = 3;
  int32 priority = 4;
  string deadline = 5;  // ISO8601
  string governance_token = 6;
  string experiment_id = 7;
  string think_box_id = 8;
  map<string, string> metadata = 9;
}
```

### Task Outcome
```protobuf
message TaskOutcomeReport {
  string task_id = 1;
  string agent_id = 2;
  TaskOutcome outcome = 3;
  string completed_at = 4;
  int64 duration_ms = 5;
  ResourceUsage resource_usage = 6;
  string result_ref = 7;
  TaskError error = 8;
  GovernanceSummary governance = 9;
  VerificationSummary verification = 10;
}

enum TaskOutcome {
  SUCCESS = 0;
  FAILED = 1;
  CANCELLED = 2;
  TIMEOUT = 3;
}
```

### Heartbeat
```protobuf
message Heartbeat {
  string agent_id = 1;
  int64 sequence = 2;
  string timestamp = 3;
  AgentStatus status = 4;
  string current_task_id = 5;
  int32 task_progress_percent = 6;
  ResourceSnapshot resource_snapshot = 7;
}

message HeartbeatResponse {
  bool ack = 1;
  int64 sequence = 2;
  string scheduler_time = 3;
  repeated SchedulerCommand commands = 4;
  ConfigUpdates config_updates = 5;
}

enum SchedulerCommandType {
  PREEMPT = 0;
  PAUSE = 1;
  RESUME = 2;
  TERMINATE = 3;
  CONFIG_UPDATE = 4;
}
```

### Capacity Report
```protobuf
message CapacityReport {
  string agent_id = 1;
  string timestamp = 2;
  ResourceCapacity capacity = 3;
  HealthStatus health = 4;
  AgentPreferences preferences = 5;
}
```

---

## Governance Protocol: Agent ↔ Admission Gate

### Admission Check
```protobuf
message AdmissionRequest {
  string agent_id = 1;
  string task_id = 2;
  string action_type = 3;
  google.protobuf.Struct action_spec = 4;
  string governance_token = 5;
  string tenant_id = 6;
  string timestamp = 7;
}

message AdmissionDecision {
  string decision_id = 1;
  bool allowed = 2;
  string reason = 3;
  repeated Condition conditions = 4;
  string expires_at = 5;
  string governance_token = 6;
}

message Condition {
  string type = 1;  // RESOURCE_LIMIT, TIME_LIMIT, NETWORK_ALLOWLIST, etc.
  google.protobuf.Struct parameters = 2;
}
```

### Approval Request
```protobuf
message ApprovalRequest {
  string request_id = 1;
  string agent_id = 2;
  string task_id = 3;
  string action_type = 4;
  google.protobuf.Struct action_spec = 5;
  GateType gate_type = 6;
  string expires_at = 7;
  Priority priority = 7;
  google.protobuf.Struct context = 8;
}

message ApprovalDecision {
  string decision_id = 1;
  string request_id = 2;
  string decided_by = 3;
  string decided_at = 4;
  ApprovalDecisionType decision = 5;
  string reason = 6;
  repeated Condition conditions = 7;
  string governance_token = 8;
  string token_expires_at = 9;
}

enum GateType {
  HUMAN = 0;
  POLICY_AUTO = 1;
  TIME_BASED = 2;
  QUOTA = 3;
}

enum ApprovalDecisionType {
  APPROVED = 0;
  DENIED = 1;
  EXPIRED = 2;
}
```

---

## Telemetry Protocol: Agent ↔ Collector

### Metrics (Prometheus Format)
```
# HELP kilo_task_duration_seconds Task execution latency
# TYPE kilo_task_duration_seconds histogram
kilo_task_duration_seconds_bucket{agent_id="01ARZ...",task_type="build",le="1.0"} 15
kilo_task_duration_seconds_bucket{agent_id="01ARZ...",task_type="build",le="+Inf"} 20
kilo_task_duration_seconds_sum{agent_id="01ARZ...",task_type="build"} 45.2
kilo_task_duration_seconds_count{agent_id="01ARZ...",task_type="build"} 20
```

### Traces (OTLP)
```protobuf
// Standard OTLP ResourceSpans
resource {
  attributes: [
    {key: "service.name", value: {string_value: "kilo-agent"}},
    {key: "kilo.agent.id", value: {string_value: "01ARZ..."}},
    {key: "kilo.tenant.id", value: {string_value: "01ARZ..."}},
    {key: "deployment.environment", value: {string_value: "production"}}
  ]
}
spans {
  name: "agent.execute_task"
  kind: SPAN_KIND_INTERNAL
  attributes: [
    {key: "kilo.task.id", value: {string_value: "01ARZ..."}},
    {key: "kilo.task.type", value: {string_value: "container_build"}}
  ]
  events: [
    {name: "checkpoint.created", attributes: [...]}
  ]
}
```

### Logs (Structured JSON)
```json
{
  "timestamp": "2026-09-19T04:00:00.123456Z",
  "level": "INFO",
  "logger": "kilo.agent.task_agent",
  "message": "Task accepted",
  "agent_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "task_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "tenant_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "trace_id": "0af7651916cd43dd8448eb211c80319c",
  "span_id": "b7ad6b7169203331",
  "fields": {"task_type": "container_build"}
}
```

---

## Health Protocol: Agent ↔ Orchestration

### Health Check (HTTP)
```
GET /health/live
→ 200 OK {"status": "ALIVE", "agent_id": "...", "timestamp": "..."}

GET /health/ready
→ 200 OK {"status": "READY", "agent_id": "...", "checks": [...], "timestamp": "..."}

GET /health
→ 200 OK {full health object}
```

### Health Check (gRPC)
```protobuf
message HealthCheckRequest {
  string service = 1;  // "" for overall
}

message HealthCheckResponse {
  ServingStatus status = 1;  // SERVING, NOT_SERVING, SERVICE_UNKNOWN
  string agent_id = 2;
  repeated HealthCheck check = 3;
}

enum ServingStatus {
  SERVING = 0;      // HEALTHY
  NOT_SERVING = 1;  // UNHEALTHY
  SERVICE_UNKNOWN = 2;
}
```

---

## Cloud Orchestration Protocol: Agent ↔ Orchestration

### Capacity Request
```protobuf
message CapacityRequest {
  string request_id = 1;
  string agent_id = 2;
  string tenant_id = 3;
  ResourceProfile resource_profile = 4;
  int32 duration_hint_seconds = 5;
  Priority priority = 6;
  PlacementConstraints constraints = 7;
  repeated string required_capabilities = 8;
}

message CapacityResponse {
  string request_id = 1;
  bool granted = 2;
  string allocation_id = 3;
  AllocatedResources resources = 4;
  string expires_at = 5;
  map<string, string> endpoints = 6;
}
```

### Service Discovery
```protobuf
message ServiceQuery {
  string service_name = 1;
  string namespace = 2;
  map<string, string> tags = 3;
  string health = 4;
}

message ServiceEndpoint {
  string service_name = 1;
  string endpoint = 2;
  string protocol = 3;
  string health = 4;
  map<string, string> metadata = 5;
}
```

### Config Watch
```protobuf
message ConfigWatchRequest {
  string key = 1;
  string current_version = 2;  // For resume
}

message ConfigValue {
  string key = 1;
  google.protobuf.Value value = 2;
  string type = 3;
  int64 version = 4;
  string updated_at = 5;
  string updated_by = 6;
}
```

---

## CNC Protocol: CNC_AGENT ↔ CNC Platform

### Job Submission
```protobuf
message CNCJobSpec {
  string job_id = 1;
  string tenant_id = 2;
  PartSpecification part_spec = 3;
  MaterialSpec material = 4;
  MachineProfile machine = 5;
  repeated Operation operations = 6;
  QualitySpec quality_requirements = 7;
  SafetySpec safety_requirements = 8;
  EvidenceSpec evidence_requirements = 9;
}

message JobSubmissionResult {
  string job_id = 1;
  bool accepted = 2;
  string status = 3;  // PLANNING, AWAITING_APPROVAL, EXECUTING, COMPLETED, FAILED
  string error = 4;
}
```

### Telemetry Stream
```protobuf
message TelemetryEvent {
  string job_id = 1;
  string timestamp = 2;
  TelemetryEventType event_type = 3;
  string operation_id = 4;
  MachineState machine_state = 5;
  SensorData sensor_data = 6;
}

enum TelemetryEventType {
  OPERATION_START = 0;
  OPERATION_PROGRESS = 1;
  OPERATION_COMPLETE = 2;
  TOOL_CHANGE = 3;
  QUALITY_CHECK = 4;
  SAFETY_EVENT = 5;
  ANOMALY_DETECTED = 6;
}
```

### Proof Package
```protobuf
message ProofPackage {
  string job_id = 1;
  string package_id = 2;
  repeated Evidence evidence = 3;
  string merkle_root = 4;
  string timestamp = 5;
  EvidenceClassification classification = 6;
}

message Evidence {
  EvidenceType type = 1;
  string artifact_ref = 2;
  string hash = 3;
  EvidenceClassification classification = 4;
  google.protobuf.Struct metadata = 5;
}
```

---

## Error Format (All Protocols)

```protobuf
message ProtocolError {
  string error_id = 1;
  string code = 2;           // Machine-readable
  string message = 3;        // Human-readable
  google.protobuf.Struct context = 4;
  bool retryable = 5;
  string retry_after = 6;    // ISO8601 duration
}
```

### Standard Error Codes
| Code | HTTP | gRPC | Meaning |
|------|------|------|---------|
| `INVALID_ARGUMENT` | 400 | INVALID_ARGUMENT | Bad request |
| `UNAUTHENTICATED` | 401 | UNAUTHENTICATED | Auth required |
| `PERMISSION_DENIED` | 403 | PERMISSION_DENIED | Authz failed |
| `NOT_FOUND` | 404 | NOT_FOUND | Resource missing |
| `CONFLICT` | 409 | ALREADY_EXISTS | Conflict |
| `RESOURCE_EXHAUSTED` | 429 | RESOURCE_EXHAUSTED | Rate limit / quota |
| `INTERNAL` | 500 | INTERNAL | Server error |
| `UNAVAILABLE` | 503 | UNAVAILABLE | Service down |
| `DEADLINE_EXCEEDED` | 504 | DEADLINE_EXCEEDED | Timeout |

---

## Protocol Implementation Requirements (PR89+)

- **Serialization:** Protobuf (gRPC) + JSON (HTTP)
- **Versioning:** `Accept: application/vnd.kilo.v1+proto` / `+json`
- **Compression:** gzip (HTTP), built-in (gRPC)
- **Timeouts:** Client: 30s default, Server: 60s default
- **Retries:** Exponential backoff (1s, 2s, 4s, 8s, max 60s), max 3
- **Idempotency:** All mutating operations idempotent (client-generated request_id)
- **Observability:** All RPCs traced, metrics emitted, logs structured
- **Testing:** Contract tests (protobuf conformance), integration tests

---

## References

- `core/agent-kernel.md` — Protocol as kernel responsibility
- `core/agent-lifecycle.md` — Protocol at each lifecycle phase
- `integration/scheduler-integration.md` — Scheduler protocol details
- `integration/cloud-orchestration.md` — Orchestration protocol details
- `integration/cnc-telemetry-integration.md` — CNC protocol details
- `governance/governance-hooks.md` — Governance protocol details
- `telemetry/telemetry-expectations.md` — Telemetry protocol details
- `telemetry/health-reporting.md` — Health protocol details