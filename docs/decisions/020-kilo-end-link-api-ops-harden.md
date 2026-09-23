# ADR 020: END LINK API / ops harden (PR #161)

**Date:** 2026-09-23
**Status:** Accepted

## Context

PR #158–#160 delivered END LINK deepen, operator UX, and docs/audit. Operators still
needed fail-closed API edges on chain filters, consistent `failure_code` values, and
observable ops metadata without live Mercury/Box calls.

## Options Considered

1. Extend PR #157 `control_plane_ops_harden` only
2. Add a dedicated PR #161 layer on the END LINK stack with hermetic gate

## Decision

We chose option 2: `thinkbox/end_link_api_ops_harden.py` plus `kilo_end_link_api_ops_harden`
gate layered on PR #160, wired into `backend/api/v1/control_plane.py` for validate,
batch, and chain list routes.

## Consequences

- Spine and CI gain `verify_kilo_end_link_api_ops_harden.py`
- Four-state remains TEST_VERIFIED; Live proof unchanged
