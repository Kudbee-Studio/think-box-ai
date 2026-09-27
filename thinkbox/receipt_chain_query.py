"""Receipt chain pagination and filters for control-plane HTTP (PR #155)."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.verify_chain import verify_chain

__all__ = (
    "ChainPage",
    "ReceiptChainValidationError",
    "decode_cursor",
    "encode_cursor",
    "fetch_chain_page",
    "fetch_head_receipt",
    "fetch_tail_receipt",
    "validate_page_prev_receipt_links",
    "validate_receipt_link",
)


class ReceiptChainValidationError(ValueError):
    """Broken or missing receipt link (fail-closed)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ChainPage:
    receipts: list[dict[str, Any]]
    next_cursor: str | None
    total: int
    chain_valid: bool


def encode_cursor(rowid: int) -> str:
    raw = json.dumps({"rowid": rowid}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str | None) -> int:
    if not cursor or not str(cursor).strip():
        return 0
    pad = "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(str(cursor).strip() + pad)
        doc = json.loads(raw.decode("utf-8"))
        rowid = int(doc.get("rowid") or 0)
        return max(0, rowid)
    except (ValueError, json.JSONDecodeError, TypeError):
        raise ReceiptChainValidationError("invalid_cursor", "cursor decode failed") from None


def _row_to_dict(
    row: tuple[Any, ...],
    *,
    prev_receipt_id: str | None,
) -> dict[str, Any]:
    receipt_id, action, status, reason, evidence_label, timestamp, prev_hash, entry_hash, metadata_str = row
    meta = json.loads(metadata_str)
    agent_id = meta.get("agent_id") if isinstance(meta, dict) else None
    operation_id = meta.get("operation_id") if isinstance(meta, dict) else None
    return {
        "receipt_id": receipt_id,
        "action": action,
        "status": status,
        "reason": reason,
        "evidence_label": evidence_label,
        "timestamp": timestamp,
        "prev_hash": prev_hash,
        "entry_hash": entry_hash,
        "prev_receipt_id": prev_receipt_id,
        "agent_id": agent_id,
        "operation_id": operation_id,
        "metadata": meta if isinstance(meta, dict) else {},
    }


def fetch_chain_page(
    store: ActionReceiptStore,
    *,
    limit: int = 50,
    cursor: str | None = None,
    action: str | None = None,
    agent_id: str | None = None,
    status_filter: str | None = None,
    evidence_label: str | None = None,
) -> ChainPage:
    """Forward page in append order with stable cursor on sqlite rowid."""
    after_rowid = decode_cursor(cursor)
    lim = max(1, min(int(limit), 200))
    result = verify_chain(store)
    with store._lock:
        rows = store._conn.execute(
            """
            SELECT rowid, receipt_id, action, status, reason, evidence_label,
                   timestamp, prev_hash, entry_hash, metadata
            FROM receipts
            WHERE rowid > ?
            ORDER BY rowid ASC
            """,
            (after_rowid,),
        ).fetchall()
    filtered: list[tuple[Any, ...]] = []
    for row in rows:
        rid, receipt_id, act, row_status, reason, ev, ts, prev_hash, entry_hash, meta_str = row
        if action and act != action:
            continue
        if agent_id:
            try:
                meta = json.loads(meta_str)
            except json.JSONDecodeError:
                continue
            if not isinstance(meta, dict) or meta.get("agent_id") != agent_id:
                continue
        if status_filter and row_status != status_filter:
            continue
        if evidence_label and ev != evidence_label:
            continue
        filtered.append(row)
        if len(filtered) >= lim:
            break

    receipts: list[dict[str, Any]] = []
    prev_id: str | None = None
    if filtered:
        first_rowid = filtered[0][0]
        with store._lock:
            prev_row = store._conn.execute(
                "SELECT receipt_id FROM receipts WHERE rowid < ? ORDER BY rowid DESC LIMIT 1",
                (first_rowid,),
            ).fetchone()
        if prev_row:
            prev_id = prev_row[0]

    for row in filtered:
        _rowid, receipt_id, action_v, status, reason, ev, ts, prev_hash, entry_hash, meta_str = row
        receipts.append(
            _row_to_dict(
                (receipt_id, action_v, status, reason, ev, ts, prev_hash, entry_hash, meta_str),
                prev_receipt_id=prev_id,
            )
        )
        prev_id = receipt_id

    next_cursor: str | None = None
    if filtered:
        last_rowid = filtered[-1][0]
        with store._lock:
            more = store._conn.execute(
                "SELECT 1 FROM receipts WHERE rowid > ? LIMIT 1",
                (last_rowid,),
            ).fetchone()
        if more:
            next_cursor = encode_cursor(last_rowid)

    total = store.count()
    if receipts:
        validate_page_prev_receipt_links(receipts)

    return ChainPage(
        receipts=receipts,
        next_cursor=next_cursor,
        total=total,
        chain_valid=result.valid,
    )


