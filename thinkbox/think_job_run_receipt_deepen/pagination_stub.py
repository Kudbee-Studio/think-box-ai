"""Receipt list pagination stub (PR #186 F19)."""
from __future__ import annotations

def page_slice(items: list[object], limit: int = 50) -> list[object]:
    return items[: max(0, limit)]
