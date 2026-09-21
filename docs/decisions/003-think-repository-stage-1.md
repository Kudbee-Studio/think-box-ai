# ADR 003: Think Repository Stage 1 — Git worktree metadata layer

**Date:** 2026-09-21
**Status:** Accepted

## Context

KUDBEE's primary object is the Think Workspace / Think Box, not the Git
repository. Git is one underlying mechanism. Stage 1 proves that an
agent session can disappear while the repository/workspace persists by
making worktree identity, Git state, ephemeral session attachment, and
checkpoints first-class metadata above Git.

The repository stack already has `thinkbox/workspace.py` for Think Box
binding and `thinkbox/git_engine.py` for Git execution. Stage 1 adds a
thin metadata layer that owns worktree identity without replacing Git.

## Decision

Build a `thinkbox.repository` module with:

- `Worktree`: identity, path, Git state, session/job attachment, timestamps.
- `Repository`: a metadata-backed facade over one Git worktree.
- `Repository` persists metadata as `.thinkbox/repository.json` inside the
  worktree. Checkpoints persist as `.thinkbox/checkpoints/<id>.json`.
- Ephemeral sessions attach/detach to a worktree. A session is not stored
  by the repository; only its ID is recorded as attachment state.
- Git state (branch, HEAD, dirty) is read from the existing `GitEngine`,
  not duplicated.

Stage 1 intentionally does **not**:

- Implement jobs, receipts, or provenance (Stage 2).
- Implement distributed storage, authentication, multi-tenant isolation, UI,
  or a Git replacement (Stage 3/4).
- Persist session state itself (sessions remain ephemeral; worktrees persist).

## Consequences

- `Repository` becomes the canonical object for "this is the current agent
  worktree and its Git state".
- Existing Git workflows are unchanged; `.thinkbox/` metadata is additive.
- Future stages can attach jobs/receipts to `Worktree` records without
  changing Stage 1 fields.
- Tests can run against temporary Git worktrees and mocked `GitEngine`
  instances. No network is required.
