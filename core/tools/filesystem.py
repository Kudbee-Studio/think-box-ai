"""Filesystem tools for THINK BOX AI."""

from __future__ import annotations

import os
from typing import Any

from core.tools.registry import ToolDefinition, tool


def _read_file_sync(file_path: str) -> tuple[str | None, int | None, str | None]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content, len(content), None
    except FileNotFoundError:
        return None, None, f"File not found: {file_path}"
    except Exception as e:
        return None, None, str(e)


def _write_file_sync(file_path: str, content: str, mode: str) -> tuple[str | None, int | None, str | None]:
    try:
        write_mode = "a" if mode == "append" else "w"
        with open(file_path, write_mode, encoding="utf-8") as f:
            f.write(content)
        return file_path, len(content.encode("utf-8")), None
    except Exception as e:
        return None, None, str(e)


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
    content, size, error = await __import__('asyncio').to_thread(_read_file_sync, file_path)
    if error:
        return {"success": False, "error": error}
    return {"success": True, "content": content, "path": file_path, "size": size}


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
    path, size, error = await __import__('asyncio').to_thread(_write_file_sync, file_path, content, mode)
    if error:
        return {"success": False, "error": error}
    return {"success": True, "path": path, "bytes_written": size}
