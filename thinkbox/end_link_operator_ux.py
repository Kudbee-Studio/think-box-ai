"""END LINK operator dashboard UX helpers (PR #159).

Hermetic view-model builders for batch summaries, chain filters, and
four-state honesty copy. No HTTP; layers on ``thinkbox.end_link_deepen``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from thinkbox.end_link_api import END_LINK_API_LABEL
from thinkbox.end_link_deepen import END_LINK_DEEPEN_LABEL

__all__ = (
    "END_LINK_OPERATOR_UX_LABEL",
    "END_LINK_OPERATOR_UX_VERSION",
    "ChainFilterParams",
    "EndLinkBatchItemRow",
    "EndLinkBatchSummaryView",
    "OperatorEmptyState",
    "OperatorErrorState",
    "OperatorLoadingState",
    "build_chain_filter_query",
    "end_link_operator_ux_contract_snippet",
    "four_state_honesty_copy",
    "operator_empty_state",
    "operator_error_state",
    "operator_loading_state",
    "summarize_end_link_batch",
    "batch_item_row_from_detail",
)

END_LINK_OPERATOR_UX_LABEL = "end-link-operator-ux"
END_LINK_OPERATOR_UX_VERSION = "1.0.0"

FOUR_STATE_MAX = "TEST_VERIFIED"


@dataclass(frozen=True)
class ChainFilterParams:
    """Chain list filters exposed to operators (#158 API, #159 controls)."""

    status_filter: str | None = None
    evidence_label: str | None = None
    action: str | None = None
    agent_id: str | None = None

    def to_query_dict(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if self.status_filter:
            out["status"] = self.status_filter.strip()
        if self.evidence_label:
            out["evidence_label"] = self.evidence_label.strip()
        if self.action:
            out["action"] = self.action.strip()
        if self.agent_id:
            out["agent_id"] = self.agent_id.strip()
        return out


@dataclass(frozen=True)
class EndLinkBatchItemRow:
    """One row in the batch results table."""

    receipt_id: str
    valid: bool
    failure_code: str | None
    link_integrity: str
    prev_receipt_id: str | None
    status_chip: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "valid": self.valid,
            "failure_code": self.failure_code,
            "link_integrity": self.link_integrity,
            "prev_receipt_id": self.prev_receipt_id,
            "status_chip": self.status_chip,
            "live_api_called": False,
        }


@dataclass(frozen=True)
class EndLinkBatchSummaryView:
    """Aggregate batch validate presentation (fail-closed)."""

    total: int
    valid_count: int
    invalid_count: int
    rows: tuple[EndLinkBatchItemRow, ...]
    summary_label: str
    fail_closed: bool
    live_api_called: bool = False
    four_state_max: str = FOUR_STATE_MAX

    def to_dict(self) -> dict[str, Any]:
        return {
            "api": END_LINK_API_LABEL,
            "deepen": END_LINK_DEEPEN_LABEL,
            "operator_ux": END_LINK_OPERATOR_UX_LABEL,
            "operator_ux_version": END_LINK_OPERATOR_UX_VERSION,
            "total": self.total,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "summary_label": self.summary_label,
            "fail_closed": self.fail_closed,
            "rows": [r.to_dict() for r in self.rows],
            "live_api_called": self.live_api_called,
            "four_state_max": self.four_state_max,
        }


@dataclass(frozen=True)
class OperatorLoadingState:
    message: str
    scope: str

    def to_dict(self) -> dict[str, Any]:
        return {"loading": True, "message": self.message, "scope": self.scope}


@dataclass(frozen=True)
class OperatorEmptyState:
    message: str
    scope: str
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "empty": True,
            "message": self.message,
            "scope": self.scope,
            "hint": self.hint,
            "four_state_max": FOUR_STATE_MAX,
        }


