"""Task lifecycle bridge for wave 2 SDK (PR #181 F21)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thinkbox.kudbee_sdk_followup.task_mirror import SdkTaskFollowup, TaskStatus


@dataclass
class TaskBridgeW2:
    task: SdkTaskFollowup

    @classmethod
    def create(cls, task_id: str, name: str) -> TaskBridgeW2:
        return cls(task=SdkTaskFollowup(task_id, name))

    def run_hermetic(self) -> dict[str, Any]:
        self.task.start()
        self.task.record_event("w2_bridge", {"phase": "start"})
        self.task.complete({"ok": True})
        return {
            "task_id": self.task.task_id,
            "status": self.task.status.value,
            "events": len(self.task.events),
            "live_api_called": False,
        }

    def is_terminal(self) -> bool:
        return self.task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
