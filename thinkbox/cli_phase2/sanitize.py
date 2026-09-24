"""Input sanitization and path safety (PR #178 F22)."""

from __future__ import annotations

from pathlib import PurePosixPath

from thinkbox.cli_phase2.errors import validation_error


def sanitize_relative_path(user_path: str) -> str:
    raw = user_path.strip().replace("\\", "/")
    if not raw or raw.startswith("/"):
        raise validation_error("path must be relative", path=user_path)
    parts = PurePosixPath(raw).parts
    if ".." in parts:
        raise validation_error("path traversal forbidden", path=user_path)
    return str(PurePosixPath(*parts))


def sanitize_goal_text(goal: str, max_len: int = 8000) -> str:
    text = goal.strip()
    if not text:
        raise validation_error("goal must be non-empty")
    if len(text) > max_len:
        raise validation_error("goal too long", max_len=max_len)
    return text
