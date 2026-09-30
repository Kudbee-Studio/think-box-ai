# Enterprise Agent OS — Roadmap (E0 to E6)

**Status:** Proposed, part of the enterprise plan in [`README.md`](README.md). **Nothing here is started.**
E0 begins only after the founder approves this plan.

## How to read this

- Each phase is split into **small, reviewable PRs** (`E0.1`, `E0.2`, ...). Each PR follows the repo
  workflow: branch, draft PR first, red tests before green, security sweep on the diff, docs updated in the
  same PR (AGENTS.md sections 4.3 and 6.4), one PR at a time unless the founder grants an exception.
- Each phase ends with a **four-state target**. Only the founder marks PRODUCTION READY.
- Gap IDs (`ID-1`, `GV-2`, ...) refer to [`gap-analysis.md`](gap-analysis.md); baseline rows to [`baseline.md`](baseline.md).
- Acceptance criteria are written as tests that can fail. A criterion that cannot fail is not a criterion.

## Order, and why

```
E0  CI + login + per-user identity        closes ID-1 ID-2 ID-3(part) ID-4 OP-1 OP-5
E1  durable governance store + audit log  closes GV-1 GV-2 GV-3(part) GV-4 AU-1..AU-4 DT-1
E2  SSH hardening (non-root, pinned key)  closes EX-1 EX-2 EX-4         (founder-gated; parallel with E1)
E3  RBAC + approvals                      closes ID-3 GV-3 GV-5 AG-4
E4  tenancy                               closes TN-1 TN-2 TN-3
E5  agent + worker registry, Think Token  closes AG-1 AG-2 AG-3 EX-3 DT-2
E6  deploy (HTTPS, backups, secrets)      closes OP-2 OP-3 OP-4
```

The required security-first order is kept. Why each step sits where it does:

- **E0 first.** Every later phase needs a person to attribute actions to (E1), a role to check (E3) and a
  tenant to scope to (E4). CI comes first because nothing else can be merged with machine verification until
  `web-typecheck` passes and tests are bounded.
- **E1 before E3.** Role changes and approvals must be auditable, and approval requests need a durable store.
- **E3 before E4.** Tenant isolation needs a permission model to scope; building RBAC first keeps each PR small.
- **E4 before E5.** Think Token spreads learning across workers (AGENTS.md section 1.3a). It must be tenant-scoped
  before it is wired, and registries need an owning tenant.
- **E6 last.** Deployment exposes everything above, so it is the final step. The risk is late integration
  surprises; mitigation is a loopback smoke script (`scripts/enterprise_smoke.py`) that runs in CI from E0 and
  grows every phase, so there is always an end-to-end check before there is a deployment.

**Two changes to the requested order, both small:**

1. **E0.1 is split out as an explicit prerequisite** (restore CI). It is already in flight as PRs #298, #299, #300
   and #302, so it adds no new work; it just makes the dependency visible.
2. **E2 may run in parallel with E1.** They share no code. E2's critical path is founder infrastructure work
   (create a non-root user, collect the host key, firewall), and root SSH is the only real-host exposure today,
   so it should not wait behind E1.

Non-PR **founder actions** for OP-4 (revoke the compromised UpCloud key, rotate Inception and Upstash Vector keys,
decide on the history purge) should happen before E0 completes; they are listed under
[Founder actions](#founder-actions-not-prs).

---

## E0 — CI, dashboard login, per-user identity (fully specified)

**Goal:** a person must sign in, every governed action is attributed to that person, and CI can say
whether a change is safe to merge.

**Four-state target:** CODE yes, TEST yes (all acceptance tests green in CI), LIVE yes (real browser, loopback),
PRODUCTION READY no (HTTPS and deployment are E6).

### E0.1 — Restore CI (prerequisite; already in flight)

**Scope.** Merge #300 (12 type errors), #302 (`update_config` validation, per-test timeout, `timeout-minutes` on
`web-typecheck`), #298 (terminal scroll), #299 (PR workflow template). Then one small PR for the Python job:
add `timeout-minutes` to `unit-and-integration` and move the slow network-backoff tests to a scheduled or
manual job so the required set stays fast (decision D5). Pushing workflow files needs a token with the
`workflow` scope.

