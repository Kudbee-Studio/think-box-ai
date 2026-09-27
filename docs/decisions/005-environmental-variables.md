# ADR 005: Environmental variables pack (PR #200)

**Date:** 2026-09-24  
**Status:** Accepted

## Context

THINK BOX / KUDBEE reads dozens of environment variables across substrate, governance, providers, cloud execution, and Think Job surfaces. Operators need fail-closed parsing, redaction in logs/receipts, and hermetic CI matrices without live secrets.

## Options Considered

1. Extend `kilo_env_matrix` only (PR #142) — contract matrix without typed parse/redaction hub.
2. New `thinkbox/env_vars` pack with schema, parse, redaction, cassettes, and bridge to #142 matrix.

## Decision

We chose option 2: a single-theme PR #200 pack (`thinkbox/env_vars`, gate `environmental-variables`) that composes with `kilo_env_matrix` via `matrix_bridge`, documents dev/test/CI profiles, and caps honesty at **TEST_VERIFIED** (`live_verified: false`).

## Consequences

- Hermetic gate `scripts/verify_kilo_pr200_environmental_variables.py` and audit pass `docs/audit/passes/2026-09-24-pr200.json`.
- Cassettes under `data/env_vars/cassettes/` for valid, missing, and malformed fixtures.
- Upstream chain requires PR #199 cloud-execution worker orchestrator manifest valid.
