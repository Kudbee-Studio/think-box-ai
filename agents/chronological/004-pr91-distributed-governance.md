# PR91: Distributed Governance — Implementation Plan

**Date:** 2026-09-19
**Status:** MERGED
**Branch:** pushed to `main` as `d803cd2` (no dedicated branch)
**PR:** KILO PR91 (no GitHub PR; pushed directly to main) 

---

## Objective

Extend the KUDBEE Control Fabric (Phase 12) to multi-node deployments: distributed AdmissionGate, distributed ActionLedger, cross-node governance tokens, and mesh compromise containment with expulsion.

---

## Scope

### Distributed Components

| Component | Single-Node (Phase 12) | Distributed (PR91) |
|-----------|------------------------|-------------------|
| **AdmissionGate** | Local in-process | Cluster-wide (Raft consensus) |
| **ActionLedger** | Local SQLite + hash chain | Multi-node (CRDT + anchoring) |
| **GovernanceToken** | Local JWT issuer | Distributed (threshold signing) |
| **PolicyEngine** | Local OPA | Cluster-wide (bundles + sync) |
| **Mesh** | Single cell | Multi-cell with expulsion |

---

## Distributed Admission Gate

### Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                    ADMISSION GATE CLUSTER                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Node 1    │  │   Node 2    │  │   Node 3    │   ...       │
│  │  (Leader)   │  │  (Follower) │  │  (Follower) │             │
│  │  ┌───────┐  │  │  ┌───────┐  │  │  ┌───────┐  │             │
│  │  │ Raft  │◀─┼──│  │ Raft  │  │  │  │ Raft  │  │             │
│  │  │ Log   │  │  │  │ Log   │  │  │  │ Log   │  │             │
│  │  └───────┘  │  │  └───────┘  │  │  └───────┘  │             │
│  │  ┌───────┐  │  │  ┌───────┐  │  │  ┌───────┐  │             │
│  │  │ OPA   │  │  │  │ OPA   │  │  │  │ OPA   │  │             │
│  │  │ Cache │  │  │  │ Cache │  │  │  │ Cache │  │             │
│  │  └───────┘  │  │  └───────┘  │  │  └───────┘  │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

### Consensus Protocol (Raft)
- **Leader:** Handles all admission requests
- **Followers:** Replicate log, serve reads (stale OK)
- **Quorum:** Majority (N/2+1) for decisions
- **Log Entry:** `AdmissionRequest` + `AdmissionDecision`
- **Latency Target:** < 50ms p99 (local), < 100ms p99 (cross-region)

### Request Flow
```
1. Agent → Local AdmissionGate (gRPC)
2. Local Gate → Forward to Leader (if not leader)
3. Leader → Append to Raft log
4. Quorum acknowledges
5. Leader → Evaluate policy (OPA)
6. Leader → Write decision to log
7. Quorum acknowledges
8. Leader → Return decision to requester
9. All nodes → Apply decision to local cache
```

### Failover
- **Leader failure:** Raft election (typically < 5s)
- **During election:** Read-only mode (cached decisions only)
- **Network partition:** Minority partition denies all (fail-closed)
- **Recovery:** Log replay, cache rebuild

---

## Distributed Action Ledger

### Architecture (CRDT-based)
```
┌─────────────────────────────────────────────────────────────────┐
│                    ACTION LEDGER CLUSTER                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Node 1    │  │   Node 2    │  │   Node 3    │   ...       │
│  │  ┌───────┐  │  │  ┌───────┐  │  │  ┌───────┐  │             │
│  │  │ Local │  │  │  │ Local │  │  │  │ Local │  │             │
│  │  │ Log   │  │  │  │ Log   │  │  │  │ Log   │  │             │
│  │  └───────┘  │  │  └───────┘  │  │  └───────┘  │             │
│  │  ┌───────┐  │  │  ┌───────┐  │  │  ┌───────┐  │             │
│  │  │ CRDT  │◀─┼──┼──│ CRDT  │  │  │  │ CRDT  │  │             │
│  │  │ Merge │  │  │  │ Merge │  │  │  │ Merge │  │             │
│  │  └───────┘  │  │  └───────┘  │  │  └───────┘  │             │
│  │  ┌───────┐  │  │  ┌───────┐  │  │  ┌───────┐  │             │
│  │  │ Anchor│  │  │  │ Anchor│  │  │  │ Anchor│  │             │
│  │  │ Service│  │  │  │ Service│  │  │  │ Service│  │             │
│  │  └───────┘  │  │  └───────┘  │  │  └───────┘  │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

### CRDT Design
- **Type:** Append-only log (RGA - Replicated Growable Array)
- **Merge:** Deterministic, commutative, associative
- **Conflict Resolution:** Timestamp + node_id tiebreaker
- **Verification:** Merkle tree over merged log
- **Anchoring:** Periodic (every 1000 entries or 1 hour) to TSA/blockchain

### Read/Write
- **Write:** Local append + async CRDT broadcast
- **Read:** Local (eventually consistent) or quorum (strong)
- **Verification:** Merkle proof for any range
- **Export:** Consistent snapshot via Merkle root

---

## Distributed Governance Tokens

### Threshold Signing (BLS)
- **Scheme:** BLS threshold signatures (t-of-n)
- **Nodes:** n=5, threshold t=3 (configurable)
- **Token:** JWT with `sig` = threshold signature
- **Verification:** Any node can verify with aggregate public key

### Token Lifecycle
```
1. Agent → Local TokenService (request)
2. Local → Forward to Token Cluster
3. Cluster → t nodes sign (async)
4. Aggregate signatures → JWT
5. Return token to agent
6. Token valid across all nodes
```

### Revocation
- **Global revocation list** (CRDT set)
- **Propagated** via ledger CRDT
- **Checked** at every admission (cached with TTL)

---

## Multi-Cell Mesh (KUDBEE Extension)

### Cell Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                        MESH                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │    Cell A       │  │    Cell B       │  │    Cell C      │  │
│  │  (us-east)      │  │  (eu-west)      │  │  (ap-south)    │  │
│  │  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌──────────┐  │  │
│  │  │ Agents    │  │  │  │ Agents    │  │  │  │ Agents   │  │  │
│  │  │ Admission │  │  │  │ Admission │  │  │  │ Admission│  │  │
│  │  │ Ledger    │  │  │  │ Ledger    │  │  │  │ Ledger   │  │  │
│  │  │ Token Svc │  │  │  │ Token Svc │  │  │  │ Token Svc│  │  │
│  │  └───────────┘  │  │  └───────────┘  │  │  └──────────┘  │  │
│  └────────┬────────┘  └────────┬────────┘  └───────┬────────┘  │
│           │                    │                    │           │
│           └────────────────────┼────────────────────┘           │
│                                ▼                                │
│                    ┌─────────────────────┐                      │
│                    │   Mesh Coordinator  │                      │
│                    │   (Expulsion Logic) │                      │
│                    └─────────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

### Compromise Detection
| Signal | Source | Action |
|--------|--------|--------|
| **Anomalous admissions** | AdmissionGate metrics | Alert, increase scrutiny |
| **Ledger divergence** | Verification failure | Quarantine cell |
| **Token misuse** | Audit log analysis | Revoke cell tokens |
| **Behavioral anomaly** | Agent telemetry | Isolate agents |

### Expulsion Protocol
```
1. Mesh Coordinator detects compromise (quorum of cells)
2. Broadcast EXPULSION order to all cells
3. Target cell: 
   - Revoke all governance tokens
   - Freeze AdmissionGate (deny all)
   - Seal ActionLedger (read-only)
   - Terminate all agents
