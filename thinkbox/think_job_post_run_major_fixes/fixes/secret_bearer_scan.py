"""FIX18: secret scan helper."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_governed_run_fixes.fixes.secret_bearer_scan import apply_fix as inner
    return {**inner(), "fix_id": "FIX18"}
