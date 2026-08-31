"""Error handling utilities for Think Box CLI."""

from __future__ import annotations

from difflib import get_close_matches
from typing import Sequence

from .colors import colorize, yellow, red, dim


def suggest_command(given: str, valid: Sequence[str]) -> str | None:
    """Suggest a close match for a mistyped command."""
    matches = get_close_matches(given, valid, n=1, cutoff=0.6)
    return matches[0] if matches else None


def handle_unknown_command(given: str, valid_commands: Sequence[str]) -> str:
    """Generate error message for unknown command with suggestion."""
    suggestion = suggest_command(given, valid_commands)
    if suggestion:
        return f"Unknown command: '{given}'. Did you mean '{suggestion}'?"
    return f"Unknown command: '{given}'. Valid commands: {', '.join(valid_commands)}"


def format_error(error: Exception, context: str = "") -> str:
    """Format an error with context and recovery suggestion."""
    msg = red(f"Error: {error}")
    if context:
        msg = f"{dim(context)}\n{msg}"
    return msg


def format_warning(message: str) -> str:
    """Format a warning message."""
    return yellow(f"Warning: {message}")


def format_success(message: str) -> str:
    """Format a success message."""
    from .colors import green
    return green(f"✓ {message}")
