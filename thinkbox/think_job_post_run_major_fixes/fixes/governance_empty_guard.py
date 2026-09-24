"""FIX04: governance empty guard."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_post_run_deepen.fixes.governance_empty_guard import apply_fix as inner
    return {**inner(), "fix_id": "FIX04"}
