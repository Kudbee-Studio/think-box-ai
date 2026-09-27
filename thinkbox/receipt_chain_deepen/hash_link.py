"""Hash link integrity helpers (PR #182 F05)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

GENESIS_HASH = "GENESIS"


def compute_entry_hash(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(body).hexdigest()[:32]


def validate_link(prev_hash: str, expected_prev: str) -> bool:
    return prev_hash == expected_prev


def link_summary(prev_hash: str, entry_hash: str) -> dict[str, Any]:
    return {
        "prev_hash": prev_hash,
        "entry_hash": entry_hash,
        "genesis": prev_hash == GENESIS_HASH,
        "live_api_called": False,
    }
