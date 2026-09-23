# ADR 021: Receipt-chain / END_LINK era audit close (PR #162)

**Date:** 2026-09-23
**Status:** Accepted

## Context

PR #154–#161 shipped the control-plane receipt-chain and END_LINK stack. PR #160
indexed #155–#159 only. Operators needed a single honesty pack through #161.

## Decision

Add `docs/audit/passes/2026-09-23-pr154-161-era-consolidated.json` and gate
`receipt-chain-end-link-era-close` (PR #162) layered on `end-link-api-ops-harden`.

## Consequences

- Prior partial era pack (#155–#159) remains historical; full era pack supersedes for review.
- Four-state stays TEST_VERIFIED; no Live proof claims.
