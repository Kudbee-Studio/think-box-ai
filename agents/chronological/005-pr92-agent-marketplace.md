# PR92: Agent Marketplace — Implementation Plan

**Date:** 2026-09-19
**Status:** MERGED
**Branch:** pushed to `main` as `c4c326c` (no dedicated branch)
**PR:** KILO PR92 (no GitHub PR; pushed directly to main) 

---

## Objective

Build the Agent Marketplace: a platform for discovering, installing, versioning, and publishing KILO Cloud Agents. Enables reuse, sharing, and composition of agent capabilities across teams and organizations.

---

## Scope

### Marketplace Components

| Component | Description |
|-----------|-------------|
| **Package Format** | Standardized agent package (manifest + code + tests + signatures) |
| **Registry API** | Discovery, search, metadata, ratings, versions |
| **Installation Engine** | Dependency resolution, sandboxed install, verification |
| **Publishing Workflow** | Review, signing, publishing, deprecation |
| **Runtime Integration** | Dynamic loading, hot reload, capability advertisement |

---

## Agent Package Format

### Package Structure
```
agent-package/
├── manifest.yaml          # Package metadata (required)
├── agent/                 # Agent implementation
│   ├── __init__.py
│   ├── kernel.py          # AgentKernel subclass
│   ├── config.py          # Pydantic config models
│   └── ...
├── tests/                 # Test suite (required)
│   ├── unit/
│   ├── integration/
│   └── contract/
├── proto/                 # Protobuf definitions (if custom)
├── signatures/            # Cosign signatures
│   ├── manifest.sig
│   ├── agent.sig
│   └── ...
├── sbom.json              # Software Bill of Materials
├── README.md              # Documentation
├── LICENSE                # License file
└── kilo-agent.lock        # Lock file (dependencies)
```

### Manifest Schema
```yaml
# manifest.yaml
name: "kilo/agent-cnc-planner"
version: "1.2.3"
description: "CNC job planning and toolpath generation agent"
category: "SPECIALIZED"
type: "CNC_AGENT"
author: "KILO Team <team@kilo.ai>"
license: "Apache-2.0"
repository: "https://github.com/kilo/agent-cnc-planner"
homepage: "https://kilo.ai/agents/cnc-planner"

# Capabilities
capabilities:
  provides:
    - "cnc.job.planning"
    - "cnc.toolpath.generation"
    - "cnc.simulation"
  requires:
    - "storage.object"
    - "compute.gpu"

# Resource Profile
resource_profile:
  cpu_cores: 4
  memory_mb: 8192
  gpu_required: true
  gpu_type: "L4"
  network_egress: true
  max_duration_seconds: 7200

# Governance
governance_tier: "RESTRICTED"
approval_required:
  - "cnc.execution"
  - "cloud.gpu_allocate"

# Dependencies
dependencies:
  kilo-core: ">=0.5.0,<0.6.0"
  thinkbox-cnc: ">=0.5.0,<0.6.0"
  numpy: ">=1.24"
  trimesh: ">=4.0"

# Compatibility
kilo_version: ">=0.5.0"
protocol_version: "1.0"
python_version: ">=3.10"

# Verification
verification:
  test_coverage_min: 80
  contract_tests: true
  security_scan: true
  sbom_required: true

# Ratings & Metadata
tags: ["cnc", "manufacturing", "toolpath", "gpu"]
maturity: "STABLE"  # ALPHA, BETA, STABLE, DEPRECATED
deprecated: false
```

---

## Registry API

### Discovery Endpoints
```protobuf
service AgentRegistry {
  // Search agents
  rpc Search(SearchRequest) returns (SearchResponse);
  
  // Get agent details
  rpc GetAgent(GetAgentRequest) returns (AgentPackage);
  
  // Get versions
  rpc ListVersions(ListVersionsRequest) returns (ListVersionsResponse);
  
  // Download package
  rpc DownloadPackage(DownloadRequest) returns (stream PackageChunk);
  
  // Ratings & reviews
  rpc GetRatings(GetRatingsRequest) returns (RatingsResponse);
  rpc SubmitRating(SubmitRatingRequest) returns (Rating);
  
  // Publisher operations
  rpc Publish(PublishRequest) returns (PublishResponse);
  rpc Deprecate(DeprecateRequest) returns (DeprecateResponse);
}
```

