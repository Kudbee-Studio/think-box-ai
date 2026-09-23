# KILO live-smoke operator fixtures (PR #153)

Hermetic operator-path fixtures for `thinkbox.kilo_live_smoke_operator.run_operator_fixture_suite`.

| Kind | Purpose |
|------|---------|
| `write_expect_ok` | Document must pass validation + disk write |
| `write_expect_fail` | Write must be refused (secrets / invalid shape) |
| `build_expect_fail` | `build_hermetic_smoke_evidence` must fail closed |

No live HTTP. Default documents keep `live_api_called: false`.
