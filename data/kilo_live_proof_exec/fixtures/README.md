# KILO live-proof-exec fixtures (PR #150)

Hermetic execution-plan JSON for `validate_execution_plan_document`.

| Band | Expectation |
|------|-------------|
| `valid_*.json` | Pass validation |
| `invalid_*.json` | Fail-closed |

No live network; `live_api_called` must be false in valid hermetic fixtures.