4. Other cells: 
   - Reject requests from expelled cell
   - Update mesh membership
5. Forensic: 
   - Snapshot ledger, memory, state
   - Preserve for investigation
```

### Re-admission
- Requires: Root cause analysis, remediation proof, multi-party approval
- Process: New cell identity, fresh keys, gradual trust restoration

---

## Policy Distribution

### Bundle Sync
- **Source:** Git repo (OPA bundles)
- **Distribution:** CRDT-based (last-writer-wins per policy)
- **Activation:** Atomic switch at version boundary
- **Rollback:** Git revert + bundle rebuild

### Policy Evaluation
- **Local:** OPA instance per node (cached decisions)
- **Consistency:** Bundle version in every decision
- **Drift Detection:** Periodic cross-node comparison

---

## Implementation Order

### Phase 1: Raft Infrastructure (Week 1)
1. Raft library integration (hashicorp/raft or bbolt+raft)
2. Cluster membership (static config → dynamic later)
3. Log replication, leader election, snapshots
4. Metrics: election latency, replication lag, commit latency

### Phase 2: Distributed Admission (Week 1-2)
3. AdmissionGate Raft FSM (apply = policy evaluation)
4. Client redirect to leader
5. Read-only mode during election
6. Cross-region latency optimization (async replication)

### Phase 3: Distributed Ledger (Week 2)
7. CRDT implementation (RGA for append-only log)
8. Merkle tree for verification
9. Anchoring service integration
10. Verification API (range, agent, merkle proof)

### Phase 4: Distributed Tokens (Week 2-3)
11. BLS threshold signing library
12. Token cluster (t-of-n signing)
13. Revocation CRDT
14. Token verification (local + distributed)

### Phase 5: Mesh Coordinator (Week 3)
15. Cell membership management
16. Compromise detection algorithms
17. Expulsion protocol implementation
18. Forensic snapshot automation

### Phase 6: Policy Sync (Week 3-4)
19. Bundle distribution via CRDT
20. Atomic activation
21. Drift detection + alerting

### Phase 7: Integration & Testing (Week 4)
22. Multi-node cluster (3+ nodes, multi-region)
23. Chaos: leader failover, network partitions, byzantine nodes
24. Performance: admission latency under load
25. Verification: ledger consistency, token validity
26. Expulsion drill: simulate compromise, verify containment

---

## FourState Target

| Phase | Target |
|-------|--------|
| **CODE_COMPLETE** | ✅ Distributed Admission, Ledger, Tokens, Mesh |
| **TEST_VERIFIED** | ✅ Unit + integration + chaos + performance |
| **LIVE_VERIFIED** | ✅ 3+ node cluster, multi-region |
| **PRODUCTION_READY** | ✅ With expulsion drill passed |

---

## Dependencies

### Requires PR89 + PR90
- `GovernanceClient` (admission, tokens, audit)
- `AgentRegistry` (mesh membership)
- Inter-agent communication (mesh coordination)

### New Dependencies
```toml
dependencies = [
    # ... PR89/90 deps ...
    "raft>=0.1",              # Raft consensus
    "crdt>=0.1",              # CRDT library
    "bls-signatures>=0.1",    # BLS threshold signatures
    "merkle-tree>=0.1",       # Merkle proofs
    "rfc3161-client>=0.1",    # Timestamp anchoring
]
```

---

## References

- `docs/kudbee-control-fabric.md` — Phase 12 Control Fabric (base)
- `agents/governance/governance-hooks.md` — AdmissionGate, ActionLedger, Tokens
- `agents/governance/audit-logging.md` — Ledger format, verification
- `agents/governance/approval-gates.md` — Approval in distributed context
- `agents/chronological/003-pr90-multi-agent-clustering.md` — Mesh cells
- `agents/integration/protocol-responsibilities.md` — Distributed protocols