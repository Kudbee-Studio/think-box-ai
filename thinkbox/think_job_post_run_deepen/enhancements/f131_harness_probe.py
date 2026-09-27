"""Probe F131 hermetic harness importability."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT


def f131_harness_probe() -> dict[str, Any]:
    path = REPO_ROOT / "tests/e2e/test_f131_post_run_think_job_contract.py"
    return {
        "contract_tests_present": path.is_file(),
        "live_api_called": False,
    }
