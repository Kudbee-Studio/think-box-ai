# THINK Burst Protocol

Goal: **maximize THINK-token quality per GPU-dollar** via short, bounded
bursts on `openai/gpt-oss-20b` — never long idle A10G time.

---

## What a burst produces

For each question, two calls form a **contrast pair**:

- **grounded** — answered with a fact card (occupancy mesh), tagged `mesh`
- **ungrounded twin** — same question without evidence, tagged `disruptor`

Reasoning (`delta.reasoning` / `message.reasoning`) is captured, never
dropped. Every trace is written as jsonl, scored by the verifier, and
recorded against a governance token under an elastic-cash ceiling.

Output: `data/evals/burst/think_burst_<id>.jsonl` + a burst report.

---

## Burst checklist (target: < 15–20 min wall clock)

1. **Founder starts think-v2** (`i-0685561c90845986d`). Wait until running.
2. **CloudShell SSM in** (founder/Cloud Bot holds access; KILO does not):
   ```bash
   AWS_PAGER="" aws ssm start-session --target i-0685561c90845986d --region us-east-1
   ```
3. **On-box health check** (loopback only — never bind publicly):
   ```bash
   nvidia-smi -L
   curl -sS --http1.0 -m 20 -H 'Authorization: Bearer EMPTY' http://127.0.0.1:8001/v1/models
   ```
   Confirm served id **`openai/gpt-oss-20b`** (bare `gpt-oss-20b` → 404).
4. **Run the burst** (from the repo on the box):
   ```bash
   python3 -m thinkbox.burst --live --pairs 24 --minutes 12 --max-calls 64 --budget 5.00 --out data/evals/burst
   ```
   The runner refuses to start without a valid governance token
   (fail closed) and hard-stops on calls, spend, or time.
5. **Stop the burst** when the report prints. **Founder stops the instance**
   (stop, not terminate).
6. Close the SSM session.

---

## Offline (no GPU)

Unit tests and the demo use the synthetic model:

```bash
python3 examples/think_burst_demo.py
python3 -m unittest tests.unit.test_burst -q
```

---

## Guardrails

| Rule | Enforced by |
|------|-------------|
| No side effect without a governance token | `AdmissionGate` in `BurstRunner._admit` |
| Bounded calls | `BurstBudget.max_calls` |
| Bounded spend (elastic cash stub) | `BurstBudget.max_spend` / `cost_per_call` |
| Bounded time | `BurstConfig.max_minutes` |
| Loopback only, no public bind | live client targets `127.0.0.1:8001` only |
| Reasoning never dropped | `capture_completion` tags + metadata |
| Honest numbers | report states construction-based rates; no invented evals |

### Honest notes on metrics

- `groundness_score = grounded_variants / total_variants`.
- `bind_failure_rate` is **construction-based** offline: ungrounded twins
  carry no evidence, so the grounding scorer flags them (1.0 when any
  disruptor twins exist). A real adversarial rate requires live disruptor
  load; do not present it as an attack-success metric.

---

## Files

- `thinkbox/burst.py` — `BurstConfig`, `BurstBudget`, `BurstRunner`, `LiveVLLMClient`
- `tests/unit/test_burst.py`
- `examples/think_burst_demo.py`
