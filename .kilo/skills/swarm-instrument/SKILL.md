# Skill: swarm-instrument

**Description:** Run swarm instrumentation, interpret TSSI scores, and identify improvements

# When to Use

Use when running swarm experiments, measuring improvement, or validating that swarm behavior is getting better over time.

# Prerequisites

- `thinkbox/experiments.py` available
- `ExperimentStore` initialized (SQLite)
- Live provider (Mercury 2) for real runs

# Workflow

## Step 1 — Verify Instrumentation (11 checks)

```bash
python3 experiments/verify_instrumentation.py --live
```

All 11 checks should pass (10 offline + 1 live).

## Step 2 — Run Swarm

```bash
python3 experiments/big_swarm.py --primary 256 --validators 64 --concurrency 32 --arena
```

## Step 3 — Check Dashboard

```bash
python3 experiments/swarm_dashboard.py --port 8787
```

Mobile-first, stdlib, DB-backed view.

## Step 4 — Interpret Results

Key metrics from `verify_instrumentation.py`:

| Metric | Current | Notes |
|--------|---------|-------|
| TSSI | 0.7318 | After 2 runs |
| Learning curve | +0.0913 | Improvement per session |
| Mercury 2 ceiling | ~24 rps | Single client, 0 errors to conc 64 |
| Test count | 390 OK | Baseline |

## Step 5 — Self-Improvement Loop

The `SelfImprovementLoop` class (`thinkbox/experiments.py:299`) exists and is tested but NOT yet wired into automatic swarm runs. Current work: wire it so each run automatically evaluates, proposes improvements, retests, and records verdicts.

# Ten Instruments

1. Flight recorder — permanent per-worker records + proof chains
2. Challenge arena — adversarial traps with detection/recovery
3. TSSI + learning curve — strength index + session store
4. Memory evolution — lifecycle (created → promoted/decayed)
5. Proof-carrying decisions — evidence-based decisions
6. Worker reputation — demonstrated performance scores
7. A/B experiments — variants + self-improvement loop
8. Cost/intelligence efficiency — tokens per insight
9. Swarm genome — replay capability
10. Self-improvement loop — weakest component → change → retest

# Rules

- Never fake metrics — all numbers must come from actual runs
- Learning curve improvements must be measured, not assumed
- Self-ImprovementLoop is NOT auto-wired yet — document as TODO
