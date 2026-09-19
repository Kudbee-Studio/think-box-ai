# KILO Cloud Agent Audit Logging — Format & Verification

**Purpose:** Defines the audit logging format, storage, verification, and retention requirements for KILO Cloud Agents. All audit logs are append-only, tamper-evident, and cryptographically verifiable.

---

## Audit Log Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT                                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Governance Client → Local Buffer → Async Flush →       │   │
│  │  ActionLedger (SQLite + Hash Chain)                     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ACTION LEDGER                                 │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐  │
│  │  Write Path  │ │  Hash Chain  │ │  Verification API      │  │
│  │  (append)    │ │  (Merkle)    │ │  (verify, range,       │  │
│  │              │ │              │ │   agent, export)       │  │
│  └──────────────┘ └──────────────┘ └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Log Entry Format (JSON Lines)

Every audit entry is a single JSON object, one per line:

```json
{
  "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "event_type": "admission.decided",
  "timestamp": "2026-09-19T04:00:00.123456Z",
  "agent_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "task_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "tenant_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "correlation_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "causation_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "payload": {
    "decision_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
    "allowed": true,
    "reason": "Policy allow: task_execution within quota",
    "governance_token_hash": "sha256:a1b2c3d4...",
    "policy_version": "v3.2.1",
    "evaluation_ms": 12
  },
  "metadata": {
    "agent_version": "1.0.0",
    "protocol_version": "1.0",
    "hostname": "kilo-host-1",
    "process_id": 12345,
    "thread_id": 67890
  },
  "hash": "sha256:f7e6d5c4b3a2...",
  "prev_hash": "sha256:a1b2c3d4e5f6..."
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_id` | ULID | ✅ | Globally unique, sortable ID |
| `event_type` | string | ✅ | Namespaced: `domain.action` |
| `timestamp` | ISO8601 | ✅ | UTC, microsecond precision |
| `agent_id` | ULID | ✅ | Agent identity |
| `task_id` | ULID | ⭕ | Task context (null if none) |
| `tenant_id` | ULID | ✅ | Tenant isolation |
| `correlation_id` | ULID | ⭕ | Cross-service trace ID |
| `causation_id` | ULID | ⭕ | Previous event that caused this |
| `payload` | object | ✅ | Event-specific data |
| `metadata` | object | ✅ | Execution context |
| `hash` | string | ✅ | `SHA256(prev_hash + canonical_json)` |
| `prev_hash` | string | ✅ | Hash of previous entry (genesis = all zeros) |

---

## Event Types Taxonomy

### Agent Lifecycle
| Event Type | Description | Payload Keys |
|------------|-------------|--------------|
| `agent.spawned` | Process created | `agent_type`, `resource_profile`, `governance_tier` |
| `agent.initialized` | Ready for work | `capabilities`, `config_hash` |
| `agent.idle` | Awaiting task | `idle_since` |
| `agent.executing` | Task started | `task_id`, `task_spec_hash` |
| `agent.checkpoint` | State persisted | `checkpoint_id`, `size_bytes`, `hash` |
| `agent.restored` | State restored | `checkpoint_id`, `verified` |
| `agent.completed` | Task succeeded | `result_ref`, `duration_ms`, `resource_usage` |
| `agent.failed` | Task failed | `error_code`, `error_context`, `retryable` |
| `agent.cancelled` | Task cancelled | `reason`, `partial_progress` |
| `agent.terminated` | Process ended | `reason`, `uptime_ms`, `final_metrics`, `resource_leaks` |

### Governance
| Event Type | Description | Payload Keys |
|------------|-------------|--------------|
| `admission.requested` | Gate check initiated | `action_type`, `action_spec` |
| `admission.decided` | Gate returned decision | `decision_id`, `allowed`, `reason`, `token_hash` |
| `approval.requested` | Human approval needed | `request_id`, `gate_type`, `expires_at` |
| `approval.decided` | Human/policy decided | `decision_id`, `decision`, `reason`, `token` |
| `token.issued` | Governance token created | `token_id`, `expires_at`, `scope` |
| `token.revoked` | Token revoked | `token_id`, `reason` |
| `policy.evaluated` | OPA evaluation | `policy_version`, `decision`, `duration_ms` |

### Resources
| Event Type | Description | Payload Keys |
|------------|-------------|--------------|
| `resource.allocated` | CPU/mem/GPU granted | `resource_type`, `amount`, `reservation_id` |
| `resource.released` | Resources returned | `reservation_id`, `actual_usage` |
| `resource.exceeded` | Limit breached | `resource_type`, `limit`, `actual` |
| `network.egress` | Outbound connection | `destination`, `port`, `protocol`, `allowed` |
| `storage.read` | Durable read | `path`, `size_bytes`, `classification` |
| `storage.write` | Durable write | `path`, `size_bytes`, `classification` |

### Security
| Event Type | Description | Payload Keys |
|------------|-------------|--------------|
| `security.boundary_violation` | Sandbox escape attempt | `violation_type`, `syscall`, `blocked` |
| `security.seccomp_violation` | Syscall filter match | `syscall`, `args`, `action` |
| `security.auth_failure` | Auth failed | `method`, `reason`, `source_ip` |
| `security.privilege_escalation` | Privilege gain attempt | `vector`, `blocked` |

---

## Hash Chain Construction

