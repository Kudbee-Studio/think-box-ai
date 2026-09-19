# CNC ROI & Evidence Report

**Date:** 2026-09-18
**Status:** TEST_VERIFIED
**Module:** `thinkbox/cnc/`

## Module State

| Component | Status | Evidence |
|-----------|--------|----------|
| CNCJob & lifecycle | COMPLETE | 59 unit tests pass, model_dump verified |
| Safety gates | COMPLETE | ApprovalGate, SafetyGateStore tested; approve/block/query paths |
| Tenant isolation | COMPLETE | Tenant, TenantBoundary, TenantStore tested |
| Proof system | COMPLETE | ProofPackage, ProofStore tested |
| Dashboard integration | COMPLETE | CNCJobEntry in dashboard_state, upsert_cnc_job |
| Demo mode | COMPLETE | DemoMode.run() produces deterministic DemoResult |
| Engine (validate/execute/proof) | COMPLETE | CNCManufacturingEngine tested |
| Memory/knowledge | COMPLETE | ManufacturingMemory, KnowledgeEntry tested |
| Adapter registry | COMPLETE | CNCAdapterRegistry, abstract interfaces tested |

## ROI Metrics (from DemoMode)

| Metric | Value |
|--------|-------|
| Programming hours avoided | 2.5 per job |
| Total savings avoided | $1,250 per job |
| Jobs completed (demo) | 1 |
| Duration | 1.5 seconds |

## Design Principles Applied

1. **No autonomous execution** — SafetyGate blocks production until human approval
2. **Evidence labeling** — All data carries evidence_label (simulated/inferred/verified/physically_measured)
3. **Tenant isolation** — TenantBoundary enforces customer data separation
4. **Replayable** — ReplayDriver can reproduce any job
5. **Self-improving** — Outcomes feed back into planning via SelfImprovementLoop
6. **No new dependencies** — Uses existing Think Box infrastructure only

## Test Results

```
Ran 59 tests in 0.782s
OK
```

Full suite: 1435 tests, 6 skipped, 3 pre-existing failures (unrelated).

## Known Limitations

- All evidence currently "simulated" — physical validation requires
  UpCloud agent infrastructure (not yet provisioned)
- No real-time machine telemetry (Phase 2+)
- UpCloud API returns 401 (read-only via API; no SSH/compute execution)
- CNC job execution in engine is deterministic simulation, not live machine control

## Integration Points

- Dashboard: CNCJobEntry upserted via `dashboard_state.upsert_cnc_job()`
- Replay: ReplayDriver supports CNC job replay
- Engine: CNCManufacturingEngine validates → gates → executes → proofs
