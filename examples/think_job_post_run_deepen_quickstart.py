#!/usr/bin/env python3
"""Hermetic Think Job POST /run deepen quickstart (PR #184)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_pr184_think_job_post_run_deepen import think_job_post_run_deepen_contract_summary
from thinkbox.think_job_post_run_deepen.deepen_status_report import run_hermetic_deepen_demo
from thinkbox.think_job_post_run_deepen.fixes.fix_registry import run_all_fixes
from thinkbox.think_job_post_run_deepen.integrate import run_feature_demo


def main() -> None:
    demo = run_feature_demo("dry_run")
    report = run_hermetic_deepen_demo()
    fixes = run_all_fixes()
    gate = think_job_post_run_deepen_contract_summary()
    print(
        json.dumps(
            {
                "dry_run": demo,
                "major_fix_count": fixes.get("fix_count"),
                "gate_ok": gate.get("hermetic_operator_ok"),
                "live_verified": report.get("live_verified"),
                "live_api_called": report.get("live_api_called"),
            },
            indent=2,
            sort_keys=True,
        ),
    )


if __name__ == "__main__":
    main()
