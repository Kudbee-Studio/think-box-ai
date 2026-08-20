"""Filesystem tools for THINK BOX AI."""

from __future__ import annotations

import os
from typing import Any

from core.tools.registry import ToolDefinition, tool


@tool(
    name="file_read",
    description="Read contents of a file",
    permission="read_only",
    input_schema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
)
async def file_read(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    file_path = args.get("path", "")
    if not file_path:
        return {"success": False, "error": "Missing 'path' argument"}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"success": True, "content": content, "path": file_path, "size": len(content)}
    except FileNotFoundError:
        return {"success": False, "error": f"File not found: {file_path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(
    name="file_write",
    description="Write content to a file",
    permission="read_write",
    requires_approval=True,
    input_schema={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "mode": {"type": "string"}}, "required": ["path", "content"]},
)
async def file_write(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    file_path = args.get("path", "")
    content = args.get("content", "")
    mode = args.get("mode", "write")
    if not file_path:
        return {"success": False, "error": "Missing 'path' argument"}
    try:
        write_mode = "a" if mode == "append" else "w"
        with open(file_path, write_mode, encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": file_path, "bytes_written": len(content.encode("utf-8"))}
    except Exception as e:
        return {"success": False, "error": str(e)}
