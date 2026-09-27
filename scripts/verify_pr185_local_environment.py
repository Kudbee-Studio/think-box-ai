#!/usr/bin/env python3
"""Verify PR #185 local environment workflow (hermetic)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_pr185_think_job_lifecycle_fixes import local_environment_contract_summary


def main() -> int:
    summary = local_environment_contract_summary(run_workflow=True)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary.get("local_environment_ok"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
