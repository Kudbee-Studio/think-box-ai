# ADR 027: Enterprise Agent OS architecture

**Date:** 2026-09-30
**Status:** Proposed

## Context

The Agent OS is a local-only operator console today: one implicit user, no login, one fixed governance identity, governance
state in process memory, no tenant concept, and a worker reachable only over SSH as `root`. Enterprise use needs real users,
roles, tenants, durable and attributable audit, and a hardened execution path. The evidence is in
[`docs/enterprise/baseline.md`](../enterprise/baseline.md) and the gaps in
[`docs/enterprise/gap-analysis.md`](../enterprise/gap-analysis.md). The phased plan is in
[`docs/enterprise/roadmap.md`](../enterprise/roadmap.md).

Constraints already on record:

- `CLAUDE.md`: no provider SDKs in runtime code; no external service dependencies unless an ADR accepts them. (Its
  "PHP/SQLite only" wording predates the Python and TypeScript runtime; see the open docs fix in the plan README.)
- ADR 026 and issue #9: SQLite stays. Postgres is reconsidered only "if scale demands it", and this ADR defines what
  that means in measurable terms (below).
- AGENTS.md section 1: layer discipline, provider independence, governance by default, evidence over assumptions.

## Current shape and trust boundaries

```
Browser / kudbee CLI
   |  session cookie (E0)              trust boundary 1: human -> web tier
   v
Web tier (Express + WebSocket, apps/web)      authenticates users, enforces RBAC (E3), scopes by tenant (E4)
   |  shared API key (per-principal in E3.3) + server-asserted user id      trust boundary 2: web tier -> governance backend
   v
Governance backend (FastAPI)                  admission gate, token service, identity ledger, action ledger, receipts
   |  governed SSH, allow-listed read-only commands                          trust boundary 3: backend -> worker
   v
Worker (upcloud-ssh)
```

The web tier is trusted to assert which user is acting, because it authenticates to the backend with a key. That is the
single most important assumption in this design and the reason E3.3 (per-principal keys) and E1 (audit records which key
asserted which user) exist.

## Options considered

**A. Incremental hardening of the current two-tier architecture (recommended).** Keep the Express web tier and the FastAPI
governance backend, keep SQLite, single node. Add identity (E0), durable governance and audit (E1), SSH hardening (E2),
RBAC and approvals (E3), tenancy as a `tenant_id` column behind a repository layer (E4), registries (E5), and a TLS
deployment (E6). Each step is a small PR with tests and ships on its own.

**B. Consolidate into one runtime** (move governance into the web tier, or web concerns into Python). Removes a boundary,
but it is a rewrite of code that is currently live-verified end to end (dashboard to backend to worker), and it would
discard the audit and policy work already proven. Rejected for this arc.

**C. Adopt external identity and data services** (an external IdP, a managed Postgres, managed auth). Fastest to a login
screen, but it adds external service dependencies that `CLAUDE.md` and ADR 026 do not accept, moves credentials and
data off-host, and is not needed for a single-node deployment. Rejected for this arc. Revisit under the reopen criteria.

**D. Multi-node and Postgres now.** Premature: nothing in the baseline shows contention or a multi-host requirement.
Rejected; gated by the criteria below.

## Decision (proposed)

**Option A**, with these design rules:

1. **Default deny.** Every route and WebSocket message needs an authenticated user and a permission-matrix entry. A route
   with no entry fails a test, so new code cannot ship open by accident.
2. **Identity is asserted server-side, never by the client.** Governance identities are `user:<id>` (and later
   `tenant:<t>/user:<u>`); a client-supplied `agent_id`, `capability` or tenant is ignored.
3. **The server is the source of truth for audit.** The browser log is relabeled as client events. Audit rows are
   append-only, hash-chained and signed with a key held outside the database.
4. **Durable before clever.** Identities, tokens (stored as hashes), revocations and policy versions move to SQLite
   (E1) before approvals or tenancy depend on them. The signing key is required and the process fails closed without it.
5. **Tenancy is a column plus a repository layer**, not a database per tenant, so SQLite stays simple and every query
   path carries a tenant. A cross-tenant id returns 404, not 403.
6. **Live contact needs approval.** Any step that touches worker-02 or an external service is founder-approved and
   labeled LIVE VERIFIED only with real evidence; otherwise it is labeled TEST VERIFIED.
7. **No new external service or provider SDK in runtime code** without its own accepted ADR. In particular: signing with
   Ed25519 needs a Python dependency (decision D2), automatic certificates (ACME) are an external service, and a cloud
   database is covered by ADR 028.

## Non-goals for this arc

- SSO/SAML/OIDC, MFA, password-reset email.
- Postgres or any cloud database (see reopen criteria).
- Multi-node or high-availability deployment.
- Token-economy features as authorization input: the THNK economic token (see `THINK_TOKEN_STRATEGY.md`) must never
  decide who may do what. Access comes from roles, agent grants and tenant quotas.
- Fine-tuning or replacing the default model provider (AGENTS.md section 1.5 requires benchmarks first).
- Autonomous production writes beyond the read-only allow-list.

## Reopen criteria for Postgres (making the "scale" gate testable)

Reopen only when one is measured, not guessed. These starting values are proposals for the founder to set:

1. More than one server process or host must read and write the same governance, audit or token store.
2. Sustained SQLite write contention: `SQLITE_BUSY` errors or p95 write latency above an agreed budget under a real
   or replayed load, after WAL mode and batching are applied.
3. A retrieval need (for example vector similarity) that is shown, in a committed benchmark (`benchmarks/`), to be poorly
   served by SQLite FTS and the in-process BM25 index.
4. Data volume or tenant count beyond an agreed ceiling for one node's disk and backup window.

A reopen needs a new ADR that names the criterion, the data policy and the cost ceiling.

## Consequences

- Eight-plus small PRs over seven phases; the order is security-first and each phase leaves `main` deployable to loopback.
- The dashboard stays local-only until E6; login ships earlier so identity and audit are real before exposure.
- SQLite remains the system of record, which keeps tests hermetic and backups simple, and it caps scale at one node.
- The web tier is a single point of trust for user identity until per-principal keys and audit attribution land (E3.3, E1).
- Several dashboard panels that look complete today (approval workflows, execution logs, integrations, collaboration)
  are client-side demos; they are rewired to server data in E1 and E3 or removed, and labeled honestly meanwhile.

## Related

ADR 026 (Neon revert), ADR 028 (Think Token persistence), issue #9, `CLAUDE.md`, AGENTS.md sections 1 and 13.
