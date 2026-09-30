# Enterprise KUDBEE Agent OS — plan

**Status:** Proposed (docs only). **As of:** `main` @ `71027021`, 2026-09-30. Nothing in this folder is implemented;
E0 starts when the founder approves the plan. No code, infrastructure, UpCloud host, Neon resource or external service was
touched to produce it.

| Document | What it is |
|---|---|
| [`baseline.md`](baseline.md) | Four-state table for every existing component, with evidence and dated measurements |
| [`gap-analysis.md`](gap-analysis.md) | What is missing, per pillar, with severity and the phase that closes each gap |
| [`roadmap.md`](roadmap.md) | Phases E0 to E6 as small PRs with acceptance tests; E0 fully specified |
| [`../decisions/027-enterprise-agent-os-architecture.md`](../decisions/027-enterprise-agent-os-architecture.md) | ADR 027 (Proposed): options, design rules, non-goals, reopen criteria |
| [`../decisions/028-think-token-persistence.md`](../decisions/028-think-token-persistence.md) | ADR 028 (Proposed): where Think Token state lives, and what a Neon database would need first |

## Do this first (not a phase)

**A private SSH key is readable in the public repository's history** (`c62e50d1`, reachable from `origin/main` and 171
refs), although `INCIDENT_RESPONSE_2026-09-28.md` says the history was purged. Revoke it on UpCloud and remove it from every
server's `authorized_keys` (ED25519, fingerprint `SHA256:makvGnTYVYSackBcxfGD/QGCV/rLvryYpWy39HK/1GQ`), and rotate the
API keys that record lists. Details: [baseline row 16](baseline.md#16-secrets-and-key-hygiene).

## Glossary: three different things called "Think Token"

| Name | What it is | Where |
|---|---|---|
| **Think Token** (#288) | A learning unit: a structured, reusable piece of agent experience with a confidence score | `apps/web/think-token*.ts`, AGENTS.md section 1.3a |
| **THNK** | An economic token: staking, rewards, governance votes, pay-for-compute; a planning draft plus in-memory Phase 9 classes (unit-tested; no persistence and no production caller) | `THINK_TOKEN_STRATEGY.md`, `think_box_ai/token.py`, `thinkbox/economy.py` |
| `ThinkToken` (Python class) | A 36-line balance/transfer class for THNK | `think_box_ai/token.py` |

This plan is about the first. THNK is out of scope and must never be an authorization input (ADR 027 non-goals).

## Top five gaps

1. **No human identity.** No login, and one shared governance identity, so receipts cannot say who acted (ID-1, ID-2).
2. **No durable, attributable audit trail.** Governance state is in memory, the token signature is never checked, and the
   dashboard's "audit log" is browser `localStorage` (GV-1, GV-2, AU-1 to AU-3).
3. **Worker execution and secrets.** Root SSH, unpinned host key, no firewall, and the exposed private key above (EX-1,
   EX-2, EX-4, OP-4).
4. **CI cannot go green.** 12 type errors, a hung test, and an unbounded multi-hour Python job (OP-1).
5. **No tenancy, roles or second approver** (TN-1, GV-5).

## E0 in one screen

CI restored (PRs #298, #299, #300, #302 plus a bounded Python job), then: authentication core with a `users` table and
server-side sessions, default-deny on every route and the WebSocket (E0.2); login UI and CLI sign-in (E0.3); per-user
governance identity replacing the shared `web-dashboard-agent` (E0.4). Acceptance tests are listed in
[`roadmap.md`](roadmap.md#e0--ci-dashboard-login-per-user-identity-fully-specified).

## Decisions needed (real ones, each with a recommended default)

If you approve the plan without comment, the defaults apply.

| # | Decision | Recommended default |
|---|---|---|
| D1 | Approve the order E0 to E6 and its two adjustments (CI split out; E2 parallel with E1) | Approve |
| D2 | Signing for receipts and audit: HMAC now, or Ed25519 (needs a Python dependency, so its own ADR) | HMAC now |
| D3 | The exposed key: revoke and rotate (required), and whether to redo the history purge (a destructive force-push) | Revoke and rotate now; redo the purge only if you want it, it does not undo the exposure |
| D4 | When to create the non-root user and firewall on worker-02; what to do with the orphan server and worker-01 | Before E2.2 |
| D5 | Python CI: bound it and move the slow network-backoff tests to a scheduled job; which checks are required; refresh the `gh` token with the `workflow` scope | Bound and split |
| D6 | Login bootstrap: first-run owner created by a script, minimum 12 characters, no "auth off" switch | As stated |
| D7 | Wire Think Tokens into agent prompts at all (ROADMAP Phase 3 item 5), and whether a cloud database is wanted for them (ADR 028) | Not wired until E5; SQLite if wired |
| D8 | `CLAUDE.md` still says "PHP/SQLite only"; correct it to describe the Python and TypeScript runtime with SQLite | Fix in a small docs PR |

Merge order for the open PRs (#298, #299, #300, #302 and this one) is yours.

## Unproven (no evidence either way; not assumed)

- The Python `unit-and-integration` suite passing in CI (never seen to finish; 1861 tests passed locally on 2026-09-29).
- Revocation of the exposed UpCloud key and rotation of the API keys (above).
- Upstash Vector reachability now (the dashboard showed "Vector offline" on 2026-09-30).
- Worker-02 and Mercury-2 availability now (last verified 2026-09-29 and 2026-09-27; not contacted for this plan).
- The local Ollama route (needs `ollama pull qwen2.5:1.5b`).
- Git panel in a real browser (no LIVE evidence).
- Test coverage of the backend `AuthenticationMiddleware`, rate limiter and `audit_storage.py` (not audited here).
- Any backup or restore procedure (none found).

## Relationship to the other roadmaps

- `ROADMAP.md` (dashboard) Phase 3 items map to this plan: SSH hardening is E2, the committed proof bundle is E1.4, the
  Think Token decision is D7 and E5.3, the Git panel browser test is verification debt, and "dashboard authentication +
  HTTPS" is E0 and E6. Phase 4's RBAC, audit compliance, cost allocation and custom agent builder are E3, E1, E4 and E5.
  That file also has stale lines (it says CI is not running, and lists the lockdown as awaiting review although #290 and
  #292 are merged); correcting it is left to the documentation-organization PR so the two do not conflict.
- `docs/roadmap.md` is history up to 2026-09-23; its "Stage 7 Enterprise" checklist (JWT, per-user sessions, immutable
  audit trail, Docker) is superseded by this plan.
- `docs/roadmaps/kilo-post-170-pr-roadmap.md` is the KILO slot table; its one-implementation-PR-at-a-time rule is kept.

## Not in this PR

Any code, any workflow file, any change to `ROADMAP.md`, `THINK_TOKEN_STRATEGY.md` or other existing documents, and any
move of files (a separate PR organizes all Markdown files into folders with an index).
