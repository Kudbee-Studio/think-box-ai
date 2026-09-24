"""Status catalog for deepen surfaces (PR #182 F15)."""

from __future__ import annotations

from typing import Any

_CATALOG: dict[str, str] = {
    "append": "Hermetic in-memory chain append",
    "verify": "Hash-link verification",
    "export": "Redacted export",
    "cassette": "Offline cassette replay",
    "fork": "Fork detection stub",
    "compaction": "Tail retention stub",
    "end_link": "END_LINK dry-run bridge",
    "etag": "Receipt-chain ETag bridge",
    "audit_ledger": "Audit ledger era bridge",
}


def status_catalog() -> dict[str, Any]:
    return {
        "catalog": dict(_CATALOG),
        "count": len(_CATALOG),
        "live_api_called": False,
    }
