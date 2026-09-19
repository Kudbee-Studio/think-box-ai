# KILO Cloud Agent Scheduler Integration — Governed Scheduler Hooks

**Purpose:** Defines how KILO Cloud Agents integrate with the Governed Scheduler (PR80-85) for work distribution, capacity management, and scheduling policies.

---

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT                                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Scheduler Client                                       │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │   │
│  │  │  Work    │ │ Capacity │ │  Health  │ │  Metrics   │  │   │
│  │  │  Pull    │ │  Report  │ │  Report  │ │  Push      │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 GOVERNED SCHEDULER (PR80-85)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────┐  │
│  │  Queue   │ │ Admission│ │  Policy  │ │  SchedulerHarness  │  │
│  │  Manager │ │  Gates   │ │  Engine  │ │  (25+ features)    │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Work Pull Model

Agents **pull** work from scheduler (not push) — enables backpressure, autonomy, and graceful degradation.

### Work Pull Protocol

```python
class SchedulerClient(Protocol):
    # Pull next task for this agent
    async def pull_work(self, request: PullWorkRequest) -> PullWorkResponse: ...
    
    # Report task outcome
    async def report_outcome(self, report: TaskOutcomeReport) -> None: ...
    
    # Report capacity/health
    async def report_capacity(self, report: CapacityReport) -> None: ...
    
    # Heartbeat
    async def heartbeat(self, hb: Heartbeat) -> HeartbeatResponse: ...

class PullWorkRequest:
    agent_id: str
    agent_type: str
    capabilities: list[str]
    resource_profile: ResourceProfile
    governance_tier: str
    max_tasks: int = 1
    accept_timeout_seconds: int = 30

class PullWorkResponse:
    tasks: list[TaskAssignment]  # Empty if no work available
    next_pull_after_seconds: int  # Backoff hint

class TaskAssignment:
    task_id: str
    task_type: str
    task_spec: dict
    priority: int
    deadline: datetime | None
    governance_token: str | None  # Pre-issued for gated actions
    experiment_id: str | None
    think_box_id: str | None
```

### Pull Behavior
| Scenario | Agent Behavior |
|----------|----------------|
| **Tasks available** | Receive up to `max_tasks`, begin execution |
| **No tasks** | Wait `next_pull_after_seconds`, then pull again |
| **Agent at capacity** | Don't pull (scheduler tracks via capacity reports) |
| **Agent unhealthy** | Stop pulling, scheduler stops assigning |
| **Governance token expired** | Request new token before executing gated actions |

---

## Capacity Reporting

Agents continuously report capacity to enable intelligent scheduling.

### Capacity Report
```json
{
  "agent_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "timestamp": "2026-09-19T04:00:00Z",
  "capacity": {
    "cpu_cores_available": 1.5,
    "cpu_cores_total": 2.0,
    "memory_mb_available": 1024,
    "memory_mb_total": 2048,
    "gpu_available": false,
    "network_mbps_available": 100,
    "disk_mb_available": 5120,
    "max_concurrent_tasks": 2,
    "current_tasks": 1
  },
  "health": {
    "status": "HEALTHY",
    "checks_passing": 5,
    "checks_warning": 0,
    "checks_failing": 0
  },
  "preferences": {
    "preferred_task_types": ["container_build", "test_run"],
    "avoid_task_types": ["gpu_training"],
    "max_task_duration_seconds": 1800
  }
}
```

### Scheduler Uses Capacity For
- **Admission:** Only assign tasks that fit available resources
- **Placement:** Prefer agents with matching preferences
- **Scaling:** Trigger SUPERVISOR_AGENT to spawn more agents
- **Preemption:** Identify preemptible tasks under pressure
- **Fairness:** Balance load across agent pools

---

## Heartbeat Protocol

```json
{
  "agent_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "timestamp": "2026-09-19T04:00:00Z",
  "sequence": 12345,
  "status": "EXECUTING",
  "current_task_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "task_progress_percent": 45,
  "resource_snapshot": {
    "cpu_percent": 65,
    "memory_percent": 70
  }
}
```

