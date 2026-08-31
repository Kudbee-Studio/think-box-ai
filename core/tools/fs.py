"""Filesystem tools for THINK BOX AI — path-jailed to repo root."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from core.tools.registry import tool

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
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
    raise PermissionError(f"Path '{path_str}' is outside allowed directories")


@tool(
    name="fs_read",
    description="Read a file. Path must be within the repo or data/ directory.",
    permission="read_only",
    input_schema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
)
async def fs_read(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    path_str = args.get("path", "")
    if not path_str:
        return {"success": False, "error": "Missing 'path' argument"}
    try:
        resolved = _jail_path(path_str)
        if not resolved.exists():
            return {"success": False, "error": f"File not found: {path_str}"}
        content = resolved.read_text(encoding="utf-8", errors="replace")
        return {"success": True, "content": content, "path": str(resolved.relative_to(_REPO_ROOT)), "size": len(content)}
    except PermissionError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(
    name="fs_write",
    description="Write content to a file under data/ or the repo. Creates parent dirs.",
    permission="read_write",
    requires_approval=False,
    input_schema={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
)
async def fs_write(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    path_str = args.get("path", "")
    content = args.get("content", "")
    if not path_str:
        return {"success": False, "error": "Missing 'path' argument"}
    try:
        resolved = _jail_path(path_str)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return {"success": True, "path": str(resolved.relative_to(_REPO_ROOT)), "bytes_written": len(content.encode("utf-8"))}
    except PermissionError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(
    name="fs_list",
    description="List files in a directory. Path must be within the repo or data/.",
    permission="read_only",
    input_schema={"type": "object", "properties": {"path": {"type": "string"}, "pattern": {"type": "string"}}, "required": ["path"]},
)
async def fs_list(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    path_str = args.get("path", "")
    pattern = args.get("pattern", "*")
    if not path_str:
        return {"success": False, "error": "Missing 'path' argument"}
    try:
        resolved = _jail_path(path_str)
        if not resolved.is_dir():
            return {"success": False, "error": f"Not a directory: {path_str}"}
        entries = []
        for item in sorted(resolved.glob(pattern)):
            rel = item.relative_to(_REPO_ROOT)
            entries.append({
                "path": str(rel),
                "is_dir": item.is_dir(),
                "size": item.stat().st_size if item.is_file() else 0,
            })
        return {"success": True, "entries": entries, "count": len(entries)}
    except PermissionError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}
