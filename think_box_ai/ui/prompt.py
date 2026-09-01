"""Interactive prompt utilities."""

from __future__ import annotations

import sys

from .colors import bold, cyan, green, yellow


def confirm(message: str, default: bool = False) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        response = input(f"  {cyan('?')} {message}{suffix}: ").strip().lower()
        if not response:
            return default
        if response in ("y", "yes"):
            return True
        if response in ("n", "no"):
            return False
        print(f"  {yellow('Please enter y or n')}")


def choice(message: str, options: list[str]) -> int:
    print(f"  {bold(message)}")
    for i, opt in enumerate(options, 1):
        print(f"    {cyan(str(i))}. {opt}")
    while True:
        try:
            sel = int(input(f"  {cyan('?')} Select (1-{len(options)}): ").strip())
            if 1 <= sel <= len(options):
                return sel - 1
        except (ValueError, EOFError):
            pass
        print(f"  {yellow(f'Please enter 1-{len(options)}')}")


def input_text(message: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    result = input(f"  {cyan('?')} {message}{suffix}: ").strip()
    return result if result else default


def password(message: str = "Password") -> str:
    import getpass

    return getpass.getpass(f"  {cyan('?')} {message}: ")


def print_step(step: int, total: int, message: str) -> None:
    print(f"  {cyan(f'[{step}/{total}]')} {bold(message)}")


def print_success(message: str) -> None:
    print(f"  {green('✓')} {message}")


def print_error(message: str) -> None:
    print(f"  {yellow('✗')} {message}", file=sys.stderr)


def print_warning(message: str) -> None:
    print(f"  {yellow('⚠')} {message}")