@dataclass(frozen=True)
class OperatorErrorState:
    message: str
    scope: str
    recoverable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": True,
            "message": self.message,
            "scope": self.scope,
            "recoverable": self.recoverable,
            "fail_closed": True,
        }


def _status_chip(valid: bool, failure_code: str | None, link_integrity: str) -> str:
    if valid and link_integrity == "ok":
        return "OK"
    if failure_code:
        return f"FAIL:{failure_code}"
    if link_integrity in ("broken", "missing", "rejected"):
        return f"INTEGRITY:{link_integrity}"
    return "INVALID"


def batch_item_row_from_detail(detail: Mapping[str, Any]) -> EndLinkBatchItemRow:
    valid = bool(detail.get("valid"))
    failure_code = detail.get("failure_code")
    link_integrity = str(detail.get("link_integrity") or "unknown")
    return EndLinkBatchItemRow(
        receipt_id=str(detail.get("receipt_id") or ""),
        valid=valid,
        failure_code=str(failure_code) if failure_code else None,
        link_integrity=link_integrity,
        prev_receipt_id=detail.get("prev_receipt_id"),
        status_chip=_status_chip(valid, failure_code, link_integrity),
    )


def summarize_end_link_batch(batch: Mapping[str, Any]) -> EndLinkBatchSummaryView:
    """Build operator batch summary from deepen ``to_dict()`` payload."""
    items: Sequence[Mapping[str, Any]]
    raw_items = batch.get("items")
    if isinstance(raw_items, list):
        items = [x for x in raw_items if isinstance(x, dict)]
    else:
        items = ()
    rows = tuple(batch_item_row_from_detail(item) for item in items)
    valid_count = int(batch.get("valid_count") or 0)
    invalid_count = int(batch.get("invalid_count") or 0)
    total = int(batch.get("total") or len(rows))
    if invalid_count > 0:
        label = f"batch {valid_count}/{total} valid — {invalid_count} fail-closed"
        fail_closed = True
    elif total == 0:
        label = "batch empty (no receipt ids)"
        fail_closed = True
    else:
        label = f"batch {valid_count}/{total} valid"
        fail_closed = False
    return EndLinkBatchSummaryView(
        total=total,
        valid_count=valid_count,
        invalid_count=invalid_count,
        rows=rows,
        summary_label=label,
        fail_closed=fail_closed,
    )


def build_chain_filter_query(params: ChainFilterParams) -> str:
    """Serialize filters for chain/page query string (dashboard client)."""
    parts = []
    for key, value in sorted(params.to_query_dict().items()):
        parts.append(f"{key}={value}")
    return "&".join(parts)


def four_state_honesty_copy() -> dict[str, str]:
    return {
        "code_complete": "CODE COMPLETE",
        "test_verified": "TEST VERIFIED",
        "live_verified": "not claimed",
        "live_api_called": "false",
        "four_state_max": FOUR_STATE_MAX,
        "operator_note": "Hermetic dashboard bind only — no Box/Mercury HTTP in this gate.",
    }


def operator_loading_state(scope: str, message: str = "Loading…") -> OperatorLoadingState:
    return OperatorLoadingState(message=message, scope=scope)


def operator_empty_state(scope: str, message: str, hint: str | None = None) -> OperatorEmptyState:
    return OperatorEmptyState(message=message, scope=scope, hint=hint)


def operator_error_state(scope: str, message: str, recoverable: bool = True) -> OperatorErrorState:
    return OperatorErrorState(message=message, scope=scope, recoverable=recoverable)


def end_link_operator_ux_contract_snippet() -> dict[str, Any]:
    return {
        "end_link_operator_ux": END_LINK_OPERATOR_UX_LABEL,
        "end_link_operator_ux_version": END_LINK_OPERATOR_UX_VERSION,
        "end_link_deepen": END_LINK_DEEPEN_LABEL,
        "api": END_LINK_API_LABEL,
        "live_api_called": False,
        "four_state_max": FOUR_STATE_MAX,
    }
