"""Durable QUEUED resume after process death (stacked on PR #202).

Uses the existing Repository lifecycle. Resume is not LIVE VERIFIED.
Never mints receipts, never recovers corrupt blobs, never reclaims RUNNING.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from thinkbox.governed_execution_lifecycle import (
    LIFECYCLE_META_KEY,
    PHASE_COMPLETED,
    PHASE_FAILED,
    PHASE_QUEUED,
    PHASE_RUNNING,
    load_lifecycle,
    persist_lifecycle_phase,
)
from thinkbox.governed_job_execution import (
    SUBSTRATE_LOCAL,
    SUBSTRATE_UPSTASH_BOX,
    GovernedJobExecutionError,
    execute_governed_job_command,
)
from thinkbox.lifecycle_harden import (
    LifecycleError,
    redact_lifecycle_result,
    reject_remote_local_fallback,
    resume_eligibility,
    validate_job_id,
    validate_substrate,
)
from thinkbox.lifecycle_lease import issue_lease
from thinkbox.repository import Repository

RESUME_CLAIM_KIND = "resume_claim"
RESUME_INCOMPLETE = "resume_incomplete"
GATE_ID = "durable-queued-resume"
OUTCOME_COMPLETED = "completed"
OUTCOME_FAILED = "failed"
OUTCOME_SKIPPED = "skipped"
OUTCOME_INCOMPLETE = RESUME_INCOMPLETE
OUTCOME_CAS_LOST = "cas_lost"

_SHELL_SUBSTRATES = frozenset({SUBSTRATE_LOCAL, SUBSTRATE_UPSTASH_BOX})
_RECEIPT_GOAL_PREFIX = "http-governed-run: "


@dataclass
class QueuedResumeResult:
    """Outcome of one QUEUED resume attempt."""

    job_id: str
    outcome: str
    claimed: bool = False
    executed: bool = False
    lease_id: str = ""
    receipt_id: str = ""
    phase: str = ""
    verdict: str = ""
    error: str = ""
    live_verified: bool = False
    live_api_called: bool = False
    transitions: list[dict[str, Any]] = field(default_factory=list)


def resume_queued_job(
    repo: Repository,
    job_id: str,
    *,
    exec_command: str | None = None,
) -> QueuedResumeResult:
    """Claim a QUEUED job and continue on the existing governed execution path.

    Fail-closed on corrupt/missing records, wrong phase, worktree mismatch,
    missing goal/receipt/command, or unconfigured remote substrate.
    """
    try:
        job_id = validate_job_id(job_id)
    except LifecycleError as exc:
        return QueuedResumeResult(job_id=job_id, outcome=OUTCOME_INCOMPLETE, error=exc.code)

    loaded = load_lifecycle(repo, job_id)
    if loaded is None:
        return QueuedResumeResult(job_id=job_id, outcome=OUTCOME_SKIPPED, error="not_loadable")

    phase = str(loaded.get("phase") or "")
    if phase != PHASE_QUEUED or not resume_eligibility(phase):
        return QueuedResumeResult(
            job_id=job_id,
            outcome=OUTCOME_SKIPPED,
            receipt_id=str(loaded.get("receipt_id") or ""),
            phase=phase,
            error="not_resume_eligible",
            transitions=list(loaded.get("transitions") or []),
        )

    snap = repo.job_status(job_id) or {}
    if not _worktree_identity_matches(repo, snap):
        return _persist_incomplete(
            repo,
            job_id,
            loaded,
            reason="worktree_mismatch",
        )

    receipt_id = str(loaded.get("receipt_id") or "").strip()
    if not receipt_id:
        return _persist_incomplete(repo, job_id, loaded, reason="missing_receipt")

    receipt = _matching_http_receipt(receipt_id, job_id)
    goal = _recover_goal(loaded, snap, receipt)
    if not goal:
        return _persist_incomplete(repo, job_id, loaded, reason="missing_goal")

    try:
        substrate = validate_substrate(str(loaded.get("execution_substrate") or ""))
        reject_remote_local_fallback(substrate, str(loaded.get("adapter_provider") or ""))
    except LifecycleError as exc:
        return _persist_incomplete(repo, job_id, loaded, reason=exc.code)

    command = (exec_command or "").strip()
    if substrate in _SHELL_SUBSTRATES and not command:
        return _persist_incomplete(repo, job_id, loaded, reason="missing_command")
    if substrate not in _SHELL_SUBSTRATES:
        return _persist_incomplete(repo, job_id, loaded, reason="missing_command")

    lease = issue_lease()
    lease_id = lease.lease_id
    try:
        persist_lifecycle_phase(
            repo,
            job_id,
            PHASE_RUNNING,
            goal=goal,
            receipt_id=receipt_id,
            experiment_id=str(loaded.get("experiment_id") or ""),
            session_id=str(loaded.get("session_id") or ""),
            execution_substrate=substrate,
            require_phase=PHASE_QUEUED,
            transition_kind=RESUME_CLAIM_KIND,
            lease_id=lease.lease_id,
            lease_started_at=lease.started_at,
            lease_expires_at=lease.expires_at,
            lease_timeout_seconds=lease.timeout_seconds,
        )
    except LifecycleError as exc:
        if exc.code == "cas_phase_mismatch":
            current = load_lifecycle(repo, job_id) or loaded
            return QueuedResumeResult(
                job_id=job_id,
                outcome=OUTCOME_CAS_LOST,
                receipt_id=receipt_id,
                phase=str(current.get("phase") or ""),
                error="cas_phase_mismatch",
                transitions=list(current.get("transitions") or []),
            )
        return _persist_incomplete(repo, job_id, loaded, reason=exc.code)

    return _execute_claimed_shell(
        repo,
        job_id,
        loaded=loaded,
        receipt_id=receipt_id,
        substrate=substrate,
        command=command,
        lease_id=lease_id,
        goal=goal,
    )


def _execute_claimed_shell(
    repo: Repository,
    job_id: str,
    *,
    loaded: dict[str, Any],
    receipt_id: str,
    substrate: str,
    command: str,
    lease_id: str,
    goal: str,
    result_flags: dict[str, Any] | None = None,
) -> QueuedResumeResult:
    try:
        result = execute_governed_job_command(
            substrate=substrate,
            job_id=job_id,
            command=command,
            repo=repo,
        )
    except GovernedJobExecutionError as exc:
        persist_lifecycle_phase(
            repo,
            job_id,
            PHASE_FAILED,
            goal=goal,
            receipt_id=receipt_id,
            execution_substrate=substrate,
            verdict=exc.code,
            result={"error": exc.code, "message": str(exc)},
        )
        current = load_lifecycle(repo, job_id) or {}
        return QueuedResumeResult(
            job_id=job_id,
            outcome=OUTCOME_FAILED,
            claimed=True,
            executed=False,
            lease_id=lease_id,
            receipt_id=receipt_id,
            phase=PHASE_FAILED,
            verdict=exc.code,
            error=exc.code,
            transitions=list(current.get("transitions") or []),
        )

    receipt = result.receipt
    succeeded = receipt.status == "COMPLETED" and receipt.verified
    public = redact_lifecycle_result(
        {
            "governed": True,
            "governed_shell": True,
            "execution_substrate": result.substrate,
            "adapter_provider": result.adapter_provider,
            "execution_proof": result.public_proof,
            **(result_flags if result_flags is not None else {"resumed": True}),
        }
    )
    persist_lifecycle_phase(
        repo,
        job_id,
        PHASE_COMPLETED if succeeded else PHASE_FAILED,
        goal=goal,
        receipt_id=receipt_id,
        experiment_id=str(loaded.get("experiment_id") or ""),
        session_id=str(loaded.get("session_id") or ""),
        execution_substrate=result.substrate,
        adapter_provider=result.adapter_provider,
        checkpoint_id=receipt.checkpoint_id,
        artifact_path=receipt.artifact_path,
        artifact_hash=receipt.artifact_hash,
        verdict=receipt.status,
        result=public,
    )
    current = load_lifecycle(repo, job_id) or {}
    return QueuedResumeResult(
        job_id=job_id,
        outcome=OUTCOME_COMPLETED if succeeded else OUTCOME_FAILED,
        claimed=True,
        executed=True,
        lease_id=lease_id,
        receipt_id=receipt_id,
        phase=str(current.get("phase") or ""),
        verdict=str(current.get("verdict") or receipt.status),
        error="" if succeeded else str(receipt.status),
        transitions=list(current.get("transitions") or []),
    )


def _persist_incomplete(
    repo: Repository,
    job_id: str,
    loaded: dict[str, Any],
    *,
    reason: str,
) -> QueuedResumeResult:
    receipt_id = str(loaded.get("receipt_id") or "")
    persist_lifecycle_phase(
        repo,
        job_id,
        PHASE_FAILED,
        goal=str(loaded.get("goal") or ""),
        receipt_id=receipt_id,
        execution_substrate=str(loaded.get("execution_substrate") or ""),
        verdict=RESUME_INCOMPLETE,
        result={"error": RESUME_INCOMPLETE, "reason": reason},
    )
    current = load_lifecycle(repo, job_id) or {}
    return QueuedResumeResult(
        job_id=job_id,
        outcome=OUTCOME_INCOMPLETE,
        receipt_id=receipt_id,
        phase=PHASE_FAILED,
        verdict=RESUME_INCOMPLETE,
        error=reason,
        transitions=list(current.get("transitions") or []),
    )


def _worktree_identity_matches(repo: Repository, snap: dict[str, Any]) -> bool:
    raw_path = str(snap.get("path") or "").strip()
    if not raw_path:
        return False
    if Path(raw_path).resolve() != repo.path.resolve():
        return False
    stored_id = str(snap.get("worktree_id") or "").strip()
    current_id = str(repo.worktree.worktree_id or "").strip()
    if stored_id and current_id and stored_id != current_id:
        return False
    return True


def _matching_http_receipt(receipt_id: str, job_id: str) -> dict[str, Any] | None:
    try:
        from backend.api.v1.run_receipts import read_run_receipt
    except ImportError:
        return None
    payload = read_run_receipt(receipt_id)
    if not payload:
        return None
    engine_id = ""
    for param in payload.get("parameters") or []:
        if param.get("name") == "engine_id":
            value = param.get("value")
            engine_id = str(value.get("value") if isinstance(value, dict) else value or "")
            break
    if engine_id and engine_id != job_id:
        return None
    return payload


def _recover_goal(
    loaded: dict[str, Any],
    snap: dict[str, Any],
    receipt: dict[str, Any] | None,
) -> str:
    if receipt is not None:
        experiment = receipt.get("experiment") if isinstance(receipt.get("experiment"), dict) else {}
        intent = str((experiment or {}).get("intent") or "").strip()
        if intent.startswith(_RECEIPT_GOAL_PREFIX):
            intent = intent[len(_RECEIPT_GOAL_PREFIX) :].strip()
        if intent:
            return intent
    life_goal = str(loaded.get("goal") or "").strip()
    if life_goal:
        return life_goal
    return str(snap.get("intent") or loaded.get("intent") or "").strip()


def resume_claim_count(transitions: list[dict[str, Any]]) -> int:
    """Count resume_claim rows (tests / operators)."""
    return sum(1 for item in transitions if item.get("kind") == RESUME_CLAIM_KIND)


def lifecycle_resume_contract_summary() -> dict[str, Any]:
    """Hermetic four-state snapshot for the resume gate."""
    return {
        "gate_id": GATE_ID,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "primary_surface": "thinkbox/lifecycle_resume",
        "resume_implemented": True,
        "orphaned_running_reclaim": False,
        "lifecycle_meta_key": LIFECYCLE_META_KEY,
    }
