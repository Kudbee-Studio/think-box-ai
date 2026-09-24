# Environmental variables matrix (PR #200)

Hermetic reference for how THINK BOX loads and validates environment variables. **No live credentials** — use placeholders from `.env.example` and cassettes under `data/env_vars/cassettes/`.

## Four-state honesty

| Field | Value |
|-------|--------|
| `live_verified` | `false` |
| `live_api_called` | `false` |
| `four_state_max` | `TEST_VERIFIED` |

## Profiles

| Profile | Detection | Notes |
|---------|-----------|--------|
| `ci` | `CI=true` | Minimal hermetic environ via `thinkbox.env_vars.ci_matrix` |
| `hermetic` | `THINKBOX_KILO_HERMETIC_MODE=true` | Loopback-only provider expectations (#142 matrix) |
| `test` | `PYTEST_CURRENT_TEST` set | Unit test runs |
| `dev` | default | Local development |

## Schema groups

- **Substrate:** `UPSTASH_PUBLIC_BOX_URL`, `UPSTASH_PUBLIC_BOX_TOKEN`, `THINKBOX_UPCLOUD_API_TOKEN`
- **Governance:** `THINKBOX_SWARM_LIVE_ACK`, `THINKBOX_GOVERNANCE_TOKEN`, `THINKBOX_KILO_CLAIM_LIVE`
- **Cloud execution:** `THINKBOX_CLOUD_EXEC_*` (worker id, concurrency, hermetic flag)
- **Provider:** `THINKBOX_DEFAULT_PROVIDER`, OpenAI-compat URL/key, `INCEPTION_API_KEY`
- **Think Job / spine:** `THINKBOX_API_KEY`, `THINKBOX_LOG_LEVEL`, `THINKBOX_KILO_HERMETIC_MODE`

## Hermetic cassettes

| Cassette | Purpose |
|----------|---------|
| `valid_minimal.json` | CI-safe minimal worker config |
| `missing_required.json` | Optional-only substrate (fail-closed parse still OK) |
| `malformed_int.json` | Invalid integer for `THINKBOX_CLOUD_EXEC_MAX_ACTIVE_JOBS` |

## Verify

```bash
python3 scripts/verify_kilo_pr200_environmental_variables.py
python3 -m unittest tests.unit.test_env_vars tests.unit.test_kilo_live_proof_readiness_pr200 -v
```

## Related

- PR #142 `thinkbox/kilo_env_matrix.py` — Live-proof readiness contracts
- PR #199 cloud execution worker — upstream gate for PR #200
