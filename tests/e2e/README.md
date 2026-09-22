# End-to-end tests (Phase 1 placeholder)

The Phase 1 architecture calls for mock-provider e2e coverage under `tests/e2e/`. **PR #126** adds a hermetic governed-runtime loop in `test_governed_runtime_loop.py` (no network). Full five-tool mock-provider loop remains **F023**.

**Target shape (not yet implemented):**

- Mock `ModelProvider` (no network)
- Single agent, five tools, governed tool execution
- Assert AdmissionGate + ActionLedger entries

**Gate today:** `python3 -m unittest discover tests/` (unit + integration only).
