# KILO Cloud Agent Categories — Taxonomy & Classification

**Purpose:** Defines the canonical taxonomy for KILO Cloud Agents. Every agent MUST declare its category at registration. This taxonomy drives scheduling, governance, resource allocation, and telemetry routing.

---

## Category Hierarchy

```
KILO Cloud Agent
├── EXECUTION AGENTS          # Perform computational work
│   ├── TASK_AGENT            # Single-task execution (stateless)
│   ├── WORKFLOW_AGENT        # Multi-step workflow orchestration
│   ├── BATCH_AGENT           # High-throughput batch processing
│   └── STREAM_AGENT          # Continuous stream processing
├── COORDINATION AGENTS       # Manage other agents
│   ├── SUPERVISOR_AGENT      # Lifecycle management of child agents
│   ├── SCHEDULER_AGENT       # Work distribution & queue management
│   ├── ROUTER_AGENT          # Task routing & load balancing
│   └── ENSEMBLE_AGENT        # Multi-agent coordination & consensus
├── SPECIALIZED AGENTS        # Domain-specific capabilities
│   ├── CNC_AGENT             # Manufacturing intelligence (PR86-87)
│   ├── RESEARCH_AGENT        # Knowledge discovery & synthesis
│   ├── BUILD_AGENT           # Compilation, testing, deployment
│   ├── ANALYSIS_AGENT        # Data analysis & visualization
│   └── SECURITY_AGENT        # Vulnerability scanning, compliance
├── INFRASTRUCTURE AGENTS     # Platform operations
│   ├── PROVISION_AGENT       # Resource provisioning & scaling
│   ├── MONITOR_AGENT         # Observability & alerting
│   ├── BACKUP_AGENT          # Data protection & recovery
│   └── NETWORK_AGENT         # Network configuration & optimization
└── GOVERNANCE AGENTS         # Policy & compliance enforcement
    ├── AUDIT_AGENT           # Continuous audit & compliance
    ├── POLICY_AGENT          # Policy evaluation & enforcement
    ├── APPROVAL_AGENT        # Human-in-the-loop approval handling
    └── QUARANTINE_AGENT      # Isolation & remediation
```

---

## Category Definitions

### EXECUTION AGENTS

#### TASK_AGENT
- **Purpose:** Execute a single, well-defined unit of work
- **Characteristics:** Stateless, idempotent, short-lived (< 5 min typical)
- **Examples:** Code generation, API call, transformation, validation
- **Resource Profile:** Low CPU, low memory, no GPU, network optional
- **Governance Tier:** GOVERNED
- **Concurrency:** High (100s per host)

#### WORKFLOW_AGENT
- **Purpose:** Orchestrate multi-step workflows with dependencies
- **Characteristics:** Stateful, maintains workflow context, manages DAG execution
- **Examples:** CI/CD pipeline, data pipeline, ML training workflow
- **Resource Profile:** Medium CPU, medium memory, network required
- **Governance Tier:** GOVERNED
- **Concurrency:** Medium (10s per host)

#### BATCH_AGENT
- **Purpose:** High-throughput processing of many similar tasks
- **Characteristics:** Optimized for throughput, minimal per-task overhead
- **Examples:** Bulk data processing, rendering, compilation farms
- **Resource Profile:** High CPU, variable memory, GPU optional
- **Governance Tier:** GOVERNED
- **Concurrency:** Very high (1000s per host via work stealing)

#### STREAM_AGENT
- **Purpose:** Continuous processing of unbounded data streams
- **Characteristics:** Long-running, exactly-once semantics, backpressure handling
- **Examples:** Log processing, metrics aggregation, real-time analytics
- **Resource Profile:** Steady CPU, steady memory, network required
- **Governance Tier:** RESTRICTED (continuous egress)
- **Concurrency:** Low (1 per stream partition)

### COORDINATION AGENTS

#### SUPERVISOR_AGENT
- **Purpose:** Manage lifecycle of child agent pools
- **Characteristics:** Spawns, monitors, restarts, scales child agents
- **Examples:** Agent pool manager, auto-scaler, health monitor
- **Resource Profile:** Low CPU, low memory, network required
- **Governance Tier:** PRIVILEGED (spawn authority)
- **Concurrency:** Low (1 per pool)

#### SCHEDULER_AGENT
- **Purpose:** Distribute work across agent pools
- **Characteristics:** Implements scheduling policies, queue management
- **Examples:** Priority scheduler, fair-share scheduler, deadline-aware
- **Resource Profile:** Low CPU, medium memory (queue state)
- **Governance Tier:** PRIVILEGED (admission authority)
- **Concurrency:** Low (1 per scheduling domain)

#### ROUTER_AGENT
- **Purpose:** Route tasks to appropriate agents based on capability
- **Characteristics:** Capability matching, load awareness, failover
- **Examples:** Capability router, geographic router, cost optimizer
- **Resource Profile:** Low CPU, low memory, network required
- **Governance Tier:** GOVERNED
- **Concurrency:** Medium (10s per routing domain)

#### ENSEMBLE_AGENT
- **Purpose:** Coordinate multiple agents for consensus or parallel work
- **Characteristics:** Manages agent groups, handles partial failures, aggregates results
- **Examples:** Consensus voting, parallel search, distributed training
- **Resource Profile:** Medium CPU, medium memory, network required
- **Governance Tier:** RESTRICTED (multi-agent coordination)
- **Concurrency:** Low (1 per ensemble)

