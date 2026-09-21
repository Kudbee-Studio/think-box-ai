# KILO Swarm Scale Guide

Operational notes for `experiments/big_swarm.py` at 256+ live calls (Mercury-2 / Inception).

## Worker accounting

| Flag | Meaning |
|------|---------|
| `--primary N` | Primary research compartments (one live call each) |
| `--validators V` | Validator wave size (challenges first V successful primaries) |
| **Total live calls** | `N + V` (e.g. 224 + 32 = **256**) |

Do not set `--primary 256` when you intend 256 total calls with 32 validators — that fires **288** calls.

## Recommended 256-call command

```bash
export INCEPTION_API_KEY=...  # injected at runtime, never committed
python3 experiments/verify_instrumentation.py --live
python3 experiments/big_swarm.py --primary 224 --validators 32 --concurrency 32 --fresh-ledger
python3 experiments/verify_swarm_proof.py data/thinkboxmd/big_swarm_*.json
```

`--fresh-ledger` resets `data/thinkboxmd/db/action_ledger.db` so `ledger_entries_this_run` equals audit rows for this session. Without it, `ledger_entries` is cumulative across runs on the same machine.

## Proof validation

`thinkbox.swarm_stats` and `experiments/verify_swarm_proof.py` check:

- `primary_calls + validator_calls == total_calls`
- `ok + failed == total_calls`
- `effective_rps == round(total_calls / elapsed_s, 2)`
- Worker row count matches reconciliation

## Event stream

Each run truncates `data/thinkboxmd/swarm_events.jsonl` (gitignored). Proof JSON under `data/thinkboxmd/big_swarm_*.json` is the durable artifact for PR evidence.

## Honesty

- Compare runs at fixed `--concurrency` only.
- Do not claim linear RPS scaling from a single baseline with HTTP 503 noise.
- `PRODUCTION_NOT_CLAIMED` until Box PATH A and multi-run baselines are recorded.
