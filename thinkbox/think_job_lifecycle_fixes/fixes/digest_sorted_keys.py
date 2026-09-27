"""FIX17: Jobs digest keys sorted for stable ETag."""
from __future__ import annotations
from typing import Any

def stable_digest_keys(keys: list[str]) -> list[str]:
    return sorted(keys)

def apply_fix() -> dict[str, Any]:
    keys = stable_digest_keys(["b", "a", "c"])
    return {"fix_id": "FIX17", "sorted": keys == ["a", "b", "c"], "live_api_called": False}
