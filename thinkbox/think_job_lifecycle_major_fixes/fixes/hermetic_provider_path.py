"""FIX05: hermetic provider path."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_governed_run_fixes.fixes.hermetic_provider_path import apply_fix as inner
    return {**inner(), "fix_id": "FIX05"}
