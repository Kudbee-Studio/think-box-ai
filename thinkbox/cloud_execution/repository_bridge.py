"""Bridge to thinkbox.repository worktree metadata (PR #197)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from thinkbox.cloud_execution.workspace import WorkspaceBinding


def workspace_binding_from_worktree_snapshot(data: dict[str, Any]) -> WorkspaceBinding:
    """Build a workspace binding from Repository Worktree.snapshot() fields."""
    wt_id = str(data.get("worktree_id") or "")
    path = str(data.get("path") or "")
    branch = str(data.get("git_branch") or "")
    return WorkspaceBinding(
        workspace_id=wt_id or f"ws_{Path(path).name}",
        worktree_path=path,
        git_branch=branch,
        metadata={"source": "thinkbox.repository.Worktree"},
    )
