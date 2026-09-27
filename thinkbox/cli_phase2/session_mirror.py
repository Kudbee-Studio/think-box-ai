"""Session lifecycle helpers (PR #178 F11)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class SessionState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    CLOSED = "closed"


@dataclass
class CliSessionMirror:
    session_id: str
    state: SessionState = SessionState.CREATED
    metadata: dict[str, Any] | None = None

    def activate(self) -> None:
        if self.state == SessionState.CLOSED:
            raise ValueError("cannot activate closed session")
        self.state = SessionState.ACTIVE

    def close(self) -> None:
        self.state = SessionState.CLOSED
