#!/usr/bin/env python3
"""Run N repeated 256-call big_swarm sessions and summarize run-to-run variance.

Default: 5 runs at 224 primary + 32 validators (--fresh-ledger each run).

Usage:
    export INCEPTION_API_KEY=...  # required for live execution
    python3 experiments/run_swarm_convergence.py --runs 5 --fresh-ledger
    python3 experiments/run_swarm_convergence.py --summarize-only \\
        data/thinkboxmd/big_swarm_a.json data/thinkboxmd/big_swarm_b.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from thinkbox.swarm_stats import (  # noqa: E402
    extract_convergence_metrics,
    load_and_validate_proof,
    summarize_convergence_proof_paths,
)

OUT = ROOT / "data" / "thinkboxmd"


def _run_one_big_swarm(
    primary: int,
    validators: int,
    concurrency: int,
    *,
    fresh_ledger: bool,
    arena: bool,
) -> dict[str, Any]:
    from experiments.big_swarm import BigSwarm

    swarm = BigSwarm(
        primary,
        validators,
        concurrency,
        arena=arena,
        fresh_ledger=fresh_ledger,
    )
    return swarm.run()


def build_convergence_document(
    *,
    runs: list[dict[str, Any]],
    summary: dict[str, Any],
    config: dict[str, Any],
    live_verified: bool,
    live_blockers: list[str],
) -> dict[str, Any]:
    return {
        "harness": "run_swarm_convergence",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "live_verified": live_verified,
        "live_blockers": live_blockers,
        "config": config,
        "run_proofs": runs,
        "variance": summary,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Five-run swarm convergence harness (256 calls each).")
    ap.add_argument("--runs", type=int, default=5, help="Number of big_swarm repetitions")
    ap.add_argument("--primary", type=int, default=224)
    ap.add_argument("--validators", type=int, default=32)
    ap.add_argument("--concurrency", type=int, default=32)
    ap.add_argument("--arena", action="store_true")
    ap.add_argument(
        "--fresh-ledger",
        action="store_true",
        help="reset action_ledger.db before each run (recommended)",
    )
    ap.add_argument(
        "--summarize-only",
        nargs="+",
        metavar="PROOF.json",
        help="skip live runs; summarize existing big_swarm proof files",
    )
    args = ap.parse_args()

    if args.summarize_only:
        agg = summarize_convergence_proof_paths(args.summarize_only)
        doc = build_convergence_document(
            runs=[
                {"proof_path": p, **extract_convergence_metrics(load_and_validate_proof(p)[0])}
                for p in agg["proof_paths"]
            ],
            summary=agg["summary"],
            config={"summarize_only": True, "n_proofs": len(agg["proof_paths"])},
            live_verified=False,
            live_blockers=[],
        )
        doc["variance"] = agg["summary"]
        out_path = OUT / f"swarm_convergence_summary_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        OUT.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(doc, indent=2))
        print(json.dumps(doc["variance"], indent=2))
        print(f"summary written: {out_path}")
        return 0

    if args.runs < 1:
        print("--runs must be >= 1")
        return 2
    if args.primary < 1 or args.validators < 0 or args.concurrency < 1:
        print("invalid worker or concurrency counts")
        return 2

    config = {
        "runs": args.runs,
        "primary": args.primary,
        "validators": args.validators,
        "concurrency": args.concurrency,
        "fresh_ledger": args.fresh_ledger,
        "arena": args.arena,
        "expected_calls_per_run": args.primary + args.validators,
    }

    if not os.environ.get("INCEPTION_API_KEY"):
        doc = build_convergence_document(
            runs=[],
            summary={},
            config=config,
            live_verified=False,
            live_blockers=["INCEPTION_API_KEY missing"],
        )
        out_path = OUT / f"swarm_convergence_BLOCKED_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        OUT.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(doc, indent=2))
        print("LIVE blocked: INCEPTION_API_KEY missing")
        print(f"blocker artifact: {out_path}")
        print("Hermetic tests cover summary math; run live when key is injected at runtime.")
        return 2

    run_records: list[dict[str, Any]] = []
    proof_paths: list[str] = []
    t0 = time.monotonic()
    for i in range(args.runs):
        print(f"=== convergence run {i + 1}/{args.runs} ===")
        proof = _run_one_big_swarm(
            args.primary,
            args.validators,
            args.concurrency,
            fresh_ledger=args.fresh_ledger,
            arena=args.arena,
        )
        path = proof["path"]
        payload = proof["payload"]
        recon = payload["reconciliation"]
        if recon.get("validation_errors"):
            print(f"validation errors: {recon['validation_errors']}")
            return 1
        proof_paths.append(path)
        metrics = extract_convergence_metrics(payload)
        run_records.append(
            {
                "run_index": i + 1,
                "proof_path": path,
                "run_id": payload.get("run_id"),
                "session_id": payload.get("session_id"),
                **metrics,
            }
        )

    agg = summarize_convergence_proof_paths(proof_paths)
    doc = build_convergence_document(
        runs=run_records,
        summary=agg["summary"],
        config=config,
        live_verified=True,
        live_blockers=[],
    )
    doc["wall_seconds"] = round(time.monotonic() - t0, 2)
    out_path = OUT / f"swarm_convergence_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(doc, indent=2))
    print("=" * 66)
    print("SWARM CONVERGENCE SUMMARY")
    print("=" * 66)
    print(json.dumps(doc["variance"], indent=2))
    print(f"artifact: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
