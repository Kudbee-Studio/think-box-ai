"""Terminal color and formatting utilities."""

from __future__ import annotations

import os
import sys

COLORS_ENABLED = (
    "--no-color" not in sys.argv
    and os.environ.get("NO_COLOR", "") == ""
    and sys.stdout.isatty()
)


def colorize(text: str, code: str) -> str:
    if COLORS_ENABLED:
        return f"\033[{code}m{text}\033[0m"
    return text


def bold(text: str) -> str:
    return colorize(text, "1")


def dim(text: str) -> str:
    return colorize(text, "2")


def green(text: str) -> str:
    return colorize(text, "32")


def yellow(text: str) -> str:
    return colorize(text, "33")


def red(text: str) -> str:
    return colorize(text, "31")


def cyan(text: str) -> str:
    return colorize(text, "36")


def magenta(text: str) -> str:
    return colorize(text, "35")


def blue(text: str) -> str:
    return colorize(text, "34")


def white(text: str) -> str:
    return colorize(text, "37")


def bg_green(text: str) -> str:
    return colorize(text, "42")


def bg_yellow(text: str) -> str:
    return colorize(text, "43")


def bg_red(text: str) -> str:
    return colorize(text, "41")


def bg_blue(text: str) -> str:
    return colorize(text, "44")


def underline(text: str) -> str:
    return colorize(text, "4")
