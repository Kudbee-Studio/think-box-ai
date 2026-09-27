"""END LINK — proprietary control-plane receipt link validation API (PR #156).

Maps to ``GET /api/v1/control-plane/receipts/{receipt_id}/validate`` with
conditional ``If-Match`` / 412 semantics (PR #155). Hermetic helpers only; no HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

__all__ = (
    "END_LINK_API_LABEL",
    "END_LINK_BATCH_ROUTE_SUFFIX",
    "END_LINK_ROUTE_SUFFIX",
    "EndLinkConditionalHint",
    "EndLinkResult",
    "EndLinkViolation",
    "build_end_link_batch_path",
    "build_end_link_path",
    "merge_end_link_deepen_fields",
    "normalize_end_link_receipt_id",
    "parse_end_link_envelope",
    "redact_end_link_summary",
)

END_LINK_API_LABEL = "END_LINK"
END_LINK_ROUTE_SUFFIX = "/receipts/{receipt_id}/validate"
END_LINK_BATCH_ROUTE_SUFFIX = "/receipts/validate/batch"


class EndLinkViolation(ValueError):
    """Fail-closed END LINK validation error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class EndLinkConditionalHint:
    """How conditional headers apply to END LINK reads."""

    supports_if_none_match: bool = True
    supports_if_match: bool = True
    mismatch_status: int = 412
    not_modified_status: int = 304


@dataclass(frozen=True)
class EndLinkResult:
    """Hermetic END LINK outcome (in-process or parsed HTTP envelope)."""

    receipt_id: str
    valid: bool
    live_api_called: bool = False
    evidence_label: str = "simulated"
    etag: str | None = None
    http_status: int | None = None
    conditional: EndLinkConditionalHint = EndLinkConditionalHint()

    link_integrity: str | None = None
    prev_receipt_id: str | None = None
    failure_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "api": END_LINK_API_LABEL,
            "receipt_id": self.receipt_id,
            "valid": self.valid,
            "live_api_called": self.live_api_called,
            "evidence_label": self.evidence_label,
            "etag": self.etag,
            "http_status": self.http_status,
            "conditional": {
                "supports_if_none_match": self.conditional.supports_if_none_match,
                "supports_if_match": self.conditional.supports_if_match,
                "mismatch_status": self.conditional.mismatch_status,
                "not_modified_status": self.conditional.not_modified_status,
            },
        }
        if self.link_integrity is not None:
            out["link_integrity"] = self.link_integrity
        if self.prev_receipt_id is not None:
            out["prev_receipt_id"] = self.prev_receipt_id
        if self.failure_code is not None:
            out["failure_code"] = self.failure_code
        return out


def build_end_link_batch_path(*, base_prefix: str = "/api/v1/control-plane") -> str:
    """Absolute path for bulk END LINK validate (POST)."""
    return f"{base_prefix.rstrip('/')}/receipts/validate/batch"


def build_end_link_path(receipt_id: str, *, base_prefix: str = "/api/v1/control-plane") -> str:
    """Absolute path for the proprietary END LINK validate route."""
    rid = normalize_end_link_receipt_id(receipt_id)
    return f"{base_prefix.rstrip('/')}/receipts/{rid}/validate"


def normalize_end_link_receipt_id(receipt_id: str) -> str:
    """Receipt id required for END LINK (non-empty, trimmed)."""
    rid = (receipt_id or "").strip()
    if not rid:
        raise EndLinkViolation("receipt_id_required", "END LINK requires receipt_id")
    if len(rid) > 256:
        raise EndLinkViolation("receipt_id_too_long", "receipt_id exceeds 256 chars")
    return rid


def parse_end_link_envelope(
    envelope: Mapping[str, Any],
    *,
    receipt_id: str,
    http_status: int | None = None,
    etag: str | None = None,
) -> EndLinkResult:
    """Parse control-plane success envelope into ``EndLinkResult``."""
    data = envelope.get("data") if isinstance(envelope.get("data"), dict) else envelope
    valid = bool(data.get("valid"))
    return EndLinkResult(
        receipt_id=str(data.get("receipt_id") or receipt_id),
        valid=valid,
        live_api_called=bool(data.get("live_api_called")),
        evidence_label=str(data.get("evidence_label") or "simulated"),
        etag=etag,
        http_status=http_status,
        link_integrity=data.get("link_integrity") if data.get("link_integrity") else None,
        prev_receipt_id=data.get("prev_receipt_id") if data.get("prev_receipt_id") else None,
        failure_code=data.get("failure_code") if data.get("failure_code") else None,
    )


def merge_end_link_deepen_fields(
    base: Mapping[str, Any],
    deepen: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge PR #158 integrity fields into a validate payload (idempotent)."""
    merged = dict(base)
    for key in (
        "link_integrity",
        "prev_receipt_id",
        "entry_hash",
        "failure_code",
        "failure_message",
        "deepen",
        "deepen_version",
    ):
        if key in deepen and deepen[key] is not None:
            merged[key] = deepen[key]
    merged.setdefault("api", END_LINK_API_LABEL)
    merged.setdefault("live_api_called", False)
    return merged


def redact_end_link_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Redact END LINK payloads for logs/spine (receipt id truncated)."""
    from thinkbox.control_plane_ops_harden import redact_mapping_for_logs

    rid = str(payload.get("receipt_id") or "")
    short = rid[:12] + "…" if len(rid) > 12 else rid
    base = {
        "api": END_LINK_API_LABEL,
        "receipt_id": short,
        "valid": payload.get("valid"),
        "live_api_called": payload.get("live_api_called"),
        "http_status": payload.get("http_status"),
    }
    return redact_mapping_for_logs(base)
