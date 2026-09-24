"""Run PR #185 unit tests locally."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT


def run_unit_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.unit.test_think_job_pr185_fixes",
            "tests.unit.test_kilo_live_proof_readiness_pr185",
            "tests.unit.test_think_job_pr185_local_env",
            "-v",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "step": "unit_tests",
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "live_api_called": False,
    }
