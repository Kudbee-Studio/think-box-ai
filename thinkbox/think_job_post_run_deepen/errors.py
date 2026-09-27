"""Structured errors (PR #184 F02)."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ThinkJobPostRunDeepenError(Exception):
    code: str
    message: str
    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
