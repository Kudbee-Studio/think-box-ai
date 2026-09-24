"""Durable governed execution lifecycle on the existing Repository job store.

Persists ADMISSION → QUEUED → RUNNING → COMPLETED/FAILED plus terminal
receipt/artifact/verdict references so status can be recovered after a
process reload. This is not a second job system and is not LIVE VERIFIED.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thinkbox.repository import Repository

SCHEMA_ID = "governed_execution_lifecycle_v1"
LIFECYCLE_META_KEY = "governed_lifecycle"

PHASE_ADMISSION = "admission"
PHASE_QUEUED = "queued"
PHASE_RUNNING = "running"
PHASE_COMPLETED = "completed"
PHASE_FAILED = "failed"

LIFECYCLE_PHASES = frozenset(
    {
        PHASE_ADMISSION,
        PHASE_QUEUED,
        PHASE_RUNNING,
        PHASE_COMPLETED,
        PHASE_FAILED,
    }
)
TERMINAL_PHASES = frozenset({PHASE_COMPLETED, PHASE_FAILED})

WORKTREE_ENV = "THINKBOX_LIFECYCLE_WORKTREE"


def lifecycle_worktree_path(worktree: str | Path | None = None) -> Path:
    """Resolve the worktree used for durable Repository job files."""
    if worktree is not None:
        return Path(worktree).resolve()
    return Path(os.environ.get(WORKTREE_ENV, ".")).resolve()


def open_lifecycle_repo(worktree: str | Path | None = None) -> Repository:
    """Open the existing Think Repository without requiring a clean git tree."""
    return Repository(lifecycle_worktree_path(worktree), enforce_git=False)


def http_status_for_phase(phase: str) -> str:
    """Map lifecycle phase to the existing Think Job HTTP status vocabulary."""
    if phase == PHASE_FAILED:
        return "failed"
    if phase == PHASE_COMPLETED:
        return "completed"
    return "running"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def persist_lifecycle_phase(
    repo: Repository,
    job_id: str,
    phase: str,
    *,
    goal: str = "",
    receipt_id: str = "",
    experiment_id: str = "",
    session_id: str = "",
    execution_substrate: str = "",
    adapter_provider: str = "",
    checkpoint_id: str = "",
    artifact_path: str = "",
    artifact_hash: str = "",
    verdict: str = "",
    http_proof_path: str = "",
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one durable lifecycle transition onto the Repository job."""
    if phase not in LIFECYCLE_PHASES:
        raise ValueError(f"unknown lifecycle phase: {phase!r}")
    existing = repo.job_status(job_id)
    if existing is None:
        repo.create_job(
            job_id=job_id,
            intent=(goal or "governed-execution")[:120],
            name="governed-lifecycle",
        )
    snap = repo.job_status(job_id) or {}
    meta = dict(snap.get("metadata") or {})
    life = dict(meta.get(LIFECYCLE_META_KEY) or {})
    if not life:
        life = {
            "schema": SCHEMA_ID,
            "live_verified": False,
            "live_api_called": False,
            "transitions": [],
        }
    if phase == PHASE_ADMISSION:
        # Reused engine ids must not inherit a prior run's provider/verdict.
        for stale in (
            "adapter_provider",
            "checkpoint_id",
            "artifact_path",
            "artifact_hash",
            "verdict",
            "http_proof_path",
            "result",
        ):
            life.pop(stale, None)
    transitions = list(life.get("transitions") or [])
    transitions.append({"phase": phase, "at": _now()})
    life["transitions"] = transitions
    life["phase"] = phase
    if goal:
        life["goal"] = goal
    optional = {
        "receipt_id": receipt_id,
        "experiment_id": experiment_id,
        "session_id": session_id,
        "execution_substrate": execution_substrate,
        "adapter_provider": adapter_provider,
        "checkpoint_id": checkpoint_id,
        "artifact_path": artifact_path,
        "artifact_hash": artifact_hash,
        "verdict": verdict,
        "http_proof_path": http_proof_path,
    }
    for key, value in optional.items():
        if value:
            life[key] = value
    if result is not None:
        life["result"] = result
    life["live_verified"] = False
    http_status = http_status_for_phase(phase)
    updated = repo.update_job(
        job_id,
        status=http_status,
        next_action="inspect" if phase in TERMINAL_PHASES else "run",
        metadata={LIFECYCLE_META_KEY: life},
        provenance_event=f"lifecycle:{phase}",
    )
    return updated or {}


def load_lifecycle(repo: Repository, job_id: str) -> dict[str, Any] | None:
    """Load a durable lifecycle record after a fresh Repository open."""
    snap = repo.job_status(job_id)
    if snap is None:
        return None
    life = (snap.get("metadata") or {}).get(LIFECYCLE_META_KEY)
    if not isinstance(life, dict) or not life.get("phase"):
        return None
    return {
        "job_id": job_id,
        "http_status": snap.get("status") or http_status_for_phase(str(life.get("phase"))),
        "checkpoint_ids": list(snap.get("checkpoint_ids") or []),
        "intent": snap.get("intent") or "",
        **life,
    }


def lifecycle_to_status_record(loaded: dict[str, Any]) -> dict[str, Any]:
    """Shape a lifecycle record like a Think Job status resolver row."""
    phase = str(loaded.get("phase") or "")
    status = http_status_for_phase(phase) if phase else str(loaded.get("http_status") or "unknown")
    result = loaded.get("result") if isinstance(loaded.get("result"), dict) else {}
    if status not in {"completed", "failed"}:
        result = {}
    return {
        "job_id": loaded.get("job_id") or "",
        "goal": loaded.get("goal") or loaded.get("intent") or "",
        "engine_id": loaded.get("job_id") or "",
        "status": status,
        "phase": phase or status,
        "progress": 1.0 if status == "completed" else 0.0,
        "receipt_id": loaded.get("receipt_id") or "",
        "experiment_id": loaded.get("experiment_id") or "",
        "session_id": loaded.get("session_id") or "",
        "proof_artifact": str(
            (result or {}).get("proof_artifact") or loaded.get("http_proof_path") or ""
        ),
        "tasks_total": int((result or {}).get("tasks_total") or (1 if status in {"completed", "failed"} else 0)),
        "tasks_completed": 1 if status == "completed" else 0,
        "started_at": "",
        "completed_at": "",
        "result": result,
        "source": "repository_lifecycle",
    }


@dataclass(frozen=True)
class LifecycleEvidence:
    """Terminal references retained so a job need not be rerun."""

    receipt_id: str
    checkpoint_id: str
    artifact_path: str
    artifact_hash: str
    verdict: str


def terminal_evidence(loaded: dict[str, Any]) -> LifecycleEvidence:
    """Extract receipt/artifact/verdict pointers from a loaded record."""
    proof = loaded.get("result") if isinstance(loaded.get("result"), dict) else {}
    exec_proof = proof.get("execution_proof") if isinstance(proof.get("execution_proof"), dict) else {}
    return LifecycleEvidence(
        receipt_id=str(loaded.get("receipt_id") or ""),
        checkpoint_id=str(
            loaded.get("checkpoint_id") or exec_proof.get("checkpoint_id") or ""
        ),
        artifact_path=str(loaded.get("artifact_path") or ""),
        artifact_hash=str(
            loaded.get("artifact_hash") or exec_proof.get("artifact_hash") or ""
        ),
        verdict=str(loaded.get("verdict") or exec_proof.get("status") or loaded.get("phase") or ""),
    )
