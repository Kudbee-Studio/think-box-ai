# KILO live-proof-exec guide (PR #150)

Gate ID: **`live-proof-exec`**. Hermetic execution-plan contract for a future bounded
KILO Live proof. This PR closes arc **#141–#150** at **CODE COMPLETE / TEST VERIFIED**
only — not LIVE VERIFIED.

## Module

- `thinkbox/kilo_live_proof_exec.py`
- Fixtures: `data/kilo_live_proof_exec/fixtures/`
- Operator: `scripts/verify_kilo_live_proof_exec.py`

## Founder / Box env (live prep only)

| Variable | Role |
|----------|------|
| `THINKBOX_SWARM_LIVE_ACK` | Founder explicit ack (`1` / `true` / `yes` / `accept`) |
| `UPSTASH_PUBLIC_BOX_URL` | Public Box URL (`*.box.upstash.com`) |

Default hermetic verify does **not** require these. Optional `--live` checks readiness
without HTTP; returns exit 1 when ack or URL is missing.

## Artifact and audit flip

1. Run bounded smoke (founder-run; governed path).
2. Write `data/thinkboxmd/artifacts/kilo_live_proof_*.json` (proof-schema shape).
3. Add `docs/audit/passes/` entry with `live_verified: true` only after evidence exists.
4. Update `docs/CONTINUITY.md` with artifact hash.

## Season close

Marker: `kilo-live-proof-arc-141-150-season-closed`. After PR #150 merge, Cloud Bot
stands by — no #151 unless founder asks.
