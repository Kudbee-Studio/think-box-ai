"""Registry of local environment steps (PR #185)."""

from __future__ import annotations

from typing import Any, Callable

from thinkbox.think_job_lifecycle_fixes.local.editable_install import editable_install_ok
from thinkbox.think_job_lifecycle_fixes.local.env_matrix import redacted_env_matrix
from thinkbox.think_job_lifecycle_fixes.local.python_version import python_version_ok
from thinkbox.think_job_lifecycle_fixes.local.run_all_fixes import run_fixes_smoke
from thinkbox.think_job_lifecycle_fixes.local.run_quickstart import run_quickstart
from thinkbox.think_job_lifecycle_fixes.local.run_unit_tests import run_unit_tests
from thinkbox.think_job_lifecycle_fixes.local.run_verify_gate import run_verify_gate
from thinkbox.think_job_lifecycle_fixes.local.venv_detect import venv_status

StepFn = Callable[[], dict[str, Any]]

LOCAL_STEPS: tuple[StepFn, ...] = (
    python_version_ok,
    venv_status,
    editable_install_ok,
    redacted_env_matrix,
    run_fixes_smoke,
    run_verify_gate,
    run_unit_tests,
    run_quickstart,
)


def run_all_local_steps() -> dict[str, Any]:
    results = [fn() for fn in LOCAL_STEPS]
    ok = all(r.get("ok") for r in results if r.get("step") != "venv_detect")
    venv_ok = next(r for r in results if r.get("step") == "venv_detect")
    return {
        "step_count": len(results),
        "all_ok": ok and venv_ok.get("ok", True),
        "results": results,
        "live_api_called": False,
        "live_verified": False,
    }
