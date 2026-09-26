#!/usr/bin/env python3
"""Analyze 1K-agent scale test results.

Reads a proof artifact from scale_1k.py and produces a regression report
comparing against baseline (256-agent run).

Usage:
    python3 scripts/analyze_scale_1k.py data/thinkboxmd/big_swarm_1k_*.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class ScaleAnalyzer:
    """Analyze scale test results."""

    BASELINE_256_AGENT = {
        "throughput_rps": 27.25,
        "success_rate": 0.984,  # 256/260 OK
        "p50_latency_s": 0.45,
        "p95_latency_s": 1.86,
        "max_latency_s": 2.31,
        "ledger_verify_time_ms": 150,
    }

    def __init__(self, proof_path: Path) -> None:
        """Initialize analyzer with proof artifact."""
        self.proof_path = proof_path
        self.payload = json.loads(proof_path.read_text())
        self.recon = self.payload.get("reconciliation", {})

    def analyze(self) -> dict[str, Any]:
        """Analyze the proof and produce report."""
        metrics = self.recon

        success_rate = metrics.get("ok", 0) / max(1, metrics.get("total_calls", 1))
        rps = metrics.get("effective_rps", 0.0)
        p50_lat = metrics.get("p50_latency_s", 0.0)
        p95_lat = metrics.get("p95_latency_s", metrics.get("max_latency_s", 0.0))
        max_lat = metrics.get("max_latency_s", 0.0)
        ledger_valid = metrics.get("ledger_valid", False)

        # Calculate scale factor
        total_workers = metrics.get("total_calls", 1000)
        scale_factor = total_workers / 256.0

        # Regression analysis
        expected_rps = self.BASELINE_256_AGENT["throughput_rps"] * scale_factor
        rps_regression = ((rps - expected_rps) / expected_rps * 100) if expected_rps > 0 else 0.0

        report = {
            "test_id": self.payload.get("run_id", "unknown"),
            "session_id": self.payload.get("session_id", "unknown"),
            "scale_target": self.payload.get("scale_target", 1000),
            "timestamp": self.payload.get("run_id", "").split("_")[-1] if "_" in self.payload.get("run_id", "") else "unknown",

            # Basic metrics
            "total_workers": metrics.get("total_calls", 0),
            "primary_workers": metrics.get("primary_calls", 0),
            "validator_workers": metrics.get("validator_calls", 0),
            "workers_ok": metrics.get("ok", 0),
            "workers_failed": metrics.get("failed", 0),

            # Success rate
            "success_rate": round(success_rate * 100, 1),
            "success_rate_pass": success_rate >= 0.90,

            # Throughput (RPS)
            "throughput_rps": round(rps, 2),
            "expected_rps": round(expected_rps, 2),
            "rps_regression_pct": round(rps_regression, 1),
            "throughput_pass": rps >= expected_rps * 0.9,  # Allow 10% regression

            # Latency
            "latency_p50_s": p50_lat,
            "latency_p95_s": p95_lat,
            "latency_max_s": max_lat,
            "latency_pass": p95_lat < 3.0,  # p95 < 3s expected

            # Ledger
            "ledger_entries": metrics.get("ledger_entries", 0),
            "ledger_entries_this_run": metrics.get("ledger_entries_this_run", 0),
            "ledger_valid": ledger_valid,
            "ledger_pass": ledger_valid,

            # Memory / traces
            "traces_total": metrics.get("traces", 0),
            "traces_grounded": metrics.get("traces_grounded", 0),
            "memory_entries": metrics.get("memory_entries", 0),

            # Tokens
            "total_tokens": metrics.get("total_tokens", 0),
            "reasoning_tokens": metrics.get("reasoning_tokens", 0),

            # Timing
            "elapsed_s": metrics.get("elapsed_s", 0),
            "wall_clock_s": self.payload.get("wave1_seconds", 0) + self.payload.get("wave2_seconds", 0),

            # Verification
            "disagreements": metrics.get("disagreements", 0),
            "tier_inflation": metrics.get("tier_inflation_by_validator", 0),
            "tier_distribution": metrics.get("tier_distribution", {}),

            # Pass/fail assessment
            "overall_pass": (
                success_rate >= 0.90 and
                rps >= expected_rps * 0.9 and
                p95_lat < 3.0 and
                ledger_valid
            ),
        }

        return report

    def format_report(self, report: dict[str, Any]) -> str:
        """Format analysis report as human-readable text."""
        lines = []

        lines.append("=" * 66)
        lines.append("SCALE 1K TEST ANALYSIS REPORT")
        lines.append("=" * 66)

        lines.append(f"\nTest ID: {report['test_id']}")
        lines.append(f"Session: {report['session_id']}")
        lines.append(f"Scale Target: {report['scale_target']} agents")

        lines.append("\n--- WORKERS ---")
        lines.append(f"  Total:     {report['total_workers']} ({report['primary_workers']} primary + {report['validator_workers']} validators)")
        lines.append(f"  OK:        {report['workers_ok']}")
        lines.append(f"  Failed:    {report['workers_failed']}")

        lines.append("\n--- SUCCESS RATE ---")
        lines.append(f"  Achieved:  {report['success_rate']:.1f}%")
        lines.append(f"  Target:    ≥90.0%")
        lines.append(f"  Status:    {'✓ PASS' if report['success_rate_pass'] else '✗ FAIL'}")

        lines.append("\n--- THROUGHPUT (RPS) ---")
        lines.append(f"  Achieved:  {report['throughput_rps']:.2f} RPS")
        lines.append(f"  Expected:  {report['expected_rps']:.2f} RPS (256-agent baseline × {report['total_workers']/256:.1f}×)")
        lines.append(f"  Regression: {report['rps_regression_pct']:+.1f}%")
        lines.append(f"  Status:    {'✓ PASS' if report['throughput_pass'] else '✗ FAIL'}")

        lines.append("\n--- LATENCY ---")
        lines.append(f"  p50:       {report['latency_p50_s']:.3f}s")
        lines.append(f"  p95:       {report['latency_p95_s']:.3f}s (target: <3.0s)")
        lines.append(f"  Max:       {report['latency_max_s']:.3f}s")
        lines.append(f"  Status:    {'✓ PASS' if report['latency_pass'] else '✗ FAIL'}")

        lines.append("\n--- LEDGER ---")
        lines.append(f"  Entries:   {report['ledger_entries']} (this run: {report['ledger_entries_this_run']})")
        lines.append(f"  Valid:     {report['ledger_valid']}")
        lines.append(f"  Status:    {'✓ PASS' if report['ledger_pass'] else '✗ FAIL'}")

        lines.append("\n--- MEMORY & TRACES ---")
        lines.append(f"  Traces:    {report['traces_total']} (grounded: {report['traces_grounded']})")
        lines.append(f"  Memory:    {report['memory_entries']} entries")

        lines.append("\n--- TOKENS ---")
        lines.append(f"  Total:     {report['total_tokens']:,}")
        lines.append(f"  Reasoning: {report['reasoning_tokens']:,}")

        lines.append("\n--- TIMING ---")
        lines.append(f"  Wall clock: {report['wall_clock_s']:.2f}s")
        lines.append(f"  Total:      {report['elapsed_s']:.2f}s")

        lines.append("\n--- CONSENSUS ---")
        lines.append(f"  Disagreements:     {report['disagreements']}")
        lines.append(f"  Tier inflation:    {report['tier_inflation']}")

        lines.append("\n--- OVERALL ASSESSMENT ---")
        status = "✓ PASS" if report['overall_pass'] else "✗ FAIL"
        lines.append(f"  {status}")

        if not report['overall_pass']:
            failures = []
            if not report['success_rate_pass']:
                failures.append(f"  - Success rate too low: {report['success_rate']:.1f}% < 90%")
            if not report['throughput_pass']:
                failures.append(f"  - Throughput regression: {report['rps_regression_pct']:+.1f}%")
            if not report['latency_pass']:
                failures.append(f"  - Latency high: {report['latency_p95_s']:.3f}s > 3.0s")
            if not report['ledger_pass']:
                failures.append(f"  - Ledger verification failed")
            if failures:
                lines.append("\nFailure reasons:")
                lines.extend(failures)

        lines.append("\n" + "=" * 66)
        return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("proof_path", type=Path, help="Path to proof artifact JSON")
    ap.add_argument("--json", action="store_true", help="Output JSON instead of text")
    args = ap.parse_args()

    if not args.proof_path.exists():
        print(f"ERROR: {args.proof_path} not found")
        return 1

    analyzer = ScaleAnalyzer(args.proof_path)
    report = analyzer.analyze()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(analyzer.format_report(report))

    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
