"""Dashboard view models for receipt-chain + END LINK bind (PR #156, hermetic)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

__all__ = (
    "ChainPageView",
    "ChainProbeView",
    "DashboardChainBindState",
    "EtagCacheView",
    "EndLinkPanelView",
    "chain_page_from_payload",
    "end_link_panel_from_result",
)


@dataclass(frozen=True)
class ChainPageView:
    """One cursor page of receipts for dashboard rendering."""

    receipts: tuple[dict[str, Any], ...]
    next_cursor: str | None
    total: int
    chain_valid: bool
    live_api_called: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipts": list(self.receipts),
            "next_cursor": self.next_cursor,
            "total": self.total,
            "chain_valid": self.chain_valid,
            "live_api_called": self.live_api_called,
        }


@dataclass(frozen=True)
class ChainProbeView:
    """Head/tail boundary probe for operators."""

    head: dict[str, Any] | None
    tail: dict[str, Any] | None
    live_api_called: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "head": self.head,
            "tail": self.tail,
            "live_api_called": self.live_api_called,
        }


@dataclass(frozen=True)
class EtagCacheView:
    """304 / cached read indicator (fail-closed display)."""

    url: str
    etag: str | None
    cached: bool
    not_modified: bool = False
    precondition_failed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "etag": self.etag,
            "cached": self.cached,
            "not_modified": self.not_modified,
            "precondition_failed": self.precondition_failed,
        }


@dataclass(frozen=True)
class EndLinkPanelView:
    """END LINK validate panel state."""

    receipt_id: str
    valid: bool
    status_label: str
    etag: str | None = None
    http_status: int | None = None
    error_code: str | None = None
    link_integrity: str | None = None
    prev_receipt_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "api": "END_LINK",
            "receipt_id": self.receipt_id,
            "valid": self.valid,
            "status_label": self.status_label,
            "etag": self.etag,
            "http_status": self.http_status,
            "error_code": self.error_code,
        }
        if self.link_integrity is not None:
            out["link_integrity"] = self.link_integrity
        if self.prev_receipt_id is not None:
            out["prev_receipt_id"] = self.prev_receipt_id
        return out


@dataclass
class DashboardChainBindState:
    """Aggregate bind state for receipt-chain dashboard slot."""

    loading: bool = True
    error: str | None = None
    page: ChainPageView | None = None
    probes: ChainProbeView | None = None
    end_link: EndLinkPanelView | None = None
    etag_events: list[EtagCacheView] = field(default_factory=list)
    live_api_called: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "loading": self.loading,
            "error": self.error,
            "page": self.page.to_dict() if self.page else None,
            "probes": self.probes.to_dict() if self.probes else None,
            "end_link": self.end_link.to_dict() if self.end_link else None,
            "etag_events": [e.to_dict() for e in self.etag_events],
            "live_api_called": self.live_api_called,
            "four_state_max": "TEST_VERIFIED",
        }


def chain_page_from_payload(data: Mapping[str, Any]) -> ChainPageView:
    """Build page view from chain/page API data envelope."""
    inner = data.get("data") if isinstance(data.get("data"), dict) else data
    receipts = tuple(inner.get("receipts") or [])
    return ChainPageView(
        receipts=receipts,
        next_cursor=inner.get("next_cursor"),
        total=int(inner.get("total") or len(receipts)),
        chain_valid=bool(inner.get("chain_valid", True)),
        live_api_called=bool(inner.get("live_api_called")),
    )


def end_link_panel_from_result(
    receipt_id: str,
    *,
    valid: bool,
    http_status: int | None = None,
    etag: str | None = None,
    error_code: str | None = None,
    link_integrity: str | None = None,
    prev_receipt_id: str | None = None,
) -> EndLinkPanelView:
    if error_code:
        label = f"END LINK FAIL ({error_code})"
    elif http_status == 412:
        label = "END LINK 412 precondition"
        valid = False
    elif valid:
        label = "END LINK OK"
    else:
        label = "END LINK invalid"
    if link_integrity == "ok" and valid:
        label = "END LINK OK (integrity)"
    return EndLinkPanelView(
        receipt_id=receipt_id,
        valid=valid,
        status_label=label,
        etag=etag,
        http_status=http_status,
        error_code=error_code,
        link_integrity=link_integrity,
        prev_receipt_id=prev_receipt_id,
    )
