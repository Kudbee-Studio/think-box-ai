# ADR 028: Where Think Token state lives (SQLite now; Neon only if a reopen criterion is met)

**Date:** 2026-09-30
**Status:** Proposed

## Context

On 2026-09-30 the founder asked for a Neon database to track Think Tokens. That request arrives hours after ADR 026
removed the unused Neon setup, and it is exactly the situation ADR 026 anticipated: "if a real Postgres/pgvector need
emerges later, a fresh ADR should state the actual trigger." This ADR records the facts and the choice so the decision is
explicit. **No Neon resource has been created, no credential used, and no `neon` command run for this ADR.**

**"Think Token" here means the learning unit from #288** (`apps/web/think-token*.ts`), not the THNK economic token in
`THINK_TOKEN_STRATEGY.md` and `think_box_ai/token.py`. They share a name and nothing else.

Facts, verified in the tree at `main` @ `71027021`:

- **Think Tokens are not persisted at all.** `ThinkTokenCollection` is an in-memory `Map`; `ThinkToken` has
  `toJSON`/`fromJSON` but nothing writes them. The existing SQLite file (`apps/web/learning.db`, `learning-store.ts`)
  holds `learned_patterns`, `session_learning` and `thought_artifacts`: patterns, session outcomes and thought text, not
  tokens. So a `think_tokens` table is missing whichever database is chosen.
- **The pipeline is not wired.** Nothing in `server.ts` or `agent.ts` imports it; `ServerLearningIntegration` has no
  callers; the dashboard's Learning panel emits mock events (`think-token-dashboard.js`). `ROADMAP.md` Phase 3 item 5 lists
  wiring as an **open founder decision** because it "changes agent prompts".
- **The data is sensitive.** A `session_learning` row stores the goal and the raw thought text
  (`thoughts[].content`) from agent runs, which can contain user data, file contents, URLs and credentials that appeared
  in a transcript.
- **Constraints.** `CLAUDE.md` accepts no external service dependency without an ADR; ADR 026 and issue #9 set the
  SQLite default with a "scale" gate; Actions and database usage are billed per use; the repository already carries 39
  Dependabot alerts.

## Options considered

**A. SQLite, add a `think_tokens` table (recommended).** Extend the existing store and the E1 migration framework with a
table for tokens (id, type, content, confidence, reuse and success counts, metadata, created and last-used times, and
`tenant_id` from E4). No new dependency, no egress, hermetic tests, same backup story as everything else. Limit: one node.

**B. Neon Postgres (requested).** Would be justified by a multi-host requirement, measured write contention, or vector
similarity retrieval (issue #9's original goal). Before it could be approved it needs all of:
1. an accepted ADR that supersedes ADR 026 for this use and amends `CLAUDE.md` (external service dependency);
2. a named reopen criterion from ADR 027 (none is met today: there is one process and no contention evidence);
3. a data policy: redact thought text before it leaves the host (store only token fields, never raw transcripts),
   tenant scoping, retention, region, TLS, and a decision on processor terms;
4. credentials: a `DATABASE_URL` held as a secret outside the repo, least-privilege role, rotation plan;
5. a cost ceiling, because Neon is usage-billed;
6. a failure mode (degrade to local storage, not stop agents);
7. a runtime dependency (`pg` or `@neondatabase/serverless`) and its Dependabot surface;
8. hermetic tests: no live database in CI.

**C. Hybrid.** SQLite is the system of record; a background job exports only redacted aggregates (token id, type,
confidence, counts, no text) to Neon for analytics. Smaller egress and reversible, but still needs items 1, 2, 4, 5, 7 of B.

## Decision (proposed)

**Option A now.** Add the `think_tokens` table with the wiring work (E5.3), behind the wiring decision below. Put access
behind a small `TokenStore` interface so a Postgres implementation could be added later without touching callers, and run
one shared test suite against every implementation. Reopen Neon only when a criterion in ADR 027 is measured. If the
founder chooses B or C regardless, the sequence is: accept this ADR with the chosen option and the data policy, amend
`CLAUDE.md` in its own PR, build the interface and migration, and only then provision (founder action).

**Needed from the founder:**
1. Do you want Think Tokens wired into `AgentSession` at all? (ROADMAP Phase 3 item 5; it changes agent prompts.) Until
   yes, there is nothing to track and the dashboard panel stays labeled as a simulation.
2. If Neon is wanted, which reopen criterion motivates it? (One line is enough; it goes in the ADR.)
3. The data policy: may thought text ever leave the host, and for which tenants?

## Consequences

- Nothing is provisioned and nothing external is touched by this ADR.
- The existing idle Neon project and the local `.neon` link file stay the founder's to handle.
- Persisting tokens is unblocked on SQLite immediately after the wiring decision.
- Choosing B or C later is a bounded change because of the `TokenStore` interface.

## Related

ADR 026, ADR 027, issue #9, `ROADMAP.md` Phase 3 item 5, `docs/enterprise/roadmap.md` (E5.3), AGENTS.md section 1.3a.
