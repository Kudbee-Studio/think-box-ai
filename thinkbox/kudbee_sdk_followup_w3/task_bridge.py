"""Task lifecycle bridge for wave 3 SDK (PR #191 F21)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thinkbox.kudbee_sdk_followup.task_mirror import SdkTaskFollowup, TaskStatus


@dataclass
class TaskBridgeW3:
    task: SdkTaskFollowup

    @classmethod
    def create(cls, task_id: str, name: str) -> TaskBridgeW3:
        return cls(task=SdkTaskFollowup(task_id, name))

    def run_hermetic(self) -> dict[str, Any]:
        self.task.start()
        self.task.record_event("w3_bridge", {"phase": "start"})
        self.task.complete({"ok": True})
        return {
            "task_id": self.task.task_id,
            "status": self.task.status.value,
            "events": len(self.task.events),
            "live_api_called": False,
        }

    def cancel_hermetic(self, reason: str = "user") -> dict[str, Any]:
        self.task.fail(f"cancelled:{reason}")
        return {
            "task_id": self.task.task_id,
            "status": self.task.status.value,
            "live_api_called": False,
        }

    def is_terminal(self) -> bool:
        return self.task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
