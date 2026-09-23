# ADR 018: KILO END LINK operator UX deepen (PR #159)

**Date:** 2026-09-23  
**Status:** Accepted

## Context

PR #158 shipped hermetic END_LINK deepen: batch validate API, link integrity fields, chain filters on the server, and minimal dashboard batch wiring. Operators still need usable controls, batch result tables, and honest four-state copy on the receipt-chain dashboard.

## Options Considered

1. Re-open #158 API surface for more fields
2. Deepen dashboard/client UX only, layering a new gate on `end-link-deepen`

## Decision

Add PR #159 gate `end-link-operator-ux` with Python view-model helpers, dashboard bind extensions, static HTML/JS operator controls (status/evidence_label filters, batch summary table, integrity detail line), hermetic tests, and spine verify. No live Box/Mercury HTTP.

## Consequences

- Spine and CI run `verify_kilo_end_link_operator_ux.py` after `verify_kilo_end_link_deepen.py`.
- `live_verified` remains false until founder-run Live proof.
