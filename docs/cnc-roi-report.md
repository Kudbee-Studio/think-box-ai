# CNC ROI & Evidence Report

**Date:** 2026-09-18
**Status:** SIMULATED PROJECTIONS (not measured)
**Module:** `thinkbox/cnc/`

> **IMPORTANT:** All ROI figures below are projections from DemoMode (`DemoMode.run()`), NOT measured outcomes. Evidence label is `simulated` throughout. Do not use these numbers for production budgeting without physical validation.

## Module State

| Component | Status | Evidence |
|-----------|--------|----------|
| CNCJob & lifecycle | COMPLETE | 68 unit tests pass, model_dump verified |
| Safety gates | COMPLETE | ApprovalGate, SafetyGateStore tested; execute_job blocks when unapproved |
| Tenant isolation | COMPLETE | Tenant, TenantBoundary, TenantStore tested |
| Proof system | COMPLETE | ProofPackage, ProofStore tested |
| Dashboard integration | COMPLETE | CNCJobEntry in dashboard_state, upsert_cnc_job |
| Demo mode | COMPLETE | DemoMode.run() produces deterministic DemoResult |
| Engine (validate/execute/proof) | COMPLETE | CNCManufacturingEngine tested, fail-closed on safety |
| Memory/knowledge | COMPLETE | ManufacturingMemory, KnowledgeEntry tested |
| Adapter registry | COMPLETE | CNCAdapterRegistry, abstract interfaces tested |

## ROI Metrics (SIMULATED from DemoMode)

> These are hypothetical projections from `DemoMode.run()`, not measured values. Evidence label: `simulated`.

| Metric | Value | Source |
|--------|-------|--------|
| Programming hours avoided | 2.5 per job | DemoMode (simulated) |
| Total savings avoided | $1,250 per job | DemoMode (simulated projection) |
| Jobs completed (demo) | 1 | DemoMode run |
| Duration | 1.5 seconds | DemoMode run |

## Design Principles Applied

1. **No autonomous execution** — SafetyGate blocks production until human approval
2. **Evidence labeling** — All data carries evidence_label (simulated/inferred/verified/physically_measured)
3. **Tenant isolation** — TenantBoundary enforces customer data separation
4. **Replayable** — ReplayDriver can reproduce any job
5. **Self-improving** — Outcomes feed back into planning via SelfImprovementLoop
6. **No new dependencies** — Uses existing Think Box infrastructure only

## Test Results

```
Ran 68 tests in 0.787s
OK
```

Full suite: 1440 tests, 6 skipped, 3 pre-existing failures (unrelated).

## Known Limitations

- All evidence currently "simulated" — physical validation requires
  UpCloud agent infrastructure (not yet provisioned)
- No real-time machine telemetry (Phase 2+)
- UpCloud API returns 401 (read-only via API; no SSH/compute execution)
- CNC job execution in engine is deterministic simulation, not live machine control
- ROI figures are projections from DemoMode, NOT measured outcomes

## Integration Points

- Dashboard: CNCJobEntry upserted via `dashboard_state.upsert_cnc_job()`
- Replay: ReplayDriver supports CNC job replay
- Engine: CNCManufacturingEngine validates → gates → executes → proofs
