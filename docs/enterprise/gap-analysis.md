# Enterprise Agent OS — Gap analysis

**As of:** `main` @ `71027021` (2026-09-30). **Status:** Proposed, part of the enterprise plan in [`README.md`](README.md).
Each gap points at the evidence in [`baseline.md`](baseline.md) (row numbers in brackets) and at the phase in
[`roadmap.md`](roadmap.md) that closes it.

**Severity.** *Critical:* blocks any multi-user use or lets one actor act as another. *High:* weakens a security
or audit guarantee we already claim. *Medium:* operational or hygiene debt.

## Identity

| ID | Gap | Sev | Closes in |
|---|---|---|---|
| ID-1 | No dashboard login and no users or roles. A login existed (#286) and was removed (#289) when the dashboard was declared a local-only console. [2] | Critical | E0 |
| ID-2 | One fixed governance identity (`web-dashboard-agent`) stands in for every human, so receipts and ledger rows cannot say who acted. [2, 4] | Critical | E0 |
| ID-3 | Backend callers authenticate with shared secrets: a set of API keys with no per-key identity, and one shared control-plane bearer compared with `!=` instead of a constant-time compare. [2] | High | E0 (constant-time compare), E3 (per-principal keys) |
| ID-4 | Sessions would live in process memory (the removed implementation did), so a restart signs everyone out; only one process can serve them. | Medium | E0 (store sessions in SQLite) |
| ID-5 | SSO/OIDC is not available. | Medium | Out of scope for this arc (see ADR 027 non-goals) |

## Tenancy

| ID | Gap | Sev | Closes in |
|---|---|---|---|
| TN-1 | No tenant or organization concept. Sessions are random UUIDs with a per-session workspace; memory (org and verified layers), run history, receipts and the ledger are global. [1, 7, 9] | Critical (for any multi-customer use) | E4 |
| TN-2 | File confinement is proven per session (#290, symlink races included) but not per tenant. [1] | High | E4 |
| TN-3 | Budgets and rate limits are global (`KUDBEE_DAILY_BUDGET_USD`, backend rate limit), not per tenant or user. [10] | Medium | E4 |

## Governance

| ID | Gap | Sev | Closes in |
|---|---|---|---|
| GV-1 | Governance tokens and the identity ledger are process-memory dictionaries, lost on restart; revocations do not survive either. [4] | High | E1 |
| GV-2 | The HMAC signature inside a governance token is never verified (`verify()` is a dict lookup), and the signing key falls back to a hardcoded default when `THINKBOX_GOVERNANCE_SIGNING_KEY` is unset. The signature gives a false impression of integrity. [4] | High | E1 (verify it or drop it; fail closed without a key) |
| GV-3 | The capability catalog is strings scattered in code; only `shell:upcloud-ssh:readonly` is meaningful end to end. There are no risk tiers. [4, 5] | High | E1, E3 |
| GV-4 | Policy is a code constant (`upcloud-ssh-readonly` v1) with no versioned records or change control. Tokens carry a `policy_version` that nothing governs. [5] | Medium | E1 |
| GV-5 | Approvals exist only as a single-person prompt (agent file overwrite, new domain, private-network requests), held in memory with an auto-deny, answered by the same person who started the run. There is no second approver for high-risk actions. [1] | High | E3 |

## Audit

| ID | Gap | Sev | Closes in |
|---|---|---|---|
| AU-1 | The dashboard audit log is browser `localStorage` and can be cleared from the UI. It is not evidence. [8] | High | E1 |
| AU-2 | The web server records no audit events (logins, failed logins, config changes, approvals, plugin execution, user changes). The Python `audit_storage.py` is separate and unaudited here. [8] | High | E1 |
| AU-3 | The action ledger is a hash chain without a signature, anchor or export format, and receipts are not signed. Someone with database write access can recompute the whole chain. [7] | High | E1 |
| AU-4 | No committed, redacted proof bundle exists for a live run (`docs/CONTINUITY.md` lists it as the next larger improvement). [6, 7] | Medium | E1 |

## Execution

| ID | Gap | Sev | Closes in |
|---|---|---|---|
| EX-1 | SSH runs as `root` by default. [6] | Critical | E2 (founder-gated infra) |
| EX-2 | Host keys use `StrictHostKeyChecking=accept-new` (trust on first use); the worker key is not pinned. [6] | High | E2 |
| EX-3 | No worker registry: one host comes from `UPCLOUD_SERVER_IP`; two UpCloud accounts, non-unique hostnames, an orphan duplicate server and an unreachable worker-01. [6] | Medium | E5 |
| EX-4 | No SSH-only firewall on worker-02 (open founder decision). [6] | High | E2 (founder-gated infra) |
| EX-5 | Upstash Box substrate is not configured (`ENV_NOT_CONFIGURED`). [15] | Medium | Not planned in this arc; revisit under E6 |

## Operations

| ID | Gap | Sev | Closes in |
|---|---|---|---|
| OP-1 | CI cannot go green: 12 type errors (#300), a hung test and no timeouts (#302), and a Python job that runs for hours with no `timeout-minutes`. No branch protection can rely on it. [14] | Critical | E0 |
| OP-2 | No HTTPS and no deployment target; `nginx.conf` has TLS config that has never been exercised, and `Caddyfile` has `auto_https off`. [17] | High | E6 |
| OP-3 | No documented backups or restore drill for SQLite files, Markdown memory and receipt artifacts. [17] | High | E6 |
| OP-4 | **A private SSH key is readable in the public repository's history** (commit `c62e50d1`, reachable from `origin/main` and 171 refs), although `INCIDENT_RESPONSE_2026-09-28.md` records the history as purged. Revocation of that key and rotation of the API keys it lists are unproven. `.env` is the only secret store. [16] | **Critical** | Founder actions now (revoke; do not rely on a history rewrite), then E6 |
| OP-5 | 39 open Dependabot alerts (19 high, 19 moderate, 1 low) on the default branch. [16] | Medium | E0 (triage) |
| OP-6 | Docs drift from code: AGENTS.md records `update_config` validation as shipped (false until #302), describes Think Token integration points that are not wired, and `docs/known-defects.md` is dated 2026-09-19. | Medium | Each phase updates its docs (AGENTS.md section 4.3) |

## Agents

| ID | Gap | Sev | Closes in |
|---|---|---|---|
| AG-1 | Web agent profiles are two hardcoded entries (`hermes`, `asclepius`) with tool allow-lists; the default worker has full tool access. There is no registry and no per-agent capability grant at the web layer. [1] | High | E5 |
| AG-2 | Think Token code is unwired, its panel simulates events, and the tokens themselves are not persisted anywhere (only patterns, sessions and thought text are). [13] | Medium | E5, only if the founder decides to wire it (ADR 028, D7); default off |
| AG-3 | Routing choice and "tokens saved" are asserted by the client and stored unvalidated, so the savings metric can be spoofed. [10] | Medium | E5 |
| AG-4 | `state_save` persists arbitrary client objects; `run_goal` passes client `model` and `routeTelemetry` through. [1] | Medium | E3 (input validation pass with the permission matrix) |

## Data

| ID | Gap | Sev | Closes in |
|---|---|---|---|
| DT-1 | State is spread across several stores (Markdown memory, a run-history JSON file, SQLite databases, receipt artifacts) with no migration framework or retention policy. [9] | Medium | E1 (migrations for governance and audit tables), E4 |
| DT-2 | `apps/web/learning.db` is created by `new LearningStore()` and is not gitignored. [13] | Medium | E5 (or a one-line `.gitignore` change earlier) |
| DT-3 | **Postgres stays gated** at issue #9 and ADR 026: "Phase 3+ if scale demands it". This arc stays on SQLite. The plan adds measurable reopen criteria (ADR 027) so the gate is testable instead of a feeling. A request for a Neon database for Think Tokens is analyzed in ADR 028 (recommendation: SQLite now). | n/a | Gate, not a phase |

## Top five, ranked

1. **No human identity anywhere** (ID-1, ID-2): no login, and one shared governance identity.
2. **No durable, attributable audit trail** (GV-1, GV-2, AU-1 to AU-3): governance state is in memory, the signature is decorative, the dashboard "audit log" is browser-local.
3. **Worker execution and secrets hygiene** (EX-1, EX-2, EX-4, OP-4): root SSH, unpinned host key, no firewall, and a private key still readable in public history with revocation unproven. OP-4 is the most urgent item in this document and does not wait for any phase.
4. **CI cannot go green** (OP-1): nothing can be verified by machine before merge.
5. **No tenancy, RBAC or second-approver model** (TN-1, GV-5): the structure an enterprise needs does not exist yet.
