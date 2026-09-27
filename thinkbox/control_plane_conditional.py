"""Canonical control-plane conditional GET helpers (PR #140 + #154 + #155).

Single path for ETag generation aligned with ``thinkbox.read_cache`` and the
browser ``control_plane_etag_store`` contract.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

from thinkbox.control_plane_etag_store import (
    apply_conditional_get_to_store,
    if_none_match_header,
)
from thinkbox.read_cache import etag_matches, weak_etag_from_payload

__all__ = (
    "chain_read_etag",
    "etag_for_chain_status",
    "record_chain_response_in_store",
    "should_return_not_modified",
)


def etag_for_chain_status(chain_status: Mapping[str, Any]) -> str:
    """Weak ETag for receipt chain status (excludes envelope wrappers)."""
    return weak_etag_from_payload(dict(chain_status))


def chain_read_etag(chain_block: Mapping[str, Any]) -> str:
    """ETag for full chain read model including health when present."""
    material = {
        "chain": chain_block.get("chain") or chain_block,
        "health": chain_block.get("health"),
    }
    explicit = chain_block.get("etag")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    return etag_for_chain_status(material.get("chain") or material)


def should_return_not_modified(
    if_none_match: str | None,
    etag: str,
) -> bool:
    """True when client sent matching If-None-Match."""
    return etag_matches(if_none_match, etag)


def record_chain_response_in_store(
    store: MutableMapping[str, Any],
    url: str,
    *,
    etag: str | None,
    body: Mapping[str, Any] | None,
    not_modified: bool = False,
) -> None:
    """Persist chain poll result for tab-shared etag store (PR #140)."""
    apply_conditional_get_to_store(
        store,
        url,
        etag=etag,
        body=body,
        not_modified=not_modified,
    )


def if_none_match_for_url(store: Mapping[str, Any], url: str) -> str | None:
    """Re-export for tests mirroring browser clients."""
    return if_none_match_header(store, url)
