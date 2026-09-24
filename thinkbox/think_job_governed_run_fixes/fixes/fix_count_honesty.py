"""FIX24: Fix registry count honesty."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kilo_pr188_think_job_governed_run_major_fixes import EXPECTED_FIX_COUNT
    from thinkbox.think_job_governed_run_fixes.fixes.fix_registry import _MODULES

    return {
        "fix_id": "FIX24",
        "ok": len(_MODULES) + 1 == EXPECTED_FIX_COUNT,
        "live_api_called": False,
    }
