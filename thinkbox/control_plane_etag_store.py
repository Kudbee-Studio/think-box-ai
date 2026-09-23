"""Shared control-plane conditional GET etag store (PR #140).

Hermetic browser tabs share ETag + cached JSON bodies via sessionStorage-shaped
payloads. Python mirrors JS for unit tests — no HTTP.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Mapping, MutableMapping

ETAG_STORE_SCHEMA_VERSION = 1
ETAG_STORE_STORAGE_KEY = "thinkbox.control_plane.etag_store.v1"
ETAG_BODY_SUFFIX = ":body"
MAX_ETAG_ENTRIES = 256


class EtagStoreError(ValueError):
    """Invalid etag store operation."""


def etag_body_key(url: str) -> str:
    """Cache key for JSON body paired with a poll URL etag."""
    return f"{url}{ETAG_BODY_SUFFIX}"


def prune_etag_store(store: MutableMapping[str, Any], *, max_entries: int = MAX_ETAG_ENTRIES) -> None:
    """Drop oldest url keys when over capacity (url keys only, not :body)."""
    url_keys = [k for k in store if isinstance(k, str) and not k.endswith(ETAG_BODY_SUFFIX)]
    if len(url_keys) <= max_entries:
        return
    for key in url_keys[: len(url_keys) - max_entries]:
        store.pop(key, None)
        store.pop(etag_body_key(key), None)


def merge_etag_stores(
    target: MutableMapping[str, Any],
    source: Mapping[str, Any],
    *,
    prefer_source: bool = True,
) -> MutableMapping[str, Any]:
    """Merge tab-local and shared etag maps for multiplex coherence."""
    for key, value in source.items():
        if not isinstance(key, str):
            continue
        if prefer_source or key not in target:
            target[key] = deepcopy(value)
    prune_etag_store(target)
    return target


def apply_conditional_get_to_store(
    store: MutableMapping[str, Any],
    url: str,
    *,
    etag: str | None,
    body: Mapping[str, Any] | None,
    not_modified: bool = False,
) -> None:
    """Record ETag response — mirrors fetchJsonConditional writes."""
    if not url:
        raise EtagStoreError("url_required")
    if not_modified:
        if etag and url not in store:
            store[url] = etag
        return
    if etag:
        store[url] = etag
    if body is not None:
        store[etag_body_key(url)] = dict(body)
    prune_etag_store(store)


def if_none_match_header(store: Mapping[str, Any], url: str) -> str | None:
    """Header value for conditional GET when store has prior etag."""
    tag = store.get(url)
    if isinstance(tag, str) and tag.strip():
        return tag.strip()
    return None


def cached_body_for_url(store: Mapping[str, Any], url: str) -> dict[str, Any] | None:
    """Body cached for 304 responses."""
    raw = store.get(etag_body_key(url))
    if isinstance(raw, dict):
        return dict(raw)
    return None


def serialize_etag_store(store: Mapping[str, Any]) -> str:
    """JSON blob for sessionStorage persistence."""
    payload = {
        "version": ETAG_STORE_SCHEMA_VERSION,
        "entries": {k: v for k, v in store.items() if isinstance(k, str)},
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def deserialize_etag_store(raw: str | None) -> dict[str, Any]:
    """Load store from sessionStorage JSON; fail-closed to empty on parse errors."""
    if not raw or not str(raw).strip():
        return {}
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(doc, dict):
        return {}
    version = int(doc.get("version") or 0)
    if version != ETAG_STORE_SCHEMA_VERSION:
        return {}
    entries = doc.get("entries")
    if not isinstance(entries, dict):
        return {}
    out: dict[str, Any] = {}
    for key, value in entries.items():
        if isinstance(key, str):
            out[key] = value
    prune_etag_store(out)
    return out


def store_entry_count(store: Mapping[str, Any]) -> int:
    """Count poll URLs with etags (excludes :body keys)."""
    return sum(
        1
        for k in store
        if isinstance(k, str) and not k.endswith(ETAG_BODY_SUFFIX)
    )


__all__ = [
    "ETAG_STORE_SCHEMA_VERSION",
    "ETAG_STORE_STORAGE_KEY",
    "ETAG_BODY_SUFFIX",
    "MAX_ETAG_ENTRIES",
    "EtagStoreError",
    "etag_body_key",
    "prune_etag_store",
    "merge_etag_stores",
    "apply_conditional_get_to_store",
    "if_none_match_header",
    "cached_body_for_url",
    "serialize_etag_store",
    "deserialize_etag_store",
    "store_entry_count",
]
