"""Think Job status polling + receipt-linked dashboard card (PR #134).

Hermetic read surfaces only — no live Mercury. Fail-closed on unknown jobs.
"""

from __future__ import annotations

from typing import Any

from backend.api.v1.run_receipts import (
    HTTP_RUN_EVIDENCE,
    HTTP_RUN_FOUR_STATE,
    read_run_receipt,
    read_run_receipt_by_engine,
    redact_receipt_payload,
)
from thinkbox.dashboard_state import ThinkJobEntry, get_dashboard_state

STATUS_SCHEMA_VERSION = "think_job_status_v1"
TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
DEFAULT_POLL_INTERVAL_MS = 250
RUNNING_POLL_INTERVAL_MS = 500


class ThinkJobNotFoundError(LookupError):
    """Raised when neither dashboard nor receipt store knows the job."""


def redact_status_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Strip secrets from poll/status responses."""
    return redact_receipt_payload(data)


def build_receipt_link_card(
    *,
    job_id: str,
    status: str,
    phase: str,
    receipt_id: str,
    experiment_id: str,
    session_id: str,
    proof_artifact: str = "",
    tasks_total: int = 0,
    tasks_completed: int = 0,
) -> dict[str, Any]:
    """Dashboard-friendly receipt linkage card (no secrets)."""
    return {
        "kind": "think_job_receipt_card",
        "job_id": job_id,
        "status": status,
        "phase": phase,
        "receipt_id": receipt_id,
        "experiment_id": experiment_id,
        "session_id": session_id,
        "proof_artifact": proof_artifact,
        "tasks_total": tasks_total,
        "tasks_completed": tasks_completed,
        "receipt_linked": bool(receipt_id and experiment_id and session_id),
        "evidence_label": HTTP_RUN_EVIDENCE,
        "four_state": HTTP_RUN_FOUR_STATE,
        "live_verified": False,
        "production_ready": False,
    }


def poll_hints_for_status(status: str) -> dict[str, Any]:
    terminal = status in TERMINAL_STATUSES
    interval = DEFAULT_POLL_INTERVAL_MS if terminal else RUNNING_POLL_INTERVAL_MS
    return {
        "terminal": terminal,
        "recommended_interval_ms": interval,
        "schema_version": STATUS_SCHEMA_VERSION,
    }


def _proof_from_receipt(receipt: dict[str, Any] | None) -> str:
    if not receipt:
        return ""
    for param in receipt.get("parameters") or []:
        if param.get("name") == "proof_artifact_path":
            val = param.get("value")
            if isinstance(val, dict):
                return str(val.get("value") or val.get("path") or "")
            return str(val or "")
    exp = receipt.get("experiment") or {}
    meta = exp.get("metadata") if isinstance(exp, dict) else {}
    if isinstance(meta, dict) and meta.get("proof_artifact"):
        return str(meta["proof_artifact"])
    return ""


def _receipt_status_from_sqlite(engine_id: str) -> dict[str, Any] | None:
    receipt = read_run_receipt_by_engine(engine_id)
    if not receipt:
        return None
    exp = receipt.get("experiment") or {}
    status = "completed"
    if isinstance(exp, dict):
        status = str(exp.get("status") or "completed")
    outcome = receipt.get("outcome")
    if outcome and isinstance(outcome, list) and outcome:
        last = outcome[-1]
        if isinstance(last, dict) and last.get("outcome", {}).get("error"):
            status = "failed"
    return {
        "job_id": engine_id,
        "engine_id": engine_id,
        "status": status,
        "phase": status,
        "receipt_id": receipt.get("receipt_id", ""),
        "experiment_id": receipt.get("experiment_id", ""),
        "session_id": _session_from_receipt(receipt),
        "proof_artifact": _proof_from_receipt(receipt),
        "tasks_total": 0,
        "tasks_completed": 0,
        "result": {},
        "source": "receipt_sqlite",
    }


def _session_from_receipt(receipt: dict[str, Any]) -> str:
    exp = receipt.get("experiment") or {}
    if isinstance(exp, dict) and exp.get("session_id"):
        return str(exp["session_id"])
    for param in receipt.get("parameters") or []:
        if param.get("name") == "session_id":
            val = param.get("value")
            if isinstance(val, dict):
                return str(val.get("value") or "")
            return str(val or "")
    return ""


def resolve_think_job_record(job_id: str) -> dict[str, Any]:
    """Resolve job from dashboard memory first, then receipt SQLite."""
    dashboard = get_dashboard_state()
    entry = dashboard.think_jobs.get(job_id)
    if entry is not None:
        return _entry_to_record(entry, source="dashboard")
    sqlite_row = _receipt_status_from_sqlite(job_id)
    if sqlite_row:
        return sqlite_row
    raise ThinkJobNotFoundError(job_id)


def resolve_think_job_by_receipt(receipt_id: str) -> dict[str, Any]:
    receipt = read_run_receipt(receipt_id)
    if not receipt:
        raise ThinkJobNotFoundError(receipt_id)
    engine_id = ""
    for param in receipt.get("parameters") or []:
        if param.get("name") == "engine_id":
            val = param.get("value")
            engine_id = str(val.get("value") if isinstance(val, dict) else val or "")
            break
    if not engine_id:
        raise ThinkJobNotFoundError(receipt_id)
    try:
        return resolve_think_job_record(engine_id)
    except ThinkJobNotFoundError:
        return _receipt_status_from_sqlite(engine_id) or {
            "job_id": engine_id,
            "engine_id": engine_id,
            "status": "unknown",
            "phase": "receipt_only",
            "receipt_id": receipt.get("receipt_id", receipt_id),
            "experiment_id": receipt.get("experiment_id", ""),
            "session_id": _session_from_receipt(receipt),
            "proof_artifact": _proof_from_receipt(receipt),
            "tasks_total": 0,
            "tasks_completed": 0,
            "result": {},
            "source": "receipt_sqlite",
        }


def _entry_to_record(entry: ThinkJobEntry, *, source: str) -> dict[str, Any]:
    goal = entry.goal
    proof = ""
    if isinstance(entry.result, dict):
        proof = str(entry.result.get("proof_artifact") or "")
    return {
        "job_id": entry.job_id,
        "goal": goal,
        "engine_id": entry.engine_id or entry.job_id,
        "status": entry.status,
        "phase": entry.phase,
        "progress": entry.progress,
        "receipt_id": entry.receipt_id,
        "experiment_id": entry.experiment_id,
        "session_id": entry.session_id,
        "proof_artifact": proof,
        "tasks_total": entry.tasks_total,
        "tasks_completed": entry.tasks_completed,
        "started_at": entry.started_at,
        "completed_at": entry.completed_at,
        "result": entry.result if entry.status in TERMINAL_STATUSES else {},
        "source": source,
    }


def build_think_job_status_payload(
    record: dict[str, Any],
    *,
    goal_hint: str = "",
) -> dict[str, Any]:
    """Stable poll-friendly status document."""
    status = str(record.get("status") or "unknown")
    receipt_id = str(record.get("receipt_id") or "")
    experiment_id = str(record.get("experiment_id") or "")
    session_id = str(record.get("session_id") or "")
    job_id = str(record.get("job_id") or record.get("engine_id") or "")
    card = build_receipt_link_card(
        job_id=job_id,
        status=status,
        phase=str(record.get("phase") or ""),
        receipt_id=receipt_id,
        experiment_id=experiment_id,
        session_id=session_id,
        proof_artifact=str(record.get("proof_artifact") or ""),
        tasks_total=int(record.get("tasks_total") or 0),
        tasks_completed=int(record.get("tasks_completed") or 0),
    )
    payload = {
        "job_id": job_id,
        "engine_id": record.get("engine_id") or job_id,
        "status": status,
        "phase": record.get("phase") or "",
        "progress": float(record.get("progress") or 0.0),
        "receipt": {
            "receipt_id": receipt_id,
            "experiment_id": experiment_id,
            "session_id": session_id,
            "linked": bool(receipt_id and experiment_id and session_id),
        },
        "receipt_card": card,
        "poll": poll_hints_for_status(status),
        "tasks_total": int(record.get("tasks_total") or 0),
        "tasks_completed": int(record.get("tasks_completed") or 0),
        "started_at": record.get("started_at") or "",
        "completed_at": record.get("completed_at") or "",
        "source": record.get("source") or "dashboard",
        "goal_preview": (goal_hint or str(record.get("goal") or ""))[:80],
        "four_state": HTTP_RUN_FOUR_STATE,
        "live_verified": False,
        "production_ready": False,
    }
    return redact_status_payload(payload)


def list_recent_think_job_statuses(limit: int = 50) -> list[dict[str, Any]]:
    dashboard = get_dashboard_state()
    jobs = list(dashboard.think_jobs.values())
    jobs.sort(key=lambda j: j.started_at, reverse=True)
    out: list[dict[str, Any]] = []
    for entry in jobs[: max(1, min(limit, 200))]:
        record = _entry_to_record(entry, source="dashboard")
        out.append(build_think_job_status_payload(record))
    return out


def job_status_snapshot_for_governance() -> dict[str, Any]:
    dashboard = get_dashboard_state()
    statuses: dict[str, int] = {}
    linked = 0
    for job in dashboard.think_jobs.values():
        statuses[job.status] = statuses.get(job.status, 0) + 1
        if job.receipt_id and job.experiment_id:
            linked += 1
    return {
        "think_jobs_tracked": len(dashboard.think_jobs),
        "receipt_linked_jobs": linked,
        "status_counts": statuses,
        "poll_schema_version": STATUS_SCHEMA_VERSION,
    }
