# End-to-end tests (Phase 1 placeholder)

The Phase 1 architecture calls for mock-provider e2e coverage under `tests/e2e/`. This directory is intentionally minimal until a hermetic full runtime loop test lands (see audit finding **F009** / **F023** in `docs/audit/passes/2026-09-22-pr125.json`).

**Target shape (not yet implemented):**

- Mock `ModelProvider` (no network)
- Single agent, five tools, governed tool execution
- Assert AdmissionGate + ActionLedger entries

**Gate today:** `python3 -m unittest discover tests/` (unit + integration only).
