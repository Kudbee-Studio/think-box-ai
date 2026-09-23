# KILO proof-schema hermetic fixtures (PR #148)

JSON fixtures for `validate_proof_document` and `run_fixture_suite`.

- `valid_*.json` must validate without `_expect`.
- `invalid_*.json` include `"_expect": "invalid"` (stripped before validation).

No secrets or live API claims. Four-state capped at TEST_VERIFIED.
