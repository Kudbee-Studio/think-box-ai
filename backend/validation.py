"""Input validation and sanitization utilities."""

from __future__ import annotations

import re
from typing import Any

MAX_GOAL_LENGTH = 10_000
MAX_PATH_LENGTH = 4096
MAX_TOOL_ARGS_SIZE = 100_000
MAX_ITERATIONS = 100

PATH_TRAVERSAL_PATTERN = re.compile(r"\.\.[\\/]|[\\/]\.\.")
SAFE_FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-./]+$")


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
    if not re.match(r"^[a-zA-Z0-9_\-]+$", job_id):
        return False, "Job ID contains invalid characters"
    return True, job_id


def validate_api_key(key: str) -> bool:
    if not isinstance(key, str):
        return False
    if len(key) < 16 or len(key) > 256:
        return False
    return bool(re.match(r"^[a-zA-Z0-9_\-]+$", key))


def generate_api_key() -> str:
    import secrets
    return f"tb_{secrets.token_urlsafe(32)}"
