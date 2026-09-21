"""Think Repository — metadata layer for Git worktrees.

The repository is the persistent agent workspace. Git supplies
versioning; this module supplies worktree identity, session
attachment, jobs, and checkpoints. Sessions stay ephemeral; only
their IDs are recorded here.
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thinkbox.git_engine import GitEngine

METADATA_VERSION = "stage1"
METADATA_FILE = ".thinkbox/repository.json"
CHECKPOINT_DIR = ".thinkbox/checkpoints"
JOB_DIR = ".thinkbox/jobs"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class GitState:
    branch: str = ""
    head: str = ""
    dirty: bool = False


@dataclass
class Worktree:
    worktree_id: str = ""
    path: Path | str = ""
    name: str = ""
    git_branch: str = ""
    head: str = ""
    status: str = "available"
    attached_session_id: str | None = None
    current_job_id: str | None = None
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.path, str):
            self.path = Path(self.path)
        if not self.worktree_id:
            self.worktree_id = _id("wt")
        now = _now()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def snapshot(self) -> dict[str, Any]:
        return {
            "worktree_id": self.worktree_id,
            "path": str(self.path),
            "name": self.name,
            "git_branch": self.git_branch,
            "head": self.head,
            "status": self.status,
            "attached_session_id": self.attached_session_id,
            "current_job_id": self.current_job_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> Worktree:
        return cls(
            worktree_id=data.get("worktree_id", ""),
            path=data.get("path", ""),
            name=data.get("name", ""),
            git_branch=data.get("git_branch", ""),
            head=data.get("head", ""),
            status=data.get("status", "available"),
            attached_session_id=data.get("attached_session_id"),
            current_job_id=data.get("current_job_id"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            metadata=data.get("metadata") or {},
        )


@dataclass
class Checkpoint:
    checkpoint_id: str = ""
    name: str = ""
    worktree_id: str = ""
    path: str | Path = ""
    git_branch: str = ""
    head: str = ""
    status: str = "available"
    attached_session_id: str | None = None
    current_job_id: str | None = None
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.path, str):
            self.path = Path(self.path)
        if not self.checkpoint_id:
            self.checkpoint_id = _id("chk")
        if not self.created_at:
            self.created_at = _now()

    def snapshot(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "name": self.name,
            "worktree_id": self.worktree_id,
            "path": str(self.path),
            "git_branch": self.git_branch,
            "head": self.head,
            "status": self.status,
            "attached_session_id": self.attached_session_id,
            "current_job_id": self.current_job_id,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> Checkpoint:
        return cls(
            checkpoint_id=data.get("checkpoint_id", ""),
            name=data.get("name", ""),
            worktree_id=data.get("worktree_id", ""),
            path=data.get("path", ""),
            git_branch=data.get("git_branch", ""),
            head=data.get("head", ""),
            status=data.get("status", "available"),
            attached_session_id=data.get("attached_session_id"),
            current_job_id=data.get("current_job_id"),
            created_at=data.get("created_at", ""),
            metadata=data.get("metadata") or {},
        )


@dataclass
class Job:
    job_id: str = ""
    worktree_id: str = ""
    path: str | Path = ""
    name: str = ""
    intent: str = ""
    status: str = "pending"
    next_action: str = "run"
    provenance: list[str] = field(default_factory=list)
    checkpoint_ids: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.path, str):
            self.path = Path(self.path)
        if not self.job_id:
            self.job_id = _id("job")
        now = _now()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def snapshot(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "worktree_id": self.worktree_id,
            "path": str(self.path),
            "name": self.name,
            "intent": self.intent,
            "status": self.status,
            "next_action": self.next_action,
            "provenance": self.provenance,
            "checkpoint_ids": self.checkpoint_ids,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> Job:
        return cls(
            job_id=data.get("job_id", ""),
            worktree_id=data.get("worktree_id", ""),
            path=data.get("path", ""),
            name=data.get("name", ""),
            intent=data.get("intent", ""),
            status=data.get("status", "pending"),
            next_action=data.get("next_action", "run"),
            provenance=data.get("provenance") or [],
            checkpoint_ids=data.get("checkpoint_ids") or [],
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            metadata=data.get("metadata") or {},
        )


class Repository:
    """Metadata-backed facade over a single Git worktree."""

    def __init__(
        self,
        repo_path: str | Path,
        git_engine: GitEngine | None = None,
        enforce_git: bool = True,
    ) -> None:
        self._path = Path(repo_path).resolve()
        self._git = git_engine or GitEngine(self._path)
        self._enforce_git = enforce_git
        self._lock = threading.RLock()
        self._ensure_dir()
        with self._lock:
            self._worktree = self._load_or_create()
            if self._enforce_git:
                self.refresh_git_state()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def worktree(self) -> Worktree:
        with self._lock:
            return replace(self._worktree)

    def _ensure_dir(self) -> None:
        self._path.mkdir(parents=True, exist_ok=True)
        (self._path / CHECKPOINT_DIR).mkdir(parents=True, exist_ok=True)

    def _metadata_path(self) -> Path:
        return self._path / METADATA_FILE

    def _checkpoints_dir(self) -> Path:
        return self._path / CHECKPOINT_DIR

    def _load_or_create(self) -> Worktree:
        metadata_path = self._metadata_path()
        if metadata_path.exists():
            try:
                data = json.loads(metadata_path.read_text(encoding="utf-8"))
                return Worktree.from_snapshot(data)
            except (json.JSONDecodeError, KeyError):
                pass
        worktree = Worktree(
            path=self._path,
            name=self._path.name,
            status="available",
        )
        self._save(worktree)
        return worktree

    def _save(self, worktree: Worktree) -> None:
        worktree.updated_at = _now()
        metadata_path = self._metadata_path()
        metadata_path.write_text(
            json.dumps(worktree.snapshot(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def refresh_git_state(self) -> GitState:
        with self._lock:
            branch = self._git.get_current_branch()
            head = ""
            history = self._git.get_commit_history(limit=1)
            if history:
                head = history[0].get("hash", "")
            dirty = self._git.has_changes()
            self._worktree.git_branch = branch
            self._worktree.head = head
            self._worktree.status = "active" if self._worktree.attached_session_id else "available"
            self._save(self._worktree)
            return GitState(branch=branch, head=head, dirty=dirty)

    def attach_session(self, session_id: str) -> Worktree:
        with self._lock:
            self._worktree.attached_session_id = session_id
            self._worktree.status = "active"
            self._save(self._worktree)
            return replace(self._worktree)

    def detach_session(self) -> Worktree:
        with self._lock:
            self._worktree.attached_session_id = None
            if not self._worktree.current_job_id:
                self._worktree.status = "available"
            self._save(self._worktree)
            return replace(self._worktree)

    def current_session(self) -> str | None:
        with self._lock:
            return self._worktree.attached_session_id

    def start_job(self, job_id: str, intent: str = "") -> Worktree:
        with self._lock:
            self._worktree.current_job_id = job_id
            self._worktree.status = "active"
            self._worktree.metadata["intent"] = intent
            self._save(self._worktree)
            return replace(self._worktree)

    def complete_job(self, outcome: str = "") -> Worktree:
        with self._lock:
            self._worktree.current_job_id = None
            self._worktree.metadata["outcome"] = outcome
            if not self._worktree.attached_session_id:
                self._worktree.status = "available"
            self._save(self._worktree)
            return replace(self._worktree)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            worktree = replace(self._worktree)
            snapshot: dict[str, Any] = {
                "repository_version": METADATA_VERSION,
                "worktree": worktree.snapshot(),
                "checkpoint_count": len(list(self._checkpoints_dir().glob("*.json"))),
            }
            if worktree.git_branch:
                snapshot["git_state"] = {
                    "branch": worktree.git_branch,
                    "head": worktree.head,
                }
            return snapshot

    def checkpoint(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
        job_id: str | None = None,
    ) -> Checkpoint:
        with self._lock:
            worktree = replace(self._worktree)
            checkpoint = Checkpoint(
                name=name,
                worktree_id=worktree.worktree_id,
                path=worktree.path,
                git_branch=worktree.git_branch,
                head=worktree.head,
                status=worktree.status,
                attached_session_id=worktree.attached_session_id,
                current_job_id=worktree.current_job_id,
                metadata=metadata or {},
            )
            checkpoint_path = self._checkpoints_dir() / f"{checkpoint.checkpoint_id}.json"
            checkpoint_path.write_text(
                json.dumps(checkpoint.snapshot(), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            if job_id:
                job = self._load_job(job_id)
                if job is None:
                    raise FileNotFoundError(f"job not found: {job_id}")
                if checkpoint.checkpoint_id not in job.checkpoint_ids:
                    job.checkpoint_ids.append(checkpoint.checkpoint_id)
                self._save_job(job)
            return checkpoint

    def checkpoints(self) -> list[Checkpoint]:
        with self._lock:
            result: list[Checkpoint] = []
            for file in sorted(self._checkpoints_dir().glob("*.json")):
                try:
                    data = json.loads(file.read_text(encoding="utf-8"))
                    result.append(Checkpoint.from_snapshot(data))
                except (json.JSONDecodeError, KeyError):
                    continue
            return result

    def restore_checkpoint(self, checkpoint_id: str) -> Worktree:
        with self._lock:
            checkpoint_file = self._checkpoints_dir() / f"{checkpoint_id}.json"
            if not checkpoint_file.exists():
                raise FileNotFoundError(f"checkpoint not found: {checkpoint_id}")
            data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            checkpoint = Checkpoint.from_snapshot(data)
            self._worktree.git_branch = checkpoint.git_branch
            self._worktree.head = checkpoint.head
            self._worktree.status = checkpoint.status
            self._worktree.attached_session_id = checkpoint.attached_session_id
            self._worktree.current_job_id = checkpoint.current_job_id
            self._worktree.metadata = checkpoint.metadata
            self._save(self._worktree)
            return replace(self._worktree)

    def _jobs_dir(self) -> Path:
        return self._path / JOB_DIR

    def _job_path(self, job_id: str) -> Path:
        return self._jobs_dir() / f"{job_id}.json"

    def _load_job(self, job_id: str) -> Job | None:
        job_file = self._job_path(job_id)
        if not job_file.exists():
            return None
        try:
            data = json.loads(job_file.read_text(encoding="utf-8"))
            return Job.from_snapshot(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def _save_job(self, job: Job) -> None:
        job.updated_at = _now()
        self._jobs_dir().mkdir(parents=True, exist_ok=True)
        self._job_path(job.job_id).write_text(
            json.dumps(job.snapshot(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def create_job(
        self,
        job_id: str | None = None,
        intent: str = "",
        name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Job:
        with self._lock:
            if job_id is None:
                job_id = _id("job")
            job = Job(
                job_id=job_id,
                worktree_id=self._worktree.worktree_id,
                path=self._worktree.path,
                name=name,
                intent=intent,
                metadata=metadata or {},
            )
            self._save_job(job)
            self._worktree.current_job_id = job_id
            self._worktree.status = "active"
            self._save(self._worktree)
            return replace(job)

    def job_status(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._load_job(job_id)
            if job is None:
                return None
            return job.snapshot()

    def update_job(
        self,
        job_id: str,
        status: str | None = None,
        next_action: str | None = None,
    ) -> dict[str, Any] | None:
        with self._lock:
            job = self._load_job(job_id)
            if job is None:
                return None
            if status is not None:
                job.status = status
            if next_action is not None:
                job.next_action = next_action
            self._save_job(job)
            return job.snapshot()

    def receipt(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._load_job(job_id)
            if job is None or not job.checkpoint_ids:
                return None
            checkpoint_id = job.checkpoint_ids[-1]
            checkpoint_file = self._checkpoints_dir() / f"{checkpoint_id}.json"
            if not checkpoint_file.exists():
                return None
            data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            return {
                "job_id": job_id,
                "checkpoint_id": checkpoint_id,
                "path": str(checkpoint_file),
                "content": data,
            }
