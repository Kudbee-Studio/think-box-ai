"""Execute fix registry in-process for local smoke."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_lifecycle_fixes.fixes.fix_registry import run_all_fixes


def run_fixes_smoke() -> dict[str, Any]:
    result = run_all_fixes()
    ok = result.get("fix_count") == 25 and result.get("all_hermetic") is True
    return {
        "step": "fixes_smoke",
        "ok": ok,
        "fix_count": result.get("fix_count"),
        "live_api_called": False,
    }
