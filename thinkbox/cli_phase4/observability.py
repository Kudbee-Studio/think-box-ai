"""Observability hooks for Phase 4 CLI (PR #196 F22)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CliPhase4Metrics:
    commands_invoked: int = 0
    cassette_replays: int = 0
    batch_runs: int = 0
    last_command: str | None = None
    tags: dict[str, str] = field(default_factory=dict)

    def record_command(self, name: str, **tags: str) -> None:
        self.commands_invoked += 1
        self.last_command = name
        self.tags.update(tags)

    def snapshot(self) -> dict[str, Any]:
        return {
            "commands_invoked": self.commands_invoked,
            "cassette_replays": self.cassette_replays,
            "batch_runs": self.batch_runs,
            "last_command": self.last_command,
            "tags": dict(self.tags),
            "live_api_called": False,
        }


_GLOBAL = CliPhase4Metrics()


def get_metrics() -> CliPhase4Metrics:
    return _GLOBAL
