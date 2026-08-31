"""Output formatting utilities."""

from __future__ import annotations

import json
import sys
from typing import Any


def output_json(data: Any) -> None:
    """Output data as JSON."""
    print(json.dumps(data, indent=2, default=str))


def output_plain(text: str) -> None:
    """Output plain text."""
    print(text)


def is_json_mode() -> bool:
    """Check if JSON output mode is active."""
    return "--json" in sys.argv


def is_plain_mode() -> bool:
    """Check if plain output mode is active."""
    return "--plain" in sys.argv


def is_quiet_mode() -> bool:
    """Check if quiet mode is active."""
    return "--quiet" in sys.argv


def is_verbose() -> bool:
    """Check if verbose mode is active."""
    return "--verbose" in sys.argv or "-v" in sys.argv


def is_dry_run() -> bool:
    """Check if dry-run mode is active."""
    return "--dry-run" in sys.argv


def verbose(msg: str) -> None:
    """Print verbose message."""
    if is_verbose():
        print(f"  [verbose] {msg}")
