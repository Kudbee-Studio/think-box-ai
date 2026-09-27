"""WebSocket message envelope validation (PR #177 F14)."""

from __future__ import annotations

from typing import Any

from thinkbox.kudbee_sdk.errors import validation_error
from thinkbox.kudbee_sdk.schema import validate_json

_WS_ENVELOPE_SCHEMA = {
    "type": "object",
    "required": ["type"],
    "properties": {
        "type": {"type": "string"},
        "timestamp": {"type": "number"},
        "data": {"type": "object"},
    },
}


def validate_ws_message(msg: dict[str, Any]) -> None:
    validate_json(msg, _WS_ENVELOPE_SCHEMA)
    if not msg["type"].strip():
        raise validation_error("ws type must be non-empty")
