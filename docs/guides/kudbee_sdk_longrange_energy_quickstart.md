# Kudbee SDK long-range + energy loops quickstart (PR #193)

Hermetic toolkit under `thinkbox/kudbee_sdk_longrange_energy/` deepening merged #191 and #192 (wave 3 + major fixes / expansion packs).
**Four-state cap:** CODE COMPLETE / TEST VERIFIED only — not LIVE VERIFIED.

## Verify gate

```bash
python3 scripts/verify_kilo_pr193_kudbee_sdk_longrange_energy.py
```

## Run example

```bash
python3 examples/kudbee_sdk_longrange_energy_quickstart.py
```

## Environment (optional)

| Variable | Purpose |
|----------|---------|
| `KUDBEE_SDK_LR_ENERGY_BASE_URL` | HTTP base (must be `http://` or `https://`) |
| `KUDBEE_SDK_LR_ENERGY_DRY_RUN` | Force dry-run transport (`true`/`1`) |
| `KUDBEE_SDK_LR_ENERGY_TIMEOUT_S` | Request timeout seconds |

## Energy mesh (hermetic)

```python
from thinkbox.kudbee_sdk_longrange_energy import EnergyLoopMesh, KudbeeSdkLrEnergyClient

client = KudbeeSdkLrEnergyClient.from_env()
print(client.capabilities())

mesh = EnergyLoopMesh("mesh-1")
loop = mesh.attach_loop("loop-a", capacity=50.0)
loop.deposit(10.0)
print(mesh.snapshot())
```

## TypeScript

See `apps/web/sdk/longrange_energy.ts` and exports from `apps/web/sdk/index.ts`.
