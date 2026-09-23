"""Control-plane deep links into Think Job receipt watch (PR #140).

Build and parse URLs for think_job_status.html without a parallel status plane.
Fail-closed on missing/invalid receipt keys (reuses #139 normalization).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import parse_qs, quote, unquote, urlencode

from thinkbox.think_job_status_ui import normalize_receipt_key, normalize_engine_key

THINK_JOB_STATUS_PAGE = "think_job_status.html"
RECEIPTS_PAGE = "receipts.html"

RECEIPT_QUERY_KEYS = ("receipt_id", "watch_receipt", "receipt")
ENGINE_QUERY_KEYS = ("engine_id", "watch_engine", "engine")
AUTO_WATCH_KEYS = ("auto_watch", "watch")
FROM_QUERY_KEY = "from"


class DeepLinkError(ValueError):
    """Invalid deep-link parameters."""


@dataclass(frozen=True)
class ThinkJobWatchDeepLink:
    """Parsed navigation target for receipt-keyed watch."""

    receipt_id: str = ""
    engine_id: str = ""
    auto_watch: bool = False
    source_page: str = ""
    preserve_hash: str = ""

    @property
    def has_watch_target(self) -> bool:
        return bool(self.receipt_id or self.engine_id)


def _first_query_value(params: Mapping[str, list[str]], keys: tuple[str, ...]) -> str:
    for key in keys:
        values = params.get(key)
        if values and str(values[0]).strip():
            return str(values[0]).strip()
    return ""


def _truthy_flag(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def parse_watch_deep_link_query(query_string: str) -> ThinkJobWatchDeepLink:
    """Parse ?receipt_id=…&auto_watch=1 style query (no leading ?)."""
    qs = (query_string or "").lstrip("?")
    params = parse_qs(qs, keep_blank_values=False)
    receipt_raw = _first_query_value(params, RECEIPT_QUERY_KEYS)
    engine_raw = _first_query_value(params, ENGINE_QUERY_KEYS)
    auto_raw = _first_query_value(params, AUTO_WATCH_KEYS)
    from_raw = _first_query_value(params, (FROM_QUERY_KEY,))
    receipt_id = ""
    engine_id = ""
    if receipt_raw:
        receipt_id = normalize_receipt_key(unquote(receipt_raw))
    if engine_raw:
        engine_id = normalize_engine_key(unquote(engine_raw))
    return ThinkJobWatchDeepLink(
        receipt_id=receipt_id,
        engine_id=engine_id,
        auto_watch=_truthy_flag(auto_raw),
        source_page=from_raw,
    )


def parse_watch_deep_link_hash(hash_fragment: str) -> ThinkJobWatchDeepLink:
    """Parse #receipt_id=… hermetic hash params (mock flows)."""
    frag = (hash_fragment or "").lstrip("#")
    if not frag:
        return ThinkJobWatchDeepLink()
    if "=" not in frag:
        try:
            return ThinkJobWatchDeepLink(receipt_id=normalize_receipt_key(unquote(frag)), auto_watch=True)
        except ValueError:
            raise DeepLinkError("receipt_key_invalid") from None
    return parse_watch_deep_link_query(frag)


def merge_deep_link_sources(
    *,
    query_string: str = "",
    hash_fragment: str = "",
) -> ThinkJobWatchDeepLink:
    """Query wins for explicit ids; hash fills gaps (hermetic mock preserves both)."""
    from_query = parse_watch_deep_link_query(query_string)
    from_hash = parse_watch_deep_link_hash(hash_fragment)
    receipt_id = from_query.receipt_id or from_hash.receipt_id
    engine_id = from_query.engine_id or from_hash.engine_id
    auto_watch = from_query.auto_watch or from_hash.auto_watch or bool(receipt_id)
    source_page = from_query.source_page or from_hash.source_page
    preserve_hash = hash_fragment if hash_fragment and not from_query.receipt_id else ""
    return ThinkJobWatchDeepLink(
        receipt_id=receipt_id,
        engine_id=engine_id,
        auto_watch=auto_watch,
        source_page=source_page,
        preserve_hash=preserve_hash,
    )


def build_think_job_watch_href(
    *,
    receipt_id: str = "",
    engine_id: str = "",
    auto_watch: bool = True,
    from_page: str = RECEIPTS_PAGE,
    use_hash_for_receipt: bool = False,
) -> str:
    """Relative href from receipts.html → think_job_status watch."""
    rec = normalize_receipt_key(receipt_id) if receipt_id else ""
    eng = normalize_engine_key(engine_id) if engine_id else ""
    if not rec and not eng:
        raise DeepLinkError("watch_target_required")
    if use_hash_for_receipt and rec:
        frag = urlencode({"receipt_id": rec, "auto_watch": "1" if auto_watch else "0"})
        return f"{THINK_JOB_STATUS_PAGE}#{frag}"
    params: dict[str, str] = {}
    if rec:
        params["receipt_id"] = rec
    if eng:
        params["engine_id"] = eng
    if auto_watch:
        params["auto_watch"] = "1"
    if from_page:
        params[FROM_QUERY_KEY] = from_page
    return f"{THINK_JOB_STATUS_PAGE}?{urlencode(params)}"


def build_receipt_row_watch_label(receipt_id: str) -> str:
    """Short label for receipts table watch link."""
    key = normalize_receipt_key(receipt_id)
    return f"Watch {key[:10]}…"


def assert_deep_link_watchable(link: ThinkJobWatchDeepLink) -> None:
    """Fail-closed before starting client watch."""
    if not link.has_watch_target:
        raise DeepLinkError("watch_target_required")
    if link.receipt_id:
        normalize_receipt_key(link.receipt_id)


__all__ = [
    "THINK_JOB_STATUS_PAGE",
    "RECEIPTS_PAGE",
    "DeepLinkError",
    "ThinkJobWatchDeepLink",
    "parse_watch_deep_link_query",
    "parse_watch_deep_link_hash",
    "merge_deep_link_sources",
    "build_think_job_watch_href",
    "build_receipt_row_watch_label",
    "assert_deep_link_watchable",
]
