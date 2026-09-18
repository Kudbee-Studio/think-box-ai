# RED: Scheduler Module

## RESOURCES

| Name | Type | Location | Description |
|------|------|----------|-------------|
| `thinkbox/scheduler.py` | Module | `thinkbox/scheduler.py:1` | Governed scheduler — 92 classes, 6107 lines, 7 layers of features |
| `tests/unit/test_scheduler.py` | Test Module | `tests/unit/test_scheduler.py:1` | 22 test classes, 571–620 tests (growing across PRs) |
| `SchedulerState` | Enum | `thinkbox/scheduler.py:30` | IDLE, ADMITTING, SCHEDULING, RUNNING, PAUSING, RECOVERING, STOPPED |
| `HealthIndicator` | Enum | `thinkbox/scheduler.py:40` | HEALTHY, DEGRADED, CRITICAL, RECOVERING, BLOCKED |
| `SchedulerDecisionType` | Enum | `thinkbox/scheduler.py:48` | ADMIT, REJECT, DEFER, CANCEL, RETRY, COMPLETE, RECOVER |
| `SchedulerDecisionReceipt` | Dataclass | `thinkbox/scheduler.py:59` | Immutable receipt for every scheduling decision with ledger hash |
| `AdaptiveConcurrencyLimiter` | Class | `thinkbox/scheduler.py:88` | Auto-tunes concurrency based on latency/throughput |
| `GlobalSchedulerAdmission` | Class | `thinkbox/scheduler.py:152` | Global admission control across all goals |
| `PerGoalConcurrencyCap` | Class | `thinkbox/scheduler.py:235` | Enforces per-goal concurrency limits |
| `WeightedPriorityScheduler` | Class | `thinkbox/scheduler.py:288` | Weighted priority-based task ordering |
| `BudgetAwareAdmission` | Class | `thinkbox/scheduler.py:330` | Admission gated by remaining budget |
| `DeadlineAwareAdmission` | Class | `thinkbox/scheduler.py:397` | Admission considering task deadlines |
| `RetryAwareReservation` | Class | `thinkbox/scheduler.py:447` | Reservation accounting for retry attempts |
| `BudgetForecaster` | Class | `thinkbox/scheduler.py:499` | Predicts future budget consumption |
| `BudgetOverspendPrevention` | Class | `thinkbox/scheduler.py:566` | Prevents budget overrun on shared sessions |
| `SchedulerTelemetry` | Class | `thinkbox/scheduler.py:608` | Base telemetry metrics |
| `QueueDepthTelemetry` | Class | `thinkbox/scheduler.py:630` | Queue depth monitoring |
| `WaitTimeTelemetry` | Class | `thinkbox/scheduler.py:663` | Wait time tracking |
| `ExecutionUtilization` | Class | `thinkbox/scheduler.py:705` | Execution utilization metrics |
| `FairnessTrendTracker` | Class | `thinkbox/scheduler.py:740` | Fairness trend across tenants |
| `SchedulerHealth` | Class | `thinkbox/scheduler.py:776` | Health assessment (healthy/degraded/critical) |
| `StarvationRecovery` | Class | `thinkbox/scheduler.py:814` | Detects and recovers from task starvation |
| `PriorityInversionRecovery` | Class | `thinkbox/scheduler.py:867` | Detects and resolves priority inversion |
| `CancellationPropagator` | Class | `thinkbox/scheduler.py:918` | Propagates cancellation through DAG |
| `FanOutBackpressure` | Class | `thinkbox/scheduler.py:964` | Backpressure on fan-out patterns |
| `FanInQuorumTracker` | Class | `thinkbox/scheduler.py:1012` | Quorum tracking for fan-in patterns |
| `CrossGoalReplayVerifier` | Class | `thinkbox/scheduler.py:1061` | Verifies replay across concurrent goals |
| `RestartSafeSchedulerRecovery` | Class | `thinkbox/scheduler.py:1101` | Recovers scheduler state after restart |
| `PersistentSchedulerState` | Class | `thinkbox/scheduler.py:1159` | SQLite-persisted scheduler state |
| `FailureDomainIsolator` | Class | `thinkbox/scheduler.py:1205` | Isolates failures by domain |
| `SchedulerDashboardExtension` | Class | `thinkbox/scheduler.py:1271` | Dashboard data for scheduler |
| `GoalTimeoutEnforcer` | Class | `thinkbox/scheduler.py:1344` | Enforces per-goal timeouts |
| `GoalDependencyResolver` | Class | `thinkbox/scheduler.py:1394` | Resolves inter-goal dependencies |
| `SchedulerPerformanceAnalytics` | Class | `thinkbox/scheduler.py:1515` | Performance analytics |
| `CapacityPredictor` | Class | `thinkbox/scheduler.py:1584` | Predicts future capacity needs |
| `WorkStealingQueue` | Class | `thinkbox/scheduler.py:1659` | Work-stealing queue for load balancing |
| `SLAComplianceTracker` | Class | `thinkbox/scheduler.py:1749` | SLA compliance monitoring |
| `CheckpointManager` | Class | `thinkbox/scheduler.py:1810` | Job checkpoint management |
| `GoalProgressTracker` | Class | `thinkbox/scheduler.py:1873` | Per-goal progress tracking |
| `ConfigurableRetryPolicy` | Class | `thinkbox/scheduler.py:1948` | Configurable retry with backoff |
| `SubtaskFailureAggregator` | Class | `thinkbox/scheduler.py:2021` | Aggregates subtask failures |
| `DAGVisualizer` | Class | `thinkbox/scheduler.py:2072` | DAG visualization data |
| `GoalPriorityBoost` | Class | `thinkbox/scheduler.py:2165` | Dynamic priority adjustment |
| `SchedulerLatencyTracker` | Class | `thinkbox/scheduler.py:2233` | Latency tracking per scheduler |
| `DeadlineExtensionPolicy` | Class | `thinkbox/scheduler.py:2291` | Conditional deadline extension |
| `GoalGroupManager` | Class | `thinkbox/scheduler.py:2360` | Groups goals for batch scheduling |
| `AdmissionPolicyChain` | Class | `thinkbox/scheduler.py:2423` | Chain of admission filters |
| `GoalRetryBudgetResolver` | Class | `thinkbox/scheduler.py:2481` | Resolves retry budget per goal |
| `CriticalPathHighlight` | Class | `thinkbox/scheduler.py:2547` | Identifies critical path tasks |
| `PriorityAging` | Class | `thinkbox/scheduler.py:2623` | Priority aging over time |
| `DeadlineMode` | Enum/Class | `thinkbox/scheduler.py:2700` | Deadline handling modes |
| `JobGroupFanInGate` | Class | `thinkbox/scheduler.py:2771` | Fan-in gate for job groups |
| `TenantFairShare` | Class | `thinkbox/scheduler.py:2868` | Fair share allocation across tenants |
| `RetryBudgetWithJitter` | Class | `thinkbox/scheduler.py:2928` | Retry budget with randomization |
| `IdempotencyStore` | Class | `thinkbox/scheduler.py:3028` | Idempotency key storage |
| `QueuePauseResume` | Class | `thinkbox/scheduler.py:3082` | Pause/resume queue processing |
| `SLABreachEmitter` | Class | `thinkbox/scheduler.py:3161` | Emits SLA breach events |
| `SchedulerPolicyPackV2` | Class | `thinkbox/scheduler.py:3228` | Policy bundle v2 |
| `MultiQueueRouting` | Class | `thinkbox/scheduler.py:3307` | Routes tasks across multiple queues |
| `BackpressureAdmissionV2` | Class | `thinkbox/scheduler.py:3387` | Admission with backpressure |
| `DurableJobCheckpoints` | Class | `thinkbox/scheduler.py:3502` | Durable checkpoint persistence |
| `DAGExecutionEngine` | Class | `thinkbox/scheduler.py:3628` | DAG execution engine |
| `ObservabilityExportPack` | Class | `thinkbox/scheduler.py:3758` | Observability data export |
| `CronWindow` | Class | `thinkbox/scheduler.py:3929` | Cron-based scheduling windows |
| `ResourceQuota` | Class | `thinkbox/scheduler.py:3980` | Per-tenant resource quotas |
| `WorkerHeartbeat` | Class | `thinkbox/scheduler.py:4074` | Worker liveness monitoring |
| `TokenBucketRateLimit` | Class | `thinkbox/scheduler.py:4138` | Token bucket rate limiter |
| `CascadeCancel` | Class | `thinkbox/scheduler.py:4249` | Cascade cancellation of dependent tasks |
| `PriorityInheritance` | Class | `thinkbox/scheduler.py:4302` | Priority inheritance protocol |
| `ShadowRun` | Class | `thinkbox/scheduler.py:4372` | Dry-run execution for prediction |
| `CostAccounting` | Class | `thinkbox/scheduler.py:4436` | Per-task cost tracking |
| `PolicyHotReload` | Class | `thinkbox/scheduler.py:4516` | Runtime policy reloading |
| `ChaosInjection` | Class | `thinkbox/scheduler.py:4584` | Controlled fault injection |
| `WeightedFairQueue` | Class | `thinkbox/scheduler.py:4670` | Deficit round robin across named queues |
| `JobLease` | Class | `thinkbox/scheduler.py:4775` | Lease/TTL with expiry reclaim |
| `DedupedDelayedEnqueue` | Class | `thinkbox/scheduler.py:4865` | Schedule-at + dedupe |
| `CircuitBreaker` | Class | `thinkbox/scheduler.py:4937` | Closed/open/half-open per target |
| `AdmissionLottery` | Class | `thinkbox/scheduler.py:5029` | Probabilistic admit at cap |
| `PlacementConstraints` | Class | `thinkbox/scheduler.py:5104` | Require/avoid label constraints |
| `ProgressiveDrain` | Class | `thinkbox/scheduler.py:5164` | Graceful drain on shutdown |
| `ReplayFromLedger` | Class | `thinkbox/scheduler.py:5245` | Rehydrate queue from ledger |
| `MultiPriorityAging` | Class | `thinkbox/scheduler.py:5303` | Per-priority-band aging |
| `SchedulerCanary` | Class | `thinkbox/scheduler.py:5357` | Synthetic probe jobs |
| `AdaptiveConcurrency` | Class | `thinkbox/scheduler.py:5429` | Auto-tune concurrency (PR #84) |
| `Preemption` | Class | `thinkbox/scheduler.py:5501` | Preempt low-priority tasks |
| `TaskCoalescing` | Class | `thinkbox/scheduler.py:5571` | Merge identical pending tasks |
| `WorkflowTemplate` | Class | `thinkbox/scheduler.py:5643` | Versioned reusable workflows |
| `BackpressurePropagation` | Class | `thinkbox/scheduler.py:5717` | Backpressure through DAG |
| `SchedulerClock` | Class | `thinkbox/scheduler.py:5779` | Monotonic clock for testing |
| `AdmissionFilter` | Class | `thinkbox/scheduler.py:5831` | Pluggable admission filter chain |
| `FairnessIndex` | Class | `thinkbox/scheduler.py:5908` | Jain's fairness index per tenant |
| `DynamicBudget` | Class | `thinkbox/scheduler.py:5959` | Dynamic budget reallocation |
| `TaskAffinity` | Class | `thinkbox/scheduler.py:6037` | Data/task locality scheduling |

## EVENTS

| Date | Event | Details |
|------|-------|---------|
| 2026-09-17 | PR #76 merged | 25 scheduler features: AdaptiveConcurrencyLimiter through FailureDomainIsolator + 2 bug fixes (BackpressureAdmissionV2 tenant tracking, DurableJobCheckpoints sqlite persistence). Branch: `feat/scheduler-25-features` |
| 2026-09-17 | PR #81 merged | 5 scheduler features: SchedulerDashboardExtension, StressReportEnhancer, GoalTimeoutEnforcer, GoalDependencyResolver, SchedulerPerformanceAnalytics. Branch: `feat/scheduler-5-analytics` |
| 2026-09-18 | PR #82 merged | 10 features: CronWindow, ResourceQuota, WorkerHeartbeat, TokenBucketRateLimit, CascadeCancel, PriorityInheritance, ShadowRun, CostAccounting, PolicyHotReload, ChaosInjection + 2 bug fixes. Branch: `feat/scheduler-10-pr82` |
| 2026-09-18 | PR #83 merged | 10 features: WeightedFairQueue, JobLease, DedupedDelayedEnqueue, CircuitBreaker, AdmissionLottery, PlacementConstraints, ProgressiveDrain, ReplayFromLedger, MultiPriorityAging, SchedulerCanary. 20 new test classes, 82 new tests. Branch: `feat/scheduler-10-pr83` |
| 2026-09-18 | PR #84 in progress | 10 features: AdaptiveConcurrency, Preemption, TaskCoalescing, WorkflowTemplate, BackpressurePropagation, SchedulerClock, AdmissionFilter, FairnessIndex, DynamicBudget, TaskAffinity. Branch: `feat/scheduler-10-pr84` |
| 2026-09-18 | Test milestone | 620 scheduler tests passing (571 after PR #83, +~50 from PR #84 WIP) |

## DECISIONS

| ID | Decision | Rationale | Status |
|----|----------|-----------|--------|
| SCHED-001 | All features extend existing governed concurrency architecture | No parallel systems; scheduler builds on ThinkBoxEngine → GovernedEngine → VerifiedRetrySession → DAG → concurrent_goals | Accepted |
| SCHED-002 | Decision receipts are immutable with ledger hash | Every scheduling decision must be auditable; ledger hash ties it to ActionLedger | Accepted |
| SCHED-003 | SchedulerState enum covers full lifecycle | IDLE→ADMITTING→SCHEDULING→RUNNING→PAUSING→RECOVERING→STOPPED covers all observed states | Accepted |
| SCHED-004 | Telemetry classes subclass SchedulerTelemetry | Unified metrics base enables dashboard extension and performance analytics | Accepted |
| SCHED-005 | Bug fixes included in feature PRs, not separate | BackpressureAdmissionV2 and DurableJobCheckpoints fixes were blockers for their feature tests | Accepted |
| SCHED-006 | PRs bundle ~10 features each | Keeps review manageable; each PR has dedicated test class | Accepted |
| SCHED-007 | SchedulerClock uses monotonic time | Deterministic time testing prevents flaky deadline/aging tests | Accepted |
| SCHED-008 | AdmissionFilter as pluggable chain | Enables composable admission policies without modifying core logic | Accepted |
| SCHED-009 | DynamicBudget reallocates across goals | Shared-session execution needs flexible budget distribution, not just per-goal caps | Accepted |
| SCHED-010 | TaskAffinity for data locality | Avoids moving large datasets between workers; scheduling respects existing data placement | Accepted |