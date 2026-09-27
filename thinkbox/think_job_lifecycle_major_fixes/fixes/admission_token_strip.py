"""FIX03: admission token whitespace guard."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_lifecycle_fixes.fixes.whitespace_admission_token import apply_fix as inner
    return {**inner(), "fix_id": "FIX03"}
