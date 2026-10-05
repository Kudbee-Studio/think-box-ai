# P3.32 escalation lane: results

Computed only from `raw-*.jsonl` by `apps/web/tests/e2e/repo-escalation-report.ts`, applying the rules pre-registered in `PLAN.md`.

## primary (n=15)

Local `qwen2.5:3b`, escalation `mercury-2`, commit `fad001a8`, goals hash `5549e075ffed`.

| Arm | Pass (95% Wilson CI) | False accepts |
|---|---|---|
| L local only | 9/15 (60.0%, 35.7%-80.2%) | 2 |
| E local + escalation | 14/15 (93.3%, 70.2%-98.8%) | 0 |

- E minus L: +33.3 pts, paired-bootstrap 95% CI [13.3, 60.0]; rescued 5, lost 0
- Trigger fired on 6/15; escalated 6; skipped for the cap 0; Mercury passed 5/6 of what it was given
- By kind (local pass / final pass / triggered): untested 0/5/5 of 5; constant 4/4/1 of 5; missing 5/5/0 of 5
- Mercury spend (from reported tokens at the price table): $0.0083; mean latency local 24.0s, Mercury 2.7s

## secondary (n=20)

Local `qwen2.5:3b`, escalation `mercury-2`, commit `fad001a8`, goals hash `8db936784996`.

| Arm | Pass (95% Wilson CI) | False accepts |
|---|---|---|
| L local only | 11/20 (55.0%, 34.2%-74.2%) | 7 |
| E local + escalation | 20/20 (100.0%, 83.9%-100.0%) | 0 |

- E minus L: +45.0 pts, paired-bootstrap 95% CI [25.0, 65.0]; rescued 9, lost 0
- Trigger fired on 9/20; escalated 9; skipped for the cap 0; Mercury passed 9/9 of what it was given
- By kind (local pass / final pass / triggered): untested 1/10/9 of 10; constant 5/5/0 of 5; missing 5/5/0 of 5
- Mercury spend (from reported tokens at the price table): $0.0119; mean latency local 22.9s, Mercury 2.5s

## Decision (pre-registered rules)

Total Mercury spend $0.0201 (cap $0.50). **Verdict: PROVEN.**

