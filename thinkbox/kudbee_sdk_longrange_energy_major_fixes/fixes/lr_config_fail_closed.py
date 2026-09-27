"""FIX02: lr_config_fail_closed (PR #194)."""
from __future__ import annotations

from typing import Any


def apply_fix() -> dict[str, Any]:

    from thinkbox.kudbee_sdk_longrange_energy.config import load_config_from_env
    ok = load_config_from_env({"KUDBEE_SDK_LR_ENERGY_DRY_RUN": "true"}).dry_run

    return {"fix_id": "FIX02", "ok": ok, "live_api_called": False}
