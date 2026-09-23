"""Resolve filesystem paths under explicit roots (CLI + plugins)."""

from __future__ import annotations

import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DATA_ROOT = _REPO_ROOT / "data"


def repo_root() -> Path:
    """Repository root directory."""
    return _REPO_ROOT


def default_data_roots() -> list[Path]:
    """Allowed roots for artifact and proof reads."""
    return [_REPO_ROOT, _DEFAULT_DATA_ROOT]


def reject_path_traversal(path_str: str) -> str:
    """Reject ``..`` segments and NUL bytes; return stripped path."""
    cleaned = str(path_str).strip()
    if not cleaned or "\x00" in cleaned:
        raise PermissionError("Invalid path")
    parts = Path(cleaned).parts
    if ".." in parts:
        raise PermissionError("Path traversal detected")
    return cleaned


def resolve_under_roots(
    path_str: str,
    roots: list[Path] | None = None,
    *,
    allow_temp_dir: bool = False,
) -> Path:
    """Resolve ``path_str`` and ensure it stays within one of ``roots``."""
    if not path_str or not str(path_str).strip():
        raise PermissionError("Empty path")
    roots = roots or default_data_roots()
    path = Path(path_str.strip())
    if path.is_absolute():
        resolved = path.resolve()
    else:
        resolved = (_REPO_ROOT / path).resolve()

    if allow_temp_dir:
        tmp_root = Path(tempfile.gettempdir()).resolve()
        try:
            resolved.relative_to(tmp_root)
            return resolved
        except ValueError:
            pass

    for allowed in roots:
        try:
            resolved.relative_to(allowed.resolve())
            return resolved
        except ValueError:
            continue
    raise PermissionError(
        f"Path '{path_str}' is outside allowed directories. "
        f"Allowed roots: {[str(r) for r in roots]}"
    )


def display_path(path: Path) -> str:
    """Prefer repo-relative paths in CLI output (no absolute leak)."""
    try:
        return str(path.resolve().relative_to(_REPO_ROOT))
    except ValueError:
        return str(path.name)
