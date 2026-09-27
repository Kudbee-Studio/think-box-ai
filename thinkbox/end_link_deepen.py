"""END LINK deepen — batch validate, integrity fields, fail-closed reasons (PR #158).

Hermetic helpers only; no HTTP. Layers on ``thinkbox.end_link_api`` and
``thinkbox.receipt_chain_query``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.control_plane_ops_harden import clamp_query_limit
from thinkbox.end_link_api import END_LINK_API_LABEL, EndLinkViolation, normalize_end_link_receipt_id
from thinkbox.receipt_chain_query import ReceiptChainValidationError, validate_receipt_link

__all__ = (
    "END_LINK_DEEPEN_LABEL",
    "END_LINK_DEEPEN_VERSION",
    "BATCH_VALIDATE_MAX_IDS",
    "EndLinkBatchItem",
    "EndLinkBatchResult",
    "EndLinkIntegrityDetail",
    "end_link_deepen_contract_snippet",
    "evaluate_end_link_batch_body",
    "run_end_link_validate_detailed",
    "run_end_link_batch_validate",
)

END_LINK_DEEPEN_LABEL = "end-link-deepen"
END_LINK_DEEPEN_VERSION = "1.0.0"
BATCH_VALIDATE_MAX_IDS = 50


@dataclass(frozen=True)
class EndLinkIntegrityDetail:
    """Rich integrity payload for a single receipt (success or fail-closed)."""

    receipt_id: str
    valid: bool
    failure_code: str | None = None
    failure_message: str | None = None
    prev_receipt_id: str | None = None
    entry_hash: str | None = None
    link_integrity: str = "unknown"
    live_api_called: bool = False
    evidence_label: str = "simulated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "api": END_LINK_API_LABEL,
            "deepen": END_LINK_DEEPEN_LABEL,
            "deepen_version": END_LINK_DEEPEN_VERSION,
            "receipt_id": self.receipt_id,
            "valid": self.valid,
            "failure_code": self.failure_code,
            "failure_message": self.failure_message,
            "prev_receipt_id": self.prev_receipt_id,
            "entry_hash": self.entry_hash,
            "link_integrity": self.link_integrity,
            "live_api_called": self.live_api_called,
            "evidence_label": self.evidence_label,
        }


@dataclass(frozen=True)
class EndLinkBatchItem:
    receipt_id: str
    detail: EndLinkIntegrityDetail


@dataclass(frozen=True)
class EndLinkBatchResult:
    items: tuple[EndLinkBatchItem, ...]
    total: int
    valid_count: int
    invalid_count: int
    live_api_called: bool = False
    evidence_label: str = "simulated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "api": END_LINK_API_LABEL,
            "deepen": END_LINK_DEEPEN_LABEL,
            "items": [item.detail.to_dict() for item in self.items],
            "total": self.total,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "live_api_called": self.live_api_called,
            "evidence_label": self.evidence_label,
        }


def _load_receipt_row(
    store: ActionReceiptStore,
    receipt_id: str,
) -> tuple[int, dict[str, Any]] | None:
    with store._lock:
        row = store._conn.execute(
            """
            SELECT rowid, receipt_id, action, status, reason, evidence_label,
                   timestamp, prev_hash, entry_hash, metadata
            FROM receipts WHERE receipt_id = ?
            """,
            (receipt_id,),
        ).fetchone()
    if row is None:
        return None
    rowid = int(row[0])
    entry_hash = row[8]
    prev_row = None
    with store._lock:
        prev_row = store._conn.execute(
            "SELECT receipt_id FROM receipts WHERE rowid < ? ORDER BY rowid DESC LIMIT 1",
            (rowid,),
        ).fetchone()
    prev_receipt_id = prev_row[0] if prev_row else None
    return rowid, {
        "receipt_id": row[1],
        "entry_hash": entry_hash,
        "prev_receipt_id": prev_receipt_id,
    }


def run_end_link_validate_detailed(
    store: ActionReceiptStore,
    receipt_id: str,
) -> EndLinkIntegrityDetail:
    """Validate one receipt; never raises — fail-closed per item."""
    try:
        rid = normalize_end_link_receipt_id(receipt_id)
    except EndLinkViolation as exc:
        code = exc.code
        message = exc.message
        return EndLinkIntegrityDetail(
            receipt_id=str(receipt_id or ""),
            valid=False,
            failure_code=str(code),
            failure_message=str(message),
            link_integrity="rejected",
        )
    try:
        validate_receipt_link(store, rid)
    except ReceiptChainValidationError as exc:
        return EndLinkIntegrityDetail(
            receipt_id=rid,
            valid=False,
            failure_code=exc.code,
            failure_message=exc.message,
            link_integrity="broken",
        )
    loaded = _load_receipt_row(store, rid)
    if loaded is None:
        return EndLinkIntegrityDetail(
            receipt_id=rid,
            valid=False,
            failure_code="receipt_not_found",
            failure_message=f"unknown receipt {rid}",
            link_integrity="missing",
        )
    _rowid, meta = loaded
    return EndLinkIntegrityDetail(
        receipt_id=rid,
        valid=True,
        prev_receipt_id=meta.get("prev_receipt_id"),
        entry_hash=meta.get("entry_hash"),
        link_integrity="ok",
    )


def run_end_link_batch_validate(
    store: ActionReceiptStore,
    receipt_ids: Sequence[str],
    *,
    limit: int | None = None,
) -> EndLinkBatchResult:
    """Bulk END LINK validate; each id evaluated independently (fail-closed)."""
    cap = clamp_query_limit(limit if limit is not None else BATCH_VALIDATE_MAX_IDS)
    cap = min(cap, BATCH_VALIDATE_MAX_IDS)
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in receipt_ids:
        key = str(raw or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(key)
        if len(ordered) >= cap:
            break
    items: list[EndLinkBatchItem] = []
    valid_count = 0
    for rid in ordered:
        detail = run_end_link_validate_detailed(store, rid)
        if detail.valid:
            valid_count += 1
        items.append(EndLinkBatchItem(receipt_id=detail.receipt_id, detail=detail))
    invalid_count = len(items) - valid_count
    return EndLinkBatchResult(
        items=tuple(items),
        total=len(items),
        valid_count=valid_count,
        invalid_count=invalid_count,
    )


def evaluate_end_link_batch_body(body: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """Parse POST batch body; returns (receipt_ids, error_codes)."""
    errors: list[str] = []
    if not isinstance(body, dict):
        return [], ["body_must_be_object"]
    raw_ids = body.get("receipt_ids")
    if raw_ids is None:
        return [], ["receipt_ids_required"]
    if not isinstance(raw_ids, list):
        return [], ["receipt_ids_must_be_array"]
    if not raw_ids:
        return [], ["receipt_ids_empty"]
    if len(raw_ids) > BATCH_VALIDATE_MAX_IDS:
        errors.append("receipt_ids_too_many")
    ids: list[str] = []
    for entry in raw_ids:
        if not isinstance(entry, str):
            errors.append("receipt_id_must_be_string")
            continue
        ids.append(entry)
    return ids, errors


def end_link_deepen_contract_snippet() -> dict[str, Any]:
    return {
        "end_link_deepen": END_LINK_DEEPEN_LABEL,
        "end_link_deepen_version": END_LINK_DEEPEN_VERSION,
        "batch_validate_max_ids": BATCH_VALIDATE_MAX_IDS,
        "api": END_LINK_API_LABEL,
        "live_api_called": False,
    }
