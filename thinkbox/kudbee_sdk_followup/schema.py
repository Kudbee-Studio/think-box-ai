"""Lightweight JSON schema validation for SDK payloads (PR #179 F08)."""

from __future__ import annotations

from typing import Any

from thinkbox.kudbee_sdk_followup.errors import validation_error


def _check_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    return False


def validate_json(data: Any, schema: dict[str, Any]) -> None:
    """Validate ``data`` against a minimal JSON-schema subset."""
    schema_type = schema.get("type")
    if schema_type and not _check_type(data, schema_type):
        raise validation_error("type mismatch", expected=schema_type, got=type(data).__name__)

    if schema_type == "object":
        props = schema.get("properties") or {}
        required = schema.get("required") or []
        for key in required:
            if key not in data:
                raise validation_error("missing required field", field=key)
        for key, sub in props.items():
            if key in data:
                validate_json(data[key], sub)

    if schema_type == "array" and data:
        item_schema = schema.get("items") or {}
        for idx, item in enumerate(data):
            try:
                validate_json(item, item_schema)
            except Exception as exc:
                raise validation_error("array item invalid", index=idx, detail=str(exc)) from exc