### Search Request
```protobuf
message SearchRequest {
  string query = 1;                    // Text search
  repeated string categories = 2;      // Filter by category
  repeated string capabilities = 3;    // Filter by capability
  repeated string tags = 4;            // Filter by tags
  MaturityFilter maturity = 5;         // ALPHA/BETA/STABLE
  GovernanceTierFilter tier = 6;       // GOVERNED/RESTRICTED/PRIVILEGED
  int32 page = 7;
  int32 page_size = 8;
  SortBy sort = 9;                     // RELEVANCE, POPULARITY, RECENT, RATING
}

message SearchResponse {
  repeated AgentSummary agents = 1;
  int32 total = 2;
  int32 page = 3;
  int32 page_size = 4;
}
```

### Agent Summary
```protobuf
message AgentSummary {
  string name = 1;
  string version = 2;
  string description = 3;
  string category = 4;
  string type = 5;
  string author = 6;
  repeated string capabilities = 7;
  repeated string tags = 8;
  Maturity maturity = 9;
  GovernanceTier governance_tier = 10;
  double rating = 11;
  int32 download_count = 12;
  string updated_at = 13;
  bool verified = 14;  // Passed security scan + contract tests
}
```

---

## Installation Engine

### Installation Flow
```
1. User requests: install kilo/agent-cnc-planner@1.2.3
2. Registry → Resolve dependencies (topological sort)
3. For each dependency:
   a. Verify signature (cosign + Rekor transparency log)
   b. Verify SBOM (no known CVEs > threshold)
   c. Download package (content-addressed, verified hash)
   d. Extract to sandbox (/opt/kilo/agents/{name}@{version})
   e. Run contract tests (isolated)
   f. Register in local AgentRegistry
4. Write lock file (kilo-agent.lock)
5. Update agent index
6. Return installation receipt
```

### Dependency Resolution
- **Algorithm:** PubGrub (like Poetry/Cargo) — handles conflicts
- **Constraints:** Semantic versioning, kilo_version compatibility
- **Lock File:** Pinned versions, content hashes, SBOM hashes
- **Conflicts:** Fail with actionable error (suggest resolutions)

### Sandboxed Installation
- **Isolation:** Separate Python environment per agent (uv/venv)
- **Permissions:** No network during install (offline-first)
- **Verification:** Signature → SBOM → Tests → Register
- **Rollback:** Atomic (remove env, restore previous index)

---

## Publishing Workflow

### Publish Process
```
1. Developer: kilo-agent publish ./my-agent
2. CLI validates:
   - Manifest schema
   - Test coverage >= 80%
   - Contract tests pass
   - Security scan (Trivy) clean
   - SBOM generated
   - License compatible
3. CLI signs with developer key (cosign)
4. CLI uploads to registry (staging)
5. Registry runs:
   - Automated security scan
   - Contract test execution
   - Compatibility matrix test
   - License compliance check
6. If all pass → Maintainer review (PR-style)
7. Approver signs with maintainer key
8. Registry promotes to production
9. Package available for install
```

### Signing & Trust
- **Developer Key:** Personal cosign key (hardware-backed preferred)
- **Maintainer Key:** Organization cosign key (multi-party for PRIVILEGED)
- **Transparency:** All signatures logged to Rekor
- **Verification:** Installer verifies both signatures + Rekor inclusion

### Versioning & Deprecation
- **Semantic Versioning:** MAJOR.MINOR.PATCH
- **Pre-releases:** `1.0.0-alpha.1`, `1.0.0-beta.2`
- **Deprecation:** `deprecated: true` in manifest + `replacement` field
- **Yanking:** Emergency removal (security) — requires maintainer + security team

---

## Runtime Integration

### Dynamic Loading
```python
class AgentLoader:
    async def load_agent(self, spec: AgentSpec) -> AgentKernel:
        # 1. Check local index
        # 2. If not installed → install (background)
        # 3. Create isolated Python environment
        # 4. Import agent module
        # 5. Instantiate AgentKernel subclass
        # 6. Verify protocol version compatibility
        # 7. Return initialized kernel
```

