"""PR #202 — 25 small hardens for durable governed lifecycle.

No second job system. No live network. ``live_verified`` stays false.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from thinkbox.governed_execution_lifecycle import (
    PHASE_ADMISSION,
    PHASE_COMPLETED,
    PHASE_FAILED,
    PHASE_QUEUED,
    PHASE_RUNNING,
    TERMINAL_PHASES,
    load_lifecycle,
    terminal_evidence,
)

GATE_ID = "durable-lifecycle-harden"
PR_NUMBER = 202
EXPECTED_HARDEN_COUNT = 25
MAX_TRANSITIONS = 32
MAX_GOAL_CHARS = 200
MAX_JOB_ID_CHARS = 128
ALLOWED_SUBSTRATES = frozenset({"", "local", "upstash-box"})
_HASH_RE = re.compile(r"^[0-9a-f]{16,128}$")
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
_SECRET_KEYS = frozenset(
    {
        "governance_token",
        "token_value",
        "signing_key",
        "api_key",
        "authorization",
        "command",
        "exec_command",
        "env",
        "environ",
    }
)

HARDENS: tuple[tuple[str, str], ...] = (
    ("H01", "validate_job_id"),
    ("H02", "lifecycle_error"),
    ("H03", "reject_unknown_phase"),
    ("H04", "reject_terminal_regression"),
    ("H05", "bound_transitions"),
    ("H06", "redact_lifecycle_result"),
    ("H07", "validate_artifact_hash"),
    ("H08", "validate_substrate"),
    ("H09", "reject_remote_local_fallback"),
    ("H10", "force_live_flags_false"),
    ("H11", "timestamps_from_transitions"),
    ("H12", "skip_duplicate_consecutive_phase"),
    ("H13", "recover_corrupt_lifecycle_blob"),
    ("H14", "list_durable_jobs"),
    ("H15", "verify_terminal_artifact_hash"),
    ("H16", "completed_requires_receipt"),
    ("H17", "admission_must_be_first"),
    ("H18", "json_safe_result"),
    ("H19", "bound_goal"),
    ("H20", "resume_eligibility"),
    ("H21", "failed_requires_error"),
    ("H22", "worktree_must_be_directory"),
    ("H23", "strip_command_from_public_result"),
    ("H24", "status_includes_lifecycle_phase"),
    ("H25", "redacted_audit_snapshot"),
)


class LifecycleError(ValueError):
    """Typed fail-closed lifecycle error (H02)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_job_id(job_id: str) -> str:
    """H01 — reject empty, oversized, or path-like job ids."""
    raw = (job_id or "").strip()
    if not raw or len(raw) > MAX_JOB_ID_CHARS or not _JOB_ID_RE.match(raw):
        raise LifecycleError("invalid_job_id", f"invalid governed job id: {job_id!r}")
    return raw


def reject_unknown_phase(phase: str) -> str:
    """H03 — unknown phase is fail-closed."""
    key = (phase or "").strip().lower()
    allowed = {
        PHASE_ADMISSION,
        PHASE_QUEUED,
        PHASE_RUNNING,
        PHASE_COMPLETED,
        PHASE_FAILED,
    }
    if key not in allowed:
        raise LifecycleError("unknown_phase", f"unknown lifecycle phase: {phase!r}")
    return key


def reject_terminal_regression(current_phase: str, next_phase: str) -> None:
    """H04 — terminal jobs only accept a fresh ADMISSION reset."""
    if current_phase in TERMINAL_PHASES and next_phase != PHASE_ADMISSION:
        raise LifecycleError(
            "terminal_immutable",
            f"cannot transition {current_phase} -> {next_phase}",
        )