**Acceptance.**
1. On `main`, `web-typecheck` is green: `npm run typecheck` reports 0 errors and `npm test` passes with no hung test.
2. A deliberately introduced type error in a scratch PR turns `web-typecheck` red (shown once, then the PR is closed).
3. `unit-and-integration` has a `timeout-minutes` and the required check set finishes in a measured time
   (target: under 20 minutes, to be set from the first measurements).
4. The founder enables branch protection with those checks required (not something a PR can do).

### E0.2 — Authentication core (server)

**Scope.** Restore the design deleted in #289 (`82165813`; recoverable from `82165813^` and `3cf9ffff`:
`apps/web/auth.ts`, `scripts/hash-password.ts`, `tests/auth.test.ts`) and change it from one env-configured user to a
`users` table. Password hashing uses `node:crypto` scrypt (no new dependency, per CLAUDE.md).

- SQLite tables: `users` (id, username, password_hash, role, disabled_at, created_at) and `sessions`
  (id hash, user_id, created_at, last_seen, expires_at, revoked_at). `role` is stored now (`owner`, `operator`,
  `viewer`) and enforced in E3.
- Cookie `kudbee_sid`: HttpOnly, SameSite=Strict, `Secure` when `KUDBEE_COOKIE_SECURE=1`; session id rotates at
  login; idle expiry 30 minutes, absolute 12 hours; logout revokes server-side; sessions survive a restart.
- Login/logout require the `X-Kudbee-Client: dashboard` header (login-CSRF guard); 5 failures per client address
  lock out for 15 minutes (429); responses never reveal whether the username or the password was wrong.
- **Default deny:** every `/api/*` route and the WebSocket upgrade need a valid session, except `/api/health`
  (returns only `{status, ready}` when unauthenticated) and `/api/auth/login|logout|me`.
- First-run bootstrap: `scripts/create-user.ts` reads the password from stdin (minimum 12 characters), creates the
  first `owner`. Until a user exists, login and every protected route return 503 (fail closed). No default password.
- Auth events are emitted to the server log in a structured form now; E1 persists them.

**Acceptance (all must be able to fail).**
1. A table-driven test over **every registered route** (enumerated from the server, not hand-listed) returns 401
   without a session, except the exceptions above. A new unmapped route makes the test fail.
2. The WebSocket upgrade without a session is refused with 401 before a session object is created.
3. Login: correct credentials succeed and rotate the session id; wrong password and unknown user return the same
   response; the 6th failure within the window returns 429; a locked client is refused even with the right password.
4. Sessions: idle and absolute expiry enforced (fake clock); logout revokes; a restart keeps a live session.
5. Passwords: stored only as scrypt hashes; no log line, response or error contains a password or hash (grep test).
6. CSRF: login without `X-Kudbee-Client` is refused; cookie flags asserted exactly.
7. Bootstrap: no user means 503 everywhere; the script creates an owner; a password under 12 characters is refused.
8. The existing real-server suites (lockdown, file confinement, governed bridge) still pass, now using a
   test helper that signs in.

### E0.3 — Login UI and CLI sign-in

**Scope.** A sign-in dialog that gates the dashboard (no panel data is fetched before sign-in), a current-user
indicator, `/login`, `/logout`, `/whoami`, and sign-in for the `kudbee` CLI (password from `KUDBEE_DASHBOARD_PASSWORD`
or a hidden prompt).

**Acceptance.**
1. Headless Chrome at 1440 and 390 px: the page shows the sign-in gate and issues no authenticated API call
   before sign-in; after sign-in `/whoami` shows the user; logout returns to the gate; 0 console errors.
