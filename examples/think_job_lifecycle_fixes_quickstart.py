#!/usr/bin/env python3
"""Quickstart for PR #185 Think Job lifecycle fix pack (hermetic)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_pr185_think_job_lifecycle_fixes import think_job_lifecycle_fixes_contract_summary
from thinkbox.think_job_lifecycle_fixes.lifecycle_status_report import (
    think_job_lifecycle_fixes_status_report,
)


def main() -> None:
    print(json.dumps(think_job_lifecycle_fixes_contract_summary(), indent=2, sort_keys=True))
    print(json.dumps(think_job_lifecycle_fixes_status_report(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
