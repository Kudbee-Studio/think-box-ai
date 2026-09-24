"""Required governance JSON fields catalog."""

from __future__ import annotations

from typing import Any

REQUIRED_FIELDS: tuple[str, ...] = ("goal", "agent_id", "governance_token")


def governance_fields_catalog() -> dict[str, Any]:
    return {
        "required_fields": list(REQUIRED_FIELDS),
        "live_api_called": False,
    }
