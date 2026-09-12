"""KUDBEE Control Fabric — Disruptor pass framework.

A disruptor pass is a single adversarial scenario run against the control
fabric. Each pass configures the fabric, performs an attack or perturbation,
and reports an outcome that the Verifier scores against a safety predicate.

Categories:
  - token        forged / expired / revoked / mismatched credentials
  - capability   attempted side effect without a granted capability
  - mesh         compromised-cell credential reuse (blast radius)
  - grounding    ungrounded reasoning detection (contrast twins)
  - ledger       tamper-evidence of the action chain
  - capacity     elastic contraction under budget exhaustion
  - control      legitimate admission (non-adversarial baseline)
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass
class DisruptorPass:
    """One adversarial scenario.

    ``setup(ctx)`` prepares the fabric state.
    ``attack(ctx)`` performs the attempt and returns an outcome dict.
    ``should_pass(outcome)`` returns True when the fabric handled the
    scenario safely (blocked, contained, detected, or admitted correctly).
    """

    name: str
    category: str
    description: str
    setup: Callable[[dict[str, Any]], None]
    attack: Callable[[dict[str, Any]], dict[str, Any]]
    should_pass: Callable[[dict[str, Any]], bool]


@dataclass
class DisruptorResult:
    name: str
    category: str
    description: str
    outcome: dict[str, Any] = field(default_factory=dict)
    passed: bool = False
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class DisruptorSuite:
    """Ordered registry of disruptor passes with thread-safe execution."""

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self._passes: list[DisruptorPass] = []
        self._lock = threading.Lock()

    def add(self, pass_: DisruptorPass) -> None:
        with self._lock:
            self._passes.append(pass_)

    def add_many(self, passes: list[DisruptorPass]) -> None:
        with self._lock:
            self._passes.extend(passes)

    @property
    def passes(self) -> list[DisruptorPass]:
        with self._lock:
            return list(self._passes)

    def __len__(self) -> int:
        with self._lock:
            return len(self._passes)

    def run_all(self, ctx: dict[str, Any]) -> list[DisruptorResult]:
        results: list[DisruptorResult] = []
        for pass_ in self._passes:
            pass_.setup(ctx)
            outcome = pass_.attack(ctx)
            results.append(
                DisruptorResult(
                    name=pass_.name,
                    category=pass_.category,
                    description=pass_.description,
                    outcome=outcome,
                    passed=bool(pass_.should_pass(outcome)),
                )
            )
        return results