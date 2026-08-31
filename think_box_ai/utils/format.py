"""Formatting utilities for Think Box CLI."""

from __future__ import annotations

from ..ui.colors import colorize, bold, dim, colorize_verdict


def format_verdict(verdict: str) -> str:
    """Format a verdict with color."""
    return colorize_verdict(verdict)


def format_id(job_id: str) -> str:
    """Format a job ID."""
    return colorize(job_id, bold(""))


def format_supply(supply: str) -> str:
    """Format a supply number with commas."""
    try:
        return f"{int(supply):,}"
    except (ValueError, TypeError):
        return str(supply)


def format_timestamp(ts: str) -> str:
    """Format a timestamp."""
    return dim(ts)
