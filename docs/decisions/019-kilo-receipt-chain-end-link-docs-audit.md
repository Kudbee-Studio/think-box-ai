# ADR 019: Receipt-chain / END_LINK docs + audit pack (PR #160)

**Date:** 2026-09-23
**Status:** Accepted

## Context

PR #155–#159 shipped receipt-chain/ETag deepen, dashboard bind, API/ops harden, END_LINK deepen, and operator UX. Operator and founder-facing honesty was spread across guides, audit passes, and spine gates. #160 consolidates that surface without new live HTTP.

## Options Considered

1. Leave docs as-is per-PR only
2. Single consolidated operator guide + era audit pack + hermetic gate (#160)

## Decision

Choose (2): gate id `receipt-chain-end-link-docs` layers on `end-link-operator-ux`, adds consolidated operator guide, era audit index for #155–#159, spine verify script, and `live_verified: false` / `live_api_called: false` throughout.

## Consequences

- AGENTS.md and STATUS docs mark #159 merged and #160 as docs+audit slice
- `scripts/verify_kilo_receipt_chain_end_link_docs.py` joins spine checklist
- No LIVE VERIFIED claims; no Box/Mercury smokes in CI for this PR
