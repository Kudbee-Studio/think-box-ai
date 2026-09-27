#!/usr/bin/env python3
"""Hermetic Trait Lab autonomous app regression verify (PR #228)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.autonomous_app_regression import trait_lab_autonomous_app_regression_contract_summary


def main() -> int:
    summary = trait_lab_autonomous_app_regression_contract_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary.get("hermetic_operator_ok") or summary.get("ops_count") != 25:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
