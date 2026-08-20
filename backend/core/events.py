"""Event types for kudbEE agent OS."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(str, Enum):
    THOUGHT = "THOUGHT"
    TOKEN = "TOKEN"
    TOOL_CALL = "TOOL_CALL"
    TOOL_RESULT = "TOOL_RESULT"
    FILE_UPDATE = "FILE_UPDATE"
    TASK_UPDATE = "TASK_UPDATE"
    MEMORY_UPDATE = "MEMORY_UPDATE"
    RISKY_ACTION = "RISKY_ACTION"
    STATUS = "STATUS"


def create_event(event_type: EventType, data: dict[str, Any]) -> dict[str, Any]:
    """Create a standardized event."""
    return {
        "type": event_type.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
