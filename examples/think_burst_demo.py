#!/usr/bin/env python3
"""Offline THINK burst demo — no GPU, no network.

Run:
    python3 examples/think_burst_demo.py

Produces grounded vs ungrounded contrast pairs as jsonl under
data/evals/burst/ and prints the burst report.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from thinkbox.burst import BurstConfig, BurstRunner
from thinkbox.harvest import HarvestReplay
from thinkbox.ledger import ActionLedger


def main() -> None:
    config = BurstConfig(max_pairs=4, max_calls=16, max_spend=0.5, output_dir="data/evals/burst")
    report = BurstRunner(config=config, ledger=ActionLedger(":memory:")).run()
    print(report.to_markdown())

    print("=== Harvest replay ===")
    harvest = HarvestReplay().replay_dir(config.output_dir)
    print(harvest.to_markdown())


if __name__ == "__main__":
    main()