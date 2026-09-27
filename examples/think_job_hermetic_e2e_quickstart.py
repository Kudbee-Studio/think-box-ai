#!/usr/bin/env python3
"""Hermetic Think Job e2e deepen quickstart (PR #183)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_pr183_think_job_hermetic_e2e import think_job_hermetic_e2e_contract_summary
from thinkbox.think_job_e2e_deepen.deepen_status_report import run_hermetic_deepen_demo
from thinkbox.think_job_e2e_deepen.fixes.fix_registry_integrate import run_all_fixes
from thinkbox.think_job_e2e_deepen.integrate import run_feature_demo


def main() -> None:
    demo = run_feature_demo("cassette")
    report = run_hermetic_deepen_demo()
    fixes = run_all_fixes()
    gate = think_job_hermetic_e2e_contract_summary()
    print(
        json.dumps(
            {
                "cassette": demo,
                "major_fix_count": fixes.get("fix_count"),
                "status": {
                    "live_verified": report.get("live_verified"),
                    "live_api_called": report.get("live_api_called"),
                },
                "gate_ok": gate.get("hermetic_operator_ok"),
            },
            indent=2,
            sort_keys=True,
        ),
    )


if __name__ == "__main__":
    main()