def bound_transitions(transitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """H05 — keep a bounded recent window."""
    if len(transitions) <= MAX_TRANSITIONS:
        return transitions
    return transitions[-MAX_TRANSITIONS:]


def json_safe_result(result: dict[str, Any] | None) -> dict[str, Any] | None:
    """H18 — coerce result to JSON-safe dict."""
    if result is None:
        return None
    raw = json.dumps(result, default=str, sort_keys=True)
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def redact_lifecycle_result(result: dict[str, Any] | None) -> dict[str, Any] | None:
    """H06 + H23 — drop tokens and command/env fields."""
    safe = json_safe_result(result)
    if safe is None:
        return None

    def _walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for key, value in obj.items():
                if str(key).lower() in _SECRET_KEYS or (
                    "token" in str(key).lower() and key != "tokens"
                ):
                    continue
                out[key] = _walk(value)
            return out
        if isinstance(obj, list):
            return [_walk(item) for item in obj]
        return obj

    return _walk(safe)


def validate_artifact_hash(artifact_hash: str) -> str:
    """H07 — hex hash or empty."""
    raw = (artifact_hash or "").strip().lower()
    if not raw:
        return ""
    if not _HASH_RE.match(raw):
        raise LifecycleError("invalid_artifact_hash", "artifact hash must be hex")
    return raw


def validate_substrate(substrate: str) -> str:
    """H08 — explicit substrates only."""
    key = (substrate or "").strip().lower()
    if key not in ALLOWED_SUBSTRATES:
        raise LifecycleError("unknown_substrate", f"unsupported substrate: {substrate!r}")
    return key


def reject_remote_local_fallback(substrate: str, adapter_provider: str) -> None:
    """H09 — upstash-box must never record provider=local."""
    if (substrate or "").strip() == "upstash-box" and (adapter_provider or "").strip() == "local":
        raise LifecycleError(
            "remote_local_fallback_forbidden",
            "upstash-box cannot record adapter_provider=local",
        )


def force_live_flags_false(life: dict[str, Any]) -> dict[str, Any]:
    """H10 — hermetic durability is never LIVE VERIFIED."""
    life["live_verified"] = False
    life["live_api_called"] = False
    return life


def timestamps_from_transitions(transitions: list[dict[str, Any]]) -> tuple[str, str]:
    """H11 — started_at / completed_at from the transition log."""
    started = ""
    completed = ""
    if transitions:
        started = str(transitions[0].get("at") or "")
        last = transitions[-1]
        if last.get("phase") in TERMINAL_PHASES:
            completed = str(last.get("at") or "")
    return started, completed


def skip_duplicate_consecutive_phase(
    transitions: list[dict[str, Any]],
    phase: str,
) -> bool:
    """H12 — True when this phase would duplicate the latest entry."""
    if not transitions:
        return False
    return str(transitions[-1].get("phase") or "") == phase


def recover_corrupt_lifecycle_blob(raw: Any) -> dict[str, Any]:
    """H13 — non-dict metadata becomes a fresh lifecycle blob."""
    if isinstance(raw, dict) and raw.get("schema"):
        return dict(raw)
    return {
        "schema": "governed_execution_lifecycle_v1",
        "live_verified": False,
        "live_api_called": False,
        "transitions": [],
    }


def list_durable_jobs(repo: Any) -> list[str]:
    """H14 — job ids that have a durable lifecycle record."""
    ids = repo.list_job_ids() if hasattr(repo, "list_job_ids") else []
    found: list[str] = []
    for job_id in ids:
        if load_lifecycle(repo, job_id) is not None:
            found.append(job_id)
    return found


def verify_terminal_artifact_hash(loaded: dict[str, Any]) -> bool:
    """H15 — re-check artifact bytes against the stored hash."""
    from thinkbox.execution_adapter import _sha256_file

    evidence = terminal_evidence(loaded)
    if not evidence.artifact_path or not evidence.artifact_hash:
        return False
    path = Path(evidence.artifact_path)
    if not path.is_file():
        return False
    return _sha256_file(path) == evidence.artifact_hash


def completed_requires_receipt(phase: str, receipt_id: str, life: dict[str, Any]) -> None:
    """H16 — COMPLETED must retain a receipt id (this write or prior)."""
    if phase != PHASE_COMPLETED:
        return
    if (receipt_id or "").strip() or str(life.get("receipt_id") or "").strip():
        return
    raise LifecycleError("completed_missing_receipt", "completed lifecycle requires receipt_id")


def admission_must_be_first(transitions: list[dict[str, Any]], phase: str) -> None:
    """H17 — first recorded phase is always ADMISSION."""
    if transitions:
        return
    if phase != PHASE_ADMISSION:
        raise LifecycleError("admission_required", "first lifecycle phase must be admission")


def bound_goal(goal: str) -> str:
    """H19 — bound stored goal text."""
    return (goal or "")[:MAX_GOAL_CHARS]


def resume_eligibility(phase: str) -> bool:
    """H20 — QUEUED jobs are the only resume candidates (resume not implemented)."""
    return phase == PHASE_QUEUED


def failed_requires_error(phase: str, result: dict[str, Any] | None, verdict: str) -> None:
    """H21 — FAILED must carry an honest error or verdict."""
    if phase != PHASE_FAILED:
        return
    if verdict.strip():
        return
    if isinstance(result, dict) and str(result.get("error") or "").strip():
        return
    raise LifecycleError("failed_missing_error", "failed lifecycle requires error or verdict")


def worktree_must_be_directory(path: Path) -> Path:
    """H22 — refuse a missing worktree path."""
    resolved = path.resolve()
    if not resolved.is_dir():
        raise LifecycleError("worktree_missing", f"lifecycle worktree is not a directory: {resolved}")
    return resolved


def status_includes_lifecycle_phase(record: dict[str, Any]) -> dict[str, Any]:
    """H24 — additive lifecycle_phase on status records."""
    out = dict(record)
    out["lifecycle_phase"] = str(record.get("phase") or record.get("lifecycle_phase") or "")
    out["resume_eligible"] = bool(record.get("resume_eligible"))
    return out


def redacted_audit_snapshot(loaded: dict[str, Any]) -> dict[str, Any]:
    """H25 — operator-safe lifecycle summary."""
    result = redact_lifecycle_result(loaded.get("result") if isinstance(loaded.get("result"), dict) else {})
    return {
        "job_id": loaded.get("job_id") or "",
        "phase": loaded.get("phase") or "",
        "receipt_id": loaded.get("receipt_id") or "",
        "execution_substrate": loaded.get("execution_substrate") or "",
        "adapter_provider": loaded.get("adapter_provider") or "",
        "verdict": loaded.get("verdict") or "",
        "artifact_hash": loaded.get("artifact_hash") or "",
        "checkpoint_id": loaded.get("checkpoint_id") or "",
        "resume_eligible": resume_eligibility(str(loaded.get("phase") or "")),
        "live_verified": False,
        "live_api_called": False,
        "result_keys": sorted((result or {}).keys()),
    }


def harden_ids() -> tuple[str, ...]:
    return tuple(item[0] for item in HARDENS)
