"""Filesystem plugin for kudbEE."""

from __future__ import annotations

import os
from typing import Any

from backend.plugins.base import Tool, ToolResult


class FileReadTool(Tool):
    name = "file_read"
    description = "Read contents of a file"
    permission = "read_only"
    requires_approval = False

    async def run(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        file_path = args.get("path", "")
        if not file_path:
            return ToolResult(success=False, error="Missing 'path' argument")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return ToolResult(success=True, data={"content": content, "path": file_path, "size": len(content)})
        except FileNotFoundError:
            return ToolResult(success=False, error=f"File not found: {file_path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileWriteTool(Tool):
    name = "file_write"
    description = "Write content to a file"
    permission = "read_write"
    requires_approval = True

    async def run(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        file_path = args.get("path", "")
        content = args.get("content", "")
        mode = args.get("mode", "write")  # write | append

        if not file_path:
            return ToolResult(success=False, error="Missing 'path' argument")

        try:
            write_mode = "a" if mode == "append" else "w"
            with open(file_path, write_mode, encoding="utf-8") as f:
                f.write(content)
            return ToolResult(success=True, data={"path": file_path, "bytes_written": len(content.encode("utf-8"))})
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileListTool(Tool):
    name = "file_list"
    description = "List directory contents"
    permission = "read_only"
    requires_approval = False

    async def run(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        dir_path = args.get("path", ".")
        try:
            items = []
            for item in sorted(os.listdir(dir_path)):
                full_path = os.path.join(dir_path, item)
                items.append({
                    "name": item,
                    "is_directory": os.path.isdir(full_path),
                    "size": os.path.getsize(full_path) if os.path.isfile(full_path) else 0,
                })
            return ToolResult(success=True, data={"files": items, "path": dir_path})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
