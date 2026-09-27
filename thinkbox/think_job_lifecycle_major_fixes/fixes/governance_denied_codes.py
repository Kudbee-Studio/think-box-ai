"""FIX04: governance denial codes stable."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_governed_run_fixes.fixes.governance_denied_codes import apply_fix as inner
    return {**inner(), "fix_id": "FIX04"}
