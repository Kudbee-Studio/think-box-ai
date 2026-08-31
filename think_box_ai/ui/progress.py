"""Progress indicators for Think Box CLI."""

from __future__ import annotations

import sys
import time

from .colors import colorize, dim


def spinner(message: str, delay: float = 0.1) -> None:
    """Show a simple spinner."""
    chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    for c in chars:
        sys.stdout.write(f"\r  {c} {message}")
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\r  \n")


def progress_bar(current: int, total: int, width: int = 30) -> None:
    """Show a progress bar."""
    if total == 0:
        return
    pct = current / total
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    sys.stdout.write(f"\r  [{bar}] {current}/{total}")
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write("\n")


def status_line(label: str, value: str, color: str = "") -> None:
    """Show a status line."""
    if color:
        value = colorize(value, color)
    print(f"  {dim(label + ':')} {value}")
