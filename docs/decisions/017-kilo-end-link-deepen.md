# ADR 017: KILO END LINK / control-plane deepen (PR #158)

**Date:** 2026-09-23  
**Status:** Accepted

## Context

PR #154–#157 shipped control-plane HTTP, receipt-chain ETag, dashboard END_LINK bind, and API ops harden. Operators need richer END_LINK validate semantics (per-item failure codes, link integrity fields) and bulk validate without live Box/Mercury calls.

## Options Considered

1. New microservice for link validation
2. Deepen existing control-plane routes and hermetic gate on #157

## Decision

Extend proprietary **END_LINK** on the existing control-plane router: `POST /receipts/validate/batch`, integrity fields on single validate, and chain query filters (`status`, `evidence_label`). Hermetic gate `end-link-deepen` layers on `api-ops-harden`.

## Consequences

- Dashboard client gains batch validate helper; #156 UX preserved with additive fields.
- Spine and CI run `verify_kilo_end_link_deepen.py`.
- `live_verified` remains false until founder-run Live proof.
