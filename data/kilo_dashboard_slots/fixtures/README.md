# KILO dashboard-slots hermetic fixtures (PR #149)

- `valid_*.json` must pass `validate_slot_registry_document`.
- `invalid_*.json` must fail with at least one violation.

No live API calls; `live_api_called` must remain false in valid fixtures.
