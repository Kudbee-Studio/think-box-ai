# P3.24 A/B results

Computed only from `raw-*.jsonl` by `apps/web/tests/e2e/token-ab-report.ts`, applying the rules pre-registered in `PLAN.md`.

## qwen2.5:1.5b

Tokens retrieved for 26/30 goals (store: 15 accepted). Goals hash `8f0526aee8b6`, commit `9bd690d7`.

| Arm | Pass (95% Wilson CI) | Grounded | Latency mean / p50 / p95 | wrong / ungrounded / failed |
|---|---|---|---|---|
| A no token, engine off | 7/30 (23.3%, CI 11.8%-40.9%) | 23.3% | 6.5s / 4.5s / 13.3s | 0 / 0 / 23 |
| B tokens, engine off | 4/30 (13.3%, CI 5.3%-29.7%) | 13.3% | 7.3s / 4.5s / 17.9s | 0 / 0 / 26 |
| C tokens + engine | 4/30 (13.3%, CI 5.3%-29.7%) | 13.3% | 7.0s / 4.8s / 15.2s | 0 / 0 / 26 |

- B - A: -10.0 pts, 95% CI [-23.3, 3.3], Fisher p=0.5062
- C - B: +0.0 pts, 95% CI [0.0, 0.0], Fisher p=1.0000
- C - A: -10.0 pts, 95% CI [-23.3, 3.3], Fisher p=0.5062
- Untested-function goals only (n=5): A 0/5, B 0/5, C 0/5; C - B: +0.0 pts, 95% CI [0.0, 0.0], Fisher p=1.0000
- Lookup goals B vs C (same config, determinism check): same outcome on 15/15
- Engine absence path on C: 0 repository findings claimed an absence, 0 escalated

Decision rules: testable=true, **B better than A: NO**, engine C better than B on untested-function: NO.

## qwen2.5:3b

Tokens retrieved for 26/30 goals (store: 15 accepted). Goals hash `8f0526aee8b6`, commit `9bd690d7`.

| Arm | Pass (95% Wilson CI) | Grounded | Latency mean / p50 / p95 | wrong / ungrounded / failed |
|---|---|---|---|---|
| A no token, engine off | 18/30 (60.0%, CI 42.3%-75.4%) | 66.7% | 14.2s / 11.6s / 35.2s | 2 / 4 / 6 |
| B tokens, engine off | 17/30 (56.7%, CI 39.2%-72.6%) | 73.3% | 15.4s / 13.2s / 36.0s | 5 / 1 / 7 |
| C tokens + engine | 20/30 (66.7%, CI 48.8%-80.8%) | 83.3% | 17.2s / 14.0s / 37.4s | 5 / 0 / 5 |

- B - A: -3.3 pts, 95% CI [-23.3, 16.7], Fisher p=1.0000
- C - B: +10.0 pts, 95% CI [0.0, 20.0], Fisher p=0.5959
- C - A: +6.7 pts, 95% CI [-10.0, 23.3], Fisher p=0.7892
- Untested-function goals only (n=5): A 0/5, B 0/5, C 0/5; C - B: +0.0 pts, 95% CI [0.0, 0.0], Fisher p=1.0000
- Lookup goals B vs C (same config, determinism check): same outcome on 14/15
- Engine absence path on C: 1 repository findings claimed an absence, 0 escalated

Decision rules: testable=true, **B better than A: NO**, engine C better than B on untested-function: NO.

## Learning benefit (pre-registered rule, PLAN.md decision 1)

**UNPROVEN** (B was not shown better than A under the pre-registered rule.)