### Canonical JSON
Before hashing, the entry (excluding `hash` field) is serialized canonically:
1. Keys sorted lexicographically
2. No whitespace
3. UTF-8 encoded
4. Deterministic float formatting

### Chain Algorithm
```
entry_0: hash = SHA256("GENESIS" + canonical_json(entry_0))
entry_n: hash = SHA256(prev_hash + canonical_json(entry_n))
```

### Genesis Entry
First entry in ledger:
```json
{
  "event_id": "00000000000000000000000000",
  "event_type": "ledger.genesis",
  "timestamp": "2026-01-01T00:00:00Z",
  "agent_id": "system",
  "tenant_id": "system",
  "payload": {"ledger_version": "1.0"},
  "metadata": {},
  "hash": "sha256:...",
  "prev_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
}
```

---

## Storage

### Primary: SQLite (ActionLedger)
- **Table:** `audit_log` (event_id PK, event_type, timestamp, agent_id, tenant_id, payload_json, hash, prev_hash)
- **Indexes:** (tenant_id, timestamp), (agent_id, timestamp), (event_type, timestamp)
- **WAL Mode:** Enabled for concurrent reads
- **Sync:** `PRAGMA synchronous = FULL`

### Secondary: Object Store (Archive)
- **Format:** Parquet (partitioned by tenant_id/date)
- **Compression:** ZSTD level 3
- **Retention:** 7 years (compliance)
- **Immutability:** Object lock (WORM)

### Tertiary: External Timestamping
- **Service:** RFC 3161 TSA or blockchain anchor
- **Frequency:** Every 1000 entries or 1 hour
- **Stored:** Anchor receipts in separate table

---

## Verification

### CLI Verification
```bash
# Full chain verification
kilo-audit verify --ledger /var/lib/kilo/ledger.db

# Range verification
kilo-audit verify --ledger /var/lib/kilo/ledger.db \
  --from 01ARZ3NDEKTSV4RRFFQ69G5FAV \
  --to 01ARZ3NDEKTSV4RRFFQ69G5FAW

# Agent-specific
kilo-audit verify --ledger /var/lib/kilo/ledger.db \
  --agent 01ARZ3NDEKTSV4RRFFQ69G5FAV

# Export for external audit
kilo-audit export --ledger /var/lib/kilo/ledger.db \
  --format jsonl --output audit_export.jsonl \
  --tenant 01ARZ3NDEKTSV4RRFFQ69G5FAV \
  --from 2026-09-01 --to 2026-09-30
```

### Programmatic Verification
```python
class ActionLedger:
    def verify(self, 
               start_id: str | None = None,
               end_id: str | None = None,
               agent_id: str | None = None) -> VerificationResult:
        """
        Returns VerificationResult:
        - valid: bool
        - entries_checked: int
        - first_invalid: Entry | None
        - chain_root: str  # Merkle root for range
        """
        ...

    def get_merkle_proof(self, event_id: str) -> MerkleProof:
        """Returns inclusion proof for single entry"""
        ...

    def verify_merkle_proof(self, proof: MerkleProof) -> bool:
        """Verifies Merkle inclusion proof"""
        ...
```

### Verification Result
```json
{
  "valid": true,
  "entries_checked": 150000,
  "first_invalid": null,
  "chain_root": "sha256:a1b2c3d4e5f6...",
  "verified_at": "2026-09-19T04:00:00Z",
  "verifier_version": "1.0.0"
}
```

---

## Retention & Disposal

| Data Tier | Retention | Storage | Disposal |
|-----------|-----------|---------|----------|
| **Hot** (SQLite) | 90 days | Local SSD | Auto-purge after archive |
| **Warm** (Parquet) | 2 years | Object store (IA) | Auto-transition to cold |
| **Cold** (Parquet + WORM) | 7 years | Object store (Glacier/Archive) | Legal hold review |
| **Anchors** (Timestamp receipts) | Indefinite | Object store + Git | Never |

### Legal Hold
- Triggered by: litigation, investigation, audit
- Applies to: All tiers for affected tenant/agent/date range
- Overrides: Auto-disposal suspended
- Release: Manual approval by Legal

---

## Performance Requirements

| Metric | Target |
|--------|--------|
| **Write Latency** (p99) | < 5 ms |
| **Read Latency** (p99) | < 50 ms |
| **Throughput** | 10,000 entries/sec |
| **Verification** (1M entries) | < 30 seconds |
| **Export** (1M entries) | < 60 seconds |
| **Disk Usage** (1M entries) | < 500 MB |

---

## Implementation Requirements (PR89+)

- Local buffer: ring buffer (10k entries), flush on batch (100) or timeout (1s)
- Async flush: non-blocking, backpressure if disk slow
- Hash computation: hardware-accelerated SHA256 (Intel SHA-NI)
- SQLite: connection pool, prepared statements, WAL
- Parquet writer: Arrow, partitioned by tenant/date
- Verification: streaming (O(1) memory), parallelizable
- Metrics: Prometheus exporter for all above

---

## References

- `governance/governance-hooks.md` — Mandatory audit events
- `governance/compliance-model.md` — Retention & compliance requirements
- `governance/approval-gates.md` — Approval decision audit trail
- `core/agent-lifecycle.md` — Lifecycle event definitions
- `integration/scheduler-integration.md` — Scheduler audit integration