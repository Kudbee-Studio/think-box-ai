"""Provider-independent workspace / worktree isolation contract (PR #197)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from thinkbox.cloud_execution.errors import WorkspaceConflictError


@dataclass(frozen=True)
class WorkspaceBinding:
    """Declares an isolated workspace identity for one execution job."""

    workspace_id: str
    worktree_path: str
    git_branch: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "worktree_path": self.worktree_path,
            "git_branch": self.git_branch,
            "metadata": self.metadata,
        }


class WorkspaceRegistry:
    """Ensures concurrent jobs do not share the same workspace identity."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_workspace: dict[str, str] = {}

    def bind(self, binding: WorkspaceBinding, job_id: str) -> None:
        with self._lock:
            existing = self._by_workspace.get(binding.workspace_id)
            if existing is not None and existing != job_id:
                raise WorkspaceConflictError(binding.workspace_id, existing)
            self._by_workspace[binding.workspace_id] = job_id

    def release(self, workspace_id: str, job_id: str) -> None:
        with self._lock:
            current = self._by_workspace.get(workspace_id)
            if current == job_id:
                del self._by_workspace[workspace_id]

    def bound_job(self, workspace_id: str) -> str | None:
        with self._lock:
            return self._by_workspace.get(workspace_id)
