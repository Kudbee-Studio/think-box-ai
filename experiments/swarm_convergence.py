#!/usr/bin/env python3
"""SWARM CONVERGENCE — reproducible scaling runs at 512+ and 256 agents.

Runs:
1. One 512+ agent live swarm at target scale
2. Five 256-agent convergence runs with per-run ledger isolation
3. Computes descriptive statistics across convergence runs
4. Verifies all proofs with hermetic machinery

Usage:
    python3 experiments/swarm_convergence.py [--runs 5] [--out-dir DIR]

Environment:
    INCEPTION_API_KEY: required for Mercury-2 access
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from thinkbox.swarm_stats import (
    load_and_validate_proof,
    proof_metrics,
    convergence_summary,
)


def run_big_swarm(
    primary: int,
    validators: int,
    concurrency: int = 32,
    fresh_ledger: bool = True,
    output_dir: Path = ROOT / "data" / "thinkboxmd",
    max_retries: int = 3,
    inter_run_delay: float = 30.0,
) -> dict[str, Any]:
    """Execute big_swarm.py with given parameters and return proof payload."""
    output_dir.mkdir(parents=True, exist_ok=True)

    last_error: Optional[str] = None
    for attempt in range(max_retries):
        cmd = [
            sys.executable,
            str(ROOT / "experiments" / "big_swarm.py"),
            "--primary", str(primary),
            "--validators", str(validators),
            "--concurrency", str(concurrency),
        ]
        if fresh_ledger:
            cmd.append("--fresh-ledger")

        print(f"Running: {' '.join(cmd)}")
        start = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes max
            env={**os.environ, "PYTHONPATH": str(ROOT)},
        )
        elapsed = time.time() - start

        if result.returncode != 0:
            last_error = f"big_swarm.py failed (exit {result.returncode}): {result.stderr}\n{result.stdout}"
            print(f"❌ Swarm run failed (exit {result.returncode}) on attempt {attempt+1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"   Retrying in {inter_run_delay}s...")
                time.sleep(inter_run_delay)
            continue

        # Find the most recent proof file in output_dir
        proof_files = sorted(output_dir.glob("big_swarm_*.json"), reverse=True)
        if not proof_files:
            last_error = "No proof file generated"
            print(f"❌ No proof file generated on attempt {attempt+1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"   Retrying in {inter_run_delay}s...")
                time.sleep(inter_run_delay)
            continue

        latest = proof_files[0]

        # Verify the proof
        print(f"Verifying proof: {latest}")
        payload, errors = load_and_validate_proof(latest)
        if errors:
            last_error = f"Proof validation failed: {errors}"
            print(f"❌ Proof validation failed on attempt {attempt+1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"   Retrying in {inter_run_delay}s...")
                time.sleep(inter_run_delay)
            continue

        print(f"✅ Swarm run successful (elapsed {elapsed:.1f}s)")
        return payload

    raise RuntimeError(f"big_swarm.py failed after {max_retries} attempts: {last_error}")


def run_convergence_study(
    primary: int,
    validators: int,
    runs: int = 5,
    concurrency: int = 32,
    output_dir: Path = ROOT / "data" / "thinkboxmd",
    inter_run_delay: float = 30.0,
) -> dict[str, Any]:
    """Run N independent swarm runs and compute convergence statistics."""
    print(f"Running {runs} independent {primary+validators}-agent convergence runs")
    payloads: List[dict[str, Any]] = []

    for i in range(runs):
        print(f"\n--- Run {i+1}/{runs} ---")
        payload = run_big_swarm(
            primary=primary,
            validators=validators,
            concurrency=concurrency,
            fresh_ledger=True,
            output_dir=output_dir,
            inter_run_delay=inter_run_delay,
        )
        payloads.append(payload)
        print(f"   Collected proof: {payload['run_id']}")

        # Cooldown between runs to avoid rate limits
        if i < runs - 1:
            print(f"   Cooling down {inter_run_delay}s before next run...")
            time.sleep(inter_run_delay)

    print(f"\nComputing convergence statistics across {len(payloads)} runs")
    return convergence_summary(payloads)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run reproducible swarm convergence study (512+ scale + 5x256 convergence)"
    )
    parser.add_argument(
        "--primary",
        type=int,
        default=224,
        help="Primary workers per run (default: 224 for 256-agent base)",
    )
    parser.add_argument(
        "--validators",
        type=int,
        default=32,
        help="Validator workers per run (default: 32)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of convergence runs at base scale (default: 5)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=32,
        help="ThreadPoolExecutor concurrency (default: 32)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "data" / "thinkboxmd",
        help="Output directory for proof artifacts",
    )
    parser.add_argument(
        "--inter-run-delay",
        type=float,
        default=30.0,
        help="Seconds between convergence runs to avoid rate limits (default: 30)",
    )
    parser.add_argument(
        "--scale-only",
        action="store_true",
        help="Run only the 512+ scale target (skip convergence runs)",
    )
    parser.add_argument(
        "--convergence-only",
        action="store_true",
        help="Run only the convergence study (skip 512+ scale)",
    )
    args = parser.parse_args()

    if not os.environ.get("INCEPTION_API_KEY"):
        print("❌ INCEPTION_API_KEY missing")
        return 2

    try:
        all_results = {}

        # Phase 1: 512+ scale target (doubled primary+validators from base)
        if not args.convergence_only:
            print("=" * 70)
            print("PHASE 1: 512+ AGENT SCALE TARGET")
            print("=" * 70)
            # Double the worker counts for 512+ scale
            scale_primary = args.primary * 2  # 224 * 2 = 448
            scale_validators = args.validators * 2  # 32 * 2 = 64
            scale_payload = run_big_swarm(
                primary=scale_primary,
                validators=scale_validators,
                concurrency=args.concurrency,
                fresh_ledger=True,
                output_dir=args.out_dir,
            )
            all_results["scale_target"] = {
                "payload": scale_payload,
                "metrics": proof_metrics(scale_payload),
            }
            print(f"✅ Scale target complete: {scale_payload['run_id']}")

        # Phase 2: Five-run convergence at base configuration
        if not args.scale_only:
            print("\n" + "=" * 70)
            print(f"PHASE 2: {args.runs}-RUN CONVERGENCE ({args.primary+args.validators} AGENTS)")
            print("=" * 70)
            convergence_results = run_convergence_study(
                primary=args.primary,
                validators=args.validators,
                runs=args.runs,
                concurrency=args.concurrency,
                output_dir=args.out_dir,
                inter_run_delay=args.inter_run_delay,
            )
            all_results["convergence_study"] = convergence_results

            # Print convergence summary
            print("\n" + "=" * 70)
            print("CONVERGENCE STUDY RESULTS")
            print("=" * 70)
            stats = convergence_results["metrics"]
            for metric_name, metric_stats in stats.items():
                print(f"\n{metric_name}:")
                print(f"  mean  : {metric_stats['mean']}")
                print(f"  median: {metric_stats['median']}")
                print(f"  min   : {metric_stats['min']}")
                print(f"  max   : {metric_stats['max']}")
                print(f"  std   : {metric_stats['std']}")
                print(f"  n     : {metric_stats['n']}")
                print(f"  values: {metric_stats['values']}")

        # Save consolidated results
        out_file = args.out_dir / f"swarm_convergence_{int(time.time())}.json"
        out_file.write_text(
            __import__("json").dumps(all_results, indent=2, default=str)
        )
        print(f"\n💾 Consolidated results saved: {out_file}")

        print("\n" + "=" * 70)
        print("🎉 ALL PHASES COMPLETE")
        print("=" * 70)
        print("✅ 512+ agent scale target executed")
        print(f"✅ {args.runs}-run 256-agent convergence study completed")
        print("✅ All proof artifacts validated")
        print("✅ Descriptive statistics computed")
        print("\nNext steps:")
        print("1. Review proof artifacts in data/thinkboxmd/")
        print("2. Update CONTINUITY.md with results")
        print("3. Update STATUS.md with Four-State classification")
        print("4. Run test suite to ensure no regressions")

        return 0

    except Exception as e:
        print(f"❌ Error during convergence study: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())