### Heartbeat Response
```json
{
  "ack": true,
  "sequence": 12345,
  "scheduler_time": "2026-09-19T04:00:00Z",
  "commands": [
    {"type": "PREEMPT", "task_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV", "reason": "HIGHER_PRIORITY"}
  ],
  "config_updates": {
    "pull_interval_seconds": 30
  }
}
```

### Scheduler Commands via Heartbeat
| Command | Description | Agent Action |
|---------|-------------|--------------|
| `PREEMPT` | Higher priority work needs resources | Checkpoint current task, release resources |
| `PAUSE` | Temporary capacity pressure | Pause task execution, hold resources |
| `RESUME` | Pressure relieved | Resume execution |
| `TERMINATE` | Agent being replaced | Graceful shutdown |
| `CONFIG_UPDATE` | Scheduler config changed | Apply new pull interval, limits |

---

## Task Outcome Reporting

```json
{
  "task_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "agent_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "outcome": "SUCCESS",  // SUCCESS | FAILED | CANCELLED | TIMEOUT
  "completed_at": "2026-09-19T04:05:00Z",
  "duration_ms": 300000,
  "resource_usage": {
    "cpu_seconds": 120,
    "memory_peak_mb": 1536,
    "gpu_seconds": 0,
    "network_egress_mb": 50
  },
  "result_ref": "s3://bucket/results/task_xyz.json",
  "error": null,
  "governance": {
    "admission_decisions": 3,
    "approvals_requested": 1,
    "approvals_granted": 1,
    "tokens_used": 2
  },
  "verification": {
    "verified": true,
    "verification_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
    "policy_version": "v3.2.1"
  }
}
```

---

## Scheduler Features Integration (PR80-85)

### 1. Adaptive Concurrency (`AdaptiveConcurrencyLimiter`)
- Agent reports capacity → Scheduler adjusts concurrency limit
- Agent respects `max_concurrent_tasks` from scheduler

### 2. Preemption (`Preemption`)
- Scheduler sends `PREEMPT` via heartbeat
- Agent checkpoints, releases resources, re-queues task

### 3. Task Coalescing (`TaskCoalescing`)
- Scheduler batches similar tasks → Agent receives batch
- Agent executes batch, reports aggregated outcome

### 4. Workflow Templates (`WorkflowTemplate`)
- Agent receives workflow task with template reference
- Agent executes steps per template, reports step outcomes

### 5. Backpressure Propagation (`BackpressurePropagation`)
- Scheduler signals backpressure via `next_pull_after_seconds`
- Agent reduces pull frequency automatically

### 6. Scheduler Clock (`SchedulerClock`)
- Agent uses scheduler time for deadlines (not local clock)
- Heartbeat response includes `scheduler_time`

### 7. Admission Filter (`AdmissionFilter`)
- Scheduler pre-filters tasks by agent capabilities
- Agent only receives compatible tasks

### 8. Fairness Index (`FairnessIndex`)
- Scheduler tracks per-agent fairness
- Agent receives fair share of work over time

### 9. Dynamic Budget (`DynamicBudget`)
- Scheduler allocates budget per agent/tenant
- Agent reports budget consumption via outcomes

### 10. Task Affinity (`TaskAffinity`)
- Scheduler prefers agent with matching affinity
- Agent declares affinity in capacity preferences

### 11. Weighted Fair Queue (`WeightedFairQueue`)
- Agent weight based on capability match + performance
- Higher weight = more work allocation

### 12. Job Lease (`JobLease`)
- Task assignment includes lease duration
- Agent must heartbeat before lease expiry

### 13. Circuit Breaker (`CircuitBreaker`)
- Scheduler tracks agent failure rate
- Opens circuit → stops sending work

### 14. Admission Lottery (`AdmissionLottery`)
- For oversubscribed queues, lottery selection
- Agent receives work probabilistically

