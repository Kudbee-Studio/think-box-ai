"""Interactive prompts for Think Box CLI."""

from __future__ import annotations

import sys

from .colors import colorize, bold, cyan, yellow


def confirm(message: str, default: bool = False) -> bool:
    """Ask for confirmation."""
    suffix = " [Y/n]" if default else " [y/N]"
    print(f"{message}{suffix}", end=" ")
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def select(message: str, options: list[str]) -> int:
    """Let user select from options."""
    print(bold(message))
    for i, opt in enumerate(options, 1):
        print(f"  {cyan(str(i))}. {opt}")
    while True:
        print(f"  Choose (1-{len(options)}): ", end="")
        try:
            answer = input().strip()
            idx = int(answer) - 1
            if 0 <= idx < len(options):
                return idx
        except (EOFError, KeyboardInterrupt):
            print()
            return -1
        except ValueError:
            pass
        print(yellow(f"  Invalid choice. Enter 1-{len(options)}."))


def prompt(message: str, default: str = "") -> str:
    """Prompt for text input."""
    if default:
        print(f"{message} [{default}]: ", end="")
    else:
        print(f"{message}: ", end="")
    try:
        answer = input().strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return answer if answer else default