### Hot Reload
- **Trigger:** New version available + `auto_update: true` in config
- **Process:** Drain → Install new → Health check → Swap → Old drain
- **Rollback:** Automatic on health check failure

### Capability Advertisement
- Installed agents auto-register capabilities with local AgentRegistry
- SUPERVISOR_AGENT discovers and pools available agents
- ROUTER_AGENT routes based on advertised capabilities

---

## Security Model

### Supply Chain Security
| Layer | Protection |
|-------|------------|
| **Source** | Signed commits (git), verified CI |
| **Build** | Reproducible builds, SLSA Level 3 |
| **Package** | Cosign signatures, SBOM, attestations |
| **Registry** | Immutable packages, transparency log |
| **Install** | Signature verification, sandbox, tests |
| **Runtime** | Capability enforcement, governance |

### Trust Policies
```yaml
# /etc/kilo/trust-policy.yaml
trust_policies:
  - name: "internal"
    sources: ["registry.internal.kilo.ai"]
    required_signatures: ["kilo-internal"]
    allow_alpha: true
  
  - name: "community"
    sources: ["registry.kilo.ai"]
    required_signatures: ["kilo-community", "kilo-security"]
    allow_alpha: false
    max_cve_severity: "HIGH"
  
  - name: "third-party"
    sources: ["*"]
    required_signatures: ["kilo-security"]
    allow_alpha: false
    max_cve_severity: "MEDIUM"
    require_manual_approval: true
```

---

## Implementation Order

### Phase 1: Package Format & Registry (Week 1)
1. Manifest schema + validation
2. Package builder (create .kilo-agent package)
3. Registry API (search, get, list versions)
4. Package storage (content-addressed, S3-compatible)

### Phase 2: Installation Engine (Week 1-2)
5. Dependency resolver (PubGrub)
6. Sandboxed installer (uv + isolated env)
7. Signature verification (cosign + Rekor)
8. SBOM verification (CVE scanning)
9. Contract test runner (isolated)
10. Lock file management

### Phase 3: Publishing Workflow (Week 2)
11. CLI publish command
12. Staging registry + automated checks
13. Review workflow (GitHub/GitLab integration)
14. Multi-party signing
15. Promotion to production

### Phase 4: Runtime Integration (Week 2-3)
16. Dynamic agent loader
17. Hot reload mechanism
18. Capability advertisement to registry
19. Version compatibility checking

### Phase 5: Security & Policy (Week 3)
20. Trust policy engine
21. CVE scanning integration (Trivy/Grype)
22. SLSA provenance verification
23. Audit logging for installs/publishes

### Phase 6: Testing & Polish (Week 3-4)
24. End-to-end: publish → install → run → update
25. Conflict resolution testing
26. Rollback testing
27. Performance: install time, search latency
28. Security penetration testing

---

## FourState Target

| Phase | Target |
|-------|--------|
| **CODE_COMPLETE** | ✅ Registry, installer, publisher, loader |
| **TEST_VERIFIED** | ✅ Unit + integration + security tests |
| **LIVE_VERIFIED** | ✅ Registry deployed, agents installable |
| **PRODUCTION_READY** | ✅ Trust policies enforced, SLSA verified |

---

## Dependencies

### Requires PR89 + PR90 + PR91
- `AgentKernel` + base agent types
- `AgentRegistry` (local + distributed)
- Distributed governance (trust policies)
- Inter-agent communication (capability discovery)

### New Dependencies
```toml
dependencies = [
    # ... PR89/90/91 deps ...
    "pubgrub>=0.1",           # Dependency resolution
    "cosign>=2.0",            # Signing/verification
    "rekor-client>=0.1",      # Transparency log
    "trivy>=0.45",            # Security scanning
    "cyclonedx-python>=1.0",  # SBOM generation
    "uv>=0.1",                # Fast Python packaging
    "slsa-verifier>=0.1",     # SLSA verification
]
```

---

## References

- `agents/core/agent-categories.md` — Agent types & capabilities
- `agents/core/agent-kernel.md` — Kernel interface for packages
- `agents/integration/protocol-responsibilities.md` — Protocol versioning
- `agents/governance/compliance-model.md` — Security/compliance requirements
- `agents/governance/audit-logging.md` — Install/publish audit trail
- `agents/chronological/004-pr91-distributed-governance.md` — Trust policies