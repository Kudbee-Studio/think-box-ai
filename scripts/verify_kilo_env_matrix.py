#!/usr/bin/env python3
"""Print KILO env-matrix contract summary (PR #142, hermetic operator gate)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_env_matrix import env_matrix_contract_summary


def main() -> int:
    summary = env_matrix_contract_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary.get("hermetic_operator_ok"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
