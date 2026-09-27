"""Offline event filter helpers (PR #180 F12)."""

from __future__ import annotations

from typing import Any


def filter_events(
    events: list[dict[str, Any]],
    *,
    event_type: str | None = None,
    min_id: int | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ev in events:
        if event_type is not None and ev.get("type") != event_type:
            continue
        eid = ev.get("id")
        if min_id is not None and isinstance(eid, int) and eid < min_id:
            continue
        out.append(ev)
    return out
