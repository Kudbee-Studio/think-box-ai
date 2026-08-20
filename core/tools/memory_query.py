"""Memory query tool for THINK BOX AI."""

from __future__ import annotations

from typing import Any

from core.tools.registry import ToolDefinition, tool


@tool(
    name="memory_query",
    description="Query memory store by key",
    permission="read_only",
    input_schema={"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
)
def memory_query(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    store = context.get("memory_store")
    if store is None:
        return {"success": False, "error": "No memory store available in context"}
    key = args.get("key", "")
    if not key:
        return {"success": False, "error": "Missing 'key' argument"}
    try:
        entry = store.get(key)
        if entry is None:
            return {"success": False, "error": f"Key not found: {key}"}
        return {"success": True, "key": key, "value": entry.value, "layer": entry.layer.value}
    except Exception as e:
        return {"success": False, "error": str(e)}
