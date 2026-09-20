"""CI timeline ordering and completeness checks."""

from __future__ import annotations

from typing import Any


def validate_ci_timeline(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Ensure chronological order and flag gaps."""
    ordered = True
    prev_ts = ""
    for ev in events:
        ts = str(ev.get("timestamp") or "")
        if prev_ts and ts < prev_ts:
            ordered = False
            break
        prev_ts = ts
    missing_conclusion = sum(1 for e in events if not e.get("conclusion"))
    return {
        "event_count": len(events),
        "chronological": ordered,
        "missing_conclusion_count": missing_conclusion,
        "complete": ordered and missing_conclusion == 0,
        "evidence_label": "simulated",
    }
