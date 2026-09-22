# ADR 005: Windows Server as Think Box Execution Substrate

**Date:** 2026-09-22
**Status:** Conditional — architecture does not currently support this; see Required Conditions

---

## Context

A dedicated UpCloud Windows Server (`kudbee-thinkbox-test-win01`) was provisioned:

- 4 CPU / 16 GB RAM / 50 GB disk
- Public IPv4: 209.50.52.85
- Private utility-network IP: 10.3.13.207

The question: should this Windows Server become a first-class Think Box execution substrate?

This ADR evaluates all architecturally plausible options against the repository's existing contracts, governance model, and execution abstractions. No code changes were made.

---

## Current Architecture

### Layer Boundaries (from AGENTS.md §1.1)

The system has five layers. A layer may only import from layers beneath it:

| Layer | Role | Examples |
|-------|------|----------|
| Foundation | Config, errors, logging, HTTP client | `core/foundation/`, `core/providers/` |
| Provider | Infrastructure providers, execution contracts | `core/providers/execution.py`, `core/providers/upcloud.py` |
| Memory | Sessions, tasks, knowledge | `core/memory/`, `thinkbox/session.py` |
| Governance/Tools | Admission, ledger, receipts, proofs | `thinkbox/governed.py`, `thinkbox/ledger/`, `thinkbox/execution_adapter.py` |
| Runtime | Agent loops, scheduling, orchestration | `thinkbox/engine.py`, `thinkbox/scheduler.py` |

### Control Plane vs. Execution Substrate

These are distinct layers. Confusing them is a fundamental error:

| Concept | Definition | Implementation |
|---------|-----------|----------------|
| **Control Plane** | Read-only infrastructure management, orchestration, governance | UpCloud REST API, `thinkbox/upcloud.py` (investigates only, never executes) |
| **Execution Substrate** | The machine that runs commands and returns artifacts | Upstash Box (Firecracker microVM) |
| **Provider Adapter** | Bridges Think Jobs to execution substrate via HTTP | `thinkbox/execution_adapter.py` (`UpstashBoxExecutionAdapter`) |
| **Infrastructure Provider** | Manages infra lifecycle (create/delete/reboot) | `core/providers/execution.py` implementations (e.g., `UpCloudExecutionProvider`) |
| **Think Job** | User task decomposed into executable units | `thinkbox/engine.py`, `thinkbox/pop_arena.py` |
| **Proof/Receipt** | Post-execution evidence with hash verification | `ExecutionReceipt`, `ActionLedger`, checkpoints |

### Execution Substrate Contract (verified from source)

**File:** `thinkbox/execution_adapter.py`

**Contract:**
- Transport: HTTP POST to `<UPSTASH_PUBLIC_BOX_URL>/run`
- Auth: Bearer token via `Authorization` header
- Request payload: `{execution_id, job_id, command, artifact_name}`
- Response payload: `{exit_code, hostname, os, output, artifact_content, artifact_hash}`
- Verification: SHA-256 hash of local artifact must match `artifact_hash` from response
- Failure mode: Fails closed with `NOT_CONFIGURED` if URL/token absent

**Environment variables (sole contract):**
- `UPSTASH_PUBLIC_BOX_URL` — substrate endpoint URL
- `UPSTASH_PUBLIC_BOX_TOKEN` — Bearer authentication token

**Key constraint:** The adapter makes NO assumptions about the substrate's OS, hypervisor type, or internal architecture. It only requires a compatible HTTP endpoint. This means Windows is NOT architecturally excluded at the protocol level.

---

## Observed Windows Server Capabilities

### FACT — Network Tests (2026-09-22)

| Test | Public IP (209.50.52.85) | Private IP (10.3.13.207) |
|------|---------------------------|---------------------------|
| **RDP (3389)** | OPEN | CLOSED/TIMEOUT |
| **SSH (22)** | TIMEOUT (blocked) | TIMEOUT (blocked) |
| **HTTP (80)** | OPEN → HTTP 403 (Cloudflare) | OPEN → HTTP 403 (Cloudflare) |
| **HTTPS (443)** | OPEN → TLS error (Cloudflare) | OPEN → TLS error (Cloudflare) |
| **WinRM (5985/5986)** | TIMEOUT (not enabled) | TIMEOUT (not enabled) |
| **`/run` endpoint** | HTTP 403 (Cloudflare) | HTTP 403 (Cloudflare) |

