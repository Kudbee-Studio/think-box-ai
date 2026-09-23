"""Hermetic dashboard client for receipt-chain reads + END LINK (PR #156)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from thinkbox.control_plane_api_surface import (
    build_chain_head_payload,
    build_chain_page_payload,
    build_chain_tail_payload,
    get_chain_payload,
    validate_chain_receipt_id,
    wrap_success,
)
from thinkbox.dashboard_receipt_chain_models import (
    ChainPageView,
    ChainProbeView,
    DashboardChainBindState,
    EtagCacheView,
    chain_page_from_payload,
    end_link_panel_from_result,
)
from thinkbox.end_link_api import (
    END_LINK_API_LABEL,
    EndLinkResult,
    build_end_link_path,
    parse_end_link_envelope,
)
from thinkbox.receipt_chain_query import ReceiptChainValidationError

__all__ = (
    "DashboardReceiptChainClient",
    "HermeticChainFetchResult",
    "chain_api_paths",
    "hermetic_end_link_validate",
    "hermetic_fetch_chain_bind_state",
)


@dataclass(frozen=True)
class HermeticChainFetchResult:
    """In-process fetch bundle (no HTTP)."""

    state: DashboardChainBindState
    paths: dict[str, str]


def chain_api_paths(base: str = "/api/v1/control-plane") -> dict[str, str]:
    """Canonical dashboard URLs for chain plane + END LINK."""
    prefix = base.rstrip("/")
    return {
        "chain": f"{prefix}/receipts/chain",
        "page": f"{prefix}/receipts/chain/page",
        "head": f"{prefix}/receipts/chain/head",
        "tail": f"{prefix}/receipts/chain/tail",
        "end_link_template": f"{prefix}/receipts/{{receipt_id}}/validate",
        "end_link_api": END_LINK_API_LABEL,
    }


def hermetic_end_link_validate(receipt_id: str) -> EndLinkResult:
    """Run END LINK validation in-process (same as HTTP route body)."""
    try:
        body = validate_chain_receipt_id(receipt_id)
        envelope = wrap_success(body, request_id="hermetic_end_link")
        return parse_end_link_envelope(envelope, receipt_id=receipt_id, http_status=200)
    except ReceiptChainValidationError as exc:
        return EndLinkResult(
            receipt_id=receipt_id,
            valid=False,
            live_api_called=False,
            http_status=404,
            evidence_label="simulated",
        )


class DashboardReceiptChainClient:
    """Compose chain page, probes, and END LINK for dashboard bind."""

    def __init__(self, *, base_prefix: str = "/api/v1/control-plane") -> None:
        self._base = base_prefix.rstrip("/")
        self.paths = chain_api_paths(self._base)

    def fetch_page(
        self,
        *,
        limit: int = 20,
        cursor: str | None = None,
        action: str | None = None,
        agent_id: str | None = None,
    ) -> ChainPageView:
        page = build_chain_page_payload(
            limit=limit,
            cursor=cursor,
            action=action,
            agent_id=agent_id,
        )
        envelope = wrap_success(page, request_id="hermetic_page")
        return chain_page_from_payload(envelope)

    def fetch_probes(self) -> ChainProbeView:
        head = build_chain_head_payload().get("head")
        tail = build_chain_tail_payload().get("tail")
        return ChainProbeView(head=head, tail=tail, live_api_called=False)

    def fetch_chain_status(self, *, limit: int = 20) -> Mapping[str, Any]:
        return get_chain_payload(limit=limit)

    def validate_end_link(self, receipt_id: str) -> EndLinkResult:
        path = build_end_link_path(receipt_id, base_prefix=self._base)
        result = hermetic_end_link_validate(receipt_id)
        return result

    def bind_state(
        self,
        *,
        limit: int = 20,
        cursor: str | None = None,
        end_link_receipt_id: str | None = None,
    ) -> DashboardChainBindState:
        state = DashboardChainBindState(loading=False, live_api_called=False)
        try:
            state.page = self.fetch_page(limit=limit, cursor=cursor)
            state.probes = self.fetch_probes()
            if end_link_receipt_id:
                el = self.validate_end_link(end_link_receipt_id)
                state.end_link = end_link_panel_from_result(
                    el.receipt_id,
                    valid=el.valid,
                    http_status=el.http_status,
                    etag=el.etag,
                    error_code=None if el.valid else "validation_failed",
                )
            state.etag_events.append(
                EtagCacheView(
                    url=self.paths["page"],
                    etag=None,
                    cached=False,
                    not_modified=False,
                )
            )
        except Exception as exc:  # noqa: BLE001 — dashboard fail-closed surface
            state.error = str(exc)
        return state


def hermetic_fetch_chain_bind_state(
    *,
    limit: int = 20,
    cursor: str | None = None,
    end_link_receipt_id: str | None = None,
) -> HermeticChainFetchResult:
    client = DashboardReceiptChainClient()
    state = client.bind_state(
        limit=limit,
        cursor=cursor,
        end_link_receipt_id=end_link_receipt_id,
    )
    return HermeticChainFetchResult(state=state, paths=client.paths)
