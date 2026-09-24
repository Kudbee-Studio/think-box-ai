"""Fork / conflict detection stubs (PR #182 F11)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ForkReport:
    fork_detected: bool
    conflicting_heads: tuple[str, ...]
    dry_run: bool


def detect_fork_stub(head_a: str, head_b: str) -> ForkReport:
    fork = head_a != head_b and head_a and head_b
    heads = (head_a, head_b) if fork else (head_a or head_b,)
    return ForkReport(fork_detected=fork, conflicting_heads=heads, dry_run=True)


def conflict_summary(report: ForkReport) -> dict[str, Any]:
    return {
        "fork_detected": report.fork_detected,
        "conflicting_heads": list(report.conflicting_heads),
        "dry_run": report.dry_run,
        "live_api_called": False,
    }
