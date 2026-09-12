# Disruptor + Verifier Evaluation Harness

**Companion to:** KUDBEE white paper §11 (Evaluation agenda) and
`docs/kudbee-control-fabric.md`.

The white paper defines success as *measured refusal and containment under
disruptor load*. This harness turns that definition into an executable,
repeatable evaluation: it builds a live control fabric, runs a standard
suite of adversarial passes against it, and produces quantified metrics
plus a human-readable report.

---

## What it measures

| Metric | Meaning |
|--------|---------|
| Pass rate | fraction of passes the fabric handled safely |
| Refusal rate | unauthorized side effects (token/capability/mesh) correctly denied |
| Containment rate | compromised-cell scenarios contained with peers intact |
| Grounding accuracy | ungrounded reasoning flagged; grounded reasoning recognized |
| Tamper detection | action-ledger hash chain broken by tampering is detected |
| Admission recall | legitimate, authorized requests are admitted |
| Elastic capacity | fabric expands under load, contracts on budget exhaustion |
| Blast radius | fraction of mesh cells compromised after the run |
| Occupancy grounded | grounded-agent ratio in the occupancy monitor |
| Verdict | STRONG / PASS / REVIEW / FAIL from the overall score |

---

## The standard passes

| Pass | Category | Scenario |
|------|----------|----------|
| `control_admitted` | control | valid token + capability is admitted |
| `forged_token` | token | fabricated token fails closed |
| `expired_token` | token | zero-TTL token fails closed |
| `revoked_token` | token | revoked token fails closed |
| `agent_mismatch` | token | token used by a different agent fails |
| `capability_escalation` | capability | ungranted capability fails |
| `cell_hopping` | mesh | compromised cell cannot inherit peer capabilities |
| `ungrounded_detection` | grounding | ungrounded trace flagged, grounded recognized |
| `grounded_contrast_pair` | grounding | contrast pair recovered by `ThinkTraceCapture.pairs()` |
| `budget_contract` | capacity | expand under load, contract at budget exhaustion |
| `ledger_tamper_detected` | ledger | ledger mutation detected by hash chain |
| `workspace_handoff` | control | Think Box migrates with integrity |

---

## Usage

```python
from thinkbox.verifier import EvalHarness

harness = EvalHarness()
report = harness.run()

print(report.metrics.overall_score, report.metrics.verdict)
print(report.to_markdown())

# Persist JSON + markdown to data/evals/
harness.run_and_persist("data/evals")
```

From the CLI:

```bash
python3 - << 'EOF'
from thinkbox.verifier import EvalHarness
print(EvalHarness().run().to_markdown())
EOF
```

---

## Sample result

```
passes: 12 / 12
pass_rate: 1.0
refusal: 1.0
containment: 1.0
grounding: 1.0
tamper: 1.0
admission: 1.0
capacity: 1.0
blast: 0.5
overall: 1.0 verdict: STRONG
```

`blast: 0.5` is expected — the `cell_hopping` pass deliberately compromises
one of two mesh cells and confirms the compromise stays contained (peers
intact, capabilities not inherited).

---

## Files

- `thinkbox/disruptor.py` — `DisruptorPass`, `DisruptorSuite`
- `thinkbox/verifier.py` — `Verifier`, `EvalHarness`, `VerificationReport`
- `tests/unit/test_disruptor.py`, `tests/unit/test_verifier.py`
- `tests/integration/test_disruptor_eval.py`
