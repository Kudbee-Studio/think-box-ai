"""Reclaim a RUNNING job whose ownership lease has expired.

Extends the existing lifecycle claim. Does not resume QUEUED jobs, does not
start a worker, and does not mint receipts or admissions.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from thinkbox.governed_execution_lifecycle import (
    PHASE_FAILED,
    PHASE_RUNNING,
    load_lifecycle,
    persist_lifecycle_phase,
)
from thinkbox.lifecycle_harden import (
    LifecycleError,
    reject_remote_local_fallback,
    validate_job_id,
    validate_substrate,
)
from thinkbox.lifecycle_lease import TIMEOUT_REASON_EXPIRED, issue_lease, lease_is_expired
from thinkbox.lifecycle_resume import (
    OUTCOME_CAS_LOST,
    OUTCOME_COMPLETED,
    OUTCOME_FAILED,
    OUTCOME_SKIPPED,
    QueuedResumeResult,
    _execute_claimed_shell,
    _matching_http_receipt,
    _recover_goal,
    _worktree_identity_matches,
)
from thinkbox.governed_job_execution import SUBSTRATE_LOCAL, SUBSTRATE_UPSTASH_BOX
from thinkbox.repository import Repository

ORPHAN_RECLAIM_KIND = "orphan_reclaim"
ORPHAN_INCOMPLETE = "orphan_reclaim_incomplete"
GATE_ID = "durable-running-reclaim"
_SHELL_SUBSTRATES = frozenset({SUBSTRATE_LOCAL, SUBSTRATE_UPSTASH_BOX})


def reclaim_running_orphan(
    repo: Repository,
    job_id: str,
    *,
    exec_command: str | None = None,
    now: datetime | None = None,
    before_claim: Callable[[], None] | None = None,
) -> QueuedResumeResult:
    """CAS-reclaim one expired RUNNING lease, then use the existing shell path.

    A fresh lease is left untouched. A second claimant that loses the CAS
    does not execute.
    """
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    try:
        job_id = validate_job_id(job_id)
    except LifecycleError as exc:
        return QueuedResumeResult(job_id=job_id, outcome=OUTCOME_SKIPPED, error=exc.code)

    loaded = load_lifecycle(repo, job_id)
    if loaded is None:
        return QueuedResumeResult(job_id=job_id, outcome=OUTCOME_SKIPPED, error="not_loadable")

    phase = str(loaded.get("phase") or "")
    if phase != PHASE_RUNNING:
        return QueuedResumeResult(
            job_id=job_id,
            outcome=OUTCOME_SKIPPED,
            receipt_id=str(loaded.get("receipt_id") or ""),
            phase=phase,
            error="not_reclaimable",
            transitions=list(loaded.get("transitions") or []),
        )

    observed_lease = str(loaded.get("lease_id") or "")
    observed_expires = str(loaded.get("lease_expires_at") or "")
    observed_started = str(loaded.get("lease_started_at") or "")
    if not observed_lease or not observed_expires:
        return _fail_closed(
            repo,
            job_id,
            loaded,
            reason="lease_incomplete",
            require_lease_id=observed_lease,
            moment=moment,
        )

    if not lease_is_expired(observed_expires, moment):
        return QueuedResumeResult(
            job_id=job_id,
            outcome=OUTCOME_SKIPPED,
            lease_id=observed_lease,
            receipt_id=str(loaded.get("receipt_id") or ""),
            phase=PHASE_RUNNING,
            error="lease_fresh",
            transitions=list(loaded.get("transitions") or []),
        )

    if before_claim is not None:
        before_claim()

    fresh = load_lifecycle(repo, job_id)
    if fresh is None:
        return QueuedResumeResult(job_id=job_id, outcome=OUTCOME_SKIPPED, error="not_loadable")
    fresh_phase = str(fresh.get("phase") or "")
    fresh_lease = str(fresh.get("lease_id") or "")
    if fresh_phase != PHASE_RUNNING:
        return QueuedResumeResult(
            job_id=job_id,
            outcome=OUTCOME_SKIPPED,
            lease_id=fresh_lease,
            receipt_id=str(fresh.get("receipt_id") or ""),
            phase=fresh_phase,
            error="not_running",
            transitions=list(fresh.get("transitions") or []),
        )
    if fresh_lease != observed_lease:
        return QueuedResumeResult(
            job_id=job_id,
            outcome=OUTCOME_CAS_LOST,
            lease_id=fresh_lease,
            receipt_id=str(fresh.get("receipt_id") or ""),
            phase=fresh_phase,
            error="cas_lease_mismatch",
            transitions=list(fresh.get("transitions") or []),
        )
    if not lease_is_expired(str(fresh.get("lease_expires_at") or ""), moment):
        return QueuedResumeResult(
            job_id=job_id,
            outcome=OUTCOME_SKIPPED,
            lease_id=fresh_lease,
            receipt_id=str(fresh.get("receipt_id") or ""),
            phase=fresh_phase,
            error="lease_fresh",
            transitions=list(fresh.get("transitions") or []),
        )

    snap = repo.job_status(job_id) or {}
    receipt_id = str(fresh.get("receipt_id") or "").strip()
    receipt = _matching_http_receipt(receipt_id, job_id) if receipt_id else None
    goal = _recover_goal(fresh, snap, receipt)
    command = (exec_command or "").strip()
    try:
        substrate = validate_substrate(str(fresh.get("execution_substrate") or ""))
        reject_remote_local_fallback(substrate, str(fresh.get("adapter_provider") or ""))
    except LifecycleError as exc:
        return _fail_closed(
            repo,
            job_id,
            fresh,
            reason=exc.code,
            require_lease_id=observed_lease,
            moment=moment,
            prior_started=observed_started,
        )

    if (
        not _worktree_identity_matches(repo, snap)
        or not receipt_id
        or not goal
        or substrate not in _SHELL_SUBSTRATES
        or not command
    ):
        reason = "missing_command"
        if not _worktree_identity_matches(repo, snap):
            reason = "worktree_mismatch"
        elif not receipt_id:
            reason = "missing_receipt"
        elif not goal:
            reason = "missing_goal"
        return _fail_closed(
            repo,
            job_id,
            fresh,
            reason=reason,
            require_lease_id=observed_lease,
            moment=moment,
            prior_started=observed_started,
        )

    lease = issue_lease(now=moment)
    try:
        persist_lifecycle_phase(
            repo,
            job_id,
            PHASE_RUNNING,
            goal=goal,
            receipt_id=receipt_id,
            experiment_id=str(fresh.get("experiment_id") or ""),
            session_id=str(fresh.get("session_id") or ""),
            execution_substrate=substrate,
            require_phase=PHASE_RUNNING,
            require_lease_id=observed_lease,
            transition_kind=ORPHAN_RECLAIM_KIND,
            lease_id=lease.lease_id,
            lease_started_at=lease.started_at,
            lease_expires_at=lease.expires_at,
            lease_timeout_seconds=lease.timeout_seconds,
            prior_lease_id=observed_lease,
            prior_lease_started_at=observed_started,
            timeout_reason=TIMEOUT_REASON_EXPIRED,
            transition_at=lease.started_at,
        )
    except LifecycleError as exc:
        current = load_lifecycle(repo, job_id) or fresh
        return QueuedResumeResult(
            job_id=job_id,
            outcome=OUTCOME_CAS_LOST,
            lease_id=str(current.get("lease_id") or ""),
            receipt_id=receipt_id,
            phase=str(current.get("phase") or ""),
            error=exc.code,
            transitions=list(current.get("transitions") or []),
        )

    result = _execute_claimed_shell(
        repo,
        job_id,
        loaded=fresh,
        receipt_id=receipt_id,
        substrate=substrate,
        command=command,
        lease_id=lease.lease_id,
        goal=goal,
        result_flags={"reclaimed": True},
    )
    return result


def orphan_reclaim_count(transitions: list[dict[str, Any]]) -> int:
    """Count orphan_reclaim rows."""
    return sum(1 for item in transitions if item.get("kind") == ORPHAN_RECLAIM_KIND)


def lifecycle_reclaim_contract_summary() -> dict[str, Any]:
    """Hermetic four-state snapshot for the reclaim gate."""
    return {
        "gate_id": GATE_ID,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "primary_surface": "thinkbox/lifecycle_reclaim",
        "orphan_reclaim_implemented": True,
        "worker_pool": False,
        "upstash_live_gate_touched": False,
    }


def _fail_closed(
    repo: Repository,
    job_id: str,
    loaded: dict[str, Any],
    *,
    reason: str,
    require_lease_id: str,
    moment: datetime,
    prior_started: str = "",
) -> QueuedResumeResult:
    receipt_id = str(loaded.get("receipt_id") or "")
    try:
        persist_lifecycle_phase(
            repo,
            job_id,
            PHASE_FAILED,
            goal=str(loaded.get("goal") or ""),
            receipt_id=receipt_id,
            execution_substrate=str(loaded.get("execution_substrate") or ""),
            verdict=ORPHAN_INCOMPLETE,
            result={"error": ORPHAN_INCOMPLETE, "reason": reason},
            require_phase=PHASE_RUNNING,
            require_lease_id=require_lease_id,
            transition_kind=ORPHAN_RECLAIM_KIND,
            prior_lease_id=require_lease_id,
            prior_lease_started_at=prior_started or str(loaded.get("lease_started_at") or ""),
            timeout_reason=TIMEOUT_REASON_EXPIRED if require_lease_id else "lease_incomplete",
            transition_at=moment.isoformat(),
        )
    except LifecycleError as exc:
        current = load_lifecycle(repo, job_id) or loaded
        return QueuedResumeResult(
            job_id=job_id,
            outcome=OUTCOME_CAS_LOST,
            receipt_id=receipt_id,
            phase=str(current.get("phase") or ""),
            error=exc.code,
            transitions=list(current.get("transitions") or []),
        )
    current = load_lifecycle(repo, job_id) or {}
    return QueuedResumeResult(
        job_id=job_id,
        outcome=ORPHAN_INCOMPLETE,
        claimed=False,
        executed=False,
        receipt_id=receipt_id,
        phase=PHASE_FAILED,
        verdict=ORPHAN_INCOMPLETE,
        error=reason,
        transitions=list(current.get("transitions") or []),
    )