2. The dialog and user menu scroll and fit at 390 px (every window scrolls).
3. The CLI signs in and runs a command; with a wrong password it exits non-zero.
4. A static UI guard test (like `dashboard-ui.test.ts`) fails if a panel script fetches before the gate clears.

### E0.4 — Per-user governance identity

**Scope.** Replace the shared `web-dashboard-agent`. The web tier, after authenticating the user, asks the backend
for an admission token for `user:<id>`. The capability stays `shell:upcloud-ssh:readonly` for every user until E3
maps roles to capabilities. Identity is never taken from the client. The backend trusts the web tier's assertion
because the web tier authenticates with the backend API key (trust boundary documented in ADR 027).

- Backend: `issue_web_admission_token(user_id)`; validate the id format; register the identity on first use; record
  `on_behalf_of` in ledger metadata.
- Disabling a user revokes outstanding tokens (`revoke_for_agent`) and blocks new ones.

**Acceptance.**
1. Two users each run `/remote hostname` against a fake worker: the two receipts and ledger rows carry different
   `agent_id` values (`user:<a>`, `user:<b>`).
2. A request body containing `agent_id` or `capability` is ignored (test sends hostile values).
3. A disabled user cannot obtain a token and a token issued before disabling is refused.
4. A token issued to user A is refused when presented for user B's run.
5. A malformed or oversized user id is rejected at the backend boundary.
6. Live (founder-approved, contacts worker-02): one command from each of two users produces two receipts with
   distinct identities. Without that approval the phase closes at TEST VERIFIED for this slice and says so.

**Out of scope for E0:** role enforcement (E3), tenants (E4), SSO, password reset email, MFA, HTTPS (E6), multi-node sessions.

---

## E1 — Durable governance store and audit log

**Goal:** governance state survives restarts and every security-relevant event leaves a tamper-evident record.
**Target:** CODE yes, TEST yes, LIVE yes for E1.4, PROD no.

- **E1.1 Durable governance store.** SQLite tables for identities, tokens (store a hash, never the raw token),
  revocations and policy versions, with numbered migrations (first use of a migration framework). The signing key
  is required at startup and the process fails closed without it (no hardcoded fallback). Token verification
  checks the stored record and the signature.
  *Acceptance:* a restart keeps identities and revocations; a token with an edited payload is rejected even if its
  hash is known; startup without a key fails; expired and revoked tokens are refused; migrations run forward on an
  empty and on an existing database.
- **E1.2 Server-side audit log.** Append-only `audit_log` (UPDATE and DELETE rejected by triggers) with a per-row hash
  chain and a signature whose key lives outside the database. Event catalog: login, failed login, lockout, logout,
  user create/disable/role change, config change, approval, plugin execution, governed run (with its receipt id).
  The dashboard audit panel reads this log; the browser `localStorage` log is relabeled "client events".
  *Acceptance:* every cataloged event type produces a row (table test); an UPDATE or DELETE fails; editing a row
  breaks verification; the chain survives a restart.
