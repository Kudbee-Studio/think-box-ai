"""Session lifecycle bridge atop wave 1 follow-up (PR #191 F20)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from thinkbox.kudbee_sdk_followup.session_mirror import SdkSessionFollowup


@dataclass
class SessionBridgeW3:
    session: SdkSessionFollowup
    twin_linked: bool = False
    tags: dict[str, str] = field(default_factory=dict)

    @classmethod
    def open(cls, session_id: str) -> SessionBridgeW3:
        return cls(session=SdkSessionFollowup(session_id))

    def link_twin(self, twin_id: str) -> None:
        self.twin_linked = True
        self.session.touch_metadata("twin_id", twin_id)

    def summary(self) -> dict[str, Any]:
        return {
            "session_id": self.session.session_id,
            "twin_linked": self.twin_linked,
            "tags": dict(self.tags),
            "metadata": dict(self.session.metadata),
            "live_api_called": False,
        }
