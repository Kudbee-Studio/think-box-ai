"""ANSI color codes and terminal rendering for Think Box CLI."""

import sys
from typing import Sequence


class Colors:
    """ANSI color codes."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


def supports_color() -> bool:
    """Check if terminal supports color."""
    if "--no-color" in sys.argv:
        return False
    if not hasattr(sys.stdout, "isatty"):
        return False
    return sys.stdout.isatty()


def colorize(text: str, color: str) -> str:
    """Wrap text in ANSI color if supported."""
    if not supports_color():
        return text
    return f"{color}{text}{Colors.RESET}"


def bold(text: str) -> str:
    return colorize(text, Colors.BOLD)


def dim(text: str) -> str:
    return colorize(text, Colors.DIM)


def red(text: str) -> str:
    return colorize(text, Colors.RED)


def green(text: str) -> str:
    return colorize(text, Colors.GREEN)


def yellow(text: str) -> str:
    return colorize(text, Colors.YELLOW)


def blue(text: str) -> str:
    return colorize(text, Colors.BLUE)


def cyan(text: str) -> str:
    return colorize(text, Colors.CYAN)


def verdict_color(verdict: str) -> str:
    """Get color for a verdict."""
    colors = {
        "succeeded": Colors.GREEN,
        "failed": Colors.RED,
        "unproven": Colors.YELLOW,
        "blocked": Colors.RED,
    }
    return colors.get(verdict, Colors.WHITE)


def colorize_verdict(verdict: str) -> str:
    """Colorize a verdict string."""
    return colorize(verdict.upper(), verdict_color(verdict))
