# Kudbee SDK quickstart (PR #177)

**Primary surface:** Python package `thinkbox/kudbee_sdk/` and TypeScript `apps/web/sdk/` for the **kudbEE web app** (`apps/web`).

**Four-state cap:** CODE COMPLETE / TEST VERIFIED only — not LIVE VERIFIED.

## Hermetic verify

```bash
python3 -m unittest tests.unit.test_kudbee_sdk tests.unit.test_kilo_live_proof_readiness_pr177 -v
python3 scripts/verify_kilo_pr177_kudbee_sdk_app.py
python3 examples/kudbee_sdk_quickstart.py
python3 scripts/scan_doc_secrets.py
```

## PR #179 follow-up (draft)

After #177 merges, the follow-up lane adds `thinkbox/kudbee_sdk_followup/` and `apps/web/sdk/followup.ts`:

```bash
python3 -m unittest tests.unit.test_kudbee_sdk_followup_deepen tests.unit.test_kilo_live_proof_readiness_pr179 -v
python3 scripts/verify_kilo_pr179_kudbee_sdk_followup.py
python3 examples/kudbee_sdk_followup_quickstart.py
```

## Python

```python
from thinkbox.kudbee_sdk import load_config_from_env, KudbeeHttpClient
from thinkbox.kudbee_sdk.dry_run import build_dry_run_transport
from thinkbox.kudbee_sdk.health import fetch_health

config = load_config_from_env({"KUDBEE_SDK_DRY_RUN": "1"})
client = KudbeeHttpClient(config, build_dry_run_transport(config))
print(fetch_health(client))
```

## TypeScript (apps/web)

```typescript
import { loadConfigFromEnv, fetchHealth } from './sdk/index.ts';

const config = loadConfigFromEnv();
const health = await fetchHealth(config);
```

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `KUDBEE_SDK_BASE_URL` | `http://127.0.0.1:3000` | HTTP base for health/capabilities |
| `KUDBEE_SDK_WS_PATH` | `/ws` | WebSocket path |
| `KUDBEE_SDK_DRY_RUN` | off | Use in-memory transport in examples |
| `KUDBEE_SDK_TIMEOUT_S` | `30` | HTTP timeout |
| `KUDBEE_SDK_MAX_RETRIES` | `2` | Idempotent GET retries |
