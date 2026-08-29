"""Terminal formatting utilities for Think Box CLI."""

from __future__ import annotations

import sys


# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"


def supports_color() -> bool:
    """Check if terminal supports color."""
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def c(text: str, *codes: str) -> str:
    """Wrap text with color codes."""
    if not supports_color():
        return text
    return "".join(codes) + text + Colors.RESET


def bold(text: str) -> str:
    return c(text, Colors.BOLD)


def dim(text: str) -> str:
    return c(text, Colors.DIM)


def green(text: str) -> str:
    return c(text, Colors.GREEN)


def red(text: str) -> str:
    return c(text, Colors.RED)


def cyan(text: str) -> str:
    return c(text, Colors.CYAN)


def yellow(text: str) -> str:
    return c(text, Colors.YELLOW)


def magenta(text: str) -> str:
    return c(text, Colors.MAGENTA)


def box(title: str, content: str, width: int = 60) -> str:
    """Draw a box around content."""
    if not supports_color():
        return f"[{title}]\n{content}"

    line_char = "─"
    title_line = line_char * max(0, width - len(title) - 5)
    top = f"┌─ {bold(title)} {title_line}┐"
    bottom = f"└{line_char * (width - 2)}┘"

    lines = content.split("\n")
    body = ""
    for line in lines:
        visible_len = len(line.replace("\033[", "").replace("m", ""))
        padding = max(0, width - visible_len - 3)
        body += f"│ {line}{' ' * padding}│\n"

    return f"{top}\n{body}{bottom}"


def print_box(title: str, content: str, width: int = 60) -> None:
    """Print a formatted box."""
    print(box(title, content, width))


def stream_token(token: str) -> None:
    """Print a streaming token without newline."""
    sys.stdout.write(token)
    sys.stdout.flush()


def print_success(message: str) -> None:
    print(green("✓ ") + message)


def print_error(message: str) -> None:
    print(red("✗ ") + message)


def print_info(message: str) -> None:
    print(cyan("ℹ ") + message)


def print_header(text: str) -> None:
    print()
    print(bold(cyan(f"═══ {text} ═══")))
    print()