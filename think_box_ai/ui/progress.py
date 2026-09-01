"""Progress bar and spinner utilities."""

from __future__ import annotations

import sys
import time
from typing import Any

from .colors import cyan, green, yellow


class ProgressBar:
    def __init__(self, total: int, desc: str = "", width: int = 40):
        self.total = total
        self.desc = desc
        self.width = width
        self.current = 0
        self.start_time = time.time()

    def update(self, n: int = 1, info: str = "") -> None:
        self.current += n
        pct = self.current / self.total if self.total > 0 else 0
        filled = int(self.width * pct)
        bar = green("█" * filled) + dim("░" * (self.width - filled))
        elapsed = time.time() - self.start_time
        rate = self.current / elapsed if elapsed > 0 else 0
        sys.stdout.write(
            f"\r  {self.desc} {bar} {pct:6.1%} ({self.current}/{self.total}) "
            f"{rate:.1f}/s {info}"
        )
        sys.stdout.flush()
        if self.current >= self.total:
            sys.stdout.write("\n")

    def finish(self, msg: str = "Done") -> None:
        self.current = self.total
        bar = green("█" * self.width)
        sys.stdout.write(f"\r  {self.desc} {bar} 100.0% {msg}\n")
        sys.stdout.flush()


class Spinner:
    def __init__(self, msg: str = ""):
        self.msg = msg
        self.running = False
        self._chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __enter__(self) -> Spinner:
        self.running = True
        self._spin()
        return self

    def __exit__(self, *args: Any) -> None:
        self.running = False
        sys.stdout.write(f"\r{' ' * (len(self.msg) + 10)}\r")
        sys.stdout.flush()

    def _spin(self) -> None:
        if not self.running:
            return
        for char in self._chars:
            if not self.running:
                return
            sys.stdout.write(f"\r  {cyan(char)} {self.msg}")
            sys.stdout.flush()
            time.sleep(0.08)