### SPECIALIZED AGENTS

#### CNC_AGENT
- **Purpose:** Manufacturing intelligence operations (CNC domain)
- **Capabilities:** Job planning, toolpath generation, simulation, safety validation
- **Integration:** CNC Manufacturing Intelligence (PR86-87)
- **Governance Tier:** RESTRICTED (physical world implications)
- **Reference:** `integration/cnc-telemetry-integration.md`

#### RESEARCH_AGENT
- **Purpose:** Autonomous knowledge discovery and synthesis
- **Capabilities:** Literature search, hypothesis generation, experiment design
- **Integration:** Experiment Manager, Memory Store, Verifier
- **Governance Tier:** GOVERNED

#### BUILD_AGENT
- **Purpose:** Compilation, testing, packaging, deployment
- **Capabilities:** Build system invocation, test execution, artifact publishing
- **Integration:** CI/CD pipelines, artifact stores
- **Governance Tier:** GOVERNED

#### ANALYSIS_AGENT
- **Purpose:** Data analysis, visualization, report generation
- **Capabilities:** Query execution, statistical analysis, chart generation
- **Integration:** Data lakes, BI tools, notebook environments
- **Governance Tier:** GOVERNED

#### SECURITY_AGENT
- **Purpose:** Vulnerability scanning, compliance checking, threat detection
- **Capabilities:** SAST/DAST, dependency scanning, policy validation
- **Integration:** Security pipelines, compliance frameworks
- **Governance Tier:** PRIVILEGED (security-sensitive)

### INFRASTRUCTURE AGENTS

#### PROVISION_AGENT
- **Purpose:** Provision and manage cloud resources
- **Capabilities:** VM/container creation, storage allocation, network config
- **Integration:** Cloud APIs (UpCloud, AWS, GCP, Azure), Terraform
- **Governance Tier:** PRIVILEGED (billing impact)

#### MONITOR_AGENT
- **Purpose:** Continuous observability and alerting
- **Capabilities:** Metric collection, log aggregation, anomaly detection
- **Integration:** Prometheus, Grafana, alerting systems
- **Governance Tier:** GOVERNED

#### BACKUP_AGENT
- **Purpose:** Data protection and disaster recovery
- **Capabilities:** Snapshot management, replication, restore orchestration
- **Integration:** Object storage, database replication, DR sites
- **Governance Tier:** RESTRICTED (data access)

#### NETWORK_AGENT
- **Purpose:** Network configuration and optimization
- **Capabilities:** DNS, load balancing, firewall, service mesh
- **Integration:** Cloud networking, service mesh (Istio, Linkerd)
- **Governance Tier:** PRIVILEGED (network topology)

### GOVERNANCE AGENTS

#### AUDIT_AGENT
- **Purpose:** Continuous audit trail validation and compliance reporting
- **Capabilities:** Ledger verification, policy drift detection, evidence collection
- **Integration:** ActionLedger, compliance frameworks (SOC2, ISO27001)
- **Governance Tier:** PRIVILEGED (audit authority)

#### POLICY_AGENT
- **Purpose:** Real-time policy evaluation and enforcement
- **Capabilities:** OPA/Rego evaluation, attribute-based access control
- **Integration:** Admission gates, runtime enforcement points
- **Governance Tier:** PRIVILEGED (enforcement authority)

#### APPROVAL_AGENT
- **Purpose:** Manage human-in-the-loop approval workflows
- **Capabilities:** Request routing, escalation, timeout handling, audit
- **Integration:** Communication channels (Slack, email, PagerDuty)
- **Governance Tier:** PRIVILEGED (approval authority)

#### QUARANTINE_AGENT
- **Purpose:** Isolate and remediate compromised agents/workloads
- **Capabilities:** Network isolation, memory snapshots, forensic collection
- **Integration:** Security infrastructure, incident response
- **Governance Tier:** PRIVILEGED (containment authority)

---

## Category Metadata

Each category defines:

```yaml
category: "TASK_AGENT"
display_name: "Task Execution Agent"
description: "Executes single units of work"
parent_category: "EXECUTION_AGENTS"
governance_tier: "GOVERNED"
default_resource_profile:
  cpu_cores: 0.5
  memory_mb: 256
  gpu_required: false
  network_egress: false
  max_duration_seconds: 300
capability_requirements: []
capability_provides: ["task.execution"]
scheduling_hints:
  priority: "normal"
  preemptible: true
  poolable: true
telemetry_profile: "standard"
```

---

## Registration Requirements

At spawn time, every agent MUST declare:

1. **Primary category** (from above taxonomy)
2. **Capability provides** (list of capability identifiers)
3. **Capability requires** (list of capability identifiers needed)
4. **Resource profile** (as above)
5. **Governance tier** (GOVERNED / RESTRICTED / PRIVILEGED)
6. **Scheduling hints** (priority, preemptible, poolable)

---

## Extensibility

New categories require:
1. ADR documenting the need
2. Addition to this taxonomy document
3. Governance tier assignment
4. Default resource profile
5. Telemetry profile
6. Integration test updates

---

## References

- `agent-kernel.md` — Agent identity includes category
- `agent-lifecycle.md` — Lifecycle varies by category
- `execution-boundaries.md` — Resource limits by category
- `governance/governance-hooks.md` — Governance tier definitions
- `telemetry/telemetry-expectations.md` — Telemetry profiles by category
- `integration/scheduler-integration.md` — Scheduling hints usage