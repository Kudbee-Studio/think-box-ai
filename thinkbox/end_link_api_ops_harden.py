"""END LINK stack API / ops hardening (PR #161).

Fail-closed chain-filter validation, normalized ``failure_code`` values, optional
request timing stamps, and idempotent GET / safe-retry hints for control-plane
routes layered on PR #157–#160. Hermetic only — ``live_api_called=False``.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping

from thinkbox.control_plane_ops_harden import (
    OPS_HARDEN_LABEL,
    fingerprint_idempotency_body,
    redact_mapping_for_logs,
)
from thinkbox.end_link_api import END_LINK_API_LABEL
from thinkbox.end_link_deepen import END_LINK_DEEPEN_LABEL
from thinkbox.end_link_operator_ux import END_LINK_OPERATOR_UX_LABEL, ChainFilterParams

__all__ = (
    "END_LINK_API_OPS_HARDEN_LABEL",
    "END_LINK_API_OPS_HARDEN_VERSION",
    "CHAIN_FILTER_MAX_LEN",
    "KNOWN_FAILURE_CODES",
    "BatchIdempotencyReplay",
    "OpsRouteTiming",
    "attach_end_link_ops_meta",
    "end_link_api_ops_harden_contract_snippet",
    "enrich_batch_validate_payload",
    "enrich_validate_payload",
    "normalize_failure_code",
    "normalize_failure_codes_in_payload",
    "lookup_batch_idempotency_replay",
    "parse_batch_idempotency_key",
    "redact_end_link_ops_summary",
    "register_batch_idempotency_replay",
    "reset_batch_idempotency_cache",
    "validate_chain_filter_query",
)

END_LINK_API_OPS_HARDEN_LABEL = "end-link-api-ops-harden"
END_LINK_API_OPS_HARDEN_VERSION = "1.0.0"

CHAIN_FILTER_MAX_LEN = 64
_FILTER_SAFE_RE = re.compile(r"^[\w.\-:/@+]+$")

KNOWN_FAILURE_CODES: frozenset[str] = frozenset(
    {
        "receipt_id_required",
        "receipt_id_too_long",
        "receipt_not_found",
        "receipt_ids_required",
        "receipt_ids_empty",
        "receipt_ids_must_be_array",
        "receipt_ids_too_many",
        "receipt_id_must_be_string",
        "body_must_be_object",
        "invalid_json",
        "invalid_body",
        "chain_filter_invalid",
        "chain_filter_too_long",
        "chain_filter_unsafe",
        "idempotency_conflict",
        "rate_limit_exceeded",
        "end_link_invalid",
    }
)


@dataclass(frozen=True)
class OpsRouteTiming:
    """Monotonic timing for ops observability (hermetic)."""

    route: str
    started_at: float

    @classmethod
    def start(cls, route: str) -> "OpsRouteTiming":
        return cls(route=route, started_at=time.monotonic())

    def elapsed_ms(self) -> int:
        return max(0, int((time.monotonic() - self.started_at) * 1000))


@dataclass(frozen=True)
class BatchIdempotencyReplay:
    """Cached batch validate response for Idempotency-Key replay."""

    operation_id: str
    body_fingerprint: str
    payload: dict[str, Any]


_BATCH_REPLAY_LOCK = threading.Lock()
_BATCH_REPLAY: dict[str, BatchIdempotencyReplay] = {}


def normalize_failure_code(code: str | None) -> str | None:
    """Map arbitrary codes to stable snake_case (fail-closed unknown bucket)."""
    if code is None:
        return None
    text = str(code).strip().lower().replace("-", "_").replace(" ", "_")
    if not text:
        return None
    if text in KNOWN_FAILURE_CODES:
        return text
    if text.endswith("_invalid") or text.endswith("_error"):
        return text
    return text[:128]


def _validate_filter_value(field: str, value: str | None) -> list[str]:
    if value is None:
        return []
    text = value.strip()
    if not text:
        return [f"{field}_empty"]
    if len(text) > CHAIN_FILTER_MAX_LEN:
        return [f"{field}_too_long"]
    if not _FILTER_SAFE_RE.match(text):
        return [f"{field}_unsafe"]
    return []


def validate_chain_filter_query(
    *,
    status: str | None = None,
    evidence_label: str | None = None,
    action: str | None = None,
    agent_id: str | None = None,
) -> tuple[ChainFilterParams, list[str]]:
    """Fail-closed validation for receipt-chain list filters."""
    errors: list[str] = []
    for field, raw in (
        ("status", status),
        ("evidence_label", evidence_label),
        ("action", action),
        ("agent_id", agent_id),
    ):
        errors.extend(_validate_filter_value(field, raw))
    if errors:
        return ChainFilterParams(), errors
    params = ChainFilterParams(
        status_filter=status.strip() if status else None,
        evidence_label=evidence_label.strip() if evidence_label else None,
        action=action.strip() if action else None,
        agent_id=agent_id.strip() if agent_id else None,
    )
    return params, []


def attach_end_link_ops_meta(
    data: Mapping[str, Any],
    *,
    route: str,
    timing: OpsRouteTiming | None = None,
    idempotent_safe: bool = False,
) -> dict[str, Any]:
    """Merge PR #161 ops metadata into a control-plane data payload."""
    merged: MutableMapping[str, Any] = dict(data)
    merged.setdefault("live_api_called", False)
    merged.setdefault("evidence_label", "simulated")
    ops: dict[str, Any] = {
        "ops_harden": OPS_HARDEN_LABEL,
        "end_link_api_ops_harden": END_LINK_API_OPS_HARDEN_LABEL,
        "end_link_api_ops_harden_version": END_LINK_API_OPS_HARDEN_VERSION,
        "route": route,
        "stack_layers": [
            END_LINK_API_OPS_HARDEN_LABEL,
            END_LINK_OPERATOR_UX_LABEL,
            END_LINK_DEEPEN_LABEL,
            END_LINK_API_LABEL,
        ],
        "idempotent_retry_safe": idempotent_safe,
        "four_state_max": "TEST_VERIFIED",
        "live_verified": False,
    }
    if timing is not None:
        ops["timing_ms"] = timing.elapsed_ms()
    merged["ops"] = ops
    return dict(merged)


