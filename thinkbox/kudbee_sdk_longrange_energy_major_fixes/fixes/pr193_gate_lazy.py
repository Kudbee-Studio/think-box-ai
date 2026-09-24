"""FIX01: pr193_gate_lazy (PR #194)."""
from __future__ import annotations

from typing import Any


def apply_fix() -> dict[str, Any]:

    from thinkbox import kilo_pr193_kudbee_sdk_longrange_energy as pr193
    ok, _ = pr193.validate_features_manifest()

    return {"fix_id": "FIX01", "ok": ok, "live_api_called": False}