### FACT — Environment Variables

- `UPSTASH_PUBLIC_BOX_URL` set to Upstash Box endpoint (not Windows)
- `UPSTASH_PUBLIC_BOX_TOKEN` **absent** — adapter fails closed
- `UPSTASH_BOX_API_KEY` present but **not consumed** by adapter (per ADR 004)
- No Windows-specific execution env vars present

### ARCHITECTURAL DECISION (from repository code)

Per `thinkbox/upcloud.py:1-10`:
> UpCloud is an INFRASTRUCTURE / CONTROL-PLANE provider (read-only REST). It is NOT the Think Box execution substrate. The live execution substrate is the Upstash Box selected by thinkbox/substrate.py::detect_substrate(). SSH-to-UpCloud execution is unsupported and not required.

Per AGENTS.md §1.2 (Provider Independence):
> No model provider is hardcoded. The runtime must work identically with: OpenAI-compatible APIs, Anthropic Messages API, Local models. Swapping a provider is a configuration change, not a code change.

Per `thinkbox/substrate.py:24-39`:
> `detect_substrate()` returns the live substrate from environment variables. Current priority: `UPSTASH_PUBLIC_BOX_URL` > `THINKBOX_UPCLOUD_API_TOKEN` > `CI` > `local`.

---

## Options Considered

### Option A: Windows + OpenSSH

| Aspect | Assessment |
|--------|-----------|
| Transport | TCP port 22 (SSH) |
| Authentication | Password/key — credentials never tested, would require env var |
| Authorization | Would need per-user ACL |
| Tool execution boundary | `exec` command on remote host |
| Receipt/proof generation | Adapter would need wrapping |
| Network requirements | Port 22 open — BLOCKED by UpCloud security groups |
| Secret requirements | SSH key or password in env |
| Failure semantics | Connection timeout, auth failure |
| Restart/reconnect | SSH reconnect on failure |
| Governance compatibility | Would need to fit AdmissionGate pattern |
| Testability | Testable with mock SSH server |
| Security implications | Open SSH to internet = high risk |
| Provider/substrate separation | VIOLATED — SSH is infra access, not substrate contract |

**Verdict:** BLOCKED. Network unreachable. Architecture explicitly excludes SSH-to-infrastructure.

### Option B: Windows + WinRM

| Aspect | Assessment |
|--------|-----------|
| Transport | TCP ports 5985/5986 (HTTP/HTTPS WinRM) |
| Authentication | NTLM/Kerberos/certificate |
| Authorization | Windows ACLs |
| Tool execution boundary | `winrm invoke` commands |
| Receipt/proof generation | Adapter wrapping needed |
| Network requirements | Ports not enabled |
| Secret requirements | WinRM credentials |
| Failure semantics | Connection refused, auth failure |
| Restart/reconnect | Session reconnection |
| Governance compatibility | Requires new governance path |
| Testability | No stdlib WinRM client in Python; requires `pywinrm` |
| Security implications | Open WinRM to internet = high risk |
| Provider/substrate separation | VIOLATED — WinRM is infra management, not substrate contract |

**Verdict:** BLOCKED. Ports not enabled. No stdlib client. Violates substrate contract.

### Option C: Windows-hosted HTTPS /run execution service

| Aspect | Assessment |
|--------|-----------|
| Transport | HTTPS POST to `/run` |
| Authentication | Bearer token (matches adapter contract) |
| Authorization | Token-based |
| Tool execution boundary | HTTP handler executing commands |
| Receipt/proof generation | Natural — adapter already handles this |
| Network requirements | HTTP/HTTPS blocked by Cloudflare 1003 |
| Secret requirements | `UPSTASH_PUBLIC_BOX_TOKEN` |
| Failure semantics | HTTP 403/503, timeout |
| Restart/reconnect | HTTP retry |
| Governance compatibility | Compatible — same adapter path |
| Testability | Fully testable with stub server (see `_BoxHandler` in test_execution_adapter.py) |
| Security implications | Moderate — exposed endpoint needs hardening |
| Provider/substrate separation | PRESERVED — this IS the substrate contract |