- **E1.3 Signed export and verifier.** `scripts/export_audit.py` writes JSONL plus a signed manifest;
  `scripts/verify_audit_export.py` verifies it offline. Receipts are signed the same way (decision D2: HMAC now, or
  Ed25519 with an ADR because Python's standard library has no Ed25519).
  *Acceptance:* export then verify passes; changing one byte fails; a redaction test proves no token, password or
  key appears in an export.
- **E1.4 Committed proof bundle.** A redacted bundle for one real worker-02 run by a named user, with the verifier.
  Needs a founder-approved live run.

## E2 — SSH hardening (founder-gated; parallel with E1)

**Goal:** the only real-host path cannot run as root and cannot be silently redirected.
**Target:** CODE yes, TEST yes, LIVE yes (founder-approved), PROD no.

- **E2.0 Founder infrastructure actions** (not a PR): create a non-root, no-sudo user on worker-02 with a restricted
  key, set `PermitRootLogin no`, add an SSH-only firewall, record the host key fingerprint, revoke the old key.
- **E2.1 Code.** Refuse `root` (`ssh_user_root_refused`) and require `UPCLOUD_SSH_USER` explicitly; replace
  `StrictHostKeyChecking=accept-new` with `yes` plus a known-hosts file or a pinned fingerprint; fail closed if the
  pin is missing; a mismatch becomes a typed `SSH_FAILED` with the reason.
  *Acceptance:* unit tests on the built `ssh` argv (no `accept-new`; `yes`; known-hosts present); root refused; missing
  pin refuses to connect.
- **E2.2 Live check** (founder-approved): `hostname` as the non-root user succeeds; a wrong pin is refused; a root
  login attempt fails.

## E3 — RBAC and approvals

**Goal:** a role decides what a person can do, and high-risk actions need a second person.
**Target:** CODE yes, TEST yes, LIVE yes (loopback browser), PROD no.

- **E3.1 RBAC core.** Roles `owner`, `operator`, `viewer`. A permission matrix as data (every route and WebSocket
  message type against every role), default deny, enforced centrally. Role-to-capability mapping for governance
  tokens (viewer: none). Owner-only user management. Also closes AG-4: validate `state_save` (shape and size) and
  the `run_goal` `model` and `routeTelemetry` fields.
  *Acceptance:* a test over every route and message type times every role fails when one is unmapped; viewer gets 403
  on every mutating route; operator cannot manage users; owner can.
- **E3.2 Approvals v2.** Approval requests persisted in SQLite, risk tiers from the capability catalog, a second
  approver who is not the requester for high-risk tiers, timeouts, audit events, and a queue in the dashboard.
  *Acceptance:* the requester cannot approve their own high-risk request; a request survives a restart; an expired
  request cannot be approved; every decision is audited.
- **E3.3 Per-principal backend keys.** Named API keys with hashes, rotation and revocation; constant-time compare
  (also for the control-plane bearer). *Acceptance:* a revoked key is refused; comparison helper is used everywhere.

## E4 — Tenancy

**Goal:** one deployment serves several organizations with no cross-reading.
**Target:** CODE yes, TEST yes, LIVE yes (loopback, two tenants), PROD no.

- **E4.1 Tenant model.** `tenants` table, `tenant_id` on users, sessions, runs, memory, receipts, ledger and audit;
  existing data migrates to a `default` tenant. A repository layer that requires a tenant context, so application
  code has no tenant-less queries. (SQLite and a `tenant_id` column; see ADR 027 for why not database-per-tenant.)
- **E4.2 Isolation.** Per-tenant workspace root, memory directory and Upstash namespace, budgets and rate limits,
  governance identity `tenant:<t>/user:<u>`, a ledger chain per tenant.
- **E4.3 Isolation test suite.** A tenant-A user cannot read, list, delete or replay anything of tenant B: files,
  memory, runs, receipts, audit, agents, tokens. *Acceptance:* a table test over every route with cross-tenant ids
  returns 404 (not 403, so existence does not leak); a cross-tenant token or `agent_id` replay is refused.

## E5 — Agent registry, worker registry, Think Token

**Goal:** agents and workers are data with owners and grants, and learning is real and scoped.
**Target:** CODE yes, TEST yes, LIVE yes (loopback), PROD no.

- **E5.1 Agent registry.** A table replaces the hardcoded `AGENT_PROFILES`; per-agent capability grants enforced at
  admission; `GET /api/agents` reads the registry. *Acceptance:* an agent without the grant is denied; the default
  worker's tool list is data, not code.
- **E5.2 Worker registry.** Hosts, pinned host keys and allowed policy ids per worker replace `UPCLOUD_SERVER_IP`.
  *Acceptance:* an unregistered worker is refused; a policy not allowed for that worker is refused.
- **E5.3 Think Token wiring, default off (only if decision D7 says to wire; ROADMAP.md Phase 3 item 5 keeps this open because it
  changes agent prompts).** Persistence is SQLite behind a `TokenStore` interface (ADR 028); Think Tokens are not persisted
  anywhere today, so this adds a `think_tokens` table. Wire `ServerLearningIntegration` into `AgentSession` behind a
  per-tenant setting; remove the mock-event emitter; the store is tenant-scoped; routing telemetry is computed
  server-side (closes AG-3); `learning.db` gets a configurable, gitignored path.
  *Acceptance:* with the setting off, no Think Token code runs (spy test); on, tokens come only from a real
  (mock-provider) run transcript; nothing propagates across tenants; the panel shows stored data, not simulated data.

## E6 — Deploy (HTTPS, backups, secrets)

**Goal:** a reachable, backed-up, TLS-terminated deployment with a proven restore.
**Target:** CODE yes, TEST yes, LIVE yes (staging), **PRODUCTION READY only on founder sign-off.**

- **E6.1 Deploy target and HTTPS.** Choose the target (decision D7). TLS through the existing `nginx.conf` with
  operator-supplied certificates; `KUDBEE_COOKIE_SECURE=1`; trusted-proxy handling; a non-loopback bind is allowed
  only when TLS termination is configured, and otherwise fails closed. Automatic certificates through ACME would
  be an external-service dependency and needs its own accepted ADR (CLAUDE.md).
- **E6.2 Backups and restore drill.** SQLite online backup, memory directory and receipt artifacts on a schedule,
  with a hermetic restore test in CI.
- **E6.3 Secrets.** No `.env` in production; secrets from the host's credential mechanism; rotation runbook; a
  secret scan in CI.
- **E6.4 Runbook and smoke.** Extend `scripts/enterprise_smoke.py` to a staging run: HTTPS login, governed run,
  receipt verify, audit export verify, restore drill.

---

## Founder actions (not PRs)

These need your credentials or authority, not code review:

1. Refresh the `gh` token with the `workflow` scope (needed to push workflow files, including #302's last commit).
2. **Do this first, before any phase.** Revoke the exposed UpCloud SSH key (ED25519, fingerprint
   `SHA256:makvGnTYVYSackBcxfGD/QGCV/rLvryYpWy39HK/1GQ`) and remove it from every server's `authorized_keys`; rotate
   `INCEPTION_API_KEY`, `UPSTASH_VECTOR_REST_TOKEN` and `CURSOR_API_KEY`. The private key is still readable in public
   history (see baseline row 16), so a purge does not undo the exposure; revocation does. Then decide whether to
   redo the history purge (a force-push that rewrites every branch; destructive and coordinated). Update
   `INCIDENT_RESPONSE_2026-09-28.md`, which currently says the purge is complete.
3. Create the non-root user and firewall on worker-02 (E2.0); decide what to do with the orphan server and worker-01.
4. Turn on branch protection with the required checks from E0.1.
5. Approve each live run that contacts worker-02 or any external service (E0.4, E1.4, E2.2).

## Risks

| Risk | Mitigation |
|---|---|
| Login without HTTPS sends credentials in clear if someone exposes the port | The server keeps refusing non-loopback binds until E6; `Secure` cookies are supported from E0. |
| The web tier is a single point of trust for user identity | Documented in ADR 027; E3.3 adds per-principal backend keys; E1 audit records which key asserted which user. |
| Late deployment hides integration problems | The loopback smoke script grows with each phase. |
| SQLite write contention as audit and governance writes grow | Reopen criteria for Postgres are defined in ADR 027, not assumed. |
| Founder-gated steps (E2, live runs) stall the roadmap | E2 is parallel with E1; every live step has a TEST VERIFIED fallback that is labeled as such. |
