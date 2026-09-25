#!/usr/bin/env python3
"""Hermetic Trait Lab autonomous worker executor verify (PR #230)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.autonomous_worker_executor import trait_lab_autonomous_worker_executor_contract_summary


def main() -> int:
    summary = trait_lab_autonomous_worker_executor_contract_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary.get("hermetic_operator_ok"):
        return 1
    if summary.get("ops_count") != 25:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())