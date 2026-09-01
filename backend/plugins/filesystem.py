"""Filesystem plugin for Think Box AI.

All filesystem operations are path-jailed to the project root.
Prevents directory traversal attacks.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from backend.plugins.base import Tool, ToolResult

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_ALLOWED_ROOTS = [_REPO_ROOT, _REPO_ROOT / "data"]


def _jail_path(path_str: str) -> Path:
    """Resolve path ensuring it stays within allowed roots."""
    path = Path(path_str)
    if path.is_absolute():
        resolved = path.resolve()
    else:
        resolved = (_REPO_ROOT / path).resolve()

    for allowed in _ALLOWED_ROOTS:
        try:
            resolved.relative_to(allowed.resolve())
            return resolved
        except ValueError:
            continue
    raise PermissionError(
        f"Path '{path_str}' is outside allowed directories. "
        f"Allowed roots: {[str(r) for r in _ALLOWED_ROOTS]}"
    )


class FileReadTool(Tool):
    name = "file_read"
    description = "Read contents of a file (path-jailed to project root)"
    permission = "read_only"
    requires_approval = False

    async def run(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        file_path = args.get("path", "")
        if not file_path:
            return ToolResult(success=False, error="Missing 'path' argument")

        try:
            resolved = _jail_path(file_path)
            if not resolved.exists():
                return ToolResult(success=False, error=f"File not found: {file_path}")
            content = resolved.read_text(encoding="utf-8", errors="replace")
            return ToolResult(success=True, data={"content": content, "path": str(resolved.relative_to(_REPO_ROOT)), "size": len(content)})
        except PermissionError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileWriteTool(Tool):
    name = "file_write"
    description = "Write content to a file (path-jailed to project root)"
    permission = "read_write"
    requires_approval = True

    async def run(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        file_path = args.get("path", "")
        content = args.get("content", "")
        mode = args.get("mode", "write")

        if not file_path:
            return ToolResult(success=False, error="Missing 'path' argument")

        try:
            resolved = _jail_path(file_path)
            resolved.parent.mkdir(parents=True, exist_ok=True)
            write_mode = "a" if mode == "append" else "w"
            with open(resolved, write_mode, encoding="utf-8") as f:
                f.write(content)
            return ToolResult(success=True, data={"path": str(resolved.relative_to(_REPO_ROOT)), "bytes_written": len(content.encode("utf-8"))})
        except PermissionError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileListTool(Tool):
    name = "file_list"
    description = "List directory contents (path-jailed to project root)"
    permission = "read_only"
    requires_approval = False

    async def run(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        dir_path = args.get("path", ".")
        try:
            resolved = _jail_path(dir_path)
            if not resolved.is_dir():
                return ToolResult(success=False, error=f"Not a directory: {dir_path}")
            items = []
            for item in sorted(resolved.iterdir()):
                items.append({
                    "name": item.name,
                    "is_directory": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else 0,
                })
            return ToolResult(success=True, data={"files": items, "path": str(resolved.relative_to(_REPO_ROOT))})
        except PermissionError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=str(e))
