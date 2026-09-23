"""Input validation and sanitization utilities."""

from __future__ import annotations

import re
from typing import Any

MAX_GOAL_LENGTH = 10_000
MAX_PATH_LENGTH = 4096
MAX_TOOL_ARGS_SIZE = 100_000
MAX_ITERATIONS = 100
MAX_THINKBOX_ID_LENGTH = 128
MAX_STREAM_EVENTS = 128
MAX_STREAM_TIMEOUT_S = 300.0

PATH_TRAVERSAL_PATTERN = re.compile(r"\.\.[\\/]|[\\/]\.\.")
SAFE_FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-./]+$")
THINKBOX_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")
RECEIPT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+_rcpt_[0-9]{14}_[a-f0-9]{8}$")


def validate_goal(goal: Any) -> tuple[bool, str]:
    if not isinstance(goal, str):
        return False, "Goal must be a string"
    goal = goal.strip()
    if not goal:
        return False, "Goal cannot be empty"
    if len(goal) > MAX_GOAL_LENGTH:
        return False, f"Goal exceeds maximum length of {MAX_GOAL_LENGTH} characters"
    return True, goal


def validate_path(path: Any) -> tuple[bool, str]:
    if not isinstance(path, str):
        return False, "Path must be a string"
    path = path.strip()
    if not path:
        return False, "Path cannot be empty"
    if len(path) > MAX_PATH_LENGTH:
        return False, f"Path exceeds maximum length of {MAX_PATH_LENGTH}"
    if PATH_TRAVERSAL_PATTERN.search(path):
        return False, "Path traversal detected"
    if path.startswith("/") and not path.startswith("/tmp/"):
        return False, "Absolute paths are not allowed"
    return True, path


def validate_tool_args(args: Any) -> tuple[bool, str | dict[str, Any]]:
    if not isinstance(args, dict):
        return False, "Tool arguments must be an object"
    import json
    serialized = json.dumps(args)
    if len(serialized) > MAX_TOOL_ARGS_SIZE:
        return False, f"Tool arguments exceed maximum size of {MAX_TOOL_ARGS_SIZE}"
    return True, args


def validate_iterations(max_iterations: Any) -> int:
    try:
        n = int(max_iterations)
    except (ValueError, TypeError):
        return 20
    return max(1, min(n, MAX_ITERATIONS))


def sanitize_string(value: str, max_length: int = 1000) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if len(value) > max_length:
        value = value[:max_length]
    value = value.replace("\x00", "")
    return value


def validate_job_id(job_id: Any) -> tuple[bool, str]:
    if not isinstance(job_id, str):
        return False, "Job ID must be a string"
    job_id = job_id.strip()
    if not job_id:
        return False, "Job ID cannot be empty"
    if len(job_id) > MAX_THINKBOX_ID_LENGTH:
        return False, "Job ID too long"
    if not THINKBOX_ID_PATTERN.match(job_id):
        return False, "Job ID contains invalid characters"
    return True, job_id


def validate_thinkbox_id(identifier: Any, *, label: str = "ID") -> tuple[bool, str]:
    """Validate engine/session/experiment style identifiers."""
    if not isinstance(identifier, str):
        return False, f"{label} must be a string"
    value = identifier.strip()
    if not value:
        return False, f"{label} cannot be empty"
    if len(value) > MAX_THINKBOX_ID_LENGTH:
        return False, f"{label} too long"
    if not THINKBOX_ID_PATTERN.match(value):
        return False, f"{label} contains invalid characters"
    return True, value


def clamp_stream_scalar(
    value: Any,
    *,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    """Fail-soft numeric clamp for SSE query parameters."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    return max(minimum, min(parsed, maximum))


def validate_receipt_id(receipt_id: Any) -> tuple[bool, str]:
    if not isinstance(receipt_id, str):
        return False, "Receipt ID must be a string"
    value = receipt_id.strip()
    if not value:
        return False, "Receipt ID cannot be empty"
    if len(value) > MAX_THINKBOX_ID_LENGTH:
        return False, "Receipt ID too long"
    if not RECEIPT_ID_PATTERN.match(value) and not THINKBOX_ID_PATTERN.match(value):
        return False, "Receipt ID format invalid"
    return True, value


def validate_api_key(key: str) -> bool:
    if not isinstance(key, str):
        return False
    if len(key) < 16 or len(key) > 256:
        return False
    return bool(re.match(r"^[a-zA-Z0-9_\-]+$", key))


def generate_api_key() -> str:
    import secrets
    return f"tb_{secrets.token_urlsafe(32)}"