**Verdict:** ARCHITECTURALLY VIABLE but OPERATIONALLY BLOCKED. Cloudflare protection explicitly forbids removal. If Cloudflare were configured to allow the `/run` endpoint, this would be the correct path and would reuse 100% of existing adapter code with zero changes.

### Option D: Windows outbound agent connecting to Think Box control plane

| Aspect | Assessment |
|--------|-----------|
| Transport | HTTPS outbound from Windows to Upstash Box |
| Authentication | Standard Bearer token |
| Authorization | Token-based |
| Tool execution boundary | Agent runs locally, reports results |
| Receipt/proof generation | Agent produces local receipt, uploads to control plane |
| Network requirements | Outbound HTTPS only — no inbound firewall changes |
| Secret requirements | Token stored on Windows agent |
| Failure semantics | Agent reconnects, retries |
| Restart/reconnect | Agent restarts, reconnects to control plane |
| Governance compatibility | Requires new pattern — agent as substrate proxy |
| Testability | Requires Windows environment |
| Security implications | Lower — outbound only |
| Provider/substrate separation | PRESERVED — substrate still hosted elsewhere |

**Verdict:** HYPOTHETICAL — UNVERIFIED. No code exists for this pattern. Would require a new "substrate agent" architecture. Not in scope for this investigation but architecturally interesting for future consideration.

### Option E: Keep Upstash Box as substrate, Windows as dev/test/control machine

| Aspect | Assessment |
|--------|-----------|
| Transport | N/A — Windows not used for execution |
| Authentication | N/A |
| Authorization | N/A |
| Tool execution boundary | N/A |
| Receipt/proof generation | Unchanged (Upstash Box) |
| Network requirements | No changes |
| Secret requirements | No new secrets |
| Failure semantics | Unchanged |
| Restart/reconnect | N/A |
| Governance compatibility | Fully compatible |
| Testability | Unchanged |
| Security implications | No change |
| Provider/substrate separation | PRESERVED |

**Verdict:** RECOMMENDED. Zero risk, zero changes, preserves all existing contracts. Windows serves as:
- Development environment for Windows-specific code
- Test/QA target for Windows compatibility
- Control/management machine (RDP access for operators)
- Future outbound agent host (Option D, if pursued)

### Option F: Existing architecture makes this unnecessary

| Aspect | Assessment |
|--------|-----------|
| Transport | N/A |
| Observation | The `ExecutionProvider` contract in `core/providers/execution.py` is for INFRASTRUCTURE providers (create/delete/reboot servers), NOT execution substrates |
| Key insight | `UpstashBoxExecutionAdapter` is the execution mechanism, not a provider. It uses the `/run` HTTP contract, which is OS-agnostic |
| Key insight | `detect_substrate()` in `substrate.py` determines the execution substrate by env var, not by type. Windows COULD appear here if a `/run` endpoint existed |
| Conclusion | No existing architecture makes Option C unnecessary, but the strict Upstash Box assignment means Windows cannot become a substrate without violating the current deployment contract |

**Verdict:** NOT APPLICABLE. The architecture does not inherently preclude Windows, but the operational assignment is clear.

---

## Security/Governance Analysis

### FACT — Governance Chain

Every execution path in the repository follows this pattern:
1. `GovernedEngine` checks `AdmissionGate` via governance token
2. Action appended to `ActionLedger` (append-only, verifiable)
3. Task executed through `VerifiedRetrySession` (bounded retries)
4. Receipt generated with hash verification
5. Proof artifact persisted with SHA-256 chain

### Security Implications of Each Option

| Option | Adds inbound exposure | Requires new secret | Compatible with governance | Risk |
|--------|----------------------|---------------------|---------------------------|------|
| A (SSH) | Yes (port 22) | Yes | No (not in contract) | HIGH |
| B (WinRM) | Yes (port 5985/5986) | Yes | No (not in contract) | HIGH |
| C (HTTPS /run) | Yes (but Cloudflare-protected) | No (existing token) | YES | MODERATE |
| D (outbound agent) | No | Yes (token on agent) | Unverified | LOW-MODERATE |
| E (dev/test/control) | No changes | No | YES | NONE |

