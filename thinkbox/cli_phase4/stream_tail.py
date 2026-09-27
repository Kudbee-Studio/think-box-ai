"""Offline stream tail helper (PR #196 F11)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TailLine:
    line_no: int
    text: str


def tail_lines(text: str, n: int = 10) -> tuple[TailLine, ...]:
    lines = text.splitlines()
    if n <= 0:
        return ()
    slice_ = lines[-n:] if len(lines) >= n else lines
    start = len(lines) - len(slice_) + 1
    return tuple(TailLine(line_no=start + i, text=line) for i, line in enumerate(slice_))
