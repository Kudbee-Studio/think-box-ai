# ADR 026: Neon serverless Postgres setup (PR #257) — revert

**Date:** 2026-09-30
**Status:** Accepted

## Context

On 2026-09-01, issue #9 ("Phase 2: PostgreSQL 19 + pgvector Migration") proposed
Postgres + pgvector to replace SQLite for vector search and multi-agent
coordination. It was built (PR #22: `core/memory/postgres_store.py` with an
asyncpg-backed store and SQLite fallback; PR body states "Full suite: 60/60 unit
tests passing" — verified directly against PR #22's own body, not secondhand;
note the PR itself says Docker/asyncpg weren't available in that sandbox, so the
60/60 exercised the SQLite fallback path, not a live Postgres connection). The
issue was then explicitly declined and closed the same day (2026-09-01T01:42:49Z):

> "## Status: DECLINED
>
> SQLite is intentional for Phase 1-2. Reasons:
> - Zero configuration
> - Single file, easy backup
> - FTS5 covers our search needs
> - No server to manage
>
> PostgreSQL migration may be considered in Phase 3+ if scale demands it.
>
> **Action:** Closing as declined for now."

25 days later, PR #257 (2026-09-26, `493b6ca6`) added Neon serverless Postgres
config (`@neon/config`, `@neon/env`, `neon.ts`, 28 generated skill files,
`skills-lock.json`) without referencing issue #9 anywhere in its commits or PR
body. Investigated for any motivation beyond "setup progress":

- No GitHub issue or discussion mentions Neon or a current/planned need for it.
- No code anywhere imports `neon.ts` or `@neon/*` (`git grep` across the full
  tree, before this revert, returned nothing but the file itself).
- The one thing #257 left undone (`neon link`, gated on `NEON_API_KEY`) was
  completed later not by any code or CI in this repo, but by a manual
  `npx neon@latest init` typed directly into a terminal (confirmed via shell
  history) — exploratory, not a project decision to proceed.

There is no stated technical trigger for Neon superseding SQLite, and the bar
issue #9 explicitly set for revisiting this ("Phase 3+ if scale demands it")
has no evidence of being met anywhere in the current record.

This also conflicts with `CLAUDE.md` (this repo, verified via `git grep` on
`main`):
- `CLAUDE.md:20` — "❌ External service dependencies (PHP/SQLite only)"
- `CLAUDE.md:83` — "**NO provider SDKs in runtime code.** Ever."

(The "PHP" half of the first line doesn't match this codebase, which is Python
and TypeScript — likely a stale detail from whatever this file was originally
templated from. That doesn't change what it says about external service
dependencies, but issue #9's explicit, dated, reasoned decision is the primary
basis for this ADR either way — the CLAUDE.md lines are corroborating, not
load-bearing on their own.)

## Options Considered

**A — Revert.** Remove `@neon/config`/`@neon/env`, `neon.ts`, the skills bundle,
`skills-lock.json`, and the root `package.json`/`package-lock.json` (which
existed only to hold the two Neon dependencies). Cost: trivial — confirmed by
`git grep` that nothing in the codebase imports or depends on any of it.

**B — Keep, supersede issue #9 via this ADR.** Would require overriding an
explicit, reasoned, closed decision with no new evidence — no code, no
discussion, no stated scale problem.

**C — Move to local, non-project config.** No demonstrated need to keep Neon
available anywhere right now — issue #9 already concluded FTS5 + SQLite covers
current search needs.

## Decision

**Option A: revert.** A specific, dated, reasoned prior decision (issue #9) is
directly on point, was never revisited with new evidence, and the thing built
on top of it (#257) is provably unused. Reverting costs nothing technical;
keeping it costs ongoing maintenance and attack surface (this repo currently
has 39 open Dependabot alerts — unused dependencies are pure downside here) for
zero current benefit. If a real Postgres/pgvector need emerges later, issue
#9's own criterion ("Phase 3+ if scale demands it") is the right gate to reopen
this, with a fresh ADR stating the actual trigger.

## Consequences

- Removed in this PR: `package.json`, `package-lock.json`, `neon.ts`,
  `skills-lock.json`, `.agents/skills/neon*` (8 skill directories, 27 files).
- Not touched: the `.gitignore` `.neon` line and the local `.neon` link file —
  both are uncommitted local state from a manual `npx neon@latest init` run
  outside this repo's process; the founder is handling those directly, along
  with any decision about the live Neon project (`long-union-70369403`).
- Not touched: `STATUS.md`, `docs/STATUS.md`, `docs/CONTINUITY.md` — their
  existing Neon-related entries are historical chronicle records of #257
  actually happening, kept append-only per this repo's own convention rather
  than edited to erase history.
- Issue #9 stays closed/declined, unchanged — this ADR reinforces it rather
  than reopening it.
