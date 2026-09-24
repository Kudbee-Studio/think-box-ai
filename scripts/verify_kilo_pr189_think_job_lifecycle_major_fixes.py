#!/usr/bin/env python3
"""Hermetic Think Job lifecycle major fixes gate verify (PR #189)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_pr189_think_job_lifecycle_major_fixes import (
    think_job_lifecycle_major_fixes_contract_summary,
)


def main() -> int:
    summary = think_job_lifecycle_major_fixes_contract_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary.get("hermetic_operator_ok"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
