#!/usr/bin/env python3
"""Derive an A/B experiment ledger from REAL recorded sessions.

This does not invent variants. It reads completed swarm sessions out of the
metrics store, records each as a variant of one experiment, computes the
cost/intelligence series from real token + insight counts, and asks the
self-improvement loop for the weakest component of the latest run.

Because it derives from persisted runs, the dashboard's Learning tab cannot show
a number that has no underlying session.

Usage:
    python3 experiments/run_experiment.py                 # derive from all sessions
    python3 experiments/run_experiment.py --kind big_swarm --limit 10
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from thinkbox.experiments import ExperimentStore, SelfImprovementLoop, Variant, VariantResult
from thinkbox.metrics import MetricsStore
from thinkbox.reputation import ReputationLedger

DB = ROOT / "data" / "thinkboxmd" / "db"
MODEL_PRICES = {"mercury-2": {"input": 0.25, "output": 0.75}}


def _cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p = MODEL_PRICES.get(model, {"input": 0.0, "output": 0.0})
    return (prompt_tokens / 1_000_000) * p["input"] + (completion_tokens / 1_000_000) * p["output"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="big_swarm")
    ap.add_argument("--limit", type=int, default=12)
    args = ap.parse_args()

    metrics = MetricsStore(DB / "metrics.db")
    store = ExperimentStore(DB / "experiments.db")
    rep = ReputationLedger(DB / "reputation.db")

    runs = metrics.trend(args.kind, limit=args.limit)["runs"]
    if not runs:
        print("no recorded sessions found — run a swarm first")
        return 1

    eid = store.start_experiment(
        name=f"derived:{args.kind}",
        task="tier + adversarial validation over a synthetic claim corpus",
        notes="variants are real recorded sessions, not synthetic fixtures",
    )
    print(f"experiment {eid}  ({len(runs)} recorded variant(s))")

    # newest first from trend(); present oldest -> newest so marginal deltas read forward
    ordered = list(reversed(runs))
    results: list[VariantResult] = []
    for r in ordered:
        sid = r["session_id"]
        totals = metrics.session_totals(sid)
        session = metrics.session(sid) or {}
        variant = Variant(
            name=sid,
            model=session.get("model", "") or "mercury-2",
            workers=int(r.get("workers_total") or 0),
            validators=0,
            concurrency=int(session.get("concurrency") or 0),
        )
        cost = _cost(variant.model, totals["prompt_tokens"], totals["completion_tokens"])
        # validated insights: successful worker calls (errors are excluded, not counted)
        insights = max(0, int(r.get("workers_ok") or 0))
        vr = VariantResult(
            variant=variant,
            index=float(r.get("strength_score") or 0.0),
            workers_ok=int(r.get("workers_ok") or 0),
            workers_failed=0,
            validated_insights=insights,
            total_tokens=int(totals["total_tokens"] or 0),
            cost_usd=cost,
            wall_seconds=float(session.get("wall_seconds") or 0.0),
        )
        store.record_variant(eid, vr)
        results.append(vr)
        print(f"  variant {sid[:28]:28s} workers={variant.workers:4d} index={vr.index:.4f} "
              f"tokens={vr.total_tokens:6d} cost=${cost:.6f}")

    store.record_efficiency(
        experiment_id=eid,
        model=results[-1].variant.model,
        workers=results[-1].variant.workers,
        insights=results[-1].validated_insights,
        tokens=results[-1].total_tokens,
        cost=results[-1].cost_usd,
        wall=results[-1].wall_seconds,
        marginal_workers=(results[-1].variant.workers - results[0].variant.workers) if len(results) > 1 else 0,
        marginal_insights=(results[-1].validated_insights - results[0].validated_insights) if len(results) > 1 else 0,
        marginal_cost=(results[-1].cost_usd - results[0].cost_usd) if len(results) > 1 else 0.0,
    )

    # self-improvement: propose from the weakest measured component of the latest run
    latest = runs[0]
    components = _latest_components(latest["session_id"])
    loop = SelfImprovementLoop(store)
    if components:
        rec = loop.run(eid, baseline_index=float(latest.get("strength_score") or 0.0),
                       baseline_components=components, retest=None)
        print(f"\nweakest component : {rec['weakness']}")
        print(f"proposed change   : {rec['proposed_change'].get('detail', '')}")
        print(f"applied           : {rec['applied']}  (retest not run in this invocation)")
    else:
        print("\nno strength components available for the latest session")

    cmp = store.compare(eid)
    print(f"\nbest={cmp['best']} spread={cmp['index_spread']}  "
          f"reputation workers={rep.summary().get('workers', 0)}")
    return 0


def _latest_components(session_id: str) -> dict[str, float]:
    """Read the TSSI components for a session from the newest proof artifact."""
    proofs = sorted((ROOT / "data" / "thinkboxmd").glob("big_swarm_*.json"))
    for p in reversed(proofs):
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("session_id") == session_id:
            return (data.get("reconciliation", {}).get("strength", {}) or {}).get("components", {}) or {}
    return {}


if __name__ == "__main__":
    sys.exit(main())
