# KILO live smoke evidence fixtures (PR #152)

Hermetic JSON fixtures for `thinkbox.kilo_live_smoke_evidence.validate_smoke_evidence_document`.

- `valid_*` — must pass validation (hermetic; `live_verified: false`).
- `invalid_*` — must fail validation (negative tests).

No secrets. No `live_api_called: true` in default CI path.
