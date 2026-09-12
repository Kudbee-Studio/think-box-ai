# KUDBEE Control Fabric — Implementation Reference

**Version:** 0.1
**Companion to:** the KUDBEE white paper (working draft)

This document maps the implemented control-fabric modules in `thinkbox/`
to the architecture and evaluation agenda in the white paper.

---

## 1. Modules

| White-paper concept | Module | Purpose |
|---------------------|--------|---------|
| Identity | `thinkbox/identity.py` | `IdentityLedger`, `AgentIdentity` — capability scopes and policy version |
| Governance token | `thinkbox/governance_token.py` | `GovernanceTokenService` — issuance, verification, revocation |
| Admission | `thinkbox/admission.py` | `AdmissionGate` — fail-closed authorization |
| Think Box workspace | `thinkbox/workspace.py` | `WorkspaceRegistry`, `WorkspaceStore` (SQLite) |
| Substrate handoff | `thinkbox/handoff.py` | `ThinkBoxHandoff` — portable work + integrity hashing |
| Occupancy mesh | `thinkbox/occupancy.py` | `OccupancyMonitor`, `MeshCellManager` — horizontal isolation |
| Elastic capacity | `thinkbox/capacity.py` | `CapacityController` — expand/contract with spend |
| Durable ledger | `thinkbox/ledger.py` | `ActionLedger` — append-only, tamper-evident |
| Think traces | `thinkbox/thinktrace.py` | `ThinkTraceCapture` — grounded vs ungrounded scoring |
| Governed engine | `thinkbox/governed.py` | `GovernedEngine` — gate side effects via admission + ledger |

---

## 2. Governance admission flow

```
Agent instance arrives
  ↓
Register identity (capabilities + policy_version)
  ↓
Mint governance token (binds identity, capabilities, policy)
  ↓
Side effect requested
  ↓
AdmissionGate.authorize(token, agent, capability)
  ├── valid + capable → allowed
  └── else → denied (recorded in ledger)
```

No token → draft only. With token → act within scope. Revocation ejects
from the society.

---

## 3. Evaluation agenda coverage

| White paper item | Status | Where |
|------------------|--------|-------|
| Contrast pairs (grounded vs ungrounded) | Implemented | `ThinkTraceCapture.pairs()` |
| Admission tests (fail closed) | Implemented | `AdmissionGate`, `test_admission.py` |
| Blast radius (compromised cell) | Implemented | `MeshCellManager`, `test_mesh.py` |
| Tamper evidence | Implemented | `ActionLedger.verify()`, `test_ledger.py` |
| Elastic occupancy | Implemented | `CapacityController`, `test_capacity.py` |

---

## 4. Usage

```python
from thinkbox.governed import GovernedEngine, GovernedEngineConfig
from thinkbox.engine import ThinkBoxEngine, EngineConfig

governed = GovernedEngine(GovernedEngineConfig(engine=ThinkBoxEngine(EngineConfig())))
token = governed.register_agent("alice", ["file:read", "goal:execute"])

# denied: no token
result = await governed.execute_goal("touch /tmp/x")

# allowed: valid token and capability
result = await governed.execute_goal("touch /tmp/x", token_value=token, agent_id="alice", capability="goal:execute")
```

---

## 5. Doc control

| Field | Value |
|-------|-------|
| Version | 0.1 |
| Status | Implemented and tested |
| Test count | Control-fabric unit + integration tests pass with full suite |