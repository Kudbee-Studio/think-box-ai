# KILO Cloud Agent Compliance Model — Expectations & Audit

**Purpose:** Defines the compliance expectations for KILO Cloud Agents and the audit framework that validates adherence. This model ensures agents meet regulatory, organizational, and platform requirements.

---

## Compliance Framework

### Compliance Domains

| Domain | Standards | Scope | Enforcement |
|--------|-----------|-------|-------------|
| **Data Protection** | GDPR, CCPA, LGPD | Personal data handling | Policy + Audit |
| **Security** | SOC 2 Type II, ISO 27001 | Infrastructure, code, data | Policy + Audit + PenTest |
| **Financial** | SOX, PCI-DSS | Billing, cost accounting | Policy + Audit |
| **Operational** | ITIL, COBIT | Change mgmt, incident response | Policy + Process |
| **Industry** | HIPAA, FedRAMP, CMMC | Sector-specific | Policy + Audit (if applicable) |

### Compliance by Governance Tier

| Tier | Required Compliance | Evidence Required | Audit Frequency |
|------|---------------------|-------------------|-----------------|
| **GOVERNED** | Data Protection, Security (baseline) | Audit logs, config snapshots | Continuous (automated) + Quarterly (manual) |
| **RESTRICTED** | + Financial, Operational | + Approval records, change logs | Continuous + Monthly |
| **PRIVILEGED** | + All applicable industry | + Full forensic trail, attestations | Continuous + Weekly |

---

## Agent Compliance Requirements

### 1. Data Handling Compliance

#### Data Classification
All data processed by agents MUST be classified:

| Classification | Description | Handling Requirements |
|----------------|-------------|----------------------|
| **PUBLIC** | No sensitivity | Standard handling |
| **INTERNAL** | Org-internal | Tenant isolation, audit logging |
| **CONFIDENTIAL** | Business-sensitive | Encryption at rest/transit, access control |
| **RESTRICTED** | Regulated (PII, PHI, PCI) | + Tokenization, DLP, retention policy |
| **SECRET** | Credentials, keys | Vault-only, never in agent memory/logs |

#### Data Processing Rules
- **Minimization:** Only process data necessary for task
- **Purpose Limitation:** Use only for declared task purpose
- **Retention:** Auto-delete per classification policy
- **Locality:** Process in compliant region (data residency)
- **Transfer:** Cross-border transfer requires approval

### 2. Security Compliance

#### Code Integrity
- Agent code: Signed, verified at spawn (sigstore/cosign)
- Dependencies: SBOM generated, vulnerability scanned (Trivy/Grype)
- Base images: Hardened, distroless where possible, regularly rebuilt
- Runtime: Immutable (no self-modification)

#### Runtime Security
- **Seccomp:** Default-deny profile (see execution-boundaries.md)
- **Capabilities:** Minimal (drop ALL, add only required)
- **Rootless:** Always run as non-root user
- **Read-only Rootfs:** Enforced
- **No New Privs:** `no_new_privs=1`

#### Network Security
- **mTLS:** All service-to-service (service mesh)
- **Egress:** Allowlist only (see execution-boundaries.md)
- **Ingress:** Zero-trust (identity-aware proxy)
- **DNS:** Platform resolver only (no custom)

### 3. Operational Compliance

#### Change Management
- Agent version changes: ADR + approval + staged rollout
- Config changes: GitOps (ArgoCD/Flux), review required
- Policy changes: Canary + automated rollback on metrics regression
- Emergency changes: Break-glass process, post-hoc review

#### Incident Response
- **Detection:** Automated (telemetry anomalies, audit alerts)
- **Containment:** QUARANTINE_AGENT automatic isolation
- **Investigation:** Forensic snapshot (memory, disk, network)
- **Remediation:** Patch, redeploy, rotate credentials
- **Post-mortem:** Required for SEV-1/2, published internally

#### Business Continuity
- **RPO:** < 1 hour (ledger, memory, vector store)
- **RTO:** < 15 minutes (agent restart, supervisor failover)
- **Backup:** Daily snapshots of all durable state
- **DR:** Cross-region replica for PRIVILEGED agents

---

## Audit Framework

### Audit Types

| Audit Type | Trigger | Scope | Performers |
|------------|---------|-------|------------|
| **Continuous** | Real-time (telemetry, audit log) | All agents | Automated (AUDIT_AGENT) |
| **Periodic** | Schedule (weekly/monthly/quarterly) | Tier-based | AUDIT_AGENT + Human |
| **Forensic** | Incident, anomaly, complaint | Specific agent/task | Security team |
| **Compliance** | Regulatory requirement | Domain-specific | External auditor |
| **Supplier** | Vendor assessment | Platform services | Procurement + Security |

