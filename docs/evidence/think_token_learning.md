# Think Token Learning-Benefit Evidence

**Generated:** 2026-11-05T19:12:59.772335+00:00

## Bottom Line (read this first)

This harness is **hermetic** and uses a **scripted provider**, not a real model. It proves the **injection mechanism** (accepted Think Tokens reach the artifact-generation path and can change the emitted artifact) and that the objective verifier is sensitive to that change. It does **NOT** prove that a real model produces better outputs *because* of the tokens. That requires a real model and is out of scope.

## Question

Do accepted Think Tokens (prior-run lessons / memory entries) produce measurable improvement on held-out goals in the same task family?

## Accepted Think Tokens Loaded

- `org:pattern:1` (source: /workspace/app/learned.db): Task task_001_rest_endpoint: Create a REST endpoint that accepts JSON items, validates schema, stores to SQLite, and ret
- `org:pattern:2` (source: /workspace/app/learned.db): Task task_002_user_api: Create a REST endpoint for user registration with validation, storage, and search

## Held-Out Goals (same family, different instances)

- `heldout_001_inventory_api`
- `heldout_002_order_api`
- `heldout_003_product_api`
- `heldout_004_shipment_api`
- `heldout_005_invoice_api`

## Arm A — Token-injection mechanism (scripted provider honoring tokens)

| Arm | Success | Rate | Mean tool calls | Mean model calls |
|-----|---------|------|-----------------|------------------|
| with_tokens | 5/5 | 1.00 | 1.00 | 1.00 |
| without_tokens | 0/5 | 0.00 | 1.00 | 1.00 |

- **Delta (with - without):** +1.0000
- **Mean paired delta:** +1.0000
- **Cohen's h:** 3.1416
- **Fisher exact (one-sided) p:** 0.003968
- **Tokens reused (with-tokens arm):** 5/5
- **Contingency table:** [[5, 0], [0, 5]]
- **Paired deltas:** [1, 1, 1, 1, 1]

**Verdict (Arm A):** MECHANISM_DEMONSTRATED

## Arm B — Negative control (NEUTRAL provider, ignores token block)

Same harness, but the provider ignores the token context block in BOTH arms. If the mechanism is real, Arm B should show NO improvement — proving the verifier detects behavioral change rather than the mere presence of text.

| Arm | Success | Rate | Mean tool calls | Mean model calls |
|-----|---------|------|-----------------|------------------|
| with_tokens | 0/5 | 0.00 | 1.00 | 1.00 |
| without_tokens | 0/5 | 0.00 | 1.00 | 1.00 |

- **Control delta:** +0.0000
- **Control Fisher exact p:** 1.000000
**Verdict (Arm B):** NO_MEASURABLE_IMPROVEMENT

## Interpretation

The accepted Think Token context block measurably changed the emitted artifact, and the objective, machine-checkable verifier is sensitive to that change (with-tokens arm passed all held-out goals; without-tokens arm passed none; Fisher exact one-sided p < 0.05).

**SCOPE LIMIT — READ THIS:** this harness uses a SCRIPTED hermetic provider, not a real model. The provider is wired to emit a parameterized-query artifact when the token context block is present and a naive f-string artifact when it is absent. Therefore this result proves that (a) the token injection mechanism reaches the artifact-generation path, and (b) the objective verifier can distinguish the two artifacts. It does NOT prove that a real model would produce better outputs because of the tokens. That question requires a real model and is out of scope for this hermetic harness.

## Commands

```bash
python3 -m thinkbox.think_token_eval --write-docs docs/evidence/think_token_learning.md
python3 -m unittest tests.unit.test_think_token_eval -v
```

## Honesty Notes

- Hermetic only: no network, no live Mercury, no new governance.
- Tokens are loaded from durable storage; none are synthesized.
- The verdict describes the measured data, not a claim of model improvement.
- A p<0.05 threshold is reported but is not treated as proof of benefit.
- The provider is scripted; real-model behavior is not measured here.