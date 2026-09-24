"""Structured errors for Think Job hermetic e2e deepen (PR #183 F02)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThinkJobE2eDeepenError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
