"""DEP24: fixture_conservation_sample deepen pack (PR #193)."""
from __future__ import annotations


def activate_pack() -> dict[str, object]:

    ok = True

    return {"pack_id": "DEP24", "ok": ok, "live_api_called": False}