### 15. Placement Constraints (`PlacementConstraints`)
- Scheduler respects zone/region/hardware constraints
- Agent declares constraints in capacity report

### 16. Progressive Drain (`ProgressiveDrain`)
- On agent termination signal, scheduler stops new work
- Agent completes in-flight, then terminates

### 17. Replay From Ledger (`ReplayFromLedger`)
- Scheduler can replay task from ledger
- Agent receives replay task with original spec

### 18. Multi-Priority Aging (`MultiPriorityAging`)
- Task priority increases with wait time
- Agent receives aged high-priority tasks first

### 19. Scheduler Canaries (`SchedulerCanary`)
- Scheduler sends canary tasks to validate agents
- Agent executes canary, reports canary outcome

### 20. Dead Letter Queue (`DeadLetterQueue`)
- Failed tasks (exhausted retries) → DLQ
- Agent never receives DLQ tasks

### 21. Config Validator (`ConfigValidator`)
- Scheduler validates agent config at registration
- Agent receives validated config

### 22. Memory Pressure Monitor (`MemoryPressureMonitor`)
- Scheduler tracks system memory pressure
- Reduces agent concurrency under pressure

### 23. Graceful Shutdown Coordinator (`GracefulShutdownCoordinator`)
- Coordinates multi-agent shutdown
- Agent participates in coordinated drain

### 24. Scheduler Sentinel (`SchedulerSentinel`)
- Monitors scheduler health
- Agent detects scheduler failover

### 25. Data Integrity Checker (`DataIntegrityChecker`)
- Verifies task/result integrity
- Agent computes and reports checksums

### 26. Retry Storm Guard (`RetryStormGuard`)
- Limits retry rate system-wide
- Agent respects retry budget from scheduler

### 27. Schema Version Tracker (`SchemaVersionTracker`)
- Tracks task/result schema versions
- Agent declares supported schema versions

### 28. Anomaly Detector (`AnomalyDetector`)
- Detects anomalous agent behavior
- Agent flagged for investigation

### 29. Admission Rate Limiter (`AdmissionRateLimiter`)
- Limits admission rate per agent/tenant
- Agent receives rate-limited work

---

## Metrics for Scheduler Integration

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `kilo_scheduler_pull_requests_total` | Counter | `agent_id`, `outcome` | Pull requests (success/empty/error) |
| `kilo_scheduler_pull_latency_seconds` | Histogram | `agent_id` | Pull RPC latency |
| `kilo_scheduler_tasks_received_total` | Counter | `agent_id`, `task_type` | Tasks assigned |
| `kilo_scheduler_heartbeats_total` | Counter | `agent_id`, `command` | Heartbeats sent |
| `kilo_scheduler_preemptions_total` | Counter | `agent_id`, `reason` | Preemptions received |
| `kilo_scheduler_capacity_reports_total` | Counter | `agent_id` | Capacity reports sent |
| `kilo_scheduler_outcome_reports_total` | Counter | `agent_id`, `outcome` | Outcome reports sent |

---

## Implementation Requirements (PR89+)

- Scheduler client: gRPC + HTTP fallback
- Pull: Long-polling (30s) for efficiency
- Heartbeat: Every 10s (configurable)
- Capacity report: Every 30s or on significant change
- Outcome report: Immediately on task completion
- Retry: Exponential backoff (1s, 2s, 4s, 8s, max 60s)
- Circuit breaker: Local (stop pulling if scheduler down > 60s)
- Metrics: Push to scheduler's Pushgateway or OTLP

---

## References

- `core/agent-kernel.md` — Task ingestion as kernel responsibility
- `core/agent-lifecycle.md` — Lifecycle states reported to scheduler
- `core/agent-categories.md` — Capabilities & preferences by category
- `core/execution-boundaries.md` — Resource limits from scheduler
- `governance/governance-hooks.md` — Governance tokens from scheduler
- `telemetry/telemetry-expectations.md` — Scheduler metrics
- `telemetry/health-reporting.md` — Health reported to scheduler