def enrich_validate_payload(
    payload: Mapping[str, Any],
    *,
    timing: OpsRouteTiming | None = None,
) -> dict[str, Any]:
    """Single-receipt END LINK validate response hardening."""
    out = attach_end_link_ops_meta(
        payload,
        route="GET /receipts/{receipt_id}/validate",
        timing=timing,
        idempotent_safe=True,
    )
    return normalize_failure_codes_in_payload(out)


def enrich_batch_validate_payload(
    payload: Mapping[str, Any],
    *,
    timing: OpsRouteTiming | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Bulk END LINK validate response hardening."""
    out = attach_end_link_ops_meta(
        payload,
        route="POST /receipts/validate/batch",
        timing=timing,
        idempotent_safe=idempotency_key is not None,
    )
    if idempotency_key:
        out.setdefault("ops", {})
        if isinstance(out["ops"], dict):
            out["ops"]["idempotency_key_present"] = True
    return normalize_failure_codes_in_payload(out)


def normalize_failure_codes_in_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Walk items and normalize per-item failure_code fields."""
    out: dict[str, Any] = dict(payload)
    if "failure_code" in out and out["failure_code"]:
        out["failure_code"] = normalize_failure_code(str(out["failure_code"]))
    items = out.get("items")
    if isinstance(items, list):
        normalized: list[Any] = []
        for item in items:
            if not isinstance(item, dict):
                normalized.append(item)
                continue
            row = dict(item)
            if row.get("failure_code"):
                row["failure_code"] = normalize_failure_code(str(row["failure_code"]))
            normalized.append(row)
        out["items"] = normalized
    return out


def parse_batch_idempotency_key(header_value: str | None) -> str | None:
    """Normalize Idempotency-Key header for batch validate."""
    if not header_value:
        return None
    key = header_value.strip()
    if not key or len(key) > 128:
        return None
    return key


def batch_body_fingerprint(body: Mapping[str, Any]) -> str:
    """Stable fingerprint for batch POST idempotency."""
    return fingerprint_idempotency_body(body)


def reset_batch_idempotency_cache() -> None:
    """Clear in-memory batch replay cache (tests)."""
    with _BATCH_REPLAY_LOCK:
        _BATCH_REPLAY.clear()


def register_batch_idempotency_replay(
    key: str,
    body: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> None:
    """Store batch validate response for safe Idempotency-Key replay."""
    fp = batch_body_fingerprint(body)
    with _BATCH_REPLAY_LOCK:
        existing = _BATCH_REPLAY.get(key)
        if existing is not None and existing.body_fingerprint != fp:
            from thinkbox.control_plane_ops_harden import IdempotencyConflict

            raise IdempotencyConflict(key)
        _BATCH_REPLAY[key] = BatchIdempotencyReplay(
            operation_id=f"batch_{fp[:16]}",
            body_fingerprint=fp,
            payload=dict(payload),
        )


def lookup_batch_idempotency_replay(
    key: str,
    body: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Return cached batch payload when key + body fingerprint match."""
    fp = batch_body_fingerprint(body)
    with _BATCH_REPLAY_LOCK:
        entry = _BATCH_REPLAY.get(key)
        if entry is None:
            return None
        if entry.body_fingerprint != fp:
            from thinkbox.control_plane_ops_harden import IdempotencyConflict

            raise IdempotencyConflict(key)
        return dict(entry.payload)


def redact_end_link_ops_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Log-safe summary for END LINK ops routes."""
    base = {
        "route": (payload.get("ops") or {}).get("route") if isinstance(payload.get("ops"), dict) else None,
        "valid": payload.get("valid"),
        "total": payload.get("total"),
        "live_api_called": payload.get("live_api_called"),
    }
    return redact_mapping_for_logs(base)


def end_link_api_ops_harden_contract_snippet() -> dict[str, Any]:
    return {
        "end_link_api_ops_harden": END_LINK_API_OPS_HARDEN_LABEL,
        "end_link_api_ops_harden_version": END_LINK_API_OPS_HARDEN_VERSION,
        "ops_harden": OPS_HARDEN_LABEL,
        "chain_filter_max_len": CHAIN_FILTER_MAX_LEN,
        "known_failure_code_count": len(KNOWN_FAILURE_CODES),
        "live_api_called": False,
        "live_verified": False,
        "four_state_max": "TEST_VERIFIED",
    }
