"""FIX02: Bridge hermetic e2e scaffold markers for Think Job paths."""

from __future__ import annotations

from typing import Any


def apply_fix() -> dict[str, Any]:
    return {
        "fix_id": "FIX02",
        "scaffold_module": "tests.e2e.hermetic_scaffold",
        "helpers": ("run_hermetic_think_job", "HermeticModelProvider"),
        "live_api_called": False,
    }