def fetch_head_receipt(store: ActionReceiptStore) -> dict[str, Any] | None:
    with store._lock:
        row = store._conn.execute(
            """
            SELECT receipt_id, action, status, reason, evidence_label,
                   timestamp, prev_hash, entry_hash, metadata
            FROM receipts ORDER BY rowid ASC LIMIT 1
            """
        ).fetchone()
    if row is None:
        return None
    return _row_to_dict(row, prev_receipt_id=None)


def fetch_tail_receipt(store: ActionReceiptStore) -> dict[str, Any] | None:
    with store._lock:
        rows = store._conn.execute(
            """
            SELECT receipt_id, action, status, reason, evidence_label,
                   timestamp, prev_hash, entry_hash, metadata
            FROM receipts ORDER BY rowid DESC LIMIT 2
            """
        ).fetchall()
    if not rows:
        return None
    tail = rows[0]
    prev_id = rows[1][0] if len(rows) > 1 else None
    return _row_to_dict(tail, prev_receipt_id=prev_id)


def validate_page_prev_receipt_links(receipts: list[dict[str, Any]]) -> None:
    """Ensure in-page prev_receipt_id fields link to the prior row in this page."""
    for index in range(1, len(receipts)):
        prior = receipts[index - 1]
        current = receipts[index]
        if current.get("prev_receipt_id") != prior.get("receipt_id"):
            raise ReceiptChainValidationError(
                "broken_prev_receipt_id",
                f"page link mismatch at {current.get('receipt_id')}",
            )


def validate_receipt_link(store: ActionReceiptStore, receipt_id: str) -> None:
    """Fail-closed when receipt missing or chain link broken at this id."""
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
        raise ReceiptChainValidationError("receipt_not_found", f"unknown receipt {receipt_id}")
    _rowid, rid, action, status, reason, ev, ts, prev_hash, entry_hash, meta_str = row
    prev_row = None
    with store._lock:
        prev_row = store._conn.execute(
            "SELECT entry_hash, receipt_id FROM receipts WHERE rowid < ? ORDER BY rowid DESC LIMIT 1",
            (_rowid,),
        ).fetchone()
    expected_prev = prev_row[0] if prev_row else "GENESIS"
    expected_prev_id = prev_row[1] if prev_row else None
    if prev_hash != expected_prev:
        raise ReceiptChainValidationError(
            "broken_prev_hash",
            f"receipt {receipt_id} prev_hash mismatch",
        )
    doc = _row_to_dict(
        (rid, action, status, reason, ev, ts, prev_hash, entry_hash, meta_str),
        prev_receipt_id=expected_prev_id,
    )
    if doc.get("prev_receipt_id") != expected_prev_id and _rowid > 1:
        raise ReceiptChainValidationError(
            "broken_prev_receipt_id",
            f"receipt {receipt_id} prev_receipt_id mismatch",
        )