---

## Decision

**CONDITIONAL — Recommendation: Option E**

**Windows Server should NOT become a first-class execution substrate in the current architecture.**

**Reasons:**
1. **Network unreachable** — All inbound execution paths blocked (Cloudflare, security groups)
2. **Architecture explicitly separates** Control Plane (UpCloud/Windows) from Execution Substrate (Upstash Box)
3. **No env var contract** — `UPSTASH_PUBLIC_BOX_URL` points to Upstash Box, not Windows
4. **Operational risk** — Making Windows a substrate would require changing the substrate detection contract, which affects every execution path

**However, Option C (Windows-hosted HTTPS `/run` service) IS architecturally valid** — the `UpstashBoxExecutionAdapter` makes no OS assumptions and would work unchanged if a compatible endpoint were reachable.

---

## Recommended Role of kudbee-thinkbox-test-win01

1. **Development and testing** — Windows-specific code development, compatibility testing
2. **Operator access** — RDP-based manual management and diagnostics
3. **Future Option D candidate** — Outbound agent that connects to Upstash Box for command execution
4. **NOT** an execution substrate under current architecture

---

## Required Conditions for First-Class Substrate (Option C)

If Windows is to become a first-class execution substrate, ALL of these must be satisfied:

1. Cloudflare must allow inbound HTTP POST to `/run` on the Windows server (or a tunnel/VPN must replace Cloudflare)
2. A Windows HTTP handler must be installed at `/run` implementing the exact request/response contract from `UpstashBoxExecutionAdapter._post()`
3. `UPSTASH_PUBLIC_BOX_URL` must be set to the Windows endpoint URL
4. `UPSTASH_PUBLIC_BOX_TOKEN` must be set to the Windows endpoint auth token
5. The endpoint must return `{exit_code, hostname, os, output, artifact_content, artifact_hash}` in JSON
6. No production code changes required — adapter is OS-agnostic

---

## Consequences

### Immediate
- Windows server remains in dev/test/control role
- Upstash Box remains the sole execution substrate
- No code changes, no risk, no debt

### Future
- Option C is fully preserved for when network allows
- Option D remains a viable future architecture for secure outbound execution
- All existing tests continue to validate the substrate contract regardless of OS

---

## Explicit Non-Goals

1. **No code changes** to `UpstashBoxExecutionAdapter` or substrate detection for Windows
2. **No firewall changes** — no port opening, no Cloudflare removal
3. **No RDP/WinRM execution** — architecture does not support these as execution paths
4. **No production claims** — Windows is not production-ready for execution
5. **No new dependencies** — no WinRM libraries, no SSH libraries, no Windows agents

---

## Verification Plan

- [x] All network connectivity tests completed (see Observed Capabilities)
- [x] `UpstashBoxExecutionAdapter` contract verified from source code
- [x] `substrate.py::detect_substrate()` logic verified from source code
- [x] `upcloud.py` architecture statements verified from source code
- [x] All existing tests pass (2243 OK, 8 skipped, 3 expected failures)
- [x] No code changes introduced
- [ ] Option D proof-of-concept (outbound agent) — future work, not started

---

## Evidence Classification

| Claim | Classification |
|-------|---------------|
| SSH port 22 blocked | FACT (tested) |
| HTTP/HTTPS blocked by Cloudflare | FACT (tested) |
| WinRM ports not enabled | FACT (tested) |
| `/run` endpoint returns 403 | FACT (tested) |
| `UPSTASH_PUBLIC_BOX_URL` points to Upstash Box | FACT (env var) |
| `UPSTASH_PUBLIC_BOX_TOKEN` absent | FACT (env var) |
| Adapter is OS-agnostic | ARCHITECTURAL DECISION (source code verification) |
| Option C is architecturally valid | ARCHITECTURAL DECISION (based on adapter contract) |
| Windows could be Option D candidate | HYPOTHESIS (no code exists) |
| Option D outbound agent works | UNVERIFIED (no implementation) |
| Windows would improve developer experience | HYPOTHESIS (not tested) |
