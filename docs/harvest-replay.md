# Harvest & Replay

Harvest once on the GPU; re-score forever offline. This closes the loop
between a paid THINK burst and the verifier: burst jsonl → reconstructed
contrast pairs → deterministic grounding score → report (and optionally
the Verifier).

---

## Pipeline

```
think-v2 burst  ──►  data/evals/burst/*.jsonl
                          │
                          ▼
                   HarvestReplay.load()
                          │  group by pair_id
                          ▼
                grounded / ungrounded variants
                          │
                GroundingScorer (deterministic)
                          │
                          ▼
                   HarvestReport (json + markdown)
                          │  optional verify=True
                          ▼
                     Verifier (grounding category)
```

---

## Metrics

| Metric | Meaning |
|--------|---------|
| Records / pairs | jsonl lines and reconstructed contrast pairs |
| Reasoning coverage | fraction of records carrying a reasoning channel |
| Groundedness score | mean grounding score of grounded variants |
| Bind-failure rate | fraction of ungrounded twins correctly scored below threshold |
| Mean grounding score | mean over all variants |
| Verifier overall | optional, when `verify=True` (grounding category only) |

The grounding scorer is deterministic: evidence-token coverage (0.7) +
numeric anchors (0.2) + reasoning present (0.1), zeroed when no evidence.
A single-character numeric token (e.g. `4`) is retained so numeric facts
score correctly.

---

## Usage

```python
from thinkbox.harvest import HarvestReplay

report = HarvestReplay().replay_dir("data/evals/burst")
print(report.metrics.groundedness_score, report.metrics.bind_failure_rate)

# with verifier bridge
records = HarvestReplay().load(report.sources)
verified = HarvestReplay().analyze(records, verify=True)
print(verified.metrics.verifier_overall, verified.metrics.verifier_verdict)
```

Offline demo:

```bash
python3 examples/think_burst_demo.py     # burst + harvest in one run
```

---

## Ledger

`BurstRunner` accepts an `ActionLedger` and appends one entry per admitted
call (plus the admission decision). `BurstReport` exposes `ledger_entries`
and `ledger_valid` (hash-chain verification).

---

## Fact-card scheduling

`FactCardRegistry.next_batch(n)` returns the least-used cards first so each
paid burst targets under-covered concepts instead of repeating. Coverage is
exposed via `coverage()`.

---

## Honest numbers

- `bind_failure_rate` is measured by the deterministic grounding scorer
  against the recorded evidence text — it is **not** an adversary outcome.
- No eval numbers are invented; offline reports are labeled construction-based.

---

## Files

- `thinkbox/harvest.py` — `HarvestReplay`, `HarvestReport`, `HarvestMetrics`
- `thinkbox/grounding.py` — `GroundingScorer`
- `thinkbox/factcards.py` — `FactCardRegistry`
- `tests/unit/test_harvest.py`, `test_grounding.py`, `test_factcards.py`
