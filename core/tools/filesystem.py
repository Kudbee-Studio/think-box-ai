"""Filesystem tools for THINK BOX AI.

When HARNESS=1 and the tool context carries a harness_runner + container_id,
file writes are executed inside the container so host filesystem is not mutated.
Reads still happen on host (the container has no access to host files).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from core.tools.registry import ToolDefinition, tool

logger = logging.getLogger("thinkbox.tools.filesystem")


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


def _harness_context(context: dict[str, Any] | None) -> tuple[Any, str] | None:
    if not context:
        return None
    runner = context.get("harness_runner")
    container_id = context.get("harness_container_id")
    if runner is not None and container_id is not None:
        return runner, container_id
    return None


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

    harness = _harness_context(context)
    if harness is not None:
        runner, container_id = harness
        import base64
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        argv = ["sh", "-c", f"echo {encoded} | base64 -d > {file_path}"]
        if mode == "append":
            argv = ["sh", "-c", f"echo {encoded} | base64 -d >> {file_path}"]
        result = await runner.exec_in_container(container_id, argv, timeout=30)
        logger.info(
            "file_write_harness path=%s rc=%d",
            file_path, result.get("return_code", -1),
        )
        if not result["success"]:
            return {"success": False, "error": result.get("stderr", result.get("error", "harness write failed"))}
        return {"success": True, "path": file_path, "bytes_written": len(content.encode("utf-8"))}

    path, size, error = await __import__('asyncio').to_thread(_write_file_sync, file_path, content, mode)
    if error:
        return {"success": False, "error": error}
    return {"success": True, "path": path, "bytes_written": size}
