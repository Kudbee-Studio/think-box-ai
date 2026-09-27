"""F131 e2e harness bridge (PR #184 F21)."""
from __future__ import annotations
from typing import Any

def e2e_bridge() -> dict[str, Any]:
    return {
        "harness": "tests.e2e.api_run_hermetic",
        "contract_tests": "tests.e2e.test_f131_post_run_think_job_contract",
        "live_api_called": False,
    }
