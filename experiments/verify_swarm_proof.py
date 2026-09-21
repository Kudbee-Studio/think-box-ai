#!/usr/bin/env python3
"""Validate a big_swarm proof JSON (accounting, RPS, worker rows)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from thinkbox.swarm_stats import load_and_validate_proof


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate KILO big_swarm proof JSON")
    ap.add_argument("proof", type=Path, help="path to big_swarm_*.json")
    args = ap.parse_args()
    if not args.proof.is_file():
        print(f"not found: {args.proof}")
        return 2
    payload, errors = load_and_validate_proof(args.proof)
    if errors:
        for err in errors:
            print(f"INVALID: {err}")
        return 1
    recon = payload["reconciliation"]
    print(f"OK {payload['run_id']} calls={recon['total_calls']} ok={recon['ok']} rps={recon['effective_rps']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
