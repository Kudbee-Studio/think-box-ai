# THINK BOX Command Center v2

**What it is:** the instrumented view of a swarm run. Ten surfaces over one
read-only SQLite set and one append-only event stream — no broker, no framework,
no build step, no second process.

**Run:**
```bash
python3 experiments/swarm_dashboard.py --port 8787
cloudflared tunnel --url http://127.0.0.1:8787     # phone-viewable link
```

**Verify:**
```bash
python3 scripts/agent_work.py verify --template dashboard-evolution
```

---

## The ten surfaces

| # | Tab | Question it answers | Endpoint | Source |
|---|-----|--------------------|----------|--------|
| 1 | **Command** | what is running right now? | `/api/live` | `swarm_events.jsonl` |
| 2 | **Trace** | *why* does a claim end the way it does? | `/api/trace` | `flight_recorder.worker_records` |
| 3 | **Proof** | is the chain intact, and has anything been tampered with? | `/api/proofs` | `proof_chains`, `proof_nodes`, `action_ledger` |
| 4 | **Learning** | is it getting stronger, and did proposed changes help? | `/api/learning` | `sessions`, `strength_history`, `improvements` |
| 5 | **Arena** | do workers catch fabricated citations and forced certainty? | `/api/arena` | `flight_recorder.arena_outcomes` |
| 6 | **Memory** | what happened to each remembered concept? | `/api/memory` | `memory_evolution.memories`, `memory_events` |
| 7 | **Workers** | who has earned trust, and on what evidence? | `/api/reputation` | `reputation.worker_reputation` |
| 8 | **Cost × Intel** | did the extra compute buy anything? | `/api/efficiency` | `experiments.variant_results`, `metrics.token_usage` |
| 9 | **Replay** | can this run be reproduced exactly? | `/api/genome`, `/api/replay` | `genomes`, `replays` |
| 10 | **Mission** | what is ready, degraded, blocked, or needs a human? | `/api/mission` | live local probes |

Preserved v1 routes, unchanged payloads: `/healthz`, `/api/live`, `/api/strength`,
`/api/instruments`, `/api/proof`, `/api/sessions`.

---

## Traceability rule

Every displayed number has exactly one path:

```
UI element → /api/* endpoint → SQLite table (read-only) → written by a run
```

There is no value in the browser that is not in a store. Percentages and colour
are the only things computed client-side. If a store is empty, the panel says so
rather than rendering a zero that looks like a measurement.

---

## Signals vs. failures

The strength index is a weighted mean of six measured ratios:

```
reliability .18 · grounding .20 · evidence quality .16
challenge resolution .16 · validator calibration .14 · reproducibility .16
```

Two quantities are **reported and never scored**:

- **challenge activity** — how often validators disagreed with primaries
- **tier inflation rate** — a governance signal about the reviewer

A swarm that never disagrees is not a well-behaved swarm; it is an untested one.
The Arena tab exists to make that visible.

---

## Mission control semantics

Capabilities are probed locally, non-destructively, with **no network calls** —
so a capability is only marked `ready` when local evidence supports it.

| Status | Meaning |
|--------|---------|
| `ready` | verified usable from local evidence |
| `degraded` | usable but limited, with a concrete reason |
| `unavailable` | configured but not usable |
| `missing` | not configured at all |
| `unknown` | could not be determined |

`overall` reflects the **core runtime path only**. Blocked external dependencies
(Upstash Box, UpCloud, Redis, MCP) are listed separately as `external_blockers`
so an external outage is never reported as the system being down.

All SQLite access, including the ledger hash-chain verification, is read-only
(`mode=ro`). The chain is replayed with the same hash function rather than opening
the ledger read-write.

---

## Honest limitations

- **No CI gate.** GitHub billing is restricted; the local suite is the gate.
  This is documented, not faked.
- **Empty panels are honest.** Arena, Experiments and Replay tabs show "none
  recorded" until a run populates them.
- **Synthetic data is labelled.** All THINKBOXMD scenarios are `SYNTHETIC=true`.
- **Cost uses list price.** `$0.25/M in`, `$0.75/M out` for Mercury 2, stated in
  the payload so the figure is auditable.

---

## Files

```
experiments/swarm_dashboard.py     the server + UI (one process)
experiments/big_swarm.py           the run that writes every store
experiments/run_experiment.py      derives the A/B ledger from real sessions
thinkbox/mission_control.py        the capability probes
thinkbox/{metrics,flightrecorder,arena,memory_evolution,reputation,experiments}.py
tests/unit/test_command_center.py  32 tests
docs/agent-templates/              the work protocol used to build this
```
