"""Pipeline PR lifecycle state machine — validates receipt-derived transitions."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional


class PipelinePRState(str, Enum):
    UNKNOWN = "UNKNOWN"
    PR_CREATED = "PR_CREATED"
    IDENTIFY = "IDENTIFY"
    EXECUTE = "EXECUTE"
    LEARN = "LEARN"
    READY_FOR_CLOSE = "READY_FOR_CLOSE"
    BLOCKED = "BLOCKED"
    QUARANTINED = "QUARANTINED"
    FAILED = "FAILED"


_TERMINAL = frozenset(
    {
        PipelinePRState.LEARN.value,
        PipelinePRState.READY_FOR_CLOSE.value,
        PipelinePRState.BLOCKED.value,
        PipelinePRState.FAILED.value,
        PipelinePRState.QUARANTINED.value,
    }
)


def infer_state_from_receipts(receipts_newest_first: list[dict[str, Any]]) -> str:
    """Derive current pipeline state from newest receipt to_state."""
    if not receipts_newest_first:
        return PipelinePRState.UNKNOWN.value
    for row in receipts_newest_first:
        action = str(row.get("action") or "")
        if action == "pipeline_quarantine":
            evidence = row.get("evidence") or {}
            if evidence.get("quarantined"):
                return PipelinePRState.QUARANTINED.value
        to_state = str(row.get("to_state") or "")
        if to_state:
            return to_state
    return PipelinePRState.UNKNOWN.value


def validate_transition(from_state: str, to_state: str, action: str) -> tuple[bool, str]:
    """Fail-closed transition guard for pipeline mutations."""
    action = action.lower()
    if action in ("admission_denied", "merge_request_denied", "merge_policy_denied"):
        return True, "denial_recorded"
    if from_state == PipelinePRState.BLOCKED.value and to_state == PipelinePRState.BLOCKED.value:
        return True, "blocked_hold"
    if from_state in _TERMINAL and to_state not in _TERMINAL and action != "lifecycle_start":
        return False, f"illegal_exit_from_terminal:{from_state}"
    return True, "ok"


def state_machine_report(receipts_newest_first: list[dict[str, Any]]) -> dict[str, Any]:
    """Summary for API: current state + last transition validity."""
    current = infer_state_from_receipts(receipts_newest_first)
    last_transition_ok = True
    reason = "no_receipts"
    if receipts_newest_first:
        row = receipts_newest_first[0]
        ok, reason = validate_transition(
            str(row.get("from_state") or ""),
            str(row.get("to_state") or ""),
            str(row.get("action") or ""),
        )
        last_transition_ok = ok
    return {
        "current_state": current,
        "terminal": current in _TERMINAL,
        "last_transition_valid": last_transition_ok,
        "last_transition_reason": reason,
        "evidence_label": "simulated",
    }