### Audit Evidence Collection

#### Automated Evidence (Continuous)
| Evidence | Source | Retention | Access |
|----------|--------|-----------|--------|
| **Audit Log** | ActionLedger | 7 years (immutable) | AUDIT_AGENT, Compliance |
| **Telemetry** | Metrics/Traces/Logs | 90 days hot, 7 years cold | Monitoring, AUDIT_AGENT |
| **Config Snapshots** | GitOps repo | Indefinite | Git history |
| **SBOM** | Build pipeline | Per version | Security, AUDIT_AGENT |
| **Vulnerability Scans** | CI/CD + Runtime | 90 days | Security |
| **Access Logs** | IAM, Vault, Mesh | 1 year | Security, Compliance |

#### On-Demand Evidence (Forensic)
| Evidence | Collection Method | Trigger |
|----------|-------------------|---------|
| **Memory Dump** | `gcore` / eBPF | Incident, anomaly |
| **Disk Image** | Snapshot + copy | Incident |
| **Network Capture** | eBPF / tcpdump | Incident, anomaly |
| **Process Tree** | `ps` / eBPF | Incident |
| **Environment** | `/proc/environ` | Incident |

### Audit Verification Procedures

#### Ledger Verification
```bash
# Verify full chain integrity
ledger verify --full

# Verify specific range
ledger verify --from <event_id> --to <event_id>

# Verify agent-specific
ledger verify --agent <agent_id>
```

#### Policy Compliance Verification
```bash
# Check all agents against current policy
opa eval -i agent_inventory.json -d policies/ "data.kilo.admission.compliant"

# Generate compliance report
kilo-audit compliance --format sarif --output compliance.sarif
```

#### Data Handling Verification
```bash
# Scan for unclassified data in agent workspaces
kilo-audit data-scan --classification required

# Verify encryption at rest
kilo-audit encryption-check --all-volumes

# Verify retention compliance
kilo-audit retention-check --policy data_retention.yaml
```

---

## Non-Compliance Handling

### Violation Classification

| Severity | Criteria | Response Time | Escalation |
|----------|----------|---------------|------------|
| **CRITICAL** | Data breach, unauthorized PRIVILEGED access, ledger tampering | < 1 hour | CISO, Legal, CEO |
| **HIGH** | Unencrypted RESTRICTED data, policy bypass, quota abuse | < 4 hours | Security Lead, Compliance |
| **MEDIUM** | Missing audit logs, expired certs, config drift | < 24 hours | Platform Team |
| **LOW** | Missing tags, suboptimal config, doc gaps | < 1 week | Platform Team |

### Remediation Workflow
1. **Detect** → Automated alert + ticket creation
2. **Triage** → Severity classification + owner assignment
3. **Contain** → Quarantine, revoke tokens, isolate network
4. **Investigate** → Root cause + impact assessment
5. **Remediate** → Fix + verify + deploy
6. **Document** → Post-mortem + policy update + training
7. **Close** → Evidence of fix + compliance sign-off

---

## Compliance Reporting

### Continuous Dashboard
- Real-time compliance posture per agent/tenant
- Policy violation count & trend
- Audit log integrity status
- Data classification coverage
- Vulnerability exposure

### Periodic Reports
| Report | Frequency | Audience | Format |
|--------|-----------|----------|--------|
| **Compliance Posture** | Weekly | Platform Team, Security | Dashboard + PDF |
| **Regulatory Summary** | Monthly | Compliance, Legal | PDF + Evidence Pack |
| **Audit Readiness** | Quarterly | Leadership, Auditors | SARIF + Narrative |
| **Annual Attestation** | Yearly | Board, Regulators | Formal Report |

---

## Implementation Requirements (PR89+)

- Compliance metadata embedded in agent identity document
- Automated compliance checks in CI/CD (pre-spawn gate)
- AUDIT_AGENT implements continuous verification loops
- Evidence collection APIs for on-demand forensic
- Integration with GRC platforms (Drata, Vanta, etc.) via webhook
- Policy-as-code: all compliance rules in Rego, versioned in Git

---

## References

- `governance/governance-hooks.md` — Admission gates & audit logging
- `governance/approval-gates.md` — Approval gate specifications
- `governance/audit-logging.md` — Audit log format & verification
- `execution-boundaries.md` — Security boundaries enforcement
- `core/cloud-interaction-model.md` — Data residency & cloud compliance
- `integration/scheduler-integration.md` — Scheduler compliance